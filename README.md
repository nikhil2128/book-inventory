# book-inventory

Manage a bookable inventory (rooms, equipment, vehicles — anything with a fixed number of units)
through a REST API and a simple server-rendered web UI.

**Stack:** FastAPI · Tortoise ORM · PostgreSQL · Pydantic v2 · Jinja2 · Pytest · Docker

**What it does**

- Keeps a stock of items, each with a number of units and an optional expiration date.
- Lets customers book units of an item; stock goes down on booking and comes back on cancellation
  or when the booking ends.
- Limits each customer to 2 active units at a time.
- Seeds itself with sample items and customers on first start.

**Docs:** [architecture.md](architecture.md) has diagrams of the components, data model, booking
lifecycle, background jobs, indexes and deployment.

## Quick start (Docker)

```bash
cp .env.example .env        # optional; defaults work without it
docker compose up --build
```

- Web UI: http://localhost:8000
- API docs (Swagger): http://localhost:8000/docs
- Health check: http://localhost:8000/api/v1/health

On first start the app creates the database schema and loads the seed data
(see [Migrations and seed data](#migrations-and-seed-data)). Source under `src/` is bind-mounted and
uvicorn runs with `--reload`, so code changes apply immediately.

```bash
make test        # run the tests in the container (= docker compose run --rm --no-deps app pytest)
```

## Local development

Run the app on your machine (for debugging, IDE tooling, or running the tests without rebuilding an
image). Postgres still runs in Docker, so you need both **Docker** and **Python 3.12+**.

1. **Create your `.env`.** Do this first: Docker Compose and the app both read it.

   ```bash
   cp .env.example .env
   ```

2. **Start Postgres** (only the database, not the app container).

   ```bash
   docker compose up -d db
   ```

3. **Create a virtualenv and install the app with its dev tools.**

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -e ".[dev]"
   ```

4. **Run the app.** It applies the migrations on startup, so there is nothing else to set up.

   ```bash
   uvicorn book_inventory.main:app --reload
   ```

   Open http://localhost:8000 (web UI) or http://localhost:8000/docs (API docs). `--reload` restarts
   the server when you edit code.

5. **Run the tests and linter** (in another terminal, with the virtualenv active).

   ```bash
   pytest
   ruff check src tests && ruff format --check src tests
   ```

   Tests use an in-memory SQLite database, so they need no running Postgres. Point them at another
   database with `TEST_DATABASE_URL`.

When you are done: `docker compose stop db` stops the database and keeps its data. To wipe the data
and start fresh (the next app start recreates it and re-imports the seed data), run
`docker compose down -v`.

### Troubleshooting

| Symptom | Cause and fix |
| --- | --- |
| `role "postgres" does not exist`, or the app cannot log in | Another Postgres on your machine is already using port 5432 and is answering instead of the container. Pick a free port: set `POSTGRES_PORT=5433` and change the port in `DATABASE_URL` to `5433` in `.env`, then run `docker compose up -d db` again. |
| `Address already in use` on startup | Something else is on port 8000. Run on another port: `uvicorn book_inventory.main:app --reload --port 8001`. |
| `bad interpreter` or `uvicorn: command not found` | The virtualenv is stale (for example the project folder was moved). Recreate it: `rm -rf .venv`, then repeat step 3. Or run `python3 -m uvicorn ...` instead. |
| `ModuleNotFoundError: No module named 'book_inventory'` | The `python` you ran is not the virtualenv's (a shell alias or PATH entry can shadow it even after `source .venv/bin/activate`). Check with `which python`, then use `python3` or `.venv/bin/python` instead. |
| `connection refused` | The database is not up yet. Check `docker compose ps` and wait until `db` is `healthy`. |

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

## API

Interactive docs are at `/docs`. Endpoints, all under `/api/v1`:

| Method | Path | Description |
| --- | --- | --- |
| GET | `/items` | List items (`?active_only=true`) |
| POST | `/items` | Create item (`name`, `remaining_quantity`, optional `description`, `expiration_date`) |
| GET / PATCH / DELETE | `/items/{id}` | Read, update, or delete an item (delete is refused when it has bookings) |
| GET | `/customers`, `/customers/{id}` | List / read customers |
| GET | `/bookings` | List bookings (`?item_id=`) |
| POST | `/bookings` | Create a booking for an `item_id` and `customer_id` |
| GET | `/bookings/{id}` | Read booking |
| POST | `/bookings/{id}/cancel` | Cancel booking |

Times without a timezone are treated as UTC.

### Booking rules

- **Statuses:** `confirmed`, `cancelled`, `completed`.
- **Stock:** confirming a booking subtracts its `quantity` from the item's `remaining_quantity`;
  cancelling it, or its `end_at` passing, adds the units back. A booking's dates do not affect whether
  it can be made.
- **Customer limit:** a customer can hold at most 2 units (`MAX_ACTIVE_UNITS_PER_CUSTOMER`) in
  `confirmed` bookings at once.
- **Completion:** a background job completes bookings once `end_at` has passed. A completed booking
  can no longer be cancelled.
- **Expiry:** an item's `expiration_date` is the last day it can be booked; after that a background
  job deactivates it. To bring an expired item back, move its `expiration_date` forward.

| Error | When |
| --- | --- |
| `404` | creating a booking for an unknown customer, or an item that is unknown, inactive or expired |
| `409` | not enough units remain, the customer is at their limit, a duplicate item name, deleting an item that has bookings, or cancelling a booking that has ended |

How these rules are enforced (transactions, locking, the background jobs) is in
[architecture.md](architecture.md).

## Migrations and seed data

The schema is managed with [Aerich](https://github.com/tortoise/aerich) migrations in
`src/book_inventory/migrations/models/`. The app applies pending ones on startup
(`RUN_MIGRATIONS=true`), so a fresh database gets the schema and the seed data:

| Migration | What it does |
| --- | --- |
| `0_…_init` | creates `inventory_items`, `customers` and `bookings` |
| `1_…_import_inventory_and_customers` | imports `migrations/data/inventory.csv` and `members.csv` as items and customers |
| `2_…_bookings_indexes` | the booking indexes (see [Indexes](architecture.md#indexes)) |

The CSVs are a snapshot read once by migration 1; changing them later does not re-import. A repeated
title such as "London" is imported as "London (2)", because item names are unique.

Common commands (run from the repo root, with `DATABASE_URL` set):

```bash
python3 -m aerich upgrade                   # apply pending migrations
python3 -m aerich migrate --name add_thing  # generate a migration after changing a model
python3 -m aerich downgrade -v 1 --yes      # roll back migration 1 (the data import) and everything after it
```

## Project layout

```
src/book_inventory/
├── main.py            # app factory and startup (migrations, database, scheduler)
├── config.py          # settings (env vars / .env)
├── db.py              # Tortoise ORM config + migration runner
├── models/            # InventoryItem, Customer, Booking
├── schemas/           # Pydantic request/response models
├── services/          # business rules: booking, cancellation, completion, item expiry
├── scheduler.py       # background jobs
├── api/               # REST API, mounted at /api/v1
├── web/               # HTML routes
├── templates/ static/ # Jinja2 pages, CSS, JS
└── migrations/        # Aerich migrations and the seed CSVs
tests/                 # pytest suite (API + web)
```
