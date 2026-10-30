from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from book_inventory.api.deps import get_booking_or_404
from book_inventory.models import Booking
from book_inventory.schemas import BookingCreate, BookingRead
from book_inventory.services.bookings import (
    BookingNotCancellableError,
    CustomerNotFoundError,
    InsufficientAvailabilityError,
    ItemNotFoundError,
    cancel_booking,
    create_booking,
)

router = APIRouter(prefix="/bookings", tags=["bookings"])

BookingDep = Annotated[Booking, Depends(get_booking_or_404)]


@router.get("", response_model=list[BookingRead])
async def list_bookings(item_id: int | None = None) -> list[Booking]:
    query = Booking.all()
    if item_id is not None:
        query = query.filter(item_id=item_id)
    return await query


@router.post("", response_model=BookingRead, status_code=status.HTTP_201_CREATED)
async def create(payload: BookingCreate) -> Booking:
    try:
        return await create_booking(payload)
    except (ItemNotFoundError, CustomerNotFoundError) as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except InsufficientAvailabilityError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc


@router.get("/{booking_id}", response_model=BookingRead)
async def get_booking(booking: BookingDep) -> Booking:
    return booking


@router.post("/{booking_id}/cancel", response_model=BookingRead)
async def cancel(booking: BookingDep) -> Booking:
    try:
        return await cancel_booking(booking)
    except BookingNotCancellableError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
