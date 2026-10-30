"""Inventory item business logic."""

from datetime import UTC, date, datetime

from book_inventory.models import InventoryItem


async def deactivate_expired_items(today: date | None = None) -> int:
    """Set `is_active=False` on active items whose `expiration_date` is before `today` (UTC).

    The expiration date is the last day an item can be booked. Returns how many items were
    deactivated. Items without an expiration date are never touched.
    """
    today = today or datetime.now(UTC).date()
    return await InventoryItem.filter(is_active=True, expiration_date__lt=today).update(
        is_active=False, updated_at=datetime.now(UTC)
    )
