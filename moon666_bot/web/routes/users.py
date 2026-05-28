from decimal import Decimal
import csv
import io

from fastapi import APIRouter, Request, Depends, Query, Form
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from pathlib import Path

from shared.database import get_session
from shared.models import User, Referral, Transaction, TransactionType, Withdrawal
from web.auth import get_current_admin
from web.notifications import send_telegram_notification

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


@router.get("/users", response_class=HTMLResponse)
async def users_page(
    request: Request,
    search: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
    _: bool = Depends(get_current_admin),
):
    query = (
        select(User, func.count(Referral.id).label("ref_count"))
        .outerjoin(Referral, Referral.referrer_id == User.id)
        .group_by(User.id)
        .order_by(func.count(Referral.id).desc())
    )
    if search:
        query = query.where(
            or_(
                User.username.ilike(f"%{search}%"),
                User.full_name.ilike(f"%{search}%"),
            )
        )
    result = await session.execute(query)
    users = result.all()
    return templates.TemplateResponse("users.html", {
        "request": request,
        "active": "users",
        "users": users,
        "search": search or "",
    })


@router.get("/users/export.csv")  # Must be BEFORE /users/{user_id}
async def export_users_csv(
    session: AsyncSession = Depends(get_session),
    _: bool = Depends(get_current_admin),
):
    result = await session.execute(
        select(User, func.count(Referral.id).label("ref_count"))
        .outerjoin(Referral, Referral.referrer_id == User.id)
        .group_by(User.id)
        .order_by(User.joined_at.desc())
    )
    rows = result.all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "username", "full_name", "balance_usdt", "ref_count",
                     "joined_at", "channel_joined_at", "is_banned"])
    for user, ref_count in rows:
        writer.writerow([
            user.id, user.username or "", user.full_name or "",
            str(user.balance_usdt), ref_count,
            user.joined_at.isoformat() if user.joined_at else "",
            user.channel_joined_at.isoformat() if user.channel_joined_at else "",
            str(user.is_banned),
        ])
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=users.csv"},
    )


@router.get("/users/{user_id}", response_class=HTMLResponse)
async def user_detail_page(
    user_id: int,
    request: Request,
    session: AsyncSession = Depends(get_session),
    _: bool = Depends(get_current_admin),
):
    user = await session.get(User, user_id)
    if not user:
        return RedirectResponse(url="/users", status_code=302)

    refs_result = await session.execute(
        select(Referral, User)
        .join(User, User.id == Referral.referred_id)
        .where(Referral.referrer_id == user_id)
        .order_by(Referral.created_at.desc())
    )
    referrals = refs_result.all()

    txs_result = await session.execute(
        select(Transaction)
        .where(Transaction.user_id == user_id)
        .order_by(Transaction.created_at.desc())
        .limit(50)
    )
    transactions = txs_result.scalars().all()

    wds_result = await session.execute(
        select(Withdrawal)
        .where(Withdrawal.user_id == user_id)
        .order_by(Withdrawal.created_at.desc())
    )
    withdrawals = wds_result.scalars().all()

    earned_res = await session.execute(
        select(func.sum(Transaction.amount_usdt)).where(
            Transaction.user_id == user_id,
            Transaction.type.in_([
                TransactionType.referral_join,
                TransactionType.referral_reaction,
                TransactionType.referral_retention,
            ])
        )
    )
    total_earned = earned_res.scalar() or Decimal("0.00")

    return templates.TemplateResponse("user_detail.html", {
        "request": request,
        "active": "users",
        "user": user,
        "referrals": referrals,
        "transactions": transactions,
        "withdrawals": withdrawals,
        "total_earned": total_earned,
    })


@router.post("/users/{user_id}/ban")
async def ban_user(
    user_id: int,
    session: AsyncSession = Depends(get_session),
    _: bool = Depends(get_current_admin),
):
    user = await session.get(User, user_id)
    if user:
        user.is_banned = True
        await session.commit()
    return RedirectResponse(url=f"/users/{user_id}", status_code=302)


@router.post("/users/{user_id}/unban")
async def unban_user(
    user_id: int,
    session: AsyncSession = Depends(get_session),
    _: bool = Depends(get_current_admin),
):
    user = await session.get(User, user_id)
    if user:
        user.is_banned = False
        await session.commit()
    return RedirectResponse(url=f"/users/{user_id}", status_code=302)


@router.post("/users/{user_id}/adjust")
async def adjust_balance(
    user_id: int,
    amount: Decimal = Form(...),
    session: AsyncSession = Depends(get_session),
    _: bool = Depends(get_current_admin),
):
    user = await session.get(User, user_id)
    if user:
        new_balance = user.balance_usdt + amount
        if new_balance < Decimal("0.00"):
            # Refuse adjustment that would make balance negative
            return RedirectResponse(url=f"/users/{user_id}?error=negative_balance", status_code=302)
        user.balance_usdt = new_balance
        session.add(Transaction(
            user_id=user_id,
            amount_usdt=amount,
            type=TransactionType.manual_adjustment,
        ))
        await session.commit()
    return RedirectResponse(url=f"/users/{user_id}", status_code=302)


@router.post("/users/{user_id}/message")
async def send_message_to_user(
    user_id: int,
    text: str = Form(...),
    _: bool = Depends(get_current_admin),
):
    await send_telegram_notification(user_id, text)
    return RedirectResponse(url=f"/users/{user_id}", status_code=302)
