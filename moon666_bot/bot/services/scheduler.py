import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import async_session_maker
from shared.models import User, Referral
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
            # Check user is still in channel
            try:
                member = await bot.get_chat_member(settings.channel_id, referred_user.id)
                if member.status not in ("member", "administrator", "creator"):
                    continue
            except Exception as e:
                logger.warning("get_chat_member failed for user %s: %s", referred_user.id, e)
                continue

            await award_retention_bonus(session, ref)

            # Notify referrer
            try:
                await bot.send_message(
                    ref.referrer_id,
                    f"🎯 Твой реферал остался в канале 30 дней!\n"
                    f"💰 +{settings.bonus_retention} USDT начислено.",
                )
            except Exception:
                pass


def start_scheduler(bot):
    """Start APScheduler for retention check every hour."""
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        check_retention,
        trigger="interval",
        hours=1,
        args=[bot],
        id="retention_check",
    )
    scheduler.start()
    return scheduler
