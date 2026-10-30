"""In-process periodic jobs, started and stopped with the app (see `main.lifespan`)."""

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from book_inventory.services.bookings import complete_expired_bookings
from book_inventory.services.items import deactivate_expired_items

JOBS: dict[str, Callable[[], Awaitable[int]]] = {
    "complete-bookings": complete_expired_bookings,
    "deactivate-expired-items": deactivate_expired_items,
}

# Shares uvicorn's handler and format, so job output shows up with the server log.
logger = logging.getLogger("uvicorn.error")


async def run_periodically(
    job: Callable[[], Awaitable[int]], interval_seconds: float, *, name: str
) -> None:
    """Call `job` now and then every `interval_seconds`, until cancelled.

    A failing run is logged and retried on the next tick rather than stopping the loop.
    """
    while True:
        try:
            if count := await job():
                logger.info("%s: processed %d row(s)", name, count)
        except Exception:
            logger.exception("%s: run failed", name)
        await asyncio.sleep(interval_seconds)


@asynccontextmanager
async def scheduler(interval_seconds: float) -> AsyncIterator[None]:
    """Run the background jobs for the duration of the `async with` block."""
    tasks = [
        asyncio.create_task(run_periodically(job, interval_seconds, name=name), name=name)
        for name, job in JOBS.items()
    ]
    try:
        yield
    finally:
        for task in tasks:
            task.cancel()
        for task in tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await task
