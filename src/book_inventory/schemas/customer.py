from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CustomerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    surname: str
    booking_count: int
    date_joined: datetime
