from enum import StrEnum

from tortoise import fields
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
    start_at = fields.DatetimeField(db_index=True)
    end_at = fields.DatetimeField(db_index=True)
    status = fields.CharEnumField(BookingStatus, default=BookingStatus.CONFIRMED)
    created_at = fields.DatetimeField(auto_now_add=True)

    item_id: int
    customer_id: int

    class Meta:
        table = "bookings"
        ordering = ["start_at"]
