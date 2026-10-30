from typing import Any

MODEL_MODULES = ["book_inventory.models"]


def get_tortoise_config(database_url: str) -> dict[str, Any]:
    return {
        "connections": {"default": database_url},
        "apps": {
            "models": {"models": MODEL_MODULES, "default_connection": "default"},
        },
        "use_tz": True,
        "timezone": "UTC",
    }
