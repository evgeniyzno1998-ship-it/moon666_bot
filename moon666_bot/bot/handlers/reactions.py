import logging

from aiogram import Router
from aiogram.types import MessageReactionUpdated
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models import ChannelReaction, Referral
from shared.config import settings
from bot.services.referral import award_reaction_bonus

logger = logging.getLogger(__name__)
router = Router()


@router.message_reaction()
async def on_channel_reaction(event: MessageReactionUpdated, session: AsyncSession):
    # Only reactions in our channel
    if event.chat.id != settings.channel_id:
        return

    user_id = event.user.id if event.user else None
    if not user_id:
        return

    # One reaction bonus per user across ALL posts — UniqueConstraint on user_id enforces this.
    # First reaction triggers deduplication; subsequent reactions are rejected by the DB constraint.
    reaction = ChannelReaction(user_id=user_id, post_id=event.message_id)
    session.add(reaction)
    try:
        await session.commit()  # always persist deduplication record
    except IntegrityError:
        await session.rollback()
        return  # concurrent duplicate, safe to ignore

    # Find referral record and credit bonus to referrer
    ref_result = await session.execute(
        select(Referral).where(Referral.referred_id == user_id)
    )
    ref = ref_result.scalar_one_or_none()
    if ref:
        await award_reaction_bonus(session, ref)
        try:
            await event.bot.send_message(
                ref.referrer_id,
                f"⚡ Твой реферал поставил реакцию на пост!\n"
                f"💰 +{settings.bonus_reaction} USDT начислено.",
            )
        except Exception as e:
            logger.warning("Failed to notify referrer %s: %s", ref.referrer_id, e)
