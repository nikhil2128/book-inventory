from enum import StrEnum

from tortoise import fields
from tortoise.indexes import Index, PartialIndex
from tortoise.models import Model


class BookingStatus(StrEnum):
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    # end_at has passed; the units were given back by the scheduler (see services/bookings.py).
    COMPLETED = "completed"


class Booking(Model):
    """A reservation of `quantity` units of an item over the interval [start_at, end_at)."""

    id = fields.IntField(primary_key=True)
    item = fields.ForeignKeyField(
        "models.InventoryItem", related_name="bookings", on_delete=fields.RESTRICT
    )
    customer = fields.ForeignKeyField(
        "models.Customer", related_name="bookings", on_delete=fields.RESTRICT
    )
    quantity = fields.IntField(default=1)
    start_at = fields.DatetimeField()
    end_at = fields.DatetimeField()
    status = fields.CharEnumField(BookingStatus, default=BookingStatus.CONFIRMED)
    created_at = fields.DatetimeField(auto_now_add=True)

    item_id: int
    customer_id: int

    class Meta:
        table = "bookings"
        ordering = ["start_at"]
        # One index per query that needs it (see "Indexes" in the README). The partial ones only
        # hold confirmed bookings, which stay few while completed/cancelled history grows.
        indexes = [
            # Bookings of an item, newest first; also covers the item foreign key.
            Index(fields=("item_id", "start_at"), name="idx_bookings_item_start"),
            # A customer's active units (booking limit, dropdown counts).
            PartialIndex(
                fields=("customer_id",),
                condition={"status": BookingStatus.CONFIRMED.value},
                name="idx_bookings_confirmed_customer",
            ),
            # The scheduler's "confirmed bookings that have ended" lookup.
            PartialIndex(
                fields=("end_at",),
                condition={"status": BookingStatus.CONFIRMED.value},
                name="idx_bookings_confirmed_end_at",
            ),
        ]
