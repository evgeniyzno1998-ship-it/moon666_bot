from decimal import Decimal
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from shared.models import Referral, Transaction, TransactionType, User, Campaign, CampaignBonusType
from shared.config import settings


async def _credit(
    session: AsyncSession,
    referral: Referral,
    amount: Decimal,
    tx_type: TransactionType,
) -> None:
    """Mutate referrer balance and insert Transaction. Does NOT commit — caller commits."""
    referrer = await session.get(User, referral.referrer_id)
    if referrer is None:
        raise ValueError(f"Referrer {referral.referrer_id} not found")
    referrer.balance_usdt += amount
    session.add(Transaction(
        user_id=referral.referrer_id,
        amount_usdt=amount,
        type=tx_type,
        related_user_id=referral.referred_id,
    ))


async def _get_active_campaign(
    session: AsyncSession,
    bonus_type: CampaignBonusType,
) -> Optional[Campaign]:
    """Return the first active campaign matching the given bonus type, or None."""
    now = datetime.now(timezone.utc)
    result = await session.execute(
        select(Campaign).where(
            Campaign.starts_at <= now,
            Campaign.ends_at >= now,
            or_(
                Campaign.applies_to == CampaignBonusType.all,
                Campaign.applies_to == bonus_type,
            )
        ).limit(1)
    )
    return result.scalar_one_or_none()


async def award_join_bonus(
    session: AsyncSession,
    referral: Referral,
    bot=None,
) -> None:
    if referral.join_bonus_paid:
        return
    campaign = await _get_active_campaign(session, CampaignBonusType.join)
    multiplier = campaign.bonus_multiplier if campaign else Decimal("1")
    amount = settings.bonus_join * multiplier
    await _credit(session, referral, amount, TransactionType.referral_join)
    referral.join_bonus_paid = True
    await session.commit()
    if bot:
        from bot.services.achievements import check_and_award_achievements
        await check_and_award_achievements(session, referral.referrer_id, bot)


async def award_reaction_bonus(session: AsyncSession, referral: Referral) -> None:
    if referral.reaction_bonus_paid:
        return
    campaign = await _get_active_campaign(session, CampaignBonusType.reaction)
    multiplier = campaign.bonus_multiplier if campaign else Decimal("1")
    amount = settings.bonus_reaction * multiplier
    await _credit(session, referral, amount, TransactionType.referral_reaction)
    referral.reaction_bonus_paid = True
    await session.commit()


async def award_retention_bonus(session: AsyncSession, referral: Referral) -> None:
    if referral.retention_bonus_paid:
        return
    await _credit(session, referral, settings.bonus_retention, TransactionType.referral_retention)
    referral.retention_bonus_paid = True
    await session.commit()
