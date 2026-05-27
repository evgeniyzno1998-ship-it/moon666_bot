from datetime import datetime, timezone
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pathlib import Path

from shared.database import get_session
from shared.models import User, Withdrawal, WithdrawalStatus
from web.auth import get_current_admin
from web.notifications import send_telegram_notification

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


@router.get("/withdrawals", response_class=HTMLResponse)
async def withdrawals_page(
    request: Request,
    session: AsyncSession = Depends(get_session),
    _: bool = Depends(get_current_admin),
):
    result = await session.execute(
        select(Withdrawal, User)
        .join(User, User.id == Withdrawal.user_id)
        .order_by(Withdrawal.created_at.desc())
    )
    withdrawals = result.all()
    return templates.TemplateResponse("withdrawals.html", {
        "request": request,
        "active": "withdrawals",
        "withdrawals": withdrawals,
    })


@router.post("/withdrawals/{withdrawal_id}/approve")
async def approve_withdrawal(
    withdrawal_id: int,
    session: AsyncSession = Depends(get_session),
    _: bool = Depends(get_current_admin),
):
    w = await session.get(Withdrawal, withdrawal_id)
    if w and w.status == WithdrawalStatus.pending:
        user = await session.get(User, w.user_id)
        w.status = WithdrawalStatus.approved
        w.processed_at = datetime.now(timezone.utc)
        user.balance_usdt -= w.amount_usdt
        await session.commit()
        await send_telegram_notification(
            w.user_id,
            f"✅ Твоя заявка на вывод <b>{w.amount_usdt:.2f} USDT</b> одобрена!\n"
            f"Средства отправлены на кошелёк <code>{w.wallet_address}</code>.",
        )
    return RedirectResponse(url="/withdrawals", status_code=302)


@router.post("/withdrawals/{withdrawal_id}/reject")
async def reject_withdrawal(
    withdrawal_id: int,
    session: AsyncSession = Depends(get_session),
    _: bool = Depends(get_current_admin),
):
    w = await session.get(Withdrawal, withdrawal_id)
    if w and w.status == WithdrawalStatus.pending:
        w.status = WithdrawalStatus.rejected
        w.processed_at = datetime.now(timezone.utc)
        await session.commit()
        await send_telegram_notification(
            w.user_id,
            f"❌ Твоя заявка на вывод <b>{w.amount_usdt:.2f} USDT</b> отклонена.\n"
            f"Обратись в поддержку если считаешь это ошибкой.",
        )
    return RedirectResponse(url="/withdrawals", status_code=302)
