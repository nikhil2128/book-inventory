"""Booking business logic, shared by the REST API and the web UI."""

from datetime import datetime

from tortoise.transactions import in_transaction

from book_inventory.models import Booking, BookingStatus, InventoryItem
from book_inventory.schemas import Availability, BookingCreate


class BookingError(Exception):
    pass


class ItemNotFoundError(BookingError):
    def __init__(self, item_id: int) -> None:
        super().__init__(f"Item {item_id} not found or inactive")


class InsufficientAvailabilityError(BookingError):
    def __init__(self, requested: int, available: int) -> None:
        super().__init__(f"Requested {requested} unit(s) but only {available} available")
        self.requested = requested
        self.available = available


async def booked_quantity(item_id: int, start_at: datetime, end_at: datetime) -> int:
    """Units of an item held by confirmed bookings overlapping [start_at, end_at)."""
    quantities = await Booking.filter(
        item_id=item_id,
        status=BookingStatus.CONFIRMED,
        start_at__lt=end_at,
        end_at__gt=start_at,
    ).values_list("quantity", flat=True)
    return sum(quantities)


async def get_availability(
    item: InventoryItem, start_at: datetime, end_at: datetime
) -> Availability:
    booked = await booked_quantity(item.id, start_at, end_at)
    return Availability(
        item_id=item.id,
        start_at=start_at,
        end_at=end_at,
        total=item.quantity,
        booked=booked,
        available=max(item.quantity - booked, 0),
    )


async def create_booking(data: BookingCreate) -> Booking:
    async with in_transaction():
        # Lock the item row so concurrent bookings for it are serialised.
        item = (
            await InventoryItem.filter(id=data.item_id, is_active=True).select_for_update().first()
        )
        if item is None:
            raise ItemNotFoundError(data.item_id)

        available = item.quantity - await booked_quantity(item.id, data.start_at, data.end_at)
        if data.quantity > available:
            raise InsufficientAvailabilityError(data.quantity, max(available, 0))

        return await Booking.create(item=item, **data.model_dump(exclude={"item_id"}))


async def cancel_booking(booking: Booking) -> Booking:
    if booking.status != BookingStatus.CANCELLED:
        booking.status = BookingStatus.CANCELLED
        await booking.save(update_fields=["status"])
    return booking
