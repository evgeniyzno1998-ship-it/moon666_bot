from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator
from decimal import Decimal
from typing import Optional


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
    database_url_sync: Optional[str] = None

    # Channel invite link
    channel_invite_link: str = "https://t.me/+your_invite_link"

    # Anti-fraud
    max_daily_referrals: int = 10
    min_referred_user_id: Optional[int] = None
    suspicious_hourly_threshold: int = 8

    # Bonus amounts
    bonus_join: Decimal = Decimal("0.20")
    bonus_reaction: Decimal = Decimal("0.01")
    bonus_retention: Decimal = Decimal("0.05")
    min_withdrawal: Decimal = Decimal("10.00")
    auto_approve_below: Decimal = Decimal("0.00")

    @model_validator(mode="after")
    def derive_sync_url(self) -> "Settings":
        if self.database_url_sync is None:
            url = self.database_url
            url = url.replace("postgresql+asyncpg://", "postgresql://")
            url = url.replace("postgres://", "postgresql://")
            self.database_url_sync = url
        return self


settings = Settings()
