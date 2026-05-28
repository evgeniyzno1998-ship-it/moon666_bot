from aiogram import Router
from aiogram.types import CallbackQuery, BufferedInputFile
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from decimal import Decimal

from shared.models import User, Referral, Transaction, TransactionType, UserAchievement, AchievementType
from shared.config import settings
from bot.keyboards import main_menu_kb
from bot.services.card_generator import generate_card

router = Router()

_ACH_EMOJI = {
    AchievementType.first_referral: "🌱",
    AchievementType.referrals_10:   "🔥",
    AchievementType.referrals_25:   "⚡",
    AchievementType.referrals_100:  "💎",
}


def _progress_bar(balance: Decimal, target: Decimal, width: int = 10) -> str:
    pct = min(float(balance / target), 1.0)
    filled = int(pct * width)
    bar = "█" * filled + "░" * (width - filled)
    return f"{bar} {int(pct * 100)}%"


@router.callback_query(lambda c: c.data == "cabinet")
async def cb_cabinet(callback: CallbackQuery, session: AsyncSession) -> None:
    user = await session.get(User, callback.from_user.id)
    if not user:
        await callback.answer("Please send /start first")
        return

    ref_count_result = await session.execute(
        select(func.count()).where(Referral.referrer_id == user.id)
    )
    ref_count = ref_count_result.scalar() or 0

    earned_result = await session.execute(
        select(func.sum(Transaction.amount_usdt)).where(
            Transaction.user_id == user.id,
            Transaction.type.in_([
                TransactionType.referral_join,
                TransactionType.referral_reaction,
                TransactionType.referral_retention,
            ])
        )
    )
    total_earned = earned_result.scalar() or Decimal("0.00")

    ach_res = await session.execute(
        select(UserAchievement).where(UserAchievement.user_id == user.id)
        .order_by(UserAchievement.achieved_at)
    )
    achievements = ach_res.scalars().all()
    ach_line = " ".join(_ACH_EMOJI.get(a.achievement_type, "🏅") for a in achievements) if achievements else "—"

    balance = user.balance_usdt
    target = settings.min_withdrawal
    progress = _progress_bar(balance, target)
    remaining = max(target - balance, Decimal("0.00"))

    bot_me = await callback.bot.get_me()
    ref_link = f"https://t.me/{bot_me.username}?start={user.id}"

    text = (
        f"🌙 <b>Moon666</b> · @{user.username or user.full_name}\n\n"
        f"┌─────────────────────────┐\n"
        f"│  <b>{balance:.2f} USDT</b>\n"
        f"│  {progress}\n"
        f"│  Until withdrawal: {remaining:.2f} USDT\n"
        f"└─────────────────────────┘\n\n"
        f"👥 {ref_count} referrals · 💰 earned {total_earned:.2f} USDT\n"
        f"🏆 Achievements: {ach_line}\n\n"
        f"🔗 <code>{ref_link}</code>"
    )
    await callback.message.edit_text(text, reply_markup=main_menu_kb(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(lambda c: c.data == "my_referrals")
async def cb_my_referrals(callback: CallbackQuery, session: AsyncSession) -> None:
    result = await session.execute(
        select(Referral, User)
        .join(User, User.id == Referral.referred_id)
        .where(Referral.referrer_id == callback.from_user.id)
        .order_by(Referral.created_at.desc())
        .limit(20)
    )
    rows = result.all()

    if not rows:
        text = "👥 You have no referrals yet.\n\nShare your link to start earning!"
    else:
        lines = ["👥 <b>My Referrals:</b>\n"]
        for ref, referred_user in rows:
            earned = Decimal("0.00")
            if ref.join_bonus_paid:
                earned += settings.bonus_join
            if ref.reaction_bonus_paid:
                earned += settings.bonus_reaction
            if ref.retention_bonus_paid:
                earned += settings.bonus_retention
            name = f"@{referred_user.username}" if referred_user.username else referred_user.full_name
            lines.append(f"• {name} — +{earned:.2f} USDT")
        text = "\n".join(lines)

    await callback.message.edit_text(text, reply_markup=main_menu_kb(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(lambda c: c.data == "my_link")
async def cb_my_link(callback: CallbackQuery) -> None:
    bot_me = await callback.bot.get_me()
    ref_link = f"https://t.me/{bot_me.username}?start={callback.from_user.id}"
    max_per_ref = settings.bonus_join + settings.bonus_reaction + settings.bonus_retention
    text = (
        f"🔗 <b>Your Referral Link:</b>\n\n"
        f"<code>{ref_link}</code>\n\n"
        f"Share with friends! For each subscriber:\n"
        f"• +{settings.bonus_join} USDT — subscribed\n"
        f"• +{settings.bonus_reaction} USDT — reacted to a post\n"
        f"• +{settings.bonus_retention} USDT — stayed 30 days\n\n"
        f"Maximum <b>{max_per_ref:.2f} USDT</b> per person"
    )
    await callback.message.edit_text(text, reply_markup=main_menu_kb(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(lambda c: c.data == "top_referrals")
async def cb_top_referrals(callback: CallbackQuery, session: AsyncSession) -> None:
    result = await session.execute(
        select(User.username, User.full_name, func.count(Referral.id).label("cnt"))
        .join(Referral, Referral.referrer_id == User.id)
        .group_by(User.id, User.username, User.full_name)
        .order_by(func.count(Referral.id).desc())
        .limit(10)
    )
    rows = result.all()

    medals = ["🥇", "🥈", "🥉"] + ["🏅"] * 7
    lines = ["🏆 <b>Top Referrers:</b>\n"]
    for i, (username, full_name, cnt) in enumerate(rows):
        name = f"@{username}" if username else full_name
        lines.append(f"{medals[i]} {name} — {cnt} ref{'s' if cnt != 1 else ''}.")

    if not rows:
        lines.append("No one yet. Be the first!")

    await callback.message.edit_text(
        "\n".join(lines), reply_markup=main_menu_kb(), parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "my_card")
async def cb_my_card(callback: CallbackQuery, session: AsyncSession) -> None:
    user = await session.get(User, callback.from_user.id)
    if not user:
        await callback.answer("Please send /start first")
        return

    ref_count_res = await session.execute(
        select(func.count()).where(Referral.referrer_id == user.id)
    )
    ref_count = ref_count_res.scalar() or 0

    earned_res = await session.execute(
        select(func.sum(Transaction.amount_usdt)).where(
            Transaction.user_id == user.id,
            Transaction.type.in_([
                TransactionType.referral_join,
                TransactionType.referral_reaction,
                TransactionType.referral_retention,
            ])
        )
    )
    earned = float(earned_res.scalar() or 0)

    username = user.username or user.full_name or str(user.id)

    bot_info = await callback.bot.get_me()
    ref_link = f"t.me/{bot_info.username}?start={user.id}"

    try:
        img_bytes = generate_card(username, ref_count, earned)
        await callback.message.answer_photo(
            BufferedInputFile(img_bytes, filename="moon666_card.png"),
            caption=(
                f"🎴 <b>Your Referral Card</b>\n\n"
                f"Share this link with friends to earn USDT!\n\n"
                f"🔗 <code>https://t.me/{bot_info.username}?start={user.id}</code>"
            ),
            parse_mode="HTML",
        )
    except Exception:
        import logging
        logging.getLogger(__name__).exception("Card generation failed for user %s", user.id)
        await callback.message.answer("⚠️ Could not generate your card. Please try again later.")

    await callback.answer()
