from datetime import datetime, timedelta, timezone
from decimal import Decimal
from fastapi import APIRouter, Request, Depends, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from pathlib import Path

from shared.database import get_session
from shared.models import User, Referral, Transaction, TransactionType
from web.auth import get_current_admin
from web.routes.dashboard import get_date_range

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


@router.get("/analytics", response_class=HTMLResponse)
async def analytics(
    request: Request,
    period: str = Query("30d"),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
    _: bool = Depends(get_current_admin),
):
    start, end = get_date_range(period, date_from, date_to)

    # Retention funnel
    total_joined = (await session.execute(
        select(func.count(User.id)).where(User.channel_joined_at.between(start, end))
    )).scalar() or 0

    now = datetime.now(timezone.utc)
    retention_funnel = []
    for days in [7, 30, 60]:
        threshold = now - timedelta(days=days)
        still_in = (await session.execute(
            select(func.count(User.id)).where(
                User.channel_joined_at <= threshold,
                User.channel_joined_at >= start,
            )
        )).scalar() or 0
        pct = round(still_in / total_joined * 100) if total_joined > 0 else 0
        retention_funnel.append({"days": days, "count": still_in, "pct": pct})

    # Bonus breakdown by type
    bonus_breakdown = []
    for tx_type in TransactionType:
        total = (await session.execute(
            select(func.sum(Transaction.amount_usdt)).where(
                Transaction.type == tx_type,
                Transaction.created_at.between(start, end),
            )
        )).scalar() or Decimal("0.00")
        bonus_breakdown.append({"type": tx_type.value, "total": total})

    total_bonus = sum(b["total"] for b in bonus_breakdown) or Decimal("1.00")
    for b in bonus_breakdown:
        b["pct"] = round(float(b["total"] / total_bonus) * 100)

    # Cost per subscriber
    new_users = (await session.execute(
        select(func.count(User.id)).where(User.joined_at.between(start, end))
    )).scalar() or 1
    total_spent = sum(b["total"] for b in bonus_breakdown)
    cost_per_user = round(float(total_spent / new_users), 4) if new_users > 0 else 0.0

    # Top referrers
    top_result = await session.execute(
        select(User.username, User.full_name, func.count(Referral.id).label("cnt"))
        .join(Referral, Referral.referrer_id == User.id)
        .where(Referral.created_at.between(start, end))
        .group_by(User.id, User.username, User.full_name)
        .order_by(func.count(Referral.id).desc())
        .limit(10)
    )
    top_referrers = top_result.all()

    return templates.TemplateResponse("analytics.html", {
        "request": request,
        "active": "analytics",
        "total_joined": total_joined,
        "retention_funnel": retention_funnel,
        "bonus_breakdown": bonus_breakdown,
        "cost_per_user": cost_per_user,
        "top_referrers": top_referrers,
        "period": period,
        "date_from": date_from,
        "date_to": date_to,
    })
