import asyncio
from datetime import UTC, date, datetime, timedelta

from httpx import AsyncClient

from book_inventory.models import Booking, BookingStatus, Customer, InventoryItem
from book_inventory.scheduler import run_periodically
from book_inventory.schemas import BookingCreate
from book_inventory.services.bookings import (
    cancel_booking,
    complete_expired_bookings,
    create_booking,
)
from book_inventory.services.items import deactivate_expired_items

NOW = datetime(2030, 6, 1, 12, 0, tzinfo=UTC)


async def book(item: InventoryItem, customer: Customer, *, ends: datetime, quantity: int = 1):
    return await create_booking(
        BookingCreate(
            item_id=item.id,
            customer_id=customer.id,
            quantity=quantity,
            start_at=ends - timedelta(hours=1),
            end_at=ends,
        )
    )


async def test_expired_booking_is_completed_and_stock_returned(
    item: InventoryItem, customer: Customer
) -> None:
    booking = await book(item, customer, ends=NOW - timedelta(minutes=1), quantity=2)
    await item.refresh_from_db()
    assert item.remaining_quantity == 0

    assert await complete_expired_bookings(NOW) == 1

    await booking.refresh_from_db()
    await item.refresh_from_db()
    await customer.refresh_from_db()
    assert booking.status == BookingStatus.COMPLETED
    assert item.remaining_quantity == 2
    assert customer.booking_count == 1  # completing does not change the count


async def test_booking_ending_exactly_now_is_completed(
    item: InventoryItem, customer: Customer
) -> None:
    await book(item, customer, ends=NOW)
    assert await complete_expired_bookings(NOW) == 1


async def test_running_bookings_are_left_alone(item: InventoryItem, customer: Customer) -> None:
    booking = await book(item, customer, ends=NOW + timedelta(minutes=1))

    assert await complete_expired_bookings(NOW) == 0

    await booking.refresh_from_db()
    await item.refresh_from_db()
    assert booking.status == BookingStatus.CONFIRMED
    assert item.remaining_quantity == 1


async def test_cancelled_booking_is_not_released_twice(
    item: InventoryItem, customer: Customer
) -> None:
    booking = await book(item, customer, ends=NOW - timedelta(hours=1))
    await cancel_booking(booking)

    assert await complete_expired_bookings(NOW) == 0

    await item.refresh_from_db()
    assert item.remaining_quantity == 2


async def test_second_run_does_nothing(item: InventoryItem, customer: Customer) -> None:
    await book(item, customer, ends=NOW - timedelta(hours=1))

    assert await complete_expired_bookings(NOW) == 1
    assert await complete_expired_bookings(NOW) == 0

    await item.refresh_from_db()
    assert item.remaining_quantity == 2


async def test_several_bookings_for_one_item_are_summed(
    item: InventoryItem, customer: Customer
) -> None:
    await book(item, customer, ends=NOW - timedelta(hours=2))
    await book(item, customer, ends=NOW - timedelta(hours=1))
    await item.refresh_from_db()
    assert item.remaining_quantity == 0

    assert await complete_expired_bookings(NOW) == 2

    await item.refresh_from_db()
    assert item.remaining_quantity == 2
    assert await Booking.filter(status=BookingStatus.COMPLETED).count() == 2


async def test_cannot_cancel_completed_booking(
    client: AsyncClient, item: InventoryItem, customer: Customer
) -> None:
    booking = await book(item, customer, ends=NOW - timedelta(hours=1))
    await complete_expired_bookings(NOW)

    response = await client.post(f"/api/v1/bookings/{booking.id}/cancel")

    assert response.status_code == 409
    await item.refresh_from_db()
    await customer.refresh_from_db()
    assert item.remaining_quantity == 2  # not given back a second time
    assert customer.booking_count == 1


async def test_run_periodically_repeats_and_survives_errors() -> None:
    calls = 0
    enough_calls = asyncio.Event()

    async def flaky_job() -> int:
        nonlocal calls
        calls += 1
        if calls >= 4:
            enough_calls.set()
        if calls == 2:
            raise RuntimeError("boom")
        return 0

    task = asyncio.create_task(run_periodically(flaky_job, 0.01, name="test"))
    try:
        async with asyncio.timeout(2):
            await enough_calls.wait()  # still looping after the failed second run
    finally:
        task.cancel()
    assert calls >= 4


async def test_deactivate_expired_items(db: None) -> None:
    today = date(2030, 6, 1)
    expired = await InventoryItem.create(
        name="Expired", remaining_quantity=1, expiration_date=today - timedelta(days=1)
    )
    last_day = await InventoryItem.create(
        name="Last day", remaining_quantity=1, expiration_date=today
    )
    future = await InventoryItem.create(
        name="Future", remaining_quantity=1, expiration_date=today + timedelta(days=1)
    )
    no_expiry = await InventoryItem.create(name="No expiry", remaining_quantity=1)

    assert await deactivate_expired_items(today) == 1
    assert await deactivate_expired_items(today) == 0  # nothing left to do

    for item, active in [(expired, False), (last_day, True), (future, True), (no_expiry, True)]:
        await item.refresh_from_db()
        assert item.is_active is active, item.name


async def test_cannot_book_expired_item_before_scheduler_runs(
    client: AsyncClient, customer: Customer
) -> None:
    yesterday = datetime.now(UTC).date() - timedelta(days=1)
    item = await InventoryItem.create(
        name="Just expired", remaining_quantity=1, expiration_date=yesterday
    )  # still is_active=True: the scheduler hasn't run yet

    response = await client.post(
        "/api/v1/bookings",
        json={
            "item_id": item.id,
            "customer_id": customer.id,
            "start_at": "2030-01-01T10:00:00Z",
            "end_at": "2030-01-01T11:00:00Z",
        },
    )

    assert response.status_code == 404
    assert "expired" in response.json()["detail"]
