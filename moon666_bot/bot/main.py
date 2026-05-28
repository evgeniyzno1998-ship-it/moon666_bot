import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from shared.config import settings
from shared.database import engine, async_session_maker
from shared.models import Base
from bot.handlers.start import router as start_router
from bot.handlers.cabinet import router as cabinet_router
from bot.handlers.withdrawal import router as withdrawal_router
from bot.handlers.reactions import router as reactions_router
from bot.handlers.channel_member import router as channel_member_router
from bot.handlers.admin_callbacks import router as admin_callbacks_router
from bot.services.scheduler import start_scheduler
from bot.middlewares.db import DbSessionMiddleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_scheduler = None  # module-level reference


async def on_startup(bot: Bot):
    global _scheduler
    # Create tables if missing (in prod use alembic)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Fix bad full_name values stored as literal "null" strings
    from sqlalchemy import update
    from shared.models import User
    async with async_session_maker() as session:
        await session.execute(
            update(User).where(User.full_name == "null").values(full_name=None)
        )
        await session.commit()

    await bot.set_my_commands([
        BotCommand(command="start", description="Main menu"),
        BotCommand(command="cancel", description="Cancel"),
    ])

    # Bot description — shown on profile page (max 512 chars)
    await bot.set_my_description(
        "🌙 Moon666 — Get Paid to Grow Our Community\n\n"
        "Earn real USDT simply by sharing your referral link:\n\n"
        "💰 +$0.20 — your friend joins the channel\n"
        "⚡ +$0.01 — they react to a post\n"
        "🎯 +$0.05 — they stay 30 days\n\n"
        "Up to $0.26 per referral. Unlimited referrals.\n\n"
        "📤 Withdraw to any USDT wallet (TRC20 / BEP20 / ERC20) once you hit $10.\n\n"
        "No investment. No risk. Just share — and earn.\n\n"
        "Press Start ↓"
    )

    # Short description — shown before the user presses Start (max 120 chars)
    await bot.set_my_short_description(
        "Earn USDT by inviting friends to Moon666. Up to $0.26 per referral. Withdraw anytime. 🚀"
    )

    _scheduler = start_scheduler(bot)
    logger.info("Bot started")


async def main():
    bot = Bot(token=settings.bot_token)
    dp = Dispatcher(storage=MemoryStorage())

    dp.update.middleware(DbSessionMiddleware())

    dp.include_router(channel_member_router)
    dp.include_router(start_router)
    dp.include_router(cabinet_router)
    dp.include_router(withdrawal_router)
    dp.include_router(reactions_router)
    dp.include_router(admin_callbacks_router)

    dp.startup.register(on_startup)

    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types() + ["chat_member"])


if __name__ == "__main__":
    asyncio.run(main())
