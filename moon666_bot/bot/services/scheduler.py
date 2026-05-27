import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from shared.database import async_session_maker
from shared.models import User, Referral, Withdrawal, WithdrawalStatus
from shared.config import settings
from bot.services.referral import award_retention_bonus

logger = logging.getLogger(__name__)


async def check_retention(bot) -> None:
    """Check users who have been in channel for 30 days."""
    async with async_session_maker() as session:
        threshold = datetime.now(timezone.utc) - timedelta(days=30)

        result = await session.execute(
            select(Referral, User)
            .join(User, User.id == Referral.referred_id)
            .where(
                Referral.retention_bonus_paid == False,
                User.channel_joined_at != None,
                User.channel_joined_at <= threshold,
            )
        )
        rows = result.all()

        for ref, referred_user in rows:
            try:
                member = await bot.get_chat_member(settings.channel_id, referred_user.id)
                if member.status not in ("member", "administrator", "creator"):
                    continue
            except Exception as e:
                logger.warning("get_chat_member failed for user %s: %s", referred_user.id, e)
                continue

            await award_retention_bonus(session, ref)

            try:
                await bot.send_message(
                    ref.referrer_id,
                    f"🎯 Your referral has been in the channel for 30 days!\n"
                    f"💰 +{settings.bonus_retention} USDT added to your balance.",
                )
            except Exception:
                pass


async def send_daily_report(bot) -> None:
    """Send daily stats report to admin every morning."""
    async with async_session_maker() as session:
        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

        # New users today
        new_users_res = await session.execute(
            select(func.count()).select_from(User).where(User.joined_at >= today_start)
        )
        new_users = new_users_res.scalar() or 0

        # New referrals today
        new_refs_res = await session.execute(
            select(func.count()).select_from(Referral).where(
                Referral.created_at >= today_start
            )
        )
        new_refs = new_refs_res.scalar() or 0

        # Paid out today
        paid_res = await session.execute(
            select(func.sum(Withdrawal.amount_usdt)).where(
                Withdrawal.status == WithdrawalStatus.approved,
                Withdrawal.processed_at >= today_start,
            )
        )
        paid_today = paid_res.scalar() or 0

        # Pending withdrawals
        pending_res = await session.execute(
            select(func.count()).select_from(Withdrawal).where(
                Withdrawal.status == WithdrawalStatus.pending
            )
        )
        pending = pending_res.scalar() or 0

        # Total users ever
        total_res = await session.execute(
            select(func.count()).select_from(User)
        )
        total_users = total_res.scalar() or 0

        # Total balance outstanding (owed to users)
        balance_res = await session.execute(
            select(func.sum(User.balance_usdt))
        )
        total_balance = balance_res.scalar() or 0

    date_str = today_start.strftime("%d.%m.%Y")
    try:
        await bot.send_message(
            settings.admin_tg_id,
            f"📊 <b>Daily Report — {date_str}</b>\n\n"
            f"👥 New users today: <b>{new_users}</b>\n"
            f"🔗 New referrals today: <b>{new_refs}</b>\n"
            f"💸 Paid out today: <b>${paid_today:.2f}</b>\n\n"
            f"⏳ Pending withdrawals: <b>{pending}</b>\n"
            f"💰 Total balance owed: <b>${total_balance:.2f}</b>\n"
            f"📈 Total users: <b>{total_users}</b>",
            parse_mode="HTML",
        )
        logger.info("Daily report sent")
    except Exception as e:
        logger.error("Failed to send daily report: %s", e)


def start_scheduler(bot):
    """Start APScheduler jobs."""
    scheduler = AsyncIOScheduler()

    # Retention check — every hour
    scheduler.add_job(
        check_retention,
        trigger="interval",
        hours=1,
        args=[bot],
        id="retention_check",
    )

    # Daily report — every day at 09:00 UTC
    scheduler.add_job(
        send_daily_report,
        trigger="cron",
        hour=9,
        minute=0,
        args=[bot],
        id="daily_report",
    )

    scheduler.start()
    return scheduler
