from aiogram import Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models import User

router = Router()


@router.callback_query(lambda c: c.data and c.data.startswith("ban_user:"))
async def callback_ban_user(callback: CallbackQuery, session: AsyncSession) -> None:
    try:
        user_id = int(callback.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await callback.answer("Invalid data.")
        return

    user = await session.get(User, user_id)
    if user:
        user.is_banned = True
        await session.commit()
        await callback.message.edit_text(
            callback.message.text + f"\n\n🚫 User <code>{user_id}</code> has been <b>banned</b>.",
            parse_mode="HTML",
        )
        await callback.answer("User banned.")
    else:
        await callback.answer("User not found.")


@router.callback_query(lambda c: c.data and c.data.startswith("ignore_alert:"))
async def callback_ignore_alert(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        callback.message.text + "\n\n✅ Alert dismissed.",
        parse_mode="HTML",
    )
    await callback.answer("Dismissed.")
