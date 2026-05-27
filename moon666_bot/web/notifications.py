import logging
import httpx
from shared.config import settings

logger = logging.getLogger(__name__)


async def send_telegram_notification(user_id: int, text: str) -> bool:
    """Send a message to a user via Bot API."""
    url = f"https://api.telegram.org/bot{settings.bot_token}/sendMessage"
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url, json={"chat_id": user_id, "text": text, "parse_mode": "HTML"})
            return resp.status_code == 200
        except Exception as e:
            logger.warning("Failed to send Telegram notification to %s: %s", user_id, e)
            return False
