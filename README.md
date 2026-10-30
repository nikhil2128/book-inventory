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
├── models/            # Tortoise models: InventoryItem, Booking
├── schemas/           # Pydantic request/response models
├── services/          # business logic (availability, booking, cancellation)
├── api/               # REST API, mounted at /api/v1
│   ├── deps.py
│   └── routes/        # health, items, bookings
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
| GET | `/api/v1/items/{id}/availability?start_at=&end_at=` | Units free in a time window |
| GET | `/api/v1/bookings` | List bookings (`?item_id=`) |
| POST | `/api/v1/bookings` | Create booking (409 if not enough units are free) |
| GET | `/api/v1/bookings/{id}` | Read booking |
| POST | `/api/v1/bookings/{id}/cancel` | Cancel booking |

Bookings cover the half-open interval `[start_at, end_at)`, so back-to-back bookings don't conflict.
Times without a timezone are treated as UTC.

## Database schema

On startup the app creates missing tables (`GENERATE_SCHEMAS=true`). That's fine for development, but
before deploying anywhere persistent, add migrations (e.g. [Aerich](https://github.com/tortoise/aerich))
and set `GENERATE_SCHEMAS=false`.
