"""Server-rendered HTML pages (Jinja2)."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from tortoise.exceptions import IntegrityError

from book_inventory.models import BookingStatus, InventoryItem
from book_inventory.schemas import BookingCreate, ItemCreate
from book_inventory.services.bookings import BookingError, create_booking

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=TEMPLATES_DIR)

router = APIRouter(include_in_schema=False)


def _error_messages(exc: ValidationError) -> list[str]:
    return [f"{'.'.join(map(str, e['loc'])) or 'form'}: {e['msg']}" for e in exc.errors()]


async def _render_index(
    request: Request,
    *,
    errors: list[str] | None = None,
    form: dict[str, Any] | None = None,
    status_code: int = status.HTTP_200_OK,
) -> HTMLResponse:
    items = await InventoryItem.all()
    return templates.TemplateResponse(
        request,
        "items/list.html",
        {"items": items, "errors": errors or [], "form": form or {}},
        status_code=status_code,
    )


async def _render_detail(
    request: Request,
    item: InventoryItem,
    *,
    errors: list[str] | None = None,
    form: dict[str, Any] | None = None,
    status_code: int = status.HTTP_200_OK,
) -> HTMLResponse:
    bookings = await item.bookings.filter(
        status=BookingStatus.CONFIRMED, end_at__gt=datetime.now(UTC)
    )
    return templates.TemplateResponse(
        request,
        "items/detail.html",
        {"item": item, "bookings": bookings, "errors": errors or [], "form": form or {}},
        status_code=status_code,
    )


@router.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return await _render_index(request)


@router.post("/items", response_class=HTMLResponse)
async def create_item(
    request: Request,
    name: Annotated[str, Form()],
    quantity: Annotated[int, Form()],
    description: Annotated[str, Form()] = "",
) -> Response:
    form = {"name": name, "quantity": quantity, "description": description}
    try:
        payload = ItemCreate(**form)
        await InventoryItem.create(**payload.model_dump())
    except ValidationError as exc:
        return await _render_index(
            request,
            errors=_error_messages(exc),
            form=form,
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )
    except IntegrityError:
        return await _render_index(
            request,
            errors=["An item with this name already exists"],
            form=form,
            status_code=status.HTTP_409_CONFLICT,
        )
    return RedirectResponse(request.url_for("index"), status_code=status.HTTP_303_SEE_OTHER)


@router.get("/items/{item_id}", response_class=HTMLResponse)
async def item_detail(request: Request, item_id: int) -> HTMLResponse:
    item = await InventoryItem.get_or_none(id=item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item not found")
    return await _render_detail(request, item)


@router.post("/items/{item_id}/bookings", response_class=HTMLResponse)
async def book_item(
    request: Request,
    item_id: int,
    customer_name: Annotated[str, Form()],
    customer_email: Annotated[str, Form()],
    start_at: Annotated[str, Form()],
    end_at: Annotated[str, Form()],
    quantity: Annotated[int, Form()] = 1,
) -> Response:
    item = await InventoryItem.get_or_none(id=item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item not found")

    form = {
        "customer_name": customer_name,
        "customer_email": customer_email,
        "start_at": start_at,
        "end_at": end_at,
        "quantity": quantity,
    }
    try:
        await create_booking(BookingCreate(item_id=item_id, **form))
    except ValidationError as exc:
        return await _render_detail(
            request,
            item,
            errors=_error_messages(exc),
            form=form,
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )
    except BookingError as exc:
        return await _render_detail(
            request, item, errors=[str(exc)], form=form, status_code=status.HTTP_409_CONFLICT
        )
    return RedirectResponse(
        request.url_for("item_detail", item_id=item_id), status_code=status.HTTP_303_SEE_OTHER
    )
