import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from shared.config import settings
from shared.database import engine
from shared.models import Base
from bot.handlers.start import router as start_router
from bot.handlers.cabinet import router as cabinet_router
from bot.handlers.withdrawal import router as withdrawal_router
from bot.handlers.reactions import router as reactions_router
from bot.handlers.channel_member import router as channel_member_router
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

    await bot.set_my_commands([
        BotCommand(command="start", description="Main menu"),
        BotCommand(command="cancel", description="Cancel"),
    ])
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

    dp.startup.register(on_startup)

    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types() + ["chat_member"])


if __name__ == "__main__":
    asyncio.run(main())
