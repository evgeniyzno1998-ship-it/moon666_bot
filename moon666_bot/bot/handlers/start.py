from aiogram import Router, Bot
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandObject
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone

from shared.models import User, Referral
from shared.database import get_session
from shared.config import settings
from bot.keyboards import main_menu_kb, check_subscription_kb
from bot.services.referral import award_join_bonus

router = Router()


async def get_or_create_user(session: AsyncSession, tg_user) -> tuple[User, bool]:
    """Returns (user, is_new). Creates user in DB if not found."""
    user = await session.get(User, tg_user.id)
    if user:
        return user, False
    user = User(
        id=tg_user.id,
        username=tg_user.username,
        full_name=tg_user.full_name,
    )
    session.add(user)
    await session.commit()
    return user, True


async def _record_referral(session: AsyncSession, user: User, referrer_id_str: str) -> None:
    """Create Referral record if referrer exists and is not the user themselves."""
    try:
        referrer_id = int(referrer_id_str)
    except (ValueError, TypeError):
        return
    if referrer_id == user.id:
        return
    referrer = await session.get(User, referrer_id)
    if not referrer:
        return
    user.referred_by = referrer_id
    ref = Referral(referrer_id=referrer_id, referred_id=user.id)
    session.add(ref)
    await session.commit()


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject, session: AsyncSession) -> None:
    user, is_new = await get_or_create_user(session, message.from_user)

    if is_new and command.args:
        await _record_referral(session, user, command.args)

    # Check channel subscription
    bot: Bot = message.bot
    try:
        member = await bot.get_chat_member(settings.channel_id, user.id)
        if member.status in ("member", "administrator", "creator"):
            await _on_subscription_confirmed(message, session, user, bot)
            return
    except Exception:
        pass

    await message.answer(
        "🌙 <b>Welcome to Moon666!</b>\n\n"
        "To join the referral program, subscribe to our channel:",
        reply_markup=check_subscription_kb(),
        parse_mode="HTML",
    )


@router.callback_query(lambda c: c.data == "check_subscription")
async def callback_check_subscription(callback: CallbackQuery, session: AsyncSession) -> None:
    user = await session.get(User, callback.from_user.id)
    if not user:
        await callback.answer("Please send /start first", show_alert=True)
        return

    bot: Bot = callback.bot
    try:
        member = await bot.get_chat_member(settings.channel_id, user.id)
        if member.status not in ("member", "administrator", "creator"):
            await callback.answer("You haven't subscribed yet 😕", show_alert=True)
            return
    except Exception:
        await callback.answer("Couldn't verify. Please try again later.", show_alert=True)
        return

    await callback.message.delete()
    await _on_subscription_confirmed(callback.message, session, user, bot)
    await callback.answer()


async def _on_subscription_confirmed(message: Message, session: AsyncSession, user: User, bot: Bot) -> None:
    """Called when subscription to the channel is confirmed."""
    if not user.channel_joined_at:
        user.channel_joined_at = datetime.now(timezone.utc)
        await session.commit()

    # Award join bonus to referrer if applicable
    if user.referred_by:
        result = await session.execute(
            select(Referral).where(Referral.referred_id == user.id)
        )
        ref = result.scalar_one_or_none()
        if ref:
            await award_join_bonus(session, ref)
            try:
                await bot.send_message(
                    ref.referrer_id,
                    f"🎉 Someone joined via your referral link!\n"
                    f"💰 +{settings.bonus_join} USDT added to your balance.",
                )
            except Exception:
                pass

    await message.answer(
        f"✅ <b>Subscription confirmed!</b>\n\n"
        f"🌙 <b>Moon666</b> — Referral Program\n"
        f"Invite friends and earn USDT!\n\n"
        f"Choose an action:",
        reply_markup=main_menu_kb(),
        parse_mode="HTML",
    )
