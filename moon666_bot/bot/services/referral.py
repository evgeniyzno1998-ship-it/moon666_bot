from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from shared.models import Referral, Transaction, TransactionType, User
from shared.config import settings


async def _credit(
    session: AsyncSession,
    referral: Referral,
    amount: Decimal,
    tx_type: TransactionType,
) -> None:
    referrer = await session.get(User, referral.referrer_id)
    referrer.balance_usdt += amount
    session.add(
        Transaction(
            user_id=referral.referrer_id,
            amount_usdt=amount,
            type=tx_type,
            related_user_id=referral.referred_id,
        )
    )
    await session.commit()


async def award_join_bonus(session: AsyncSession, referral: Referral) -> None:
    if referral.join_bonus_paid:
        return
    await _credit(session, referral, settings.bonus_join, TransactionType.referral_join)
    referral.join_bonus_paid = True
    await session.commit()


async def award_reaction_bonus(session: AsyncSession, referral: Referral) -> None:
    if referral.reaction_bonus_paid:
        return
    await _credit(session, referral, settings.bonus_reaction, TransactionType.referral_reaction)
    referral.reaction_bonus_paid = True
    await session.commit()


async def award_retention_bonus(session: AsyncSession, referral: Referral) -> None:
    if referral.retention_bonus_paid:
        return
    await _credit(session, referral, settings.bonus_retention, TransactionType.referral_retention)
    referral.retention_bonus_paid = True
    await session.commit()
