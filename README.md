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

On startup the app applies the database migrations, which create the schema and import the seed data
(see [Database schema and seed data](#database-schema-and-seed-data)).

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

The app applies pending migrations itself when it starts, so there is no separate setup step.

Tests use an in-memory SQLite database by default, so they need no running Postgres.
Point them at another database with `TEST_DATABASE_URL`.

## Project layout

```
src/book_inventory/
├── main.py            # app factory, lifespan (migrations, DB init, scheduler), routers, static files
├── config.py          # settings via pydantic-settings (env vars / .env)
├── db.py              # Tortoise ORM config + migration runner
├── models/            # Tortoise models: InventoryItem, Customer, Booking
├── schemas/           # Pydantic request/response models
├── migrations/        # Aerich migrations (models/) and the seed CSVs (data/)
├── scheduler.py       # background jobs: complete ended bookings, deactivate expired items
├── services/          # business logic (booking, cancellation, completion, item expiry)
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
| POST | `/api/v1/items` | Create item (`name`, `remaining_quantity`, optional `description`, `expiration_date`) |
| GET / PATCH / DELETE | `/api/v1/items/{id}` | Read, update, or delete an item (delete is refused when it has bookings) |
| GET | `/api/v1/customers`, `/api/v1/customers/{id}` | List / read customers |
| GET | `/api/v1/bookings` | List bookings (`?item_id=`) |
| POST | `/api/v1/bookings` | Create booking for an `item_id` and `customer_id` (404 if the customer is unknown or the item is unknown, inactive or expired; 409 if not enough units remain or the customer is at their limit) |
| GET | `/api/v1/bookings/{id}` | Read booking |
| POST | `/api/v1/bookings/{id}/cancel` | Cancel booking (409 if it has already ended) |

Times without a timezone are treated as UTC.

### Stock and booking counts

Booking statuses are `confirmed`, `cancelled` and `completed`.

- Confirming a booking subtracts its `quantity` from the item's `remaining_quantity` and adds one to
  the customer's `booking_count`. Cancelling reverses both.
- A customer can hold at most 2 units (`MAX_ACTIVE_UNITS_PER_CUSTOMER`) in active bookings at once. A
  booking that would take them past that is refused with 409. "Active" means `confirmed`: cancelled
  and completed bookings don't count, so cancelling or finishing a booking frees allowance. The
  customer dropdown on the item page shows each customer's active count next to their name.
- `remaining_quantity` is a running counter, so a booking's `start_at`/`end_at` don't affect whether
  it can be made.
- Once a booking's `end_at` has passed, a background job marks it `completed` and returns its units
  to `remaining_quantity`. The customer's `booking_count` is left as is, and a completed booking can
  no longer be cancelled.

### Item expiry

`expiration_date` is the last day an item can be booked. After it, a background job sets the item
inactive, and booking it is refused even before the job has run. The job keeps an expired item
inactive, so to bring one back, move its `expiration_date` forward.

## Background jobs

`scheduler.py` runs two asyncio jobs inside the app process:

- `complete-bookings` – completes ended bookings and returns their stock
- `deactivate-expired-items` – deactivates items past their `expiration_date`

Each runs once at startup (catching up after downtime) and then every
`COMPLETE_BOOKINGS_INTERVAL_SECONDS` (default 60). A failed run is logged and retried on the next
tick. They are safe with several app instances or workers: rows are locked, so each booking is
released exactly once.

## Configuration

Set as environment variables or in `.env` (see `.env.example`):

| Variable | Default | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | `postgres://postgres:postgres@localhost:5432/book_inventory` | Database connection |
| `RUN_MIGRATIONS` | `true` | Apply pending migrations on startup |
| `GENERATE_SCHEMAS` | `false` | Create tables straight from the models; migrations own the schema, so leave it off |
| `MAX_ACTIVE_UNITS_PER_CUSTOMER` | `2` | Most units one customer can hold in active bookings |
| `RUN_SCHEDULER` | `true` | Run the background jobs |
| `COMPLETE_BOOKINGS_INTERVAL_SECONDS` | `60` | How often the background jobs run |

## Database schema and seed data

The schema is managed with [Aerich](https://github.com/tortoise/aerich) migrations in
`src/book_inventory/migrations/models/`. The app applies pending migrations on startup
(`RUN_MIGRATIONS=true`, the default), so a fresh database ends up with the schema and the seed data:

- `0_…_init` – the full schema: `inventory_items`, `customers`, `bookings`
- `1_…_import_inventory_and_customers` – imports `migrations/data/inventory.csv` and `members.csv`
  (inventory `title` → item `name`, `remaining_count` → `remaining_quantity`, `expiration_date`;
  members → `customers`; a repeated title such as "London" is imported as "London (2)" because
  item names are unique)
- `2_…_bookings_indexes` – replaces the single-column `start_at`/`end_at` indexes with the ones
  described under [Indexes](#indexes)

The CSVs are a snapshot read once by that migration; changing them later does not re-import.

Common commands (run from the repo root, with `DATABASE_URL` set):

```bash
python -m aerich upgrade                   # apply pending migrations
python -m aerich migrate --name add_thing  # generate a migration after changing a model
python -m aerich downgrade -v 1 --yes      # roll back migration 1 (the data import) and everything after it
```

## Indexes

Every index exists for a specific query; check any new one with `EXPLAIN ANALYZE` before adding it.

| Table | Index | Serves |
| --- | --- | --- |
| all | primary keys | lookups by id |
| `inventory_items` | unique `name` | duplicate-name check, name lookups |
| `bookings` | `(item_id, start_at)` | an item's bookings newest-first (item page, `GET /bookings?item_id=`), the delete-item guard, and the `item_id` foreign key |
| `bookings` | `(customer_id)` where `status = 'confirmed'` | a customer's active units (booking limit, customer dropdown) |
| `bookings` | `(end_at)` where `status = 'confirmed'` | the scheduler's "confirmed bookings that have ended" lookup, every minute |

The two `confirmed` indexes are partial: bookings pile up as `completed`/`cancelled` history, but only
the few confirmed ones are ever looked up this way, so the indexes stay tiny. (Measured on 300,000
bookings: each is about 40 kB, and those lookups dropped from ~20 ms full-table scans to ~0.06 ms.)

`customers` has no secondary index and `inventory_items` has none besides `name`: both stay small and
are read whole, so Postgres would scan them rather than use an index. Revisit if that changes.

Not indexed on purpose: `bookings.start_at` and `end_at` on their own. They were indexed for a
time-window overlap query that no longer exists, and nothing uses them.

List the indexes in a running database:

```sql
SELECT tablename, indexname, indexdef FROM pg_indexes WHERE schemaname = 'public' ORDER BY 1, 2;
```

## Performance notes

- The item page shows the latest 100 bookings (a note appears when older ones are left out); bookings
  only ever accumulate, so an unbounded list would grow forever.
- Per-customer active units are summed by the database (one query for the limit check, one grouped
  query for the whole dropdown) rather than loaded into Python or joined across all booking history.
- The Postgres connection pool defaults to 5 connections. Raise it through the URL when serving more
  concurrent requests, e.g. `DATABASE_URL=postgres://…/book_inventory?maxsize=20`.
- `GET /api/v1/items`, `/customers` and `/bookings` return every row (no pagination yet), which is fine
  at this size.
