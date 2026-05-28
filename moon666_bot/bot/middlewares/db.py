from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update

from shared.database import async_session_maker
from shared.models import User


class DbSessionMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        async with async_session_maker() as session:
            data["session"] = session

            # Extract user_id to check ban status
            user_id = None
            if isinstance(event, Update):
                if event.message and event.message.from_user:
                    user_id = event.message.from_user.id
                elif event.callback_query and event.callback_query.from_user:
                    user_id = event.callback_query.from_user.id

            if user_id:
                user = await session.get(User, user_id)
                if user and user.is_banned:
                    if isinstance(event, Update):
                        if event.message:
                            await event.message.answer("🚫 You've been restricted from using this bot.")
                        elif event.callback_query:
                            await event.callback_query.answer(
                                "🚫 You've been restricted from using this bot.",
                                show_alert=True,
                            )
                    return  # Do not dispatch to handler

            return await handler(event, data)
