from typing import TYPE_CHECKING

from tortoise import fields
from tortoise.models import Model

if TYPE_CHECKING:
    from book_inventory.models.booking import Booking


class Customer(Model):
    """A person who can make bookings. Names are not unique: two customers may share both."""

    id = fields.IntField(primary_key=True)
    name = fields.CharField(max_length=100)
    surname = fields.CharField(max_length=100)
    booking_count = fields.IntField(default=0)
    date_joined = fields.DatetimeField()

    bookings: fields.ReverseRelation["Booking"]

    class Meta:
        table = "customers"
        ordering = ["surname", "name"]

    def __str__(self) -> str:
        return f"{self.name} {self.surname}"
