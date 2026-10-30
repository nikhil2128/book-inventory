# syntax=docker/dockerfile:1

FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
RUN useradd --create-home --uid 1000 appuser

COPY pyproject.toml README.md ./
COPY src ./src


# Development image: editable install + test tooling; source is bind-mounted by compose.
FROM base AS dev
RUN pip install -e ".[dev]"
COPY tests ./tests
USER appuser
EXPOSE 8000
CMD ["uvicorn", "book_inventory.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--reload-dir", "src"]


# Production image: regular install, no dev dependencies.
FROM base AS prod
RUN pip install .
USER appuser
EXPOSE 8000
CMD ["uvicorn", "book_inventory.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
