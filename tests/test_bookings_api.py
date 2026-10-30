from typing import Any

import pytest
from httpx import AsyncClient

from book_inventory.models import Booking, BookingStatus, Customer, InventoryItem


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
    other = await Customer.create(
        name="Grace", surname="Hopper", date_joined="2024-01-02T12:00:00Z"
    )
    # item has 2 units
    assert (
        await client.post(
            "/api/v1/bookings", json=booking_payload(item.id, customer.id, quantity=2)
        )
    ).status_code == 201

    response = await client.post(
        "/api/v1/bookings",
        json=booking_payload(
            item.id, other.id, start_at="2031-01-01T11:00:00Z", end_at="2031-01-01T13:00:00Z"
        ),
    )
    assert response.status_code == 409  # stock is a running counter, dates don't matter
    assert "available" in response.json()["detail"]


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


async def _book(client: AsyncClient, item: InventoryItem, customer: Customer, quantity: int):
    return await client.post(
        "/api/v1/bookings", json=booking_payload(item.id, customer.id, quantity=quantity)
    )


async def test_customer_cannot_exceed_max_active_units(
    client: AsyncClient, customer: Customer
) -> None:
    stocked = await InventoryItem.create(name="Plenty", remaining_quantity=10)
    assert (await _book(client, stocked, customer, 2)).status_code == 201

    response = await _book(client, stocked, customer, 1)  # 2 + 1 > 2

    assert response.status_code == 409
    assert "at most 2" in response.json()["detail"]
    await stocked.refresh_from_db()
    await customer.refresh_from_db()
    assert (stocked.remaining_quantity, customer.booking_count) == (8, 1)  # nothing changed


async def test_limit_is_checked_across_bookings_and_items(
    client: AsyncClient, customer: Customer
) -> None:
    first = await InventoryItem.create(name="First", remaining_quantity=5)
    second = await InventoryItem.create(name="Second", remaining_quantity=5)
    assert (await _book(client, first, customer, 1)).status_code == 201
    assert (await _book(client, second, customer, 1)).status_code == 201

    assert (await _book(client, first, customer, 1)).status_code == 409


async def test_single_booking_over_the_limit_is_rejected(
    client: AsyncClient, customer: Customer
) -> None:
    stocked = await InventoryItem.create(name="Plenty", remaining_quantity=10)
    assert (await _book(client, stocked, customer, 3)).status_code == 409


async def test_cancelling_frees_the_customers_allowance(
    client: AsyncClient, customer: Customer
) -> None:
    stocked = await InventoryItem.create(name="Plenty", remaining_quantity=10)
    created = (await _book(client, stocked, customer, 2)).json()
    assert (await _book(client, stocked, customer, 1)).status_code == 409

    await client.post(f"/api/v1/bookings/{created['id']}/cancel")

    assert (await _book(client, stocked, customer, 2)).status_code == 201


async def test_completed_bookings_do_not_count_towards_the_limit(
    client: AsyncClient, customer: Customer
) -> None:
    stocked = await InventoryItem.create(name="Plenty", remaining_quantity=10)
    await Booking.create(
        item=stocked,
        customer=customer,
        quantity=2,
        status=BookingStatus.COMPLETED,
        start_at="2020-01-01T10:00:00Z",
        end_at="2020-01-01T11:00:00Z",
    )

    assert (await _book(client, stocked, customer, 2)).status_code == 201


async def test_limit_is_per_customer(client: AsyncClient, customer: Customer) -> None:
    other = await Customer.create(
        name="Grace", surname="Hopper", date_joined="2024-01-02T12:00:00Z"
    )
    stocked = await InventoryItem.create(name="Plenty", remaining_quantity=10)
    assert (await _book(client, stocked, customer, 2)).status_code == 201

    assert (await _book(client, stocked, other, 2)).status_code == 201
