import re

from httpx import AsyncClient

from book_inventory.main import create_app
from book_inventory.models import Booking, BookingStatus, Customer, InventoryItem


async def test_index_lists_items(client: AsyncClient, item: InventoryItem) -> None:
    response = await client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert item.name in response.text


async def test_create_item_via_form(client: AsyncClient) -> None:
    response = await client.post("/items", data={"name": "Bike", "remaining_quantity": "4"})
    assert response.status_code == 303
    assert await InventoryItem.exists(name="Bike")

    page = await client.get(response.headers["location"])
    assert "Item added." in page.text
    assert "Bike" in page.text


async def test_item_detail_page(
    client: AsyncClient, item: InventoryItem, customer: Customer
) -> None:
    response = await client.get(f"/items/{item.id}")
    assert response.status_code == 200
    assert "Book this item" in response.text
    assert "Ada Lovelace (0 active bookings)" in response.text


async def test_book_item_via_form(
    client: AsyncClient, item: InventoryItem, customer: Customer
) -> None:
    response = await client.post(
        f"/items/{item.id}/bookings",
        data={
            "customer_id": str(customer.id),
            "quantity": "1",
            "start_at": "2030-05-01T09:00",
            "end_at": "2030-05-01T10:00",
        },
    )
    assert response.status_code == 303
    assert await Booking.filter(item_id=item.id).count() == 1

    page = await client.get(response.headers["location"])
    assert "Booking confirmed." in page.text
    assert "Ada Lovelace" in page.text  # listed in the bookings table


async def test_book_item_via_form_shows_errors(
    client: AsyncClient, item: InventoryItem, customer: Customer
) -> None:
    response = await client.post(
        f"/items/{item.id}/bookings",
        data={
            "customer_id": str(customer.id),
            "quantity": "1",
            "start_at": "2030-05-01T10:00",
            "end_at": "2030-05-01T09:00",
        },
    )
    assert response.status_code == 422
    assert "end_at must be after start_at" in response.text


async def test_notice_only_shows_known_messages(client: AsyncClient, item: InventoryItem) -> None:
    response = await client.get(f"/items/{item.id}", params={"notice": "<script>alert(1)</script>"})
    assert response.status_code == 200
    assert "<script>alert(1)</script>" not in response.text
    assert 'class="notice"' not in response.text


async def test_bookings_table_lists_every_status_with_cancel_only_for_confirmed(
    client: AsyncClient, item: InventoryItem, customer: Customer
) -> None:
    confirmed = await Booking.create(
        item=item, customer=customer, start_at="2030-01-01T10:00:00Z", end_at="2030-01-01T11:00:00Z"
    )
    await Booking.create(
        item=item,
        customer=customer,
        start_at="2020-01-01T10:00:00Z",
        end_at="2020-01-01T11:00:00Z",
        status=BookingStatus.COMPLETED,
    )
    cancelled = await Booking.create(
        item=item,
        customer=customer,
        start_at="2031-01-01T10:00:00Z",
        end_at="2031-01-01T11:00:00Z",
        status=BookingStatus.CANCELLED,
    )

    page = (await client.get(f"/items/{item.id}")).text

    assert page.count("Ada Lovelace</td>") == 3
    for label in ("Confirmed", "Completed", "Cancelled"):
        assert f"<td>{label}</td>" in page
    assert f"/items/{item.id}/bookings/{confirmed.id}/cancel" in page
    assert f"/bookings/{cancelled.id}/cancel" not in page


async def test_cancel_booking_via_form(
    client: AsyncClient, item: InventoryItem, customer: Customer
) -> None:
    await client.post(
        f"/items/{item.id}/bookings",
        data={
            "customer_id": str(customer.id),
            "quantity": "2",
            "start_at": "2030-05-01T09:00",
            "end_at": "2030-05-01T10:00",
        },
    )
    booking = await Booking.get(item_id=item.id)

    response = await client.post(f"/items/{item.id}/bookings/{booking.id}/cancel")

    assert response.status_code == 303
    page = await client.get(response.headers["location"])
    assert "Booking cancelled." in page.text
    await booking.refresh_from_db()
    await item.refresh_from_db()
    await customer.refresh_from_db()
    assert booking.status == BookingStatus.CANCELLED
    assert (item.remaining_quantity, customer.booking_count) == (2, 0)


async def test_cancel_completed_booking_via_form_shows_error(
    client: AsyncClient, item: InventoryItem, customer: Customer
) -> None:
    booking = await Booking.create(
        item=item,
        customer=customer,
        start_at="2020-01-01T10:00:00Z",
        end_at="2020-01-01T11:00:00Z",
        status=BookingStatus.COMPLETED,
    )

    response = await client.post(f"/items/{item.id}/bookings/{booking.id}/cancel")

    assert response.status_code == 409
    assert "already ended" in response.text


async def test_cancel_unknown_booking_returns_404(client: AsyncClient, item: InventoryItem) -> None:
    response = await client.post(f"/items/{item.id}/bookings/9999/cancel")
    assert response.status_code == 404


async def test_customer_dropdown_counts_only_active_bookings(
    client: AsyncClient, item: InventoryItem, customer: Customer
) -> None:
    other = await Customer.create(
        name="Grace", surname="Hopper", date_joined="2024-01-02T12:00:00Z"
    )
    window = {"start_at": "2030-01-01T10:00:00Z", "end_at": "2030-01-01T11:00:00Z"}
    for status in (BookingStatus.CONFIRMED, BookingStatus.COMPLETED, BookingStatus.CANCELLED):
        await Booking.create(item=item, customer=customer, status=status, **window)
    await Booking.create(item=item, customer=other, **window)
    await Booking.create(item=item, customer=other, **window)
    await Customer.filter(id=customer.id).update(booking_count=7)  # the stored count is not used

    page = (await client.get(f"/items/{item.id}")).text

    assert "Ada Lovelace (1 active booking)" in page
    assert "Grace Hopper (2 active bookings)" in page


async def test_pages_load_the_loading_state_script(
    client: AsyncClient, item: InventoryItem
) -> None:
    for path in ("/", f"/items/{item.id}"):
        assert "/static/js/app.js" in (await client.get(path)).text

    script = await client.get("/static/js/app.js")
    assert script.status_code == 200
    assert (await client.get("/static/css/style.css")).text.count("button.loading") >= 1


async def test_dropdown_counts_units_and_web_form_enforces_the_limit(
    client: AsyncClient, customer: Customer
) -> None:
    stocked = await InventoryItem.create(name="Plenty", remaining_quantity=10)
    # Booked as 2 units and then 1 unit through the API/DB: 3 active in total.
    for quantity in (2, 1):
        await Booking.create(
            item=stocked,
            customer=customer,
            quantity=quantity,
            start_at="2030-01-01T10:00:00Z",
            end_at="2030-01-01T11:00:00Z",
        )

    page = (await client.get(f"/items/{stocked.id}")).text
    assert "Ada Lovelace (3 active bookings)" in page

    response = await client.post(
        f"/items/{stocked.id}/bookings",
        data={
            "customer_id": str(customer.id),
            "quantity": "1",
            "start_at": "2030-05-01T09:00",
            "end_at": "2030-05-01T10:00",
        },
    )
    assert response.status_code == 409
    assert "at most 2" in response.text
    assert await Booking.filter(item_id=stocked.id).count() == 2


async def test_book_button_is_enabled_while_units_remain(
    client: AsyncClient, item: InventoryItem
) -> None:
    page = (await client.get(f"/items/{item.id}")).text
    assert "No units remaining" not in page
    assert '<button type="submit" >Book</button>' in page


async def test_book_button_is_disabled_with_message_when_no_units_remain(
    client: AsyncClient, customer: Customer
) -> None:
    sold_out = await InventoryItem.create(name="Sold out", remaining_quantity=0)

    page = (await client.get(f"/items/{sold_out.id}")).text

    assert "No units remaining" in page
    assert '<button type="submit" disabled>Book</button>' in page


async def test_booking_the_last_unit_disables_the_form(
    client: AsyncClient, customer: Customer
) -> None:
    last = await InventoryItem.create(name="Last one", remaining_quantity=1)
    response = await client.post(
        f"/items/{last.id}/bookings",
        data={
            "customer_id": str(customer.id),
            "quantity": "1",
            "start_at": "2030-05-01T09:00",
            "end_at": "2030-05-01T10:00",
        },
    )

    page = (await client.get(response.headers["location"])).text

    assert "Booking confirmed." in page
    assert "No units remaining" in page
    assert '<button type="submit" disabled>Book</button>' in page


async def test_item_page_shows_only_the_latest_bookings(
    client: AsyncClient, item: InventoryItem, customer: Customer
) -> None:
    def booking(day: int) -> Booking:
        return Booking(
            item=item,
            customer=customer,
            status=BookingStatus.COMPLETED,
            start_at=f"2020-01-{day:02d}T10:00:00Z",
            end_at=f"2020-01-{day:02d}T11:00:00Z",
        )

    await Booking.bulk_create([booking(day) for day in range(1, 29)] * 4)  # 112 bookings

    page = (await client.get(f"/items/{item.id}")).text

    assert page.count("Ada Lovelace</td>") == 100
    assert "Showing the latest 100 bookings." in page


async def test_item_page_has_no_truncation_note_for_few_bookings(
    client: AsyncClient, item: InventoryItem, customer: Customer
) -> None:
    await Booking.create(
        item=item, customer=customer, start_at="2030-01-01T10:00:00Z", end_at="2030-01-01T11:00:00Z"
    )
    assert "Showing the latest" not in (await client.get(f"/items/{item.id}")).text


def form_action(html: str, containing: str = "") -> str:
    """The `action` of the first form whose action contains `containing`, as a browser reads it."""
    actions = re.findall(r'<form[^>]*action="([^"]+)"', html)
    return next(action for action in actions if containing in action)


async def test_add_item_form_posts_to_the_web_route_not_the_api(client: AsyncClient) -> None:
    page = (await client.get("/")).text
    action = form_action(page)
    assert "/api/" not in action

    response = await client.post(
        action, data={"name": "India", "remaining_quantity": "1", "description": "India"}
    )

    assert response.status_code == 303
    assert await InventoryItem.exists(name="India")


async def test_booking_forms_post_to_working_web_routes(
    client: AsyncClient, item: InventoryItem, customer: Customer
) -> None:
    page = (await client.get(f"/items/{item.id}")).text
    response = await client.post(
        form_action(page, "/bookings"),
        data={
            "customer_id": str(customer.id),
            "quantity": "1",
            "start_at": "2030-05-01T09:00",
            "end_at": "2030-05-01T10:00",
        },
    )
    assert response.status_code == 303

    page = (await client.get(f"/items/{item.id}")).text
    cancel = await client.post(form_action(page, "/cancel"))
    assert cancel.status_code == 303


def endpoint_names(routes) -> list[str]:
    """Names of every real route; FastAPI wraps included routers, so walk into them."""
    names: list[str] = []
    for route in routes:
        if (router := getattr(route, "original_router", None)) is not None:
            names += endpoint_names(router.routes)
        elif hasattr(route, "path") and hasattr(route, "endpoint"):
            names.append(route.name)
    return names


def test_route_names_are_unique() -> None:
    """`url_for` resolves by name, so a duplicate silently sends a form to the wrong route."""
    names = endpoint_names(create_app().routes)
    assert len(names) > 15  # guards against this test silently finding nothing
    assert len(names) == len(set(names)), sorted({n for n in names if names.count(n) > 1})


async def test_item_list_notice_only_shows_known_messages_and_no_notice_by_default(
    client: AsyncClient,
) -> None:
    assert 'class="notice"' not in (await client.get("/")).text
    page = await client.get("/", params={"notice": "<script>alert(1)</script>"})
    assert 'class="notice"' not in page.text
    assert "<script>alert(1)</script>" not in page.text


async def test_failed_add_item_shows_error_and_no_success_message(
    client: AsyncClient, item: InventoryItem
) -> None:
    response = await client.post("/items", data={"name": item.name, "remaining_quantity": "1"})

    assert response.status_code == 409
    assert "An item with this name already exists" in response.text
    assert "Item added." not in response.text
