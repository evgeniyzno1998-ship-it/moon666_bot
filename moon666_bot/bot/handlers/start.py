from aiogram import Router, Bot
from aiogram.filters import CommandStart, CommandObject
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone, timedelta

from shared.models import User, Referral
from shared.config import settings
from bot.keyboards import main_menu_kb, check_subscription_kb
from bot.services.referral import award_join_bonus
from bot.services.onboarding import schedule_onboarding

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


async def _record_referral(
    session: AsyncSession,
    user: User,
    referrer_id_str: str,
    bot: Bot | None = None,
) -> None:
    """Create Referral record if referrer exists and passes all anti-fraud checks."""
    try:
        referrer_id = int(referrer_id_str)
    except (ValueError, TypeError):
        return
    if referrer_id == user.id:
        return
    referrer = await session.get(User, referrer_id)
    if not referrer:
        return

    # Anti-fraud: block if referred user's Telegram ID is above the configured threshold
    if settings.min_referred_user_id is not None and user.id > settings.min_referred_user_id:
        return

    # Anti-fraud: daily referral limit per referrer
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    daily_count_res = await session.execute(
        select(func.count()).select_from(Referral).where(
            Referral.referrer_id == referrer_id,
            Referral.created_at >= today_start,
        )
    )
    if (daily_count_res.scalar() or 0) >= settings.max_daily_referrals:
        return

    user.referred_by = referrer_id
    ref = Referral(referrer_id=referrer_id, referred_id=user.id)
    session.add(ref)
    await session.commit()

    # Anti-fraud: suspicious activity alert (fires once when hourly count hits threshold)
    if bot and settings.suspicious_hourly_threshold > 0:
        one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
        hourly_res = await session.execute(
            select(func.count()).select_from(Referral).where(
                Referral.referrer_id == referrer_id,
                Referral.created_at >= one_hour_ago,
            )
        )
        hourly_count = hourly_res.scalar() or 0
        if hourly_count == settings.suspicious_hourly_threshold:
            kb = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🚫 Ban user", callback_data=f"ban_user:{referrer_id}"),
                InlineKeyboardButton(text="✅ Ignore",   callback_data=f"ignore_alert:{referrer_id}"),
            ]])
            try:
                await bot.send_message(
                    settings.admin_tg_id,
                    f"⚠️ <b>Suspicious activity!</b>\n\n"
                    f"User <code>{referrer_id}</code> attracted "
                    f"<b>{hourly_count} referrals</b> in the last hour.\n\n"
                    f"Threshold: {settings.suspicious_hourly_threshold}",
                    reply_markup=kb,
                    parse_mode="HTML",
                )
            except Exception:
                pass


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject, session: AsyncSession) -> None:
    user, is_new = await get_or_create_user(session, message.from_user)

    if is_new and command.args:
        await _record_referral(session, user, command.args, bot=message.bot)

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


async def _on_subscription_confirmed(
    message: Message, session: AsyncSession, user: User, bot: Bot
) -> None:
    """Called when subscription to the channel is confirmed."""
    is_first_join = not user.channel_joined_at
    if is_first_join:
        user.channel_joined_at = datetime.now(timezone.utc)
        await session.commit()

    if user.referred_by:
        result = await session.execute(
            select(Referral).where(Referral.referred_id == user.id)
        )
        ref = result.scalar_one_or_none()
        if ref:
            await award_join_bonus(session, ref, bot=bot)
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

    if is_first_join:
        schedule_onboarding(
            bot, user.id,
            settings.bonus_join,
            settings.bonus_reaction,
            settings.bonus_retention,
        )
