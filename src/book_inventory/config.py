from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, loaded from environment variables (and an optional .env file)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Book Inventory"
    debug: bool = False
    database_url: str = "postgres://postgres:postgres@localhost:5432/book_inventory"
    # Apply pending Aerich migrations (schema + seed data) on startup.
    run_migrations: bool = True
    # Create missing tables straight from the models. Migrations own the schema, so leave this
    # off unless you are running without them.
    generate_schemas: bool = False
    # Most units a customer can hold in active (confirmed) bookings at once.
    max_active_units_per_customer: int = 2
    # Background job that completes bookings whose end_at has passed and returns their stock.
    run_scheduler: bool = True
    complete_bookings_interval_seconds: int = 60


@lru_cache
def get_settings() -> Settings:
    return Settings()
