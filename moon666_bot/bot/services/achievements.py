"""
Check and award achievement badges to a referrer.
Called from referral.award_join_bonus() after each confirmed join.
"""
import logging
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models import Referral, UserAchievement, AchievementType

logger = logging.getLogger(__name__)

# (min_referrals, achievement_type, notification_text)
_MILESTONES = [
    (
        1,
        AchievementType.first_referral,
        "🌱 <b>Achievement Unlocked: First Referral!</b>\n\n"
        "You invited your first person to the channel.\n"
        "Keep going — there's more USDT to earn! 🚀",
    ),
    (
        10,
        AchievementType.referrals_10,
        "🔥 <b>Achievement Unlocked: 10 Referrals!</b>\n\n"
        "You've invited 10 people. You're on fire!\n"
        "Next milestone: 25 referrals ⚡",
    ),
    (
        25,
        AchievementType.referrals_25,
        "⚡ <b>Achievement Unlocked: 25 Referrals!</b>\n\n"
        "25 people joined via your link. Seriously impressive!\n"
        "Next milestone: 100 referrals 💎",
    ),
    (
        100,
        AchievementType.referrals_100,
        "💎 <b>Achievement Unlocked: 100 Referrals!</b>\n\n"
        "100 people joined Moon666 via your link.\n"
        "You are a legend. 🏆",
    ),
]


async def check_and_award_achievements(
    session: AsyncSession,
    referrer_id: int,
    bot,
) -> None:
    """Check whether referrer has crossed any milestone and award unearned badges."""
    # Count referrals where the join bonus was paid (= confirmed referrals)
    total_res = await session.execute(
        select(func.count()).select_from(Referral).where(
            Referral.referrer_id == referrer_id,
            Referral.join_bonus_paid == True,
        )
    )
    total = total_res.scalar() or 0

    for threshold, ach_type, msg in _MILESTONES:
        if total < threshold:
            continue  # not reached yet

        existing = await session.execute(
            select(UserAchievement).where(
                UserAchievement.user_id == referrer_id,
                UserAchievement.achievement_type == ach_type,
            )
        )
        if existing.scalar_one_or_none():
            continue  # already awarded

        session.add(UserAchievement(user_id=referrer_id, achievement_type=ach_type))
        await session.commit()

        try:
            await bot.send_message(referrer_id, msg, parse_mode="HTML")
        except Exception as e:
            logger.warning("Could not send achievement notification to %s: %s", referrer_id, e)
