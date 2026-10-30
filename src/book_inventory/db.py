from pathlib import Path
from typing import Any

from aerich import Command

from book_inventory.config import get_settings

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"

# `aerich.models` holds the table that tracks which migrations have been applied.
MODEL_MODULES = ["book_inventory.models", "aerich.models"]


def get_tortoise_config(database_url: str) -> dict[str, Any]:
    return {
        "connections": {"default": database_url},
        "apps": {
            "models": {"models": MODEL_MODULES, "default_connection": "default"},
        },
        "use_tz": True,
        "timezone": "UTC",
    }


async def run_migrations(database_url: str) -> None:
    """Apply pending Aerich migrations (schema changes and seed data)."""
    async with Command(
        get_tortoise_config(database_url), app="models", location=str(MIGRATIONS_DIR)
    ) as command:
        await command.upgrade()


# Used by the `aerich` CLI (see [tool.aerich] in pyproject.toml).
TORTOISE_ORM = get_tortoise_config(get_settings().database_url)
