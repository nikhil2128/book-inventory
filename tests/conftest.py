import os
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from tortoise import Tortoise

from book_inventory.config import Settings
from book_inventory.db import get_tortoise_config
from book_inventory.main import create_app
from book_inventory.models import Customer, InventoryItem

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "sqlite://:memory:")


@pytest.fixture
async def db() -> AsyncIterator[None]:
    """Fresh database per test: created on setup, dropped on teardown."""
    await Tortoise.init(config=get_tortoise_config(TEST_DATABASE_URL), _create_db=True)
    await Tortoise.generate_schemas()
    yield
    await Tortoise._drop_databases()


@pytest.fixture
async def client(db: None) -> AsyncIterator[AsyncClient]:
    # ASGITransport does not run the app lifespan, so the `db` fixture owns the connection.
    app = create_app(Settings(database_url=TEST_DATABASE_URL, generate_schemas=False))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest.fixture
async def item(db: None) -> InventoryItem:
    return await InventoryItem.create(name="Meeting Room A", remaining_quantity=2)


@pytest.fixture
async def customer(db: None) -> Customer:
    return await Customer.create(name="Ada", surname="Lovelace", date_joined="2024-01-02T12:00:00Z")
