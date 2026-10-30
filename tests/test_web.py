from httpx import AsyncClient

from book_inventory.models import Booking, InventoryItem


async def test_index_lists_items(client: AsyncClient, item: InventoryItem) -> None:
    response = await client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert item.name in response.text


async def test_create_item_via_form(client: AsyncClient) -> None:
    response = await client.post("/items", data={"name": "Bike", "quantity": "4"})
    assert response.status_code == 303
    assert await InventoryItem.exists(name="Bike")


async def test_item_detail_page(client: AsyncClient, item: InventoryItem) -> None:
    response = await client.get(f"/items/{item.id}")
    assert response.status_code == 200
    assert "Book this item" in response.text


async def test_book_item_via_form(client: AsyncClient, item: InventoryItem) -> None:
    response = await client.post(
        f"/items/{item.id}/bookings",
        data={
            "customer_name": "Grace",
            "customer_email": "grace@example.com",
            "quantity": "1",
            "start_at": "2030-05-01T09:00",
            "end_at": "2030-05-01T10:00",
        },
    )
    assert response.status_code == 303
    assert await Booking.filter(item_id=item.id).count() == 1


async def test_book_item_via_form_shows_errors(client: AsyncClient, item: InventoryItem) -> None:
    response = await client.post(
        f"/items/{item.id}/bookings",
        data={
            "customer_name": "Grace",
            "customer_email": "grace@example.com",
            "quantity": "1",
            "start_at": "2030-05-01T10:00",
            "end_at": "2030-05-01T09:00",
        },
    )
    assert response.status_code == 422
    assert "end_at must be after start_at" in response.text
