"""
Onboarding funnel: 3 follow-up messages after a user subscribes.
  - +1 hour  : reminder to share referral link
  - +24 hours: tip about all 3 bonus types
Uses asyncio.create_task so it survives as long as the bot process is alive.
"""
import asyncio
import logging

logger = logging.getLogger(__name__)


async def _run_funnel(bot, user_id: int, bonus_join, bonus_reaction, bonus_retention) -> None:
    # ── Message 2: 1 hour after subscription ──────────────────────────────
    await asyncio.sleep(3600)
    try:
        await bot.send_message(
            user_id,
            "👋 Hey! Don't forget — you can start earning right now.\n\n"
            "🔗 Share your referral link with friends:\n"
            "Press /start → <b>My Link</b>\n\n"
            "Every person who joins via your link = <b>USDT in your balance</b>.",
            parse_mode="HTML",
        )
    except Exception as e:
        logger.debug("Onboarding msg2 failed for %s: %s", user_id, e)

    # ── Message 3: 24 hours after subscription ────────────────────────────
    await asyncio.sleep(23 * 3600)  # 23h more = 24h total
    try:
        await bot.send_message(
            user_id,
            "💡 <b>Did you know?</b> You earn in 3 ways per referral:\n\n"
            f"💰 +${bonus_join} — friend joins the channel\n"
            f"⚡ +${bonus_reaction} — friend reacts to a post\n"
            f"🎯 +${bonus_retention} — friend stays 30 days\n\n"
            "The more you invite — the more you earn. No limits! 🚀\n\n"
            "Press /start to see your balance and link.",
            parse_mode="HTML",
        )
    except Exception as e:
        logger.debug("Onboarding msg3 failed for %s: %s", user_id, e)


def schedule_onboarding(bot, user_id: int, bonus_join, bonus_reaction, bonus_retention) -> None:
    """Fire-and-forget: schedule the follow-up sequence for a new subscriber."""
    asyncio.create_task(
        _run_funnel(bot, user_id, bonus_join, bonus_reaction, bonus_retention)
    )
