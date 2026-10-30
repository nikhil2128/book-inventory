from typing import Any

import pytest
from httpx import AsyncClient

from book_inventory.models import Customer, InventoryItem


def booking_payload(item_id: int, customer_id: int, **overrides: Any) -> dict[str, Any]:
    return {
        "item_id": item_id,
        "customer_id": customer_id,
        "quantity": 1,
        "start_at": "2030-01-01T10:00:00Z",
        "end_at": "2030-01-01T12:00:00Z",
    } | overrides


async def test_create_booking(client: AsyncClient, item: InventoryItem, customer: Customer) -> None:
    response = await client.post("/api/v1/bookings", json=booking_payload(item.id, customer.id))
    assert response.status_code == 201
    body = response.json()
    assert body["item_id"] == item.id
    assert body["status"] == "confirmed"


async def test_booking_rejects_overbooking(
    client: AsyncClient, item: InventoryItem, customer: Customer
) -> None:
    # item has 2 units
    assert (
        await client.post(
            "/api/v1/bookings", json=booking_payload(item.id, customer.id, quantity=2)
        )
    ).status_code == 201

    response = await client.post(
        "/api/v1/bookings",
        json=booking_payload(
            item.id, customer.id, start_at="2031-01-01T11:00:00Z", end_at="2031-01-01T13:00:00Z"
        ),
    )
    assert response.status_code == 409  # stock is a running counter, dates don't matter


async def test_cancelled_booking_frees_stock(
    client: AsyncClient, item: InventoryItem, customer: Customer
) -> None:
    created = (
        await client.post(
            "/api/v1/bookings", json=booking_payload(item.id, customer.id, quantity=2)
        )
    ).json()

    response = await client.post(f"/api/v1/bookings/{created['id']}/cancel")
    assert response.json()["status"] == "cancelled"

    response = await client.post(
        "/api/v1/bookings", json=booking_payload(item.id, customer.id, quantity=2)
    )
    assert response.status_code == 201


@pytest.mark.parametrize(
    "overrides",
    [
        {"end_at": "2030-01-01T09:00:00Z"},
        {"quantity": 0},
    ],
)
async def test_invalid_booking_payload(
    client: AsyncClient, item: InventoryItem, customer: Customer, overrides: dict[str, Any]
) -> None:
    response = await client.post(
        "/api/v1/bookings", json=booking_payload(item.id, customer.id, **overrides)
    )
    assert response.status_code == 422


async def test_booking_inactive_item_returns_404(client: AsyncClient, customer: Customer) -> None:
    item = await InventoryItem.create(name="Retired", remaining_quantity=1, is_active=False)
    response = await client.post("/api/v1/bookings", json=booking_payload(item.id, customer.id))
    assert response.status_code == 404


async def test_booking_unknown_customer_returns_404(
    client: AsyncClient, item: InventoryItem
) -> None:
    response = await client.post("/api/v1/bookings", json=booking_payload(item.id, 9999))
    assert response.status_code == 404
    assert "Customer 9999" in response.json()["detail"]


async def test_booking_decrements_stock_and_increments_booking_count(
    client: AsyncClient, item: InventoryItem, customer: Customer
) -> None:
    # item has 2 units, customer starts at 0 bookings
    response = await client.post("/api/v1/bookings", json=booking_payload(item.id, customer.id))
    assert response.status_code == 201

    await item.refresh_from_db()
    await customer.refresh_from_db()
    assert item.remaining_quantity == 1
    assert customer.booking_count == 1


async def test_cancel_restores_stock_and_booking_count(
    client: AsyncClient, item: InventoryItem, customer: Customer
) -> None:
    created = (
        await client.post(
            "/api/v1/bookings", json=booking_payload(item.id, customer.id, quantity=2)
        )
    ).json()
    await item.refresh_from_db()
    assert item.remaining_quantity == 0

    await client.post(f"/api/v1/bookings/{created['id']}/cancel")

    await item.refresh_from_db()
    await customer.refresh_from_db()
    assert item.remaining_quantity == 2
    assert customer.booking_count == 0


async def test_cancelling_twice_only_restores_once(
    client: AsyncClient, item: InventoryItem, customer: Customer
) -> None:
    created = (
        await client.post("/api/v1/bookings", json=booking_payload(item.id, customer.id))
    ).json()

    for _ in range(2):
        response = await client.post(f"/api/v1/bookings/{created['id']}/cancel")
        assert response.json()["status"] == "cancelled"

    await item.refresh_from_db()
    await customer.refresh_from_db()
    assert item.remaining_quantity == 2
    assert customer.booking_count == 0


async def test_rejected_booking_changes_nothing(
    client: AsyncClient, item: InventoryItem, customer: Customer
) -> None:
    response = await client.post(
        "/api/v1/bookings", json=booking_payload(item.id, customer.id, quantity=3)
    )
    assert response.status_code == 409

    await item.refresh_from_db()
    await customer.refresh_from_db()
    assert item.remaining_quantity == 2
    assert customer.booking_count == 0
