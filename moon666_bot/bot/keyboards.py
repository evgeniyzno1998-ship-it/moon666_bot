from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from shared.config import settings


def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 My Balance",    callback_data="cabinet")],
        [InlineKeyboardButton(text="👥 My Referrals",  callback_data="my_referrals")],
        [InlineKeyboardButton(text="🔗 My Link",       callback_data="my_link")],
        [InlineKeyboardButton(text="📤 Withdraw",      callback_data="withdrawal")],
        [InlineKeyboardButton(text="🏆 Top Referrers", callback_data="top_referrals")],
    ])


def check_subscription_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Join Channel",      url=settings.channel_invite_link)],
        [InlineKeyboardButton(text="✅ I've Subscribed",   callback_data="check_subscription")],
    ])
