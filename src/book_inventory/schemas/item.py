from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class ItemBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    remaining_quantity: int = Field(ge=0, description="Units that can be booked concurrently")
    is_active: bool = True
    expiration_date: date | None = Field(
        default=None, description="Last day the item can be booked; it is deactivated after"
    )


class ItemCreate(ItemBase):
    pass


class ItemUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    remaining_quantity: int | None = Field(default=None, ge=0)
    is_active: bool | None = None
    expiration_date: date | None = None


class ItemRead(ItemBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
