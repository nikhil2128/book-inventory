.PHONY: up down logs test lint format shell

up:  ## Start app + Postgres
	docker compose up --build -d

down:  ## Stop containers
	docker compose down

logs:
	docker compose logs -f app

test:  ## Run tests inside the app container
	docker compose run --rm --no-deps app pytest

lint:
	docker compose run --rm --no-deps app ruff check src tests

format:
	docker compose run --rm --no-deps app ruff format src tests

shell:
	docker compose run --rm app bash
