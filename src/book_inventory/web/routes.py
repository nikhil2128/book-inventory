"""Server-rendered HTML pages (Jinja2)."""

from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from tortoise.exceptions import IntegrityError

from book_inventory.models import Booking, Customer, InventoryItem
from book_inventory.schemas import BookingCreate, ItemCreate
from book_inventory.services.bookings import (
    BookingError,
    active_units_by_customer,
    cancel_booking,
    create_booking,
)

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=TEMPLATES_DIR)

router = APIRouter(include_in_schema=False)

# Bookings only ever accumulate, so the item page shows just the most recent ones.
MAX_BOOKINGS_SHOWN = 100

# Confirmation messages, selected by a fixed key in the redirect URL (`?notice=booked`) so the
# page never echoes arbitrary text from the query string.
NOTICES = {
    "booked": "Booking confirmed.",
    "cancelled": "Booking cancelled.",
    "item_added": "Item added.",
}


def _error_messages(exc: ValidationError) -> list[str]:
    return [f"{'.'.join(map(str, e['loc'])) or 'form'}: {e['msg']}" for e in exc.errors()]


async def _render_index(
    request: Request,
    *,
    errors: list[str] | None = None,
    form: dict[str, Any] | None = None,
    notice: str | None = None,
    status_code: int = status.HTTP_200_OK,
) -> HTMLResponse:
    items = await InventoryItem.all()
    return templates.TemplateResponse(
        request,
        "items/list.html",
        {
            "items": items,
            "notice": NOTICES.get(notice or ""),
            "errors": errors or [],
            "form": form or {},
        },
        status_code=status_code,
    )


async def _render_detail(
    request: Request,
    item: InventoryItem,
    *,
    errors: list[str] | None = None,
    form: dict[str, Any] | None = None,
    notice: str | None = None,
    status_code: int = status.HTTP_200_OK,
) -> HTMLResponse:
    # Fetch one extra row to know whether older bookings were left out, without a COUNT query.
    bookings = list(
        await item.bookings.all()
        .order_by("-start_at")
        .limit(MAX_BOOKINGS_SHOWN + 1)
        .prefetch_related("customer")
    )
    bookings_truncated = len(bookings) > MAX_BOOKINGS_SHOWN
    bookings = bookings[:MAX_BOOKINGS_SHOWN]
    # Active = units in confirmed bookings (not cancelled, not completed); the same quantity the
    # per-customer limit is checked against. Shown next to each customer.
    customers = await Customer.all()
    active = await active_units_by_customer()
    for customer in customers:
        customer.active_bookings = active.get(customer.id, 0)
    return templates.TemplateResponse(
        request,
        "items/detail.html",
        {
            "item": item,
            "bookings": bookings,
            "bookings_note": f"Showing the latest {MAX_BOOKINGS_SHOWN} bookings."
            if bookings_truncated
            else None,
            "customers": customers,
            "notice": NOTICES.get(notice or ""),
            "errors": errors or [],
            "form": form or {},
        },
        status_code=status_code,
    )


def _redirect_to_item(request: Request, item_id: int, *, notice: str) -> RedirectResponse:
    url = request.url_for("item_detail", item_id=item_id).include_query_params(notice=notice)
    return RedirectResponse(url, status_code=status.HTTP_303_SEE_OTHER)


@router.get("/", response_class=HTMLResponse)
async def index(request: Request, notice: str | None = None) -> HTMLResponse:
    return await _render_index(request, notice=notice)


@router.post("/items", response_class=HTMLResponse)
async def create_item_form(
    request: Request,
    name: Annotated[str, Form()],
    remaining_quantity: Annotated[int, Form()],
    description: Annotated[str, Form()] = "",
) -> Response:
    form = {"name": name, "remaining_quantity": remaining_quantity, "description": description}
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
    url = request.url_for("index").include_query_params(notice="item_added")
    return RedirectResponse(url, status_code=status.HTTP_303_SEE_OTHER)


@router.get("/items/{item_id}", response_class=HTMLResponse)
async def item_detail(request: Request, item_id: int, notice: str | None = None) -> HTMLResponse:
    item = await InventoryItem.get_or_none(id=item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item not found")
    return await _render_detail(request, item, notice=notice)


@router.post("/items/{item_id}/bookings", response_class=HTMLResponse)
async def book_item(
    request: Request,
    item_id: int,
    customer_id: Annotated[int, Form()],
    start_at: Annotated[str, Form()],
    end_at: Annotated[str, Form()],
    quantity: Annotated[int, Form()] = 1,
) -> Response:
    item = await InventoryItem.get_or_none(id=item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item not found")

    form = {
        "customer_id": customer_id,
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
    return _redirect_to_item(request, item_id, notice="booked")


@router.post("/items/{item_id}/bookings/{booking_id}/cancel", response_class=HTMLResponse)
async def cancel_item_booking(request: Request, item_id: int, booking_id: int) -> Response:
    item = await InventoryItem.get_or_none(id=item_id)
    booking = await Booking.get_or_none(id=booking_id, item_id=item_id)
    if item is None or booking is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Booking not found")

    try:
        await cancel_booking(booking)
    except BookingError as exc:
        return await _render_detail(
            request, item, errors=[str(exc)], status_code=status.HTTP_409_CONFLICT
        )
    return _redirect_to_item(request, item_id, notice="cancelled")
