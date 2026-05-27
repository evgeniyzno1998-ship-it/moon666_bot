from datetime import datetime, timedelta, timezone
from decimal import Decimal
from fastapi import APIRouter, Request, Depends, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from pathlib import Path

from shared.database import get_session
from shared.models import User, Transaction, Withdrawal, WithdrawalStatus
from web.auth import get_current_admin

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


def get_date_range(period: str, date_from: str | None, date_to: str | None):
    now = datetime.now(timezone.utc)
    if period == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "7d":
        start = now - timedelta(days=7)
    elif period == "30d":
        start = now - timedelta(days=30)
    elif period == "90d":
        start = now - timedelta(days=90)
    elif period == "custom" and date_from:
        start = datetime.fromisoformat(date_from).replace(tzinfo=timezone.utc)
        end = datetime.fromisoformat(date_to).replace(tzinfo=timezone.utc) if date_to else now
        return start, end
    else:
        start = now - timedelta(days=30)
    return start, now


@router.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    period: str = Query("30d"),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
    _: bool = Depends(get_current_admin),
):
    start, end = get_date_range(period, date_from, date_to)

    total_users = (await session.execute(select(func.count(User.id)))).scalar() or 0
    total_accrued = (await session.execute(
        select(func.sum(Transaction.amount_usdt)).where(
            Transaction.created_at.between(start, end)
        )
    )).scalar() or Decimal("0.00")
    total_paid = (await session.execute(
        select(func.sum(Withdrawal.amount_usdt)).where(
            Withdrawal.status == WithdrawalStatus.approved,
            Withdrawal.processed_at.between(start, end),
        )
    )).scalar() or Decimal("0.00")
    pending_count = (await session.execute(
        select(func.count(Withdrawal.id)).where(Withdrawal.status == WithdrawalStatus.pending)
    )).scalar() or 0

    # Last 5 pending withdrawal requests
    recent_withdrawals_result = await session.execute(
        select(Withdrawal, User)
        .join(User, User.id == Withdrawal.user_id)
        .where(Withdrawal.status == WithdrawalStatus.pending)
        .order_by(Withdrawal.created_at.desc())
        .limit(5)
    )
    recent_withdrawals = recent_withdrawals_result.all()

    # Subscriber growth by week (last 8 weeks)
    growth = []
    for i in range(7, -1, -1):
        week_start = datetime.now(timezone.utc) - timedelta(weeks=i + 1)
        week_end = datetime.now(timezone.utc) - timedelta(weeks=i)
        cnt = (await session.execute(
            select(func.count(User.id)).where(User.joined_at.between(week_start, week_end))
        )).scalar() or 0
        growth.append({"week": f"-{i + 1}w", "count": cnt})

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "active": "dashboard",
        "total_users": total_users,
        "total_accrued": total_accrued,
        "total_paid": total_paid,
        "pending_count": pending_count,
        "recent_withdrawals": recent_withdrawals,
        "growth": growth,
        "period": period,
        "date_from": date_from,
        "date_to": date_to,
    })
