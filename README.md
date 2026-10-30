# book-inventory

Manage a bookable inventory (rooms, equipment, vehicles — anything with a fixed number of units)
through a REST API and a simple server-rendered web UI.

**Stack:** FastAPI · Tortoise ORM · PostgreSQL · Pydantic v2 · Jinja2 · Pytest · Docker

## Quick start (Docker)

```bash
cp .env.example .env        # optional; defaults work without it
docker compose up --build
```

- Web UI: http://localhost:8000
- API docs (Swagger): http://localhost:8000/docs
- Health check: http://localhost:8000/api/v1/health

Source under `src/` is bind-mounted and uvicorn runs with `--reload`, so code changes apply immediately.

Run the tests in the container:

```bash
make test        # = docker compose run --rm --no-deps app pytest
```

## Local development (without Docker for the app)

```bash
docker compose up -d db
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
uvicorn book_inventory.main:app --reload
pytest
```

Tests use an in-memory SQLite database by default, so they need no running Postgres.
Point them at another database with `TEST_DATABASE_URL`.

## Project layout

```
src/book_inventory/
├── main.py            # app factory, lifespan (DB init), router + static mounting
├── config.py          # settings via pydantic-settings (env vars / .env)
├── db.py              # Tortoise ORM config
├── models/            # Tortoise models: InventoryItem, Customer, Booking
├── schemas/           # Pydantic request/response models
├── scheduler.py       # background job: complete ended bookings, return stock
├── services/          # business logic (booking, cancellation, completion)
├── api/               # REST API, mounted at /api/v1
│   ├── deps.py
│   └── routes/        # health, items, customers, bookings
├── web/               # HTML routes rendering Jinja2 templates
├── templates/
└── static/
tests/                 # pytest suite (API + web)
```

## API overview

| Method | Path | Description |
| --- | --- | --- |
| GET | `/api/v1/items` | List items (`?active_only=true`) |
| POST | `/api/v1/items` | Create item |
| GET / PATCH / DELETE | `/api/v1/items/{id}` | Read, update, or delete an item (delete is refused when it has bookings) |
| GET | `/api/v1/customers`, `/api/v1/customers/{id}` | List / read customers |
| GET | `/api/v1/bookings` | List bookings (`?item_id=`) |
| POST | `/api/v1/bookings` | Create booking for an `item_id` and `customer_id` (404 if either is unknown, 409 if not enough units are free) |
| GET | `/api/v1/bookings/{id}` | Read booking |
| POST | `/api/v1/bookings/{id}/cancel` | Cancel booking |

Booking stock: confirming a booking subtracts its `quantity` from the item's `remaining_quantity` and
adds one to the customer's `booking_count`; cancelling reverses both. `remaining_quantity` is a running
counter, so `start_at`/`end_at` don't affect availability when booking.

Once a booking's `end_at` has passed, a background job marks it `completed` and returns its units to
`remaining_quantity` (the customer's `booking_count` is left as is). A completed booking can no longer
be cancelled (409). See below.

## Background job

`scheduler.py` runs an asyncio task inside the app process: it completes ended bookings once at
startup (catching up after downtime) and then every `COMPLETE_BOOKINGS_INTERVAL_SECONDS` (default 60).
Set `RUN_SCHEDULER=false` to turn it off. A failed run is logged and retried on the next tick. It is
safe with several app instances or workers: rows are locked, so each booking is released exactly once.
Times without a timezone are treated as UTC.

## Database schema and seed data

The schema is managed with [Aerich](https://github.com/tortoise/aerich) migrations in
`src/book_inventory/migrations/models/`. The app applies pending migrations on startup
(`RUN_MIGRATIONS=true`, the default), so a fresh database ends up with the schema and the seed data:

- `0_…_init` – the full schema: `inventory_items`, `customers`, `bookings`
- `1_…_import_inventory_and_customers` – imports `migrations/data/inventory.csv` and `members.csv`
  (inventory `title` → item `name`, `remaining_count` → `remaining_quantity`, `expiration_date`;
  members → `customers`; a repeated title such as "London" is imported as "London (2)" because
  item names are unique)

The CSVs are a snapshot read once by that migration; changing them later does not re-import.

Common commands (run from the repo root, with `DATABASE_URL` set):

```bash
python -m aerich upgrade                   # apply pending migrations
python -m aerich migrate --name add_thing  # generate a migration after changing a model
python -m aerich downgrade -v 1 --yes      # roll back to before the data import
```
