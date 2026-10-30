from enum import StrEnum

from tortoise import fields
from tortoise.models import Model


class BookingStatus(StrEnum):
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


class Booking(Model):
    """A reservation of `quantity` units of an item over the interval [start_at, end_at)."""

    id = fields.IntField(primary_key=True)
    item = fields.ForeignKeyField(
        "models.InventoryItem", related_name="bookings", on_delete=fields.RESTRICT
    )
    customer_name = fields.CharField(max_length=200)
    customer_email = fields.CharField(max_length=254)
    quantity = fields.IntField(default=1)
    start_at = fields.DatetimeField(db_index=True)
    end_at = fields.DatetimeField(db_index=True)
    status = fields.CharEnumField(BookingStatus, default=BookingStatus.CONFIRMED)
    created_at = fields.DatetimeField(auto_now_add=True)

    item_id: int

    class Meta:
        table = "bookings"
        ordering = ["start_at"]
