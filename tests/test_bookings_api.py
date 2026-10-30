from typing import Any

import pytest
from httpx import AsyncClient

from book_inventory.models import InventoryItem


def booking_payload(item_id: int, **overrides: Any) -> dict[str, Any]:
    return {
        "item_id": item_id,
        "customer_name": "Ada Lovelace",
        "customer_email": "ada@example.com",
        "quantity": 1,
        "start_at": "2030-01-01T10:00:00Z",
        "end_at": "2030-01-01T12:00:00Z",
    } | overrides


async def test_create_booking(client: AsyncClient, item: InventoryItem) -> None:
    response = await client.post("/api/v1/bookings", json=booking_payload(item.id))
    assert response.status_code == 201
    body = response.json()
    assert body["item_id"] == item.id
    assert body["status"] == "confirmed"


async def test_booking_rejects_overbooking(client: AsyncClient, item: InventoryItem) -> None:
    # item has 2 units
    assert (
        await client.post("/api/v1/bookings", json=booking_payload(item.id, quantity=2))
    ).status_code == 201

    response = await client.post(
        "/api/v1/bookings",
        json=booking_payload(
            item.id, start_at="2030-01-01T11:00:00Z", end_at="2030-01-01T13:00:00Z"
        ),
    )
    assert response.status_code == 409


async def test_adjacent_bookings_do_not_overlap(client: AsyncClient, item: InventoryItem) -> None:
    first = booking_payload(item.id, quantity=2)
    second = booking_payload(
        item.id, quantity=2, start_at=first["end_at"], end_at="2030-01-01T14:00:00Z"
    )
    assert (await client.post("/api/v1/bookings", json=first)).status_code == 201
    assert (await client.post("/api/v1/bookings", json=second)).status_code == 201


async def test_cancelled_booking_frees_capacity(client: AsyncClient, item: InventoryItem) -> None:
    created = (
        await client.post("/api/v1/bookings", json=booking_payload(item.id, quantity=2))
    ).json()

    response = await client.post(f"/api/v1/bookings/{created['id']}/cancel")
    assert response.json()["status"] == "cancelled"

    response = await client.post("/api/v1/bookings", json=booking_payload(item.id, quantity=2))
    assert response.status_code == 201


@pytest.mark.parametrize(
    "overrides",
    [
        {"end_at": "2030-01-01T09:00:00Z"},
        {"quantity": 0},
        {"customer_email": "not-an-email"},
    ],
)
async def test_invalid_booking_payload(
    client: AsyncClient, item: InventoryItem, overrides: dict[str, Any]
) -> None:
    response = await client.post("/api/v1/bookings", json=booking_payload(item.id, **overrides))
    assert response.status_code == 422


async def test_booking_inactive_item_returns_404(client: AsyncClient) -> None:
    item = await InventoryItem.create(name="Retired", quantity=1, is_active=False)
    response = await client.post("/api/v1/bookings", json=booking_payload(item.id))
    assert response.status_code == 404


async def test_availability(client: AsyncClient, item: InventoryItem) -> None:
    await client.post("/api/v1/bookings", json=booking_payload(item.id))

    response = await client.get(
        f"/api/v1/items/{item.id}/availability",
        params={"start_at": "2030-01-01T11:00:00Z", "end_at": "2030-01-01T11:30:00Z"},
    )
    assert response.status_code == 200
    body = response.json()
    assert (body["total"], body["booked"], body["available"]) == (2, 1, 1)
