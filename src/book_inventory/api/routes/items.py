from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from tortoise.exceptions import IntegrityError

from book_inventory.api.deps import get_item_or_404
from book_inventory.models import InventoryItem
from book_inventory.schemas import Availability, ItemCreate, ItemRead, ItemUpdate
from book_inventory.schemas.booking import ensure_aware
from book_inventory.services.bookings import get_availability

router = APIRouter(prefix="/items", tags=["items"])

ItemDep = Annotated[InventoryItem, Depends(get_item_or_404)]


@router.get("", response_model=list[ItemRead])
async def list_items(active_only: bool = False) -> list[InventoryItem]:
    query = InventoryItem.all()
    if active_only:
        query = query.filter(is_active=True)
    return await query


@router.post("", response_model=ItemRead, status_code=status.HTTP_201_CREATED)
async def create_item(payload: ItemCreate) -> InventoryItem:
    try:
        return await InventoryItem.create(**payload.model_dump())
    except IntegrityError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "Item name already exists") from exc


@router.get("/{item_id}", response_model=ItemRead)
async def get_item(item: ItemDep) -> InventoryItem:
    return item


@router.patch("/{item_id}", response_model=ItemRead)
async def update_item(item: ItemDep, payload: ItemUpdate) -> InventoryItem:
    changes = payload.model_dump(exclude_unset=True)
    if changes:
        item.update_from_dict(changes)
        try:
            await item.save()
        except IntegrityError as exc:
            raise HTTPException(status.HTTP_409_CONFLICT, "Item name already exists") from exc
    return item


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(item: ItemDep) -> None:
    if await item.bookings.all().exists():
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Item has bookings; deactivate it instead of deleting"
        )
    await item.delete()


@router.get("/{item_id}/availability", response_model=Availability)
async def item_availability(
    item: ItemDep,
    start_at: Annotated[datetime, Query()],
    end_at: Annotated[datetime, Query()],
) -> Availability:
    start_at, end_at = ensure_aware(start_at), ensure_aware(end_at)
    if end_at <= start_at:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "end_at must be after start_at")
    return await get_availability(item, start_at, end_at)
