from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models import User, Withdrawal, WithdrawalStatus
from shared.config import settings
from bot.keyboards import main_menu_kb

router = Router()


class WithdrawalForm(StatesGroup):
    waiting_wallet = State()


@router.callback_query(lambda c: c.data == "withdrawal")
async def cb_withdrawal(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    user = await session.get(User, callback.from_user.id)
    if not user:
        await callback.answer("Please send /start first")
        return

    if user.balance_usdt < settings.min_withdrawal:
        remaining = settings.min_withdrawal - user.balance_usdt
        await callback.answer(
            f"Minimum withdrawal: {settings.min_withdrawal} USDT\n"
            f"You need {remaining:.2f} more USDT",
            show_alert=True,
        )
        return

    await state.set_state(WithdrawalForm.waiting_wallet)
    await callback.message.answer(
        f"💳 Enter your wallet address to withdraw <b>{user.balance_usdt:.2f} USDT</b>:\n\n"
        f"Supported networks: TRC20 (USDT), BEP20, ERC20\n\n"
        f"Send /cancel to cancel.",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(WithdrawalForm.waiting_wallet, Command("cancel"))
async def cmd_cancel_withdrawal(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("❌ Withdrawal cancelled.", reply_markup=main_menu_kb())


@router.message(WithdrawalForm.waiting_wallet)
async def process_wallet_address(message: Message, state: FSMContext, session: AsyncSession) -> None:
    wallet = message.text.strip()

    if len(wallet) < 20:
        await message.answer("❌ Invalid address. Please try again or send /cancel to cancel.")
        return

    user = await session.get(User, message.from_user.id)
    if not user or user.balance_usdt < settings.min_withdrawal:
        await message.answer("❌ Insufficient balance.")
        await state.clear()
        return

    # Check for existing pending withdrawal
    existing_pending = await session.execute(
        select(Withdrawal).where(
            Withdrawal.user_id == user.id,
            Withdrawal.status == WithdrawalStatus.pending,
        )
    )
    if existing_pending.scalar_one_or_none():
        await message.answer(
            "⏳ You already have a pending withdrawal request.\n"
            "Please wait for it to be processed or contact support.",
            reply_markup=main_menu_kb(),
        )
        await state.clear()
        return

    withdrawal = Withdrawal(
        user_id=user.id,
        amount_usdt=user.balance_usdt,
        wallet_address=wallet,
        status=WithdrawalStatus.pending,
    )
    session.add(withdrawal)
    await session.commit()

    await state.clear()

    # Notify admin
    try:
        await message.bot.send_message(
            settings.admin_tg_id,
            f"💸 <b>New Withdrawal Request!</b>\n\n"
            f"👤 @{user.username or user.full_name}\n"
            f"💰 {withdrawal.amount_usdt:.2f} USDT\n"
            f"💳 <code>{wallet}</code>\n\n"
            f"Request ID: #{withdrawal.id}",
            parse_mode="HTML",
        )
    except Exception:
        pass

    await message.answer(
        f"✅ Withdrawal request for <b>{withdrawal.amount_usdt:.2f} USDT</b> submitted!\n\n"
        f"Wallet: <code>{wallet}</code>\n\n"
        f"We'll process it within 24 hours.",
        reply_markup=main_menu_kb(),
        parse_mode="HTML",
    )
