from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from tortoise.contrib.fastapi import RegisterTortoise

from book_inventory import __version__
from book_inventory.api import api_router
from book_inventory.config import Settings, get_settings
from book_inventory.db import get_tortoise_config
from book_inventory.web import web_router

STATIC_DIR = Path(__file__).resolve().parent / "static"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with RegisterTortoise(
            app,
            config=get_tortoise_config(settings.database_url),
            generate_schemas=settings.generate_schemas,
        ):
            yield

    app = FastAPI(
        title=settings.app_name, version=__version__, debug=settings.debug, lifespan=lifespan
    )
    app.include_router(api_router, prefix="/api/v1")
    app.include_router(web_router)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    return app


app = create_app()
