from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, loaded from environment variables (and an optional .env file)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Book Inventory"
    debug: bool = False
    database_url: str = "postgres://postgres:postgres@localhost:5432/book_inventory"
    # Create tables on startup. Convenient for local development; replace with
    # migrations (e.g. Aerich) before running against a production database.
    generate_schemas: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
