from httpx import AsyncClient

from book_inventory.models import Booking, InventoryItem


async def test_health(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_create_and_get_item(client: AsyncClient) -> None:
    response = await client.post("/api/v1/items", json={"name": "Projector", "quantity": 3})
    assert response.status_code == 201
    created = response.json()
    assert created["name"] == "Projector"
    assert created["is_active"] is True

    response = await client.get(f"/api/v1/items/{created['id']}")
    assert response.status_code == 200
    assert response.json()["quantity"] == 3


async def test_create_item_duplicate_name_conflicts(
    client: AsyncClient, item: InventoryItem
) -> None:
    response = await client.post("/api/v1/items", json={"name": item.name, "quantity": 1})
    assert response.status_code == 409


async def test_create_item_rejects_negative_quantity(client: AsyncClient) -> None:
    response = await client.post("/api/v1/items", json={"name": "Desk", "quantity": -1})
    assert response.status_code == 422


async def test_list_items_active_only(client: AsyncClient) -> None:
    await InventoryItem.create(name="Active", quantity=1)
    await InventoryItem.create(name="Retired", quantity=1, is_active=False)

    response = await client.get("/api/v1/items", params={"active_only": True})
    assert [i["name"] for i in response.json()] == ["Active"]


async def test_update_item(client: AsyncClient, item: InventoryItem) -> None:
    response = await client.patch(f"/api/v1/items/{item.id}", json={"quantity": 5})
    assert response.status_code == 200
    assert response.json()["quantity"] == 5
    assert response.json()["name"] == item.name


async def test_get_missing_item_returns_404(client: AsyncClient) -> None:
    response = await client.get("/api/v1/items/999")
    assert response.status_code == 404


async def test_delete_item(client: AsyncClient, item: InventoryItem) -> None:
    response = await client.delete(f"/api/v1/items/{item.id}")
    assert response.status_code == 204
    assert not await InventoryItem.exists(id=item.id)


async def test_delete_item_with_bookings_conflicts(
    client: AsyncClient, item: InventoryItem
) -> None:
    await Booking.create(
        item=item,
        customer_name="Ada",
        customer_email="ada@example.com",
        start_at="2030-01-01T10:00:00Z",
        end_at="2030-01-01T11:00:00Z",
    )
    response = await client.delete(f"/api/v1/items/{item.id}")
    assert response.status_code == 409
