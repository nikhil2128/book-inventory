from fastapi import APIRouter

from book_inventory.api.deps import CustomerDep
from book_inventory.models import Customer
from book_inventory.schemas import CustomerRead

router = APIRouter(prefix="/customers", tags=["customers"])


@router.get("", response_model=list[CustomerRead])
async def list_customers() -> list[Customer]:
    return await Customer.all()


@router.get("/{customer_id}", response_model=CustomerRead)
async def get_customer(customer: CustomerDep) -> Customer:
    return customer
