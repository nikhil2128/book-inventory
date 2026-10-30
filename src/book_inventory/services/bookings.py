"""Booking business logic, shared by the REST API and the web UI.

A confirmed booking takes `quantity` units out of the item's `remaining_quantity` and adds one to
the customer's `booking_count`; cancelling puts both back. Once a booking's `end_at` has passed,
`complete_expired_bookings` marks it completed and returns the units (the count is left alone).

A customer may hold at most `max_active_units_per_customer` units in confirmed ("active")
bookings at once; a booking that would exceed that is refused.
"""

from collections import defaultdict
from datetime import UTC, datetime

from tortoise.expressions import F, Q
from tortoise.functions import Sum
from tortoise.transactions import in_transaction

from book_inventory.config import get_settings
from book_inventory.models import Booking, BookingStatus, Customer, InventoryItem
from book_inventory.schemas import BookingCreate


class BookingError(Exception):
    pass


class ItemNotFoundError(BookingError):
    def __init__(self, item_id: int) -> None:
        super().__init__(f"Item {item_id} not found, inactive or expired")


class CustomerNotFoundError(BookingError):
    def __init__(self, customer_id: int) -> None:
        super().__init__(f"Customer {customer_id} not found")


class BookingNotCancellableError(BookingError):
    def __init__(self, booking_id: int) -> None:
        super().__init__(f"Booking {booking_id} has already ended and cannot be cancelled")


class CustomerLimitReachedError(BookingError):
    def __init__(self, active: int, requested: int, limit: int) -> None:
        super().__init__(
            f"Customer already has {active} active booking(s) and can have at most {limit}; "
            f"cannot add {requested} more"
        )
        self.active = active
        self.requested = requested
        self.limit = limit


class InsufficientAvailabilityError(BookingError):
    def __init__(self, requested: int, available: int) -> None:
        super().__init__(f"Requested {requested} unit(s) but only {available} available")
        self.requested = requested
        self.available = available


async def active_units(customer_id: int) -> int:
    """Units a customer holds in confirmed ("active") bookings."""
    totals = (
        await Booking.filter(customer_id=customer_id, status=BookingStatus.CONFIRMED)
        .annotate(total=Sum("quantity"))
        .values_list("total", flat=True)
    )
    return totals[0] or 0


async def active_units_by_customer() -> dict[int, int]:
    """Active units per customer id; customers with none are absent."""
    rows = (
        await Booking.filter(status=BookingStatus.CONFIRMED)
        .group_by("customer_id")
        .annotate(total=Sum("quantity"))
        .values("customer_id", "total")
    )
    return {row["customer_id"]: row["total"] for row in rows}


async def create_booking(data: BookingCreate) -> Booking:
    async with in_transaction():
        # Lock the item row so concurrent bookings for it are serialised.
        # Don't wait for the scheduler to deactivate an item that has just expired.
        not_expired = Q(expiration_date__isnull=True) | Q(
            expiration_date__gte=datetime.now(UTC).date()
        )
        item = (
            await InventoryItem.filter(not_expired, id=data.item_id, is_active=True)
            .select_for_update()
            .first()
        )
        if item is None:
            raise ItemNotFoundError(data.item_id)

        # Lock the customer too, so two concurrent bookings can't both slip under the limit.
        customer = await Customer.filter(id=data.customer_id).select_for_update().first()
        if customer is None:
            raise CustomerNotFoundError(data.customer_id)

        limit = get_settings().max_active_units_per_customer
        active = await active_units(customer.id)
        if active + data.quantity > limit:
            raise CustomerLimitReachedError(active, data.quantity, limit)

        if data.quantity > item.remaining_quantity:
            raise InsufficientAvailabilityError(data.quantity, item.remaining_quantity)

        item.remaining_quantity -= data.quantity
        await item.save(update_fields=["remaining_quantity", "updated_at"])
        await Customer.filter(id=data.customer_id).update(booking_count=F("booking_count") + 1)
        return await Booking.create(item=item, **data.model_dump(exclude={"item_id"}))


async def cancel_booking(booking: Booking) -> Booking:
    async with in_transaction():
        # Re-read under a lock so two concurrent cancellations can't both give the units back.
        locked = await Booking.filter(id=booking.id).select_for_update().get()
        if locked.status == BookingStatus.CANCELLED:
            return locked
        if locked.status == BookingStatus.COMPLETED:
            raise BookingNotCancellableError(locked.id)

        locked.status = BookingStatus.CANCELLED
        await locked.save(update_fields=["status"])
        item = await InventoryItem.filter(id=locked.item_id).select_for_update().get()
        item.remaining_quantity += locked.quantity
        await item.save(update_fields=["remaining_quantity", "updated_at"])
        await Customer.filter(id=locked.customer_id).update(booking_count=F("booking_count") - 1)
        return locked


async def complete_expired_bookings(now: datetime | None = None) -> int:
    """Mark confirmed bookings that ended at or before `now` as completed and return their units.

    Safe to run from several workers at once: rows are locked and ones another run holds are
    skipped, so each booking is released exactly once. Returns how many bookings were completed.
    """
    now = now or datetime.now(UTC)
    async with in_transaction():
        expired = (
            await Booking.filter(status=BookingStatus.CONFIRMED, end_at__lte=now)
            .select_for_update(skip_locked=True)
            .order_by("id")
        )
        if not expired:
            return 0

        units_by_item: dict[int, int] = defaultdict(int)
        for booking in expired:
            units_by_item[booking.item_id] += booking.quantity

        await Booking.filter(id__in=[b.id for b in expired]).update(status=BookingStatus.COMPLETED)
        for item_id in sorted(units_by_item):  # fixed order, same as cancel: bookings, then items
            item = await InventoryItem.filter(id=item_id).select_for_update().get()
            item.remaining_quantity += units_by_item[item_id]
            await item.save(update_fields=["remaining_quantity", "updated_at"])
        return len(expired)
