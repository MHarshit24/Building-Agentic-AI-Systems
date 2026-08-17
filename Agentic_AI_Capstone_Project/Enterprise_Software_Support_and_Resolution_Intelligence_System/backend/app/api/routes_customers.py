"""
app/api/routes_customers.py

GET /customers — frontend integration pass. support_agent|admin (not
admin-only — agents need this routinely to start a new conversation).

Real gap this closes: POST /chat's ChatRequest.customer_id is a required
int, but nothing anywhere in the API surface ever let a client discover
what customer_id values exist — an agent starting a new chat had no way
to know what to type, which is exactly why sending a first message was
blocked with no clear feedback. Search is a simple case-insensitive
ILIKE on company_name; ~124 seeded customers (scripts/seed_synthetic_
data.py's NUM_CUSTOMERS + Part 2 starters) is small enough that a single
generously-sized page covers the whole table for a client-side picker,
while still supporting server-side search for future growth.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Customer
from app.db.session import get_db
from app.middleware.rate_limit import limiter
from app.middleware.rbac_check import require_support_or_admin

router = APIRouter(prefix="/customers", tags=["customers"])


class CustomerSummary(BaseModel):
    customer_id: int
    company_name: str
    subscription_tier: str | None = None
    account_status: str | None = None
    region: str | None = None


class CustomerListResponse(BaseModel):
    customers: list[CustomerSummary]
    total: int


@router.get("", response_model=CustomerListResponse)
@limiter.limit("60/minute")
async def list_customers(
    request: Request,
    search: str | None = Query(default=None, description="Case-insensitive substring match on company_name"),
    limit: int = Query(default=150, le=200, ge=1),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_support_or_admin),
) -> CustomerListResponse:
    stmt = select(Customer)
    count_stmt = select(func.count()).select_from(Customer)
    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(Customer.company_name.ilike(pattern))
        count_stmt = count_stmt.where(Customer.company_name.ilike(pattern))

    total = (await db.execute(count_stmt)).scalar_one()
    rows = (
        (await db.execute(stmt.order_by(Customer.company_name).limit(limit).offset(offset)))
        .scalars()
        .all()
    )

    return CustomerListResponse(
        customers=[
            CustomerSummary(
                customer_id=c.customer_id,
                company_name=c.company_name,
                subscription_tier=c.subscription_tier,
                account_status=c.account_status,
                region=c.region,
            )
            for c in rows
        ],
        total=total,
    )
