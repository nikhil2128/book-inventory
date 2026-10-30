from datetime import UTC, datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from book_inventory.models import BookingStatus


def ensure_aware(value: datetime) -> datetime:
    """Treat naive datetimes (e.g. from HTML datetime-local inputs) as UTC."""
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


class BookingCreate(BaseModel):
    item_id: int
    customer_id: int
    quantity: int = Field(default=1, ge=1)
    start_at: datetime
    end_at: datetime

    @field_validator("start_at", "end_at")
    @classmethod
    def make_aware(cls, value: datetime) -> datetime:
        return ensure_aware(value)

    @model_validator(mode="after")
    def check_period(self) -> Self:
        if self.end_at <= self.start_at:
            raise ValueError("end_at must be after start_at")
        return self


class BookingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    item_id: int
    customer_id: int
    quantity: int
    start_at: datetime
    end_at: datetime
    status: BookingStatus
    created_at: datetime
