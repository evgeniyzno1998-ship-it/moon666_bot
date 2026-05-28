# Anti-Fraud 2.0 + Admin Power Tools + Premium Features Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden fraud protection, give the admin full operational control (user detail, campaigns, CSV, auto-approval, mobile), and add viral mechanics (referral cards, achievements) to increase engagement.

**Architecture:** All changes extend the existing aiogram 3 + FastAPI + SQLAlchemy async stack without introducing new infrastructure. DB gets `is_banned` column, `campaigns` table, `user_achievements` table. Business logic stays in `bot/services/`. Web follows the existing FastAPI + Jinja2 + Crypto Dark CSS pattern.

**Tech Stack:** Python 3.12, aiogram 3.7, FastAPI, SQLAlchemy 2.0 async, PostgreSQL, Alembic, Pillow (new dependency), Jinja2

---

## File Map

**New files:**
- `alembic/versions/002_antifrud_features.py` — DB migration
- `bot/handlers/admin_callbacks.py` — bot-side ban/ignore inline keyboard callbacks
- `bot/services/card_generator.py` — Pillow referral card image
- `bot/services/achievements.py` — check and award achievement badges
- `web/routes/campaigns.py` — campaign CRUD
- `web/templates/user_detail.html` — user detail page
- `web/templates/campaigns.html` — campaigns list
- `web/templates/campaign_form.html` — create/edit campaign form

**Modified files:**
- `shared/models.py` — `User.is_banned`, `Campaign`, `UserAchievement`, new enums
- `shared/config.py` — 3 new settings
- `bot/middlewares/db.py` — ban check before handler dispatch
- `bot/handlers/start.py` — user_id threshold + suspicious alert + pass bot
- `bot/services/referral.py` — campaign multiplier + call achievements
- `bot/handlers/cabinet.py` — /card command + achievements display
- `bot/keyboards.py` — add 🎴 My Card button
- `bot/handlers/withdrawal.py` — auto-approval logic
- `bot/main.py` — register admin_callbacks router
- `bot/Dockerfile` — install DejaVu fonts
- `requirements.txt` — add Pillow
- `web/routes/users.py` — detail page, ban/unban, adjust balance, send msg, CSV export
- `web/routes/withdrawals.py` — CSV export
- `web/main.py` — register campaigns_router
- `web/templates/base.html` — Campaigns sidebar link + mobile CSS + hamburger JS
- `web/templates/users.html` — clickable rows, ban button, export button
- `web/templates/withdrawals.html` — export button

---

## Task 1: DB Schema + Config + Migration

**Files:**
- Modify: `shared/models.py`
- Modify: `shared/config.py`
- Create: `alembic/versions/002_antifrud_features.py`

- [ ] **Step 1: Update `shared/models.py`** — add 4 new enums/models and `is_banned` field

Replace the entire file content:

```python
import enum
from decimal import Decimal
from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    BigInteger, String, Numeric, Boolean, DateTime,
    ForeignKey, Enum as SAEnum, UniqueConstraint, func
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class TransactionType(str, enum.Enum):
    referral_join = "referral_join"
    referral_reaction = "referral_reaction"
    referral_retention = "referral_retention"
    manual_adjustment = "manual_adjustment"


class WithdrawalStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class CampaignBonusType(str, enum.Enum):
    join = "join"
    reaction = "reaction"
    all = "all"


class AchievementType(str, enum.Enum):
    first_referral = "first_referral"
    referrals_10 = "referrals_10"
    referrals_25 = "referrals_25"
    referrals_100 = "referrals_100"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[Optional[str]] = mapped_column(String(64))
    full_name: Mapped[str] = mapped_column(String(256))
    referred_by: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.id"))
    balance_usdt: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"), server_default="0")
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    channel_joined_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    referrals_made: Mapped[List["Referral"]] = relationship(
        "Referral", foreign_keys="Referral.referrer_id", back_populates="referrer"
    )
    transactions: Mapped[List["Transaction"]] = relationship("Transaction", back_populates="user")
    withdrawals: Mapped[List["Withdrawal"]] = relationship("Withdrawal", back_populates="user")
    achievements: Mapped[List["UserAchievement"]] = relationship("UserAchievement", back_populates="user")


class Referral(Base):
    __tablename__ = "referrals"

    id: Mapped[int] = mapped_column(primary_key=True)
    referrer_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    referred_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), unique=True)
    join_bonus_paid: Mapped[bool] = mapped_column(Boolean, default=False)
    reaction_bonus_paid: Mapped[bool] = mapped_column(Boolean, default=False)
    retention_bonus_paid: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())

    referrer: Mapped["User"] = relationship("User", foreign_keys=[referrer_id], back_populates="referrals_made")
    referred: Mapped["User"] = relationship("User", foreign_keys=[referred_id])


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    amount_usdt: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    type: Mapped[TransactionType] = mapped_column(SAEnum(TransactionType))
    related_user_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())

    user: Mapped["User"] = relationship("User", back_populates="transactions")


class Withdrawal(Base):
    __tablename__ = "withdrawals"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    amount_usdt: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    wallet_address: Mapped[str] = mapped_column(String(256))
    status: Mapped[WithdrawalStatus] = mapped_column(
        SAEnum(WithdrawalStatus), default=WithdrawalStatus.pending
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    user: Mapped["User"] = relationship("User", back_populates="withdrawals")


class ChannelReaction(Base):
    __tablename__ = "channel_reactions"
    __table_args__ = (UniqueConstraint("user_id", name="uq_channel_reactions_user"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    post_id: Mapped[int] = mapped_column(BigInteger)
    reacted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    bonus_multiplier: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("1.00"), server_default="1.00")
    applies_to: Mapped[CampaignBonusType] = mapped_column(SAEnum(CampaignBonusType))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())


class UserAchievement(Base):
    __tablename__ = "user_achievements"
    __table_args__ = (UniqueConstraint("user_id", "achievement_type", name="uq_user_achievement"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    achievement_type: Mapped[AchievementType] = mapped_column(SAEnum(AchievementType))
    achieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())

    user: Mapped["User"] = relationship("User", back_populates="achievements")
```

- [ ] **Step 2: Update `shared/config.py`** — add 3 new settings

```python
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
    min_referred_user_id: Optional[int] = None  # None = disabled; e.g. 7_000_000_000 blocks very new TG accounts
    suspicious_hourly_threshold: int = 8         # referrals from one referrer in 1 hour → alert admin

    # Bonus amounts
    bonus_join: Decimal = Decimal("0.20")
    bonus_reaction: Decimal = Decimal("0.01")
    bonus_retention: Decimal = Decimal("0.05")
    min_withdrawal: Decimal = Decimal("10.00")
    auto_approve_below: Decimal = Decimal("0.00")  # 0.00 = disabled; e.g. 5.00 auto-approves withdrawals < $5

    @model_validator(mode="after")
    def derive_sync_url(self) -> "Settings":
        if self.database_url_sync is None:
            url = self.database_url
            url = url.replace("postgresql+asyncpg://", "postgresql://")
            url = url.replace("postgres://", "postgresql://")
            self.database_url_sync = url
        return self


settings = Settings()
```

- [ ] **Step 3: Create Alembic migration `alembic/versions/002_antifrud_features.py`**

```python
"""antifrud features: is_banned, campaigns, user_achievements

Revision ID: b2c3d4e5
Revises: a1b2c3d4
Create Date: 2026-05-28
"""
from alembic import op
import sqlalchemy as sa

revision = 'b2c3d4e5'
down_revision = 'a1b2c3d4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add is_banned to users
    op.add_column('users', sa.Column('is_banned', sa.Boolean(), nullable=False, server_default='false'))

    # 2. Add manual_adjustment value to existing transactiontype enum
    op.execute("ALTER TYPE transactiontype ADD VALUE IF NOT EXISTS 'manual_adjustment'")

    # 3. Create campaignbonustype enum + campaigns table
    campaignbonustype = sa.Enum('join', 'reaction', 'all', name='campaignbonustype')
    campaignbonustype.create(op.get_bind(), checkfirst=True)

    op.create_table(
        'campaigns',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(128), nullable=False),
        sa.Column('bonus_multiplier', sa.Numeric(5, 2), nullable=False, server_default='1.00'),
        sa.Column('applies_to', sa.Enum('join', 'reaction', 'all', name='campaignbonustype'), nullable=False),
        sa.Column('starts_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('ends_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )

    # 4. Create achievementtype enum + user_achievements table
    achievementtype = sa.Enum('first_referral', 'referrals_10', 'referrals_25', 'referrals_100', name='achievementtype')
    achievementtype.create(op.get_bind(), checkfirst=True)

    op.create_table(
        'user_achievements',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('achievement_type', sa.Enum('first_referral', 'referrals_10', 'referrals_25', 'referrals_100', name='achievementtype'), nullable=False),
        sa.Column('achieved_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'achievement_type', name='uq_user_achievement'),
    )


def downgrade() -> None:
    op.drop_table('user_achievements')
    sa.Enum(name='achievementtype').drop(op.get_bind(), checkfirst=True)
    op.drop_table('campaigns')
    sa.Enum(name='campaignbonustype').drop(op.get_bind(), checkfirst=True)
    op.drop_column('users', 'is_banned')
    # Note: PostgreSQL does not support removing enum values; manual_adjustment stays
```

- [ ] **Step 4: Run migration locally to verify it applies cleanly**

```bash
cd moon666_bot
alembic upgrade head
```

Expected output ends with: `Running upgrade a1b2c3d4 -> b2c3d4e5, antifrud features`

- [ ] **Step 5: Commit**

```bash
git add shared/models.py shared/config.py alembic/versions/002_antifrud_features.py
git commit -m "feat: db schema — is_banned, campaigns, user_achievements, manual_adjustment"
```

---

## Task 2: Ban Middleware + User ID Age Check

**Files:**
- Modify: `bot/middlewares/db.py`
- Modify: `bot/handlers/start.py`

- [ ] **Step 1: Rewrite `bot/middlewares/db.py`** — add ban check before dispatching to handlers

```python
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
```

- [ ] **Step 2: Update `bot/handlers/start.py`** — add user_id threshold check and pass `bot` to `_record_referral`

Replace the entire file:

```python
from aiogram import Router, Bot
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandObject
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone, timedelta

from shared.models import User, Referral
from shared.database import get_session
from shared.config import settings
from bot.keyboards import main_menu_kb, check_subscription_kb
from bot.services.referral import award_join_bonus
from bot.services.onboarding import schedule_onboarding

router = Router()


async def get_or_create_user(session: AsyncSession, tg_user) -> tuple[User, bool]:
    """Returns (user, is_new). Creates user in DB if not found."""
    user = await session.get(User, tg_user.id)
    if user:
        return user, False
    user = User(
        id=tg_user.id,
        username=tg_user.username,
        full_name=tg_user.full_name,
    )
    session.add(user)
    await session.commit()
    return user, True


async def _record_referral(
    session: AsyncSession,
    user: User,
    referrer_id_str: str,
    bot: Bot | None = None,
) -> None:
    """Create Referral record if referrer exists and passes all anti-fraud checks."""
    try:
        referrer_id = int(referrer_id_str)
    except (ValueError, TypeError):
        return
    if referrer_id == user.id:
        return
    referrer = await session.get(User, referrer_id)
    if not referrer:
        return

    # Anti-fraud: block if referred user's Telegram ID is above the configured threshold
    # (lower IDs = older accounts; very high IDs = potentially brand-new accounts)
    if settings.min_referred_user_id is not None and user.id > settings.min_referred_user_id:
        return

    # Anti-fraud: daily referral limit per referrer
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    daily_count_res = await session.execute(
        select(func.count()).select_from(Referral).where(
            Referral.referrer_id == referrer_id,
            Referral.created_at >= today_start,
        )
    )
    if (daily_count_res.scalar() or 0) >= settings.max_daily_referrals:
        return

    user.referred_by = referrer_id
    ref = Referral(referrer_id=referrer_id, referred_id=user.id)
    session.add(ref)
    await session.commit()

    # Anti-fraud: suspicious activity alert (fires once when hourly count hits threshold)
    if bot and settings.suspicious_hourly_threshold > 0:
        one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
        hourly_res = await session.execute(
            select(func.count()).select_from(Referral).where(
                Referral.referrer_id == referrer_id,
                Referral.created_at >= one_hour_ago,
            )
        )
        hourly_count = hourly_res.scalar() or 0
        if hourly_count == settings.suspicious_hourly_threshold:
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            kb = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🚫 Ban user", callback_data=f"ban_user:{referrer_id}"),
                InlineKeyboardButton(text="✅ Ignore",   callback_data=f"ignore_alert:{referrer_id}"),
            ]])
            try:
                await bot.send_message(
                    settings.admin_tg_id,
                    f"⚠️ <b>Suspicious activity!</b>\n\n"
                    f"User <code>{referrer_id}</code> attracted "
                    f"<b>{hourly_count} referrals</b> in the last hour.\n\n"
                    f"Threshold: {settings.suspicious_hourly_threshold}",
                    reply_markup=kb,
                    parse_mode="HTML",
                )
            except Exception:
                pass


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject, session: AsyncSession) -> None:
    user, is_new = await get_or_create_user(session, message.from_user)

    if is_new and command.args:
        await _record_referral(session, user, command.args, bot=message.bot)

    bot: Bot = message.bot
    try:
        member = await bot.get_chat_member(settings.channel_id, user.id)
        if member.status in ("member", "administrator", "creator"):
            await _on_subscription_confirmed(message, session, user, bot)
            return
    except Exception:
        pass

    await message.answer(
        "🌙 <b>Welcome to Moon666!</b>\n\n"
        "To join the referral program, subscribe to our channel:",
        reply_markup=check_subscription_kb(),
        parse_mode="HTML",
    )


@router.callback_query(lambda c: c.data == "check_subscription")
async def callback_check_subscription(callback: CallbackQuery, session: AsyncSession) -> None:
    user = await session.get(User, callback.from_user.id)
    if not user:
        await callback.answer("Please send /start first", show_alert=True)
        return

    bot: Bot = callback.bot
    try:
        member = await bot.get_chat_member(settings.channel_id, user.id)
        if member.status not in ("member", "administrator", "creator"):
            await callback.answer("You haven't subscribed yet 😕", show_alert=True)
            return
    except Exception:
        await callback.answer("Couldn't verify. Please try again later.", show_alert=True)
        return

    await callback.message.delete()
    await _on_subscription_confirmed(callback.message, session, user, bot)
    await callback.answer()


async def _on_subscription_confirmed(
    message: Message, session: AsyncSession, user: User, bot: Bot
) -> None:
    """Called when subscription to the channel is confirmed."""
    if not user.channel_joined_at:
        user.channel_joined_at = datetime.now(timezone.utc)
        await session.commit()

    if user.referred_by:
        result = await session.execute(
            select(Referral).where(Referral.referred_id == user.id)
        )
        ref = result.scalar_one_or_none()
        if ref:
            await award_join_bonus(session, ref, bot=bot)
            try:
                await bot.send_message(
                    ref.referrer_id,
                    f"🎉 Someone joined via your referral link!\n"
                    f"💰 +{settings.bonus_join} USDT added to your balance.",
                )
            except Exception:
                pass

    await message.answer(
        f"✅ <b>Subscription confirmed!</b>\n\n"
        f"🌙 <b>Moon666</b> — Referral Program\n"
        f"Invite friends and earn USDT!\n\n"
        f"Choose an action:",
        reply_markup=main_menu_kb(),
        parse_mode="HTML",
    )

    schedule_onboarding(
        bot, user.id,
        settings.bonus_join,
        settings.bonus_reaction,
        settings.bonus_retention,
    )
```

- [ ] **Step 3: Verify bot starts without errors**

```bash
python -m bot.main
```

Expected: `Bot started` in logs, no import errors.

- [ ] **Step 4: Commit**

```bash
git add bot/middlewares/db.py bot/handlers/start.py
git commit -m "feat: ban middleware + user_id age check in referral flow"
```

---

## Task 3: Suspicious Activity Alert + Admin Callbacks

**Files:**
- Create: `bot/handlers/admin_callbacks.py`
- Modify: `bot/main.py`

- [ ] **Step 1: Create `bot/handlers/admin_callbacks.py`**

```python
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
```

- [ ] **Step 2: Register router in `bot/main.py`** — add import and include_router

Add to imports:
```python
from bot.handlers.admin_callbacks import router as admin_callbacks_router
```

Add inside `main()` after existing routers:
```python
dp.include_router(admin_callbacks_router)
```

- [ ] **Step 3: Test manually** — trigger 8+ referrals from one account and verify admin receives alert with inline buttons.

- [ ] **Step 4: Commit**

```bash
git add bot/handlers/admin_callbacks.py bot/main.py
git commit -m "feat: suspicious activity alert with bot-side ban/ignore callbacks"
```

---

## Task 4: Web Ban UI + User Detail Page

**Files:**
- Modify: `web/routes/users.py`
- Modify: `web/templates/users.html`
- Create: `web/templates/user_detail.html`

- [ ] **Step 1: Replace `web/routes/users.py`** with full version including ban endpoints, detail page, adjust balance, and send message:

```python
from decimal import Decimal
from datetime import datetime, timezone

from fastapi import APIRouter, Request, Depends, Query, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from pathlib import Path

from shared.database import get_session
from shared.models import User, Referral, Transaction, TransactionType, Withdrawal
from web.auth import get_current_admin
from web.notifications import send_telegram_notification

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


@router.get("/users", response_class=HTMLResponse)
async def users_page(
    request: Request,
    search: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
    _: bool = Depends(get_current_admin),
):
    query = (
        select(User, func.count(Referral.id).label("ref_count"))
        .outerjoin(Referral, Referral.referrer_id == User.id)
        .group_by(User.id)
        .order_by(func.count(Referral.id).desc())
    )
    if search:
        query = query.where(
            or_(
                User.username.ilike(f"%{search}%"),
                User.full_name.ilike(f"%{search}%"),
            )
        )
    result = await session.execute(query)
    users = result.all()
    return templates.TemplateResponse("users.html", {
        "request": request,
        "active": "users",
        "users": users,
        "search": search or "",
    })


@router.get("/users/export.csv")  # Must be BEFORE /users/{user_id}
async def export_users_csv(
    session: AsyncSession = Depends(get_session),
    _: bool = Depends(get_current_admin),
):
    import csv, io
    from fastapi.responses import StreamingResponse

    result = await session.execute(
        select(User, func.count(Referral.id).label("ref_count"))
        .outerjoin(Referral, Referral.referrer_id == User.id)
        .group_by(User.id)
        .order_by(User.joined_at.desc())
    )
    rows = result.all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "username", "full_name", "balance_usdt", "ref_count",
                     "joined_at", "channel_joined_at", "is_banned"])
    for user, ref_count in rows:
        writer.writerow([
            user.id, user.username or "", user.full_name or "",
            str(user.balance_usdt), ref_count,
            user.joined_at.isoformat() if user.joined_at else "",
            user.channel_joined_at.isoformat() if user.channel_joined_at else "",
            str(user.is_banned),
        ])
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=users.csv"},
    )


@router.get("/users/{user_id}", response_class=HTMLResponse)
async def user_detail_page(
    user_id: int,
    request: Request,
    session: AsyncSession = Depends(get_session),
    _: bool = Depends(get_current_admin),
):
    user = await session.get(User, user_id)
    if not user:
        return RedirectResponse(url="/users", status_code=302)

    refs_result = await session.execute(
        select(Referral, User)
        .join(User, User.id == Referral.referred_id)
        .where(Referral.referrer_id == user_id)
        .order_by(Referral.created_at.desc())
    )
    referrals = refs_result.all()

    txs_result = await session.execute(
        select(Transaction)
        .where(Transaction.user_id == user_id)
        .order_by(Transaction.created_at.desc())
        .limit(50)
    )
    transactions = txs_result.scalars().all()

    wds_result = await session.execute(
        select(Withdrawal)
        .where(Withdrawal.user_id == user_id)
        .order_by(Withdrawal.created_at.desc())
    )
    withdrawals = wds_result.scalars().all()

    total_earned = sum(
        t.amount_usdt for t in transactions
        if t.type in (TransactionType.referral_join,
                      TransactionType.referral_reaction,
                      TransactionType.referral_retention)
    )

    return templates.TemplateResponse("user_detail.html", {
        "request": request,
        "active": "users",
        "user": user,
        "referrals": referrals,
        "transactions": transactions,
        "withdrawals": withdrawals,
        "total_earned": total_earned,
    })


@router.post("/users/{user_id}/ban")
async def ban_user(
    user_id: int,
    session: AsyncSession = Depends(get_session),
    _: bool = Depends(get_current_admin),
):
    user = await session.get(User, user_id)
    if user:
        user.is_banned = True
        await session.commit()
    return RedirectResponse(url=f"/users/{user_id}", status_code=302)


@router.post("/users/{user_id}/unban")
async def unban_user(
    user_id: int,
    session: AsyncSession = Depends(get_session),
    _: bool = Depends(get_current_admin),
):
    user = await session.get(User, user_id)
    if user:
        user.is_banned = False
        await session.commit()
    return RedirectResponse(url=f"/users/{user_id}", status_code=302)


@router.post("/users/{user_id}/adjust")
async def adjust_balance(
    user_id: int,
    amount: Decimal = Form(...),
    session: AsyncSession = Depends(get_session),
    _: bool = Depends(get_current_admin),
):
    user = await session.get(User, user_id)
    if user:
        user.balance_usdt += amount
        session.add(Transaction(
            user_id=user_id,
            amount_usdt=amount,
            type=TransactionType.manual_adjustment,
        ))
        await session.commit()
    return RedirectResponse(url=f"/users/{user_id}", status_code=302)


@router.post("/users/{user_id}/message")
async def send_message_to_user(
    user_id: int,
    text: str = Form(...),
    _: bool = Depends(get_current_admin),
):
    await send_telegram_notification(user_id, text)
    return RedirectResponse(url=f"/users/{user_id}", status_code=302)
```

- [ ] **Step 2: Create `web/templates/user_detail.html`**

```html
{% extends "base.html" %}
{% block content %}

<div class="pg-head">
    <a href="/users" style="color:var(--text-3);text-decoration:none;font-size:13px;margin-right:8px">← Users</a>
    <div class="pg-ico">👤</div>
    <div>
        <div class="pg-title">@{{ user.username or '—' }}</div>
        <div style="font-size:12px;color:var(--text-2);margin-top:2px">{{ user.full_name or '' }} · ID: {{ user.id }}</div>
    </div>
    {% if user.is_banned %}
    <span class="badge" style="background:var(--red-dim);color:var(--red);margin-left:auto">🚫 Banned</span>
    {% endif %}
</div>

<!-- Stats row -->
<div class="kpi-grid" style="grid-template-columns:repeat(3,1fr)">
    <div class="kpi">
        <div class="kpi-lbl">Balance</div>
        <div class="kpi-val" style="color:var(--gold)">${{ "%.2f"|format(user.balance_usdt) }}</div>
        <div class="kpi-bg-ico">💰</div>
    </div>
    <div class="kpi">
        <div class="kpi-lbl">Referrals</div>
        <div class="kpi-val" style="color:var(--green)">{{ referrals|length }}</div>
        <div class="kpi-bg-ico">👥</div>
    </div>
    <div class="kpi">
        <div class="kpi-lbl">Total Earned</div>
        <div class="kpi-val" style="color:var(--purple)">${{ "%.2f"|format(total_earned) }}</div>
        <div class="kpi-bg-ico">📈</div>
    </div>
</div>

<!-- Actions -->
<div class="card" style="display:flex;gap:10px;flex-wrap:wrap;align-items:center">
    <div style="font-size:12px;font-weight:600;color:var(--text-2);margin-right:4px">Actions:</div>

    {% if user.is_banned %}
    <form method="post" action="/users/{{ user.id }}/unban">
        <button type="submit" class="btn btn-green">✅ Unban</button>
    </form>
    {% else %}
    <form method="post" action="/users/{{ user.id }}/ban"
          onsubmit="return confirm('Ban user @{{ user.username or user.id }}?')">
        <button type="submit" class="btn btn-red">🚫 Ban</button>
    </form>
    {% endif %}

    <form method="post" action="/users/{{ user.id }}/adjust"
          style="display:flex;gap:6px;align-items:center">
        <input type="number" name="amount" step="0.01" placeholder="±amount"
               style="width:110px" required>
        <button type="submit" class="btn btn-ghost">💰 Adjust Balance</button>
    </form>

    <form method="post" action="/users/{{ user.id }}/message"
          style="display:flex;gap:6px;align-items:center">
        <input type="text" name="text" placeholder="Message text…" style="width:220px" required>
        <button type="submit" class="btn btn-primary">📨 Send</button>
    </form>
</div>

<!-- Referrals -->
<div class="card" style="padding:0;overflow:hidden;margin-bottom:16px">
    <div style="padding:16px 20px;border-bottom:1px solid var(--border)">
        <span class="card-ttl">Referrals ({{ referrals|length }})</span>
    </div>
    {% if referrals %}
    <table>
        <thead><tr>
            <th>User</th><th>Date</th><th>Join</th><th>Reaction</th><th>30d</th>
        </tr></thead>
        <tbody>
        {% for ref, referred_user in referrals %}
        <tr>
            <td>@{{ referred_user.username or referred_user.full_name or ref.referred_id }}</td>
            <td style="color:var(--text-2);font-size:12px">{{ ref.created_at.strftime('%d.%m.%Y') }}</td>
            <td>{% if ref.join_bonus_paid %}<span style="color:var(--green)">✓</span>{% else %}<span style="color:var(--text-3)">—</span>{% endif %}</td>
            <td>{% if ref.reaction_bonus_paid %}<span style="color:var(--green)">✓</span>{% else %}<span style="color:var(--text-3)">—</span>{% endif %}</td>
            <td>{% if ref.retention_bonus_paid %}<span style="color:var(--green)">✓</span>{% else %}<span style="color:var(--text-3)">—</span>{% endif %}</td>
        </tr>
        {% endfor %}
        </tbody>
    </table>
    {% else %}
    <div class="empty"><div class="empty-ico">👥</div><div class="empty-txt">No referrals</div></div>
    {% endif %}
</div>

<!-- Transactions -->
<div class="card" style="padding:0;overflow:hidden;margin-bottom:16px">
    <div style="padding:16px 20px;border-bottom:1px solid var(--border)">
        <span class="card-ttl">Transactions (last 50)</span>
    </div>
    {% if transactions %}
    <table>
        <thead><tr><th>Date</th><th>Type</th><th>Amount</th></tr></thead>
        <tbody>
        {% for tx in transactions %}
        <tr>
            <td style="color:var(--text-2);font-size:12px">{{ tx.created_at.strftime('%d.%m.%Y %H:%M') }}</td>
            <td style="font-size:12px;color:var(--text-2)">{{ tx.type.value.replace('_', ' ') }}</td>
            <td style="color:{% if tx.amount_usdt >= 0 %}var(--green){% else %}var(--red){% endif %};font-weight:600">
                {{ '+' if tx.amount_usdt >= 0 else '' }}${{ "%.2f"|format(tx.amount_usdt) }}
            </td>
        </tr>
        {% endfor %}
        </tbody>
    </table>
    {% else %}
    <div class="empty"><div class="empty-ico">📋</div><div class="empty-txt">No transactions</div></div>
    {% endif %}
</div>

<!-- Withdrawals -->
<div class="card" style="padding:0;overflow:hidden">
    <div style="padding:16px 20px;border-bottom:1px solid var(--border)">
        <span class="card-ttl">Withdrawals</span>
    </div>
    {% if withdrawals %}
    <table>
        <thead><tr><th>Date</th><th>Amount</th><th>Wallet</th><th>Status</th></tr></thead>
        <tbody>
        {% for w in withdrawals %}
        <tr>
            <td style="color:var(--text-2);font-size:12px">{{ w.created_at.strftime('%d.%m.%Y') }}</td>
            <td style="color:var(--gold);font-weight:600">${{ "%.2f"|format(w.amount_usdt) }}</td>
            <td style="font-size:11px;color:var(--text-2)">{{ w.wallet_address[:20] }}…</td>
            <td>
                <span class="badge badge-{{ w.status.value }}">{{ w.status.value }}</span>
            </td>
        </tr>
        {% endfor %}
        </tbody>
    </table>
    {% else %}
    <div class="empty"><div class="empty-ico">📤</div><div class="empty-txt">No withdrawals</div></div>
    {% endif %}
</div>

{% endblock %}
```

- [ ] **Step 3: Update `web/templates/users.html`** — make rows clickable, add ban badge, add export button

Replace the file:

```html
{% extends "base.html" %}
{% block content %}

<div class="pg-head">
    <div class="pg-ico">👥</div>
    <div class="pg-title">Пользователи</div>
    <a href="/users/export.csv" class="btn btn-ghost" style="margin-left:auto;text-decoration:none">
        ⬇ Export CSV
    </a>
</div>

<form method="get" style="display:flex;gap:8px;margin-bottom:16px;align-items:center">
    <div style="position:relative;flex:1;max-width:340px">
        <span style="position:absolute;left:12px;top:50%;transform:translateY(-50%);font-size:14px;pointer-events:none">🔍</span>
        <input type="text" name="search" placeholder="Поиск по username или имени…"
               value="{{ search }}" style="width:100%;padding-left:36px">
    </div>
    <button type="submit" class="btn btn-primary">Найти</button>
    {% if search %}
    <a href="/users" class="btn btn-ghost" style="text-decoration:none">Сбросить</a>
    {% endif %}
</form>

<div class="card" style="padding:0;overflow:hidden">
    {% if users %}
    <table>
        <thead>
            <tr>
                <th>Пользователь</th>
                <th>Баланс</th>
                <th>Рефералов</th>
                <th>Дата вступления</th>
                <th>Подписан</th>
                <th>Статус</th>
            </tr>
        </thead>
        <tbody>
        {% for u, ref_count in users %}
        <tr style="cursor:pointer" onclick="window.location='/users/{{ u.id }}'">
            <td>
                <div style="font-weight:600">@{{ u.username or '—' }}</div>
                {% if u.full_name and u.full_name.lower() not in ['null', 'none', ''] and u.full_name != u.username %}
                <div style="font-size:11px;color:var(--text-3);margin-top:2px">{{ u.full_name }}</div>
                {% endif %}
            </td>
            <td><span style="color:var(--gold);font-weight:700">${{ "%.2f"|format(u.balance_usdt) }}</span></td>
            <td>
                {% if ref_count > 0 %}
                <span style="color:var(--green);font-weight:600">{{ ref_count }}</span>
                {% else %}
                <span style="color:var(--text-3)">0</span>
                {% endif %}
            </td>
            <td style="color:var(--text-2);font-size:12px">
                {{ u.joined_at.strftime('%d.%m.%Y') if u.joined_at else '—' }}
            </td>
            <td>
                {% if u.channel_joined_at %}
                <span class="badge" style="background:var(--green-dim);color:var(--green)">● Да</span>
                {% else %}
                <span class="badge" style="background:rgba(255,255,255,.03);color:var(--text-3)">○ Нет</span>
                {% endif %}
            </td>
            <td>
                {% if u.is_banned %}
                <span class="badge" style="background:var(--red-dim);color:var(--red)">🚫 Banned</span>
                {% else %}
                <span style="color:var(--text-3);font-size:12px">Active</span>
                {% endif %}
            </td>
        </tr>
        {% endfor %}
        </tbody>
    </table>
    {% else %}
    <div class="empty" style="padding:64px 24px">
        <div class="empty-ico">👤</div>
        <div class="empty-txt">{% if search %}Пользователи не найдены{% else %}Нет пользователей{% endif %}</div>
    </div>
    {% endif %}
</div>

{% endblock %}
```

- [ ] **Step 4: Commit**

```bash
git add web/routes/users.py web/templates/user_detail.html web/templates/users.html
git commit -m "feat: user detail page, ban/unban, adjust balance, send message, CSV export"
```

---

## Task 5: Campaign Manager

**Files:**
- Create: `web/routes/campaigns.py`
- Create: `web/templates/campaigns.html`
- Create: `web/templates/campaign_form.html`
- Modify: `web/main.py`
- Modify: `web/templates/base.html`
- Modify: `bot/services/referral.py`

- [ ] **Step 1: Create `web/routes/campaigns.py`**

```python
from datetime import datetime, timezone
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from decimal import Decimal
from pathlib import Path

from shared.database import get_session
from shared.models import Campaign, CampaignBonusType
from web.auth import get_current_admin

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


@router.get("/campaigns", response_class=HTMLResponse)
async def campaigns_page(
    request: Request,
    session: AsyncSession = Depends(get_session),
    _: bool = Depends(get_current_admin),
):
    result = await session.execute(select(Campaign).order_by(Campaign.starts_at.desc()))
    campaigns = result.scalars().all()
    now = datetime.now(timezone.utc)
    return templates.TemplateResponse("campaigns.html", {
        "request": request,
        "active": "campaigns",
        "campaigns": campaigns,
        "now": now,
    })


@router.get("/campaigns/new", response_class=HTMLResponse)
async def new_campaign_form(
    request: Request,
    _: bool = Depends(get_current_admin),
):
    return templates.TemplateResponse("campaign_form.html", {
        "request": request,
        "active": "campaigns",
        "campaign": None,
        "bonus_types": list(CampaignBonusType),
    })


@router.post("/campaigns")
async def create_campaign(
    name: str = Form(...),
    bonus_multiplier: Decimal = Form(...),
    applies_to: str = Form(...),
    starts_at: str = Form(...),
    ends_at: str = Form(...),
    session: AsyncSession = Depends(get_session),
    _: bool = Depends(get_current_admin),
):
    campaign = Campaign(
        name=name,
        bonus_multiplier=bonus_multiplier,
        applies_to=CampaignBonusType(applies_to),
        starts_at=datetime.fromisoformat(starts_at).replace(tzinfo=timezone.utc),
        ends_at=datetime.fromisoformat(ends_at).replace(tzinfo=timezone.utc),
    )
    session.add(campaign)
    await session.commit()
    return RedirectResponse(url="/campaigns", status_code=302)


@router.get("/campaigns/{campaign_id}/edit", response_class=HTMLResponse)
async def edit_campaign_form(
    campaign_id: int,
    request: Request,
    session: AsyncSession = Depends(get_session),
    _: bool = Depends(get_current_admin),
):
    campaign = await session.get(Campaign, campaign_id)
    if not campaign:
        return RedirectResponse(url="/campaigns", status_code=302)
    return templates.TemplateResponse("campaign_form.html", {
        "request": request,
        "active": "campaigns",
        "campaign": campaign,
        "bonus_types": list(CampaignBonusType),
    })


@router.post("/campaigns/{campaign_id}")
async def update_campaign(
    campaign_id: int,
    name: str = Form(...),
    bonus_multiplier: Decimal = Form(...),
    applies_to: str = Form(...),
    starts_at: str = Form(...),
    ends_at: str = Form(...),
    session: AsyncSession = Depends(get_session),
    _: bool = Depends(get_current_admin),
):
    campaign = await session.get(Campaign, campaign_id)
    if campaign:
        campaign.name = name
        campaign.bonus_multiplier = bonus_multiplier
        campaign.applies_to = CampaignBonusType(applies_to)
        campaign.starts_at = datetime.fromisoformat(starts_at).replace(tzinfo=timezone.utc)
        campaign.ends_at = datetime.fromisoformat(ends_at).replace(tzinfo=timezone.utc)
        await session.commit()
    return RedirectResponse(url="/campaigns", status_code=302)


@router.post("/campaigns/{campaign_id}/delete")
async def delete_campaign(
    campaign_id: int,
    session: AsyncSession = Depends(get_session),
    _: bool = Depends(get_current_admin),
):
    campaign = await session.get(Campaign, campaign_id)
    if campaign:
        await session.delete(campaign)
        await session.commit()
    return RedirectResponse(url="/campaigns", status_code=302)
```

- [ ] **Step 2: Create `web/templates/campaigns.html`**

```html
{% extends "base.html" %}
{% block content %}

<div class="pg-head">
    <div class="pg-ico">🎯</div>
    <div class="pg-title">Кампании</div>
    <a href="/campaigns/new" class="btn btn-primary" style="margin-left:auto;text-decoration:none">
        + Новая кампания
    </a>
</div>

<div class="card" style="padding:0;overflow:hidden">
    {% if campaigns %}
    <table>
        <thead>
            <tr>
                <th>Название</th>
                <th>Множитель</th>
                <th>Применяется к</th>
                <th>Старт</th>
                <th>Конец</th>
                <th>Статус</th>
                <th></th>
            </tr>
        </thead>
        <tbody>
        {% for c in campaigns %}
        <tr>
            <td style="font-weight:600">{{ c.name }}</td>
            <td style="color:var(--gold);font-weight:700">×{{ c.bonus_multiplier }}</td>
            <td style="color:var(--text-2);font-size:12px">{{ c.applies_to.value }}</td>
            <td style="color:var(--text-2);font-size:12px">{{ c.starts_at.strftime('%d.%m.%Y %H:%M') }}</td>
            <td style="color:var(--text-2);font-size:12px">{{ c.ends_at.strftime('%d.%m.%Y %H:%M') }}</td>
            <td>
                {% if now >= c.starts_at and now <= c.ends_at %}
                <span class="badge badge-approved">● Active</span>
                {% elif now < c.starts_at %}
                <span class="badge badge-pending">⏳ Upcoming</span>
                {% else %}
                <span class="badge" style="background:rgba(255,255,255,.03);color:var(--text-3)">Expired</span>
                {% endif %}
            </td>
            <td style="text-align:right">
                <a href="/campaigns/{{ c.id }}/edit" class="btn btn-ghost" style="text-decoration:none;font-size:11px">Edit</a>
                <form method="post" action="/campaigns/{{ c.id }}/delete" style="display:inline"
                      onsubmit="return confirm('Delete campaign {{ c.name }}?')">
                    <button type="submit" class="btn btn-red" style="font-size:11px">Delete</button>
                </form>
            </td>
        </tr>
        {% endfor %}
        </tbody>
    </table>
    {% else %}
    <div class="empty" style="padding:64px 24px">
        <div class="empty-ico">🎯</div>
        <div class="empty-txt">Нет кампаний. Создайте первую!</div>
    </div>
    {% endif %}
</div>

{% endblock %}
```

- [ ] **Step 3: Create `web/templates/campaign_form.html`**

```html
{% extends "base.html" %}
{% block content %}

<div class="pg-head">
    <a href="/campaigns" style="color:var(--text-3);text-decoration:none;font-size:13px;margin-right:8px">← Кампании</a>
    <div class="pg-ico">🎯</div>
    <div class="pg-title">{% if campaign %}Редактировать кампанию{% else %}Новая кампания{% endif %}</div>
</div>

<div class="card" style="max-width:520px">
    <form method="post"
          action="{% if campaign %}/campaigns/{{ campaign.id }}{% else %}/campaigns{% endif %}">

        <div style="margin-bottom:16px">
            <label style="display:block;font-size:12px;font-weight:600;color:var(--text-2);margin-bottom:6px">
                Название
            </label>
            <input type="text" name="name" required style="width:100%"
                   value="{{ campaign.name if campaign else '' }}"
                   placeholder="Weekend 2x">
        </div>

        <div style="margin-bottom:16px">
            <label style="display:block;font-size:12px;font-weight:600;color:var(--text-2);margin-bottom:6px">
                Множитель бонуса
            </label>
            <input type="number" name="bonus_multiplier" step="0.1" min="1" max="10" required style="width:100%"
                   value="{{ campaign.bonus_multiplier if campaign else '2.0' }}"
                   placeholder="2.0">
            <div style="font-size:11px;color:var(--text-3);margin-top:4px">
                2.0 = двойной бонус, 1.5 = +50%, и т.д.
            </div>
        </div>

        <div style="margin-bottom:16px">
            <label style="display:block;font-size:12px;font-weight:600;color:var(--text-2);margin-bottom:6px">
                Применяется к
            </label>
            <select name="applies_to" style="width:100%;background:var(--bg);border:1px solid var(--border);
                    color:var(--text);padding:8px 13px;border-radius:var(--r-sm);font-size:13px;font-family:inherit">
                {% for bt in bonus_types %}
                <option value="{{ bt.value }}"
                    {% if campaign and campaign.applies_to == bt %}selected{% endif %}>
                    {{ bt.value }}
                </option>
                {% endfor %}
            </select>
        </div>

        <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:16px">
            <div>
                <label style="display:block;font-size:12px;font-weight:600;color:var(--text-2);margin-bottom:6px">
                    Дата начала (UTC)
                </label>
                <input type="datetime-local" name="starts_at" required style="width:100%"
                       value="{{ campaign.starts_at.strftime('%Y-%m-%dT%H:%M') if campaign else '' }}">
            </div>
            <div>
                <label style="display:block;font-size:12px;font-weight:600;color:var(--text-2);margin-bottom:6px">
                    Дата конца (UTC)
                </label>
                <input type="datetime-local" name="ends_at" required style="width:100%"
                       value="{{ campaign.ends_at.strftime('%Y-%m-%dT%H:%M') if campaign else '' }}">
            </div>
        </div>

        <div style="display:flex;gap:10px">
            <button type="submit" class="btn btn-primary">
                {% if campaign %}Сохранить{% else %}Создать{% endif %}
            </button>
            <a href="/campaigns" class="btn btn-ghost" style="text-decoration:none">Отмена</a>
        </div>
    </form>
</div>

{% endblock %}
```

- [ ] **Step 4: Register campaigns router in `web/main.py`**

Add import:
```python
from web.routes import dashboard, analytics, withdrawals, users, settings as settings_route, campaigns
```

Add after existing routers:
```python
app.include_router(campaigns.router)
```

- [ ] **Step 5: Add Campaigns link to `web/templates/base.html`** sidebar

Find the line:
```html
        <div class="nav-section">Настройка</div>
```

Insert before it:
```html
        <a href="/campaigns" class="{% if active == 'campaigns' %}active{% endif %}">
            <span class="nav-ico">🎯</span> Кампании
        </a>
```

- [ ] **Step 6: Update `bot/services/referral.py`** — add campaign multiplier to `award_join_bonus` and `award_reaction_bonus`

Replace the entire file:

```python
from decimal import Decimal
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from shared.models import Referral, Transaction, TransactionType, User, Campaign, CampaignBonusType
from shared.config import settings


async def _credit(
    session: AsyncSession,
    referral: Referral,
    amount: Decimal,
    tx_type: TransactionType,
) -> None:
    """Mutate referrer balance and insert Transaction. Does NOT commit — caller commits."""
    referrer = await session.get(User, referral.referrer_id)
    if referrer is None:
        raise ValueError(f"Referrer {referral.referrer_id} not found")
    referrer.balance_usdt += amount
    session.add(Transaction(
        user_id=referral.referrer_id,
        amount_usdt=amount,
        type=tx_type,
        related_user_id=referral.referred_id,
    ))


async def _get_active_campaign(
    session: AsyncSession,
    bonus_type: CampaignBonusType,
) -> Optional[Campaign]:
    """Return the first active campaign matching the given bonus type, or None."""
    now = datetime.now(timezone.utc)
    result = await session.execute(
        select(Campaign).where(
            Campaign.starts_at <= now,
            Campaign.ends_at >= now,
            or_(
                Campaign.applies_to == CampaignBonusType.all,
                Campaign.applies_to == bonus_type,
            )
        ).limit(1)
    )
    return result.scalar_one_or_none()


async def award_join_bonus(
    session: AsyncSession,
    referral: Referral,
    bot=None,
) -> None:
    if referral.join_bonus_paid:
        return
    campaign = await _get_active_campaign(session, CampaignBonusType.join)
    multiplier = campaign.bonus_multiplier if campaign else Decimal("1")
    amount = settings.bonus_join * multiplier
    await _credit(session, referral, amount, TransactionType.referral_join)
    referral.join_bonus_paid = True
    await session.commit()
    if bot:
        from bot.services.achievements import check_and_award_achievements
        await check_and_award_achievements(session, referral.referrer_id, bot)


async def award_reaction_bonus(session: AsyncSession, referral: Referral) -> None:
    if referral.reaction_bonus_paid:
        return
    campaign = await _get_active_campaign(session, CampaignBonusType.reaction)
    multiplier = campaign.bonus_multiplier if campaign else Decimal("1")
    amount = settings.bonus_reaction * multiplier
    await _credit(session, referral, amount, TransactionType.referral_reaction)
    referral.reaction_bonus_paid = True
    await session.commit()


async def award_retention_bonus(session: AsyncSession, referral: Referral) -> None:
    if referral.retention_bonus_paid:
        return
    await _credit(session, referral, settings.bonus_retention, TransactionType.referral_retention)
    referral.retention_bonus_paid = True
    await session.commit()
```

- [ ] **Step 7: Commit**

```bash
git add web/routes/campaigns.py web/templates/campaigns.html web/templates/campaign_form.html \
        web/main.py web/templates/base.html bot/services/referral.py
git commit -m "feat: campaign manager (web CRUD + bot multiplier)"
```

---

## Task 6: CSV Export for Withdrawals

**Files:**
- Modify: `web/routes/withdrawals.py`
- Modify: `web/templates/withdrawals.html` (add export button)

- [ ] **Step 1: Add CSV export endpoint to `web/routes/withdrawals.py`**

Add this route after the existing imports and before `withdrawals_page`. Add imports at the top:
```python
import csv
import io
from fastapi.responses import StreamingResponse
```

Add route (insert before `@router.get("/withdrawals"`):
```python
@router.get("/withdrawals/export.csv")  # Must be BEFORE /withdrawals/{id}
async def export_withdrawals_csv(
    session: AsyncSession = Depends(get_session),
    _: bool = Depends(get_current_admin),
):
    result = await session.execute(
        select(Withdrawal, User)
        .join(User, User.id == Withdrawal.user_id)
        .order_by(Withdrawal.created_at.desc())
    )
    rows = result.all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "user_id", "username", "amount_usdt", "wallet_address",
                     "status", "created_at", "processed_at"])
    for w, user in rows:
        writer.writerow([
            w.id, w.user_id, user.username or "",
            str(w.amount_usdt), w.wallet_address,
            w.status.value,
            w.created_at.isoformat() if w.created_at else "",
            w.processed_at.isoformat() if w.processed_at else "",
        ])
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=withdrawals.csv"},
    )
```

- [ ] **Step 2: Add Export button to `web/templates/withdrawals.html`**

Find the `<div class="pg-head">` block and add the button. Replace:
```html
<div class="pg-head">
```
with:
```html
<div class="pg-head" style="display:flex;align-items:center;gap:13px">
```

Then add before the closing `</div>` of pg-head:
```html
    <a href="/withdrawals/export.csv" class="btn btn-ghost" style="margin-left:auto;text-decoration:none">
        ⬇ Export CSV
    </a>
```

- [ ] **Step 3: Commit**

```bash
git add web/routes/withdrawals.py web/templates/withdrawals.html
git commit -m "feat: CSV export for withdrawals"
```

---

## Task 7: Auto-Approval + Mobile Admin

**Files:**
- Modify: `bot/handlers/withdrawal.py`
- Modify: `web/templates/base.html`

- [ ] **Step 1: Add auto-approval to `bot/handlers/withdrawal.py`**

In `process_wallet_address`, replace the block after `session.add(withdrawal)` and before `await state.clear()`:

```python
    withdrawal = Withdrawal(
        user_id=user.id,
        amount_usdt=user.balance_usdt,
        wallet_address=wallet,
        status=WithdrawalStatus.pending,
    )
    session.add(withdrawal)
    await session.commit()
    await state.clear()

    # Auto-approve if amount is below the configured threshold
    if settings.auto_approve_below > 0 and withdrawal.amount_usdt <= settings.auto_approve_below:
        from datetime import timezone
        withdrawal.status = WithdrawalStatus.approved
        withdrawal.processed_at = datetime.now(timezone.utc)
        user.balance_usdt -= withdrawal.amount_usdt
        await session.commit()
        await message.answer(
            f"✅ Withdrawal of <b>{withdrawal.amount_usdt:.2f} USDT</b> was auto-approved!\n\n"
            f"Funds sent to: <code>{wallet}</code>",
            reply_markup=main_menu_kb(),
            parse_mode="HTML",
        )
        return

    # Notify admin about pending withdrawal
    try:
        await message.bot.send_message(
            settings.admin_tg_id,
            f"💸 <b>New Withdrawal Request!</b>\n\n"
            f"👤 @{user.username or user.full_name}\n"
            f"💰 {withdrawal.amount_usdt:.2f} USDT\n"
            f"💳 <code>{wallet}</code>\n\n"
            f"Request ID: #{withdrawal.id}",
            parse_mode="HTML",
        )
    except Exception:
        pass

    await message.answer(
        f"✅ Withdrawal request for <b>{withdrawal.amount_usdt:.2f} USDT</b> submitted!\n\n"
        f"Wallet: <code>{wallet}</code>\n\n"
        f"We'll process it within 24 hours.",
        reply_markup=main_menu_kb(),
        parse_mode="HTML",
    )
```

Also add `from datetime import datetime` to the imports at the top of the file.

- [ ] **Step 2: Add mobile CSS + hamburger to `web/templates/base.html`**

Find `</style>` (line ~304) and insert before it:

```css
        /* ─── MOBILE ──────────────────────────────── */
        .hamburger {
            display: none;
            background: var(--bg-card);
            border: 1px solid var(--border);
            color: var(--text);
            border-radius: var(--r-sm);
            padding: 6px 10px;
            font-size: 18px;
            cursor: pointer;
            margin-bottom: 18px;
        }
        @media (max-width: 768px) {
            .sidebar {
                position: fixed;
                left: 0; top: 0;
                height: 100vh;
                transform: translateX(-100%);
                transition: transform 0.25s ease;
                z-index: 1000;
                box-shadow: 4px 0 24px rgba(0,0,0,.5);
            }
            .sidebar.open { transform: translateX(0); }
            .main { width: 100%; padding: 16px; }
            .hamburger { display: block; }
            .kpi-grid { grid-template-columns: 1fr 1fr !important; }
            table { font-size: 12px; }
            thead th, td { padding: 10px 10px; }
            .pg-title { font-size: 17px; }
        }
```

Find `<div class="main">` and replace it with:

```html
<div class="main">
    <button class="hamburger" id="hamburger" onclick="toggleSidebar()">☰</button>
```

Add before `</body>`:

```html
<script>
function toggleSidebar() {
    document.querySelector('.sidebar').classList.toggle('open');
}
document.addEventListener('click', function(e) {
    var sidebar = document.querySelector('.sidebar');
    var hamburger = document.getElementById('hamburger');
    if (sidebar.classList.contains('open') && !sidebar.contains(e.target) && e.target !== hamburger) {
        sidebar.classList.remove('open');
    }
});
</script>
```

- [ ] **Step 3: Commit**

```bash
git add bot/handlers/withdrawal.py web/templates/base.html
git commit -m "feat: auto-approval for small withdrawals + mobile-responsive admin"
```

---

## Task 8: Referral Card Generator

**Files:**
- Modify: `requirements.txt`
- Modify: `bot/Dockerfile`
- Create: `bot/services/card_generator.py`
- Modify: `bot/handlers/cabinet.py`
- Modify: `bot/keyboards.py`

- [ ] **Step 1: Add Pillow to `requirements.txt`**

Add the line:
```
Pillow==10.3.0
```

- [ ] **Step 2: Install font package in `bot/Dockerfile`**

Replace:
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
```

With:
```dockerfile
FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
```

- [ ] **Step 3: Create `bot/services/card_generator.py`**

```python
import io
from PIL import Image, ImageDraw, ImageFont

_FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
]

_BG        = (11, 12, 16)
_CARD      = (17, 18, 25)
_GOLD      = (240, 185, 11)
_GREEN     = (14, 203, 129)
_TEXT      = (234, 236, 239)
_SUBTLE    = (132, 142, 156)
_BORDER    = (28, 30, 46)
_TETHER    = (38, 161, 123)


def _font(size: int) -> ImageFont.FreeTypeFont:
    for path in _FONT_PATHS:
        try:
            return ImageFont.truetype(path, size)
        except (IOError, OSError):
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def generate_card(username: str, ref_count: int, earned: float) -> bytes:
    """Generate a 800×400 PNG referral card and return as bytes."""
    W, H = 800, 400

    img = Image.new("RGB", (W, H), _BG)
    draw = ImageDraw.Draw(img)

    # Card background with gold border
    draw.rounded_rectangle([6, 6, W - 7, H - 7], radius=18, fill=_CARD, outline=_GOLD, width=2)

    # Header band
    draw.rounded_rectangle([6, 6, W - 7, 68], radius=18, fill=(20, 21, 30))
    draw.rectangle([6, 40, W - 7, 68], fill=(20, 21, 30))  # square bottom corners

    # Title
    draw.text((W // 2, 38), "MOON666 · REFERRAL PROGRAM", fill=_GOLD, font=_font(24), anchor="mm")

    # Crescent moon (left side, centred at 130, 225)
    cx, cy = 130, 225
    draw.ellipse([cx - 80, cy - 80, cx + 80, cy + 80], fill=_GOLD)
    draw.ellipse([cx - 35, cy - 100, cx + 105, cy + 60], fill=_CARD)  # cut-out

    # USDT coin inside crescent curve
    draw.ellipse([cx + 30, cy - 18, cx + 78, cy + 28], fill=_TETHER)
    draw.text((cx + 54, cy + 5), "T", fill=(255, 255, 255), font=_font(26), anchor="mm")

    # Vertical divider
    draw.line([(240, 88), (240, H - 30)], fill=_BORDER, width=1)

    # Username
    uname = f"@{username}" if not username.startswith("@") else username
    draw.text((520, 130), uname, fill=_TEXT, font=_font(26), anchor="mm")

    # Horizontal divider under username
    draw.line([(265, 165), (775, 165)], fill=_BORDER, width=1)

    # Vertical stat divider
    draw.line([(520, 175), (520, 345)], fill=_BORDER, width=1)

    # Referrals
    draw.text((390, 255), str(ref_count), fill=_GOLD, font=_font(56), anchor="mm")
    draw.text((390, 315), "REFERRALS", fill=_SUBTLE, font=_font(14), anchor="mm")

    # Earned
    draw.text((650, 255), f"${earned:.2f}", fill=_GREEN, font=_font(52), anchor="mm")
    draw.text((650, 315), "EARNED", fill=_SUBTLE, font=_font(14), anchor="mm")

    # Footer
    draw.line([(6, H - 52), (W - 7, H - 52)], fill=_BORDER, width=1)
    draw.text((W // 2, H - 28), "Earn USDT by inviting friends  ·  @moon666_bot",
              fill=_SUBTLE, font=_font(14), anchor="mm")

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
```

- [ ] **Step 4: Add 🎴 My Card button to `bot/keyboards.py`**

Replace `main_menu_kb`:
```python
def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 My Balance",    callback_data="cabinet")],
        [InlineKeyboardButton(text="👥 My Referrals",  callback_data="my_referrals")],
        [InlineKeyboardButton(text="🔗 My Link",       callback_data="my_link")],
        [InlineKeyboardButton(text="📤 Withdraw",      callback_data="withdrawal")],
        [InlineKeyboardButton(text="🏆 Top Referrers", callback_data="top_referrals")],
        [InlineKeyboardButton(text="🎴 My Card",       callback_data="my_card")],
    ])
```

- [ ] **Step 5: Add `/card` handler to `bot/handlers/cabinet.py`**

Add imports at top:
```python
from decimal import Decimal
from aiogram.types import BufferedInputFile
from shared.models import User, Referral, Transaction, TransactionType, UserAchievement, AchievementType
from bot.services.card_generator import generate_card
```

Add handler after `cb_top_referrals`:
```python
_ACH_EMOJI = {
    AchievementType.first_referral: "🌱",
    AchievementType.referrals_10:   "🔥",
    AchievementType.referrals_25:   "⚡",
    AchievementType.referrals_100:  "💎",
}


@router.callback_query(lambda c: c.data == "my_card")
async def cb_my_card(callback: CallbackQuery, session: AsyncSession) -> None:
    user = await session.get(User, callback.from_user.id)
    if not user:
        await callback.answer("Please send /start first")
        return

    ref_count_res = await session.execute(
        select(func.count()).where(Referral.referrer_id == user.id)
    )
    ref_count = ref_count_res.scalar() or 0

    earned_res = await session.execute(
        select(func.sum(Transaction.amount_usdt)).where(
            Transaction.user_id == user.id,
            Transaction.type.in_([
                TransactionType.referral_join,
                TransactionType.referral_reaction,
                TransactionType.referral_retention,
            ])
        )
    )
    earned = float(earned_res.scalar() or 0)

    username = user.username or user.full_name or str(user.id)

    try:
        img_bytes = generate_card(username, ref_count, earned)
        await callback.message.answer_photo(
            BufferedInputFile(img_bytes, filename="moon666_card.png"),
            caption=(
                f"🎴 <b>Your Referral Card</b>\n\n"
                f"Share this to invite friends and earn USDT!"
            ),
            parse_mode="HTML",
        )
    except Exception as e:
        await callback.message.answer(f"⚠️ Could not generate card: {e}")

    await callback.answer()
```

Also update `cb_cabinet` to show achievements. Find the `text = (...)` block and add an achievements line. First, fetch achievements at the start of the function:

After `total_earned = earned_result.scalar() or Decimal("0.00")`, add:
```python
    ach_res = await session.execute(
        select(UserAchievement).where(UserAchievement.user_id == user.id)
        .order_by(UserAchievement.achieved_at)
    )
    achievements = ach_res.scalars().all()
    ach_line = " ".join(_ACH_EMOJI.get(a.achievement_type, "🏅") for a in achievements) if achievements else "—"
```

Then add `f"🏅 Achievements: {ach_line}\n\n"` to the text string before `f"🔗 <code>{ref_link}</code>"`.

- [ ] **Step 6: Commit**

```bash
git add requirements.txt bot/Dockerfile bot/services/card_generator.py \
        bot/handlers/cabinet.py bot/keyboards.py
git commit -m "feat: referral card generator (Pillow) + achievements display in cabinet"
```

---

## Task 9: Achievement System

**Files:**
- Create: `bot/services/achievements.py`
- (referral.py already calls it — wired in Task 5, Step 6)

- [ ] **Step 1: Create `bot/services/achievements.py`**

```python
"""
Check and award achievement badges to a referrer.
Called from referral.award_join_bonus() after each confirmed join.
"""
import logging
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models import Referral, UserAchievement, AchievementType

logger = logging.getLogger(__name__)

# (min_referrals, achievement_type, notification_text)
_MILESTONES = [
    (
        1,
        AchievementType.first_referral,
        "🌱 <b>Achievement Unlocked: First Referral!</b>\n\n"
        "You invited your first person to the channel.\n"
        "Keep going — there's more USDT to earn! 🚀",
    ),
    (
        10,
        AchievementType.referrals_10,
        "🔥 <b>Achievement Unlocked: 10 Referrals!</b>\n\n"
        "You've invited 10 people. You're on fire!\n"
        "Next milestone: 25 referrals ⚡",
    ),
    (
        25,
        AchievementType.referrals_25,
        "⚡ <b>Achievement Unlocked: 25 Referrals!</b>\n\n"
        "25 people joined via your link. Seriously impressive!\n"
        "Next milestone: 100 referrals 💎",
    ),
    (
        100,
        AchievementType.referrals_100,
        "💎 <b>Achievement Unlocked: 100 Referrals!</b>\n\n"
        "100 people joined Moon666 via your link.\n"
        "You are a legend. 🏆",
    ),
]


async def check_and_award_achievements(
    session: AsyncSession,
    referrer_id: int,
    bot,
) -> None:
    """Check whether referrer has crossed any milestone and award unearned badges."""
    # Count referrals where the join bonus was paid (= confirmed referrals)
    total_res = await session.execute(
        select(func.count()).select_from(Referral).where(
            Referral.referrer_id == referrer_id,
            Referral.join_bonus_paid == True,
        )
    )
    total = total_res.scalar() or 0

    for threshold, ach_type, msg in _MILESTONES:
        if total < threshold:
            continue  # not reached yet

        existing = await session.execute(
            select(UserAchievement).where(
                UserAchievement.user_id == referrer_id,
                UserAchievement.achievement_type == ach_type,
            )
        )
        if existing.scalar_one_or_none():
            continue  # already awarded

        session.add(UserAchievement(user_id=referrer_id, achievement_type=ach_type))
        await session.commit()

        try:
            await bot.send_message(referrer_id, msg, parse_mode="HTML")
        except Exception as e:
            logger.warning("Could not send achievement notification to %s: %s", referrer_id, e)
```

- [ ] **Step 2: Verify the full import chain**

`referral.py` → `award_join_bonus()` → (lazy import) `from bot.services.achievements import check_and_award_achievements`

Run the bot and confirm no circular import errors:
```bash
python -m bot.main
```

Expected: `Bot started` with no `ImportError`.

- [ ] **Step 3: Commit**

```bash
git add bot/services/achievements.py
git commit -m "feat: achievement system — 4 milestones with Telegram notifications"
```

---

## Final: Push + Deploy

- [ ] **Push all commits to Railway**

```bash
git push
```

Railway will auto-redeploy the bot service. Migration runs on startup via `Base.metadata.create_all` — but for production, run:

```bash
railway run alembic upgrade head
```

- [ ] **Verify in Railway logs** — look for `Bot started` with no errors about missing columns

- [ ] **Smoke test checklist**
  - [ ] Banned user gets "You've been restricted" when sending /start
  - [ ] User detail page opens from /users table click
  - [ ] Ban/Unban button toggles correctly
  - [ ] Creating a campaign shows in list with correct Active/Upcoming status
  - [ ] Active campaign multiplies bonus (check transaction amount in DB)
  - [ ] CSV export downloads a valid file
  - [ ] `/card` (via My Card button) sends an image in bot
  - [ ] First referral → achievement notification fires
  - [ ] `auto_approve_below` set to 5 → withdrawal ≤ $5 auto-approved
  - [ ] Admin panel looks correct on mobile (hamburger opens sidebar)
