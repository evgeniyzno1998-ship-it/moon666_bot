import logging
from aiogram import Router
from aiogram.types import ChatMemberUpdated
from aiogram.filters.chat_member_updated import ChatMemberUpdatedFilter, IS_MEMBER, IS_NOT_MEMBER
from sqlalchemy.ext.asyncio import AsyncSession

from shared.config import settings
from shared.models import User

logger = logging.getLogger(__name__)
router = Router()


@router.chat_member(ChatMemberUpdatedFilter(IS_MEMBER >> IS_NOT_MEMBER))
async def on_member_left(event: ChatMemberUpdated, session: AsyncSession) -> None:
    """When user leaves / is kicked from channel — reset channel_joined_at so retention timer restarts."""
    if event.chat.id != settings.channel_id:
        return

    user_id = event.new_chat_member.user.id
    user = await session.get(User, user_id)
    if user and user.channel_joined_at is not None:
        user.channel_joined_at = None
        await session.commit()
        logger.info("User %s left channel — channel_joined_at reset", user_id)
