from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Мой баланс", callback_data="cabinet")],
        [InlineKeyboardButton(text="👥 Мои рефералы", callback_data="my_referrals")],
        [InlineKeyboardButton(text="🔗 Моя ссылка", callback_data="my_link")],
        [InlineKeyboardButton(text="📤 Вывод", callback_data="withdrawal")],
        [InlineKeyboardButton(text="🏆 Топ рефералов", callback_data="top_referrals")],
    ])


def check_subscription_kb(bot_username: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Подписаться на канал", url="https://t.me/Moon666")],
        [InlineKeyboardButton(text="✅ Я подписался", callback_data="check_subscription")],
    ])
