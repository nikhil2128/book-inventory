from typing import TYPE_CHECKING

from tortoise import fields
from tortoise.models import Model

if TYPE_CHECKING:
    from book_inventory.models.booking import Booking


class InventoryItem(Model):
    """A bookable resource. `remaining_quantity` is how many units can be booked at once."""

    id = fields.IntField(primary_key=True)
    name = fields.CharField(max_length=200, unique=True)
    description = fields.TextField(default="")
    remaining_quantity = fields.IntField()
    is_active = fields.BooleanField(default=True)
    expiration_date = fields.DateField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    bookings: fields.ReverseRelation["Booking"]

    class Meta:
        table = "inventory_items"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name
