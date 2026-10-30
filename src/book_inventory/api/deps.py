from typing import Annotated

from fastapi import Depends, HTTPException, status

from book_inventory.models import Booking, Customer, InventoryItem


async def get_item_or_404(item_id: int) -> InventoryItem:
    item = await InventoryItem.get_or_none(id=item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item not found")
    return item


async def get_booking_or_404(booking_id: int) -> Booking:
    booking = await Booking.get_or_none(id=booking_id)
    if booking is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Booking not found")
    return booking


async def get_customer_or_404(customer_id: int) -> Customer:
    customer = await Customer.get_or_none(id=customer_id)
    if customer is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Customer not found")
    return customer


CustomerDep = Annotated[Customer, Depends(get_customer_or_404)]
