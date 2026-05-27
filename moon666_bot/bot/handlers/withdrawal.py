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
        await callback.answer("Сначала напиши /start")
        return

    if user.balance_usdt < settings.min_withdrawal:
        remaining = settings.min_withdrawal - user.balance_usdt
        await callback.answer(
            f"Минимальная сумма для вывода: {settings.min_withdrawal} USDT\n"
            f"Тебе не хватает ещё {remaining:.2f} USDT",
            show_alert=True,
        )
        return

    await state.set_state(WithdrawalForm.waiting_wallet)
    await callback.message.answer(
        f"💳 Введи адрес кошелька для вывода <b>{user.balance_usdt:.2f} USDT</b>:\n\n"
        f"Поддерживается: TRC20 (USDT), BEP20, ERC20\n\n"
        f"Отправь /cancel для отмены.",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(WithdrawalForm.waiting_wallet, Command("cancel"))
async def cmd_cancel_withdrawal(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("❌ Вывод отменён.", reply_markup=main_menu_kb())


@router.message(WithdrawalForm.waiting_wallet)
async def process_wallet_address(message: Message, state: FSMContext, session: AsyncSession) -> None:
    wallet = message.text.strip()

    if len(wallet) < 20:
        await message.answer("❌ Некорректный адрес. Попробуй ещё раз или /cancel для отмены.")
        return

    user = await session.get(User, message.from_user.id)
    if not user or user.balance_usdt < settings.min_withdrawal:
        await message.answer("❌ Недостаточно средств.")
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
            "⏳ У тебя уже есть активная заявка на вывод.\n"
            "Дождись её обработки или обратись в поддержку.",
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

    # Notify owner
    try:
        await message.bot.send_message(
            settings.admin_tg_id,
            f"💸 <b>Новая заявка на вывод!</b>\n\n"
            f"👤 @{user.username or user.full_name}\n"
            f"💰 {withdrawal.amount_usdt:.2f} USDT\n"
            f"💳 <code>{wallet}</code>\n\n"
            f"ID заявки: #{withdrawal.id}",
            parse_mode="HTML",
        )
    except Exception:
        pass

    await message.answer(
        f"✅ Заявка на вывод <b>{withdrawal.amount_usdt:.2f} USDT</b> принята!\n\n"
        f"Кошелёк: <code>{wallet}</code>\n\n"
        f"Мы обработаем её в течение 24 часов.",
        reply_markup=main_menu_kb(),
        parse_mode="HTML",
    )
