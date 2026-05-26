from pydantic_settings import BaseSettings, SettingsConfigDict
from decimal import Decimal


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Telegram
    bot_token: str
    channel_id: int
    admin_tg_id: int

    # Web admin
    admin_login: str
    admin_password: str
    jwt_secret: str

    # Database
    database_url: str
    database_url_sync: str

    # Bonus amounts
    bonus_join: Decimal = Decimal("0.20")
    bonus_reaction: Decimal = Decimal("0.01")
    bonus_retention: Decimal = Decimal("0.05")
    min_withdrawal: Decimal = Decimal("10.00")


settings = Settings()
