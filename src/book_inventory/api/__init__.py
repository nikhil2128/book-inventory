from fastapi import APIRouter

from book_inventory.api.routes import bookings, customers, health, items

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(items.router)
api_router.include_router(bookings.router)
api_router.include_router(customers.router)

__all__ = ["api_router"]
