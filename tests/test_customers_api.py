from httpx import AsyncClient

from book_inventory.models import Customer


async def test_list_customers(client: AsyncClient, customer: Customer) -> None:
    response = await client.get("/api/v1/customers")
    assert response.status_code == 200
    assert [c["id"] for c in response.json()] == [customer.id]


async def test_get_customer(client: AsyncClient, customer: Customer) -> None:
    response = await client.get(f"/api/v1/customers/{customer.id}")
    assert response.status_code == 200
    body = response.json()
    assert (body["name"], body["surname"], body["booking_count"]) == ("Ada", "Lovelace", 0)


async def test_get_unknown_customer_returns_404(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/customers/9999")).status_code == 404
