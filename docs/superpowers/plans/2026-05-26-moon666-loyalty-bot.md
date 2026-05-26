# Moon666 Loyalty Bot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Построить Telegram-бот с реферальной программой лояльности для канала Moon666 — подписчики зарабатывают USDT за рефералов и активность, владелец управляет выплатами через веб-панель.

**Architecture:** Два сервиса (aiogram бот + FastAPI веб-панель) с общей PostgreSQL БД. Бот обрабатывает пользователей и события канала. Веб-панель — только для владельца: аналитика, управление выплатами, настройки. Деплой через docker-compose.

**Tech Stack:** Python 3.12, aiogram 3.x, FastAPI, SQLAlchemy 2 async, asyncpg, PostgreSQL 16, Alembic, APScheduler, Jinja2, pytest + pytest-asyncio, docker-compose.

---

## Карта файлов

```
moon666_bot/
├── shared/
│   ├── config.py          # Settings из .env (pydantic-settings)
│   ├── database.py        # async engine + session factory
│   └── models.py          # все SQLAlchemy модели
├── bot/
│   ├── main.py            # aiogram App, dp, startup/shutdown
│   ├── keyboards.py       # все InlineKeyboardMarkup
│   ├── handlers/
│   │   ├── start.py       # /start + deep link + проверка подписки
│   │   ├── cabinet.py     # кабинет, баланс, рефералы, ссылка, топ
│   │   ├── withdrawal.py  # запрос на вывод (FSM)
│   │   └── reactions.py   # channel_post_reaction handler
│   └── services/
│       ├── referral.py    # award_join_bonus, award_reaction_bonus, award_retention_bonus
│       └── scheduler.py   # APScheduler job: retention check раз в час
├── web/
│   ├── main.py            # FastAPI app, роутеры, lifespan
│   ├── auth.py            # JWT login/logout, get_current_admin dep
│   ├── notifications.py   # send_telegram_notification(user_id, text)
│   ├── routes/
│   │   ├── dashboard.py   # GET / — KPI + growth chart
│   │   ├── analytics.py   # GET /analytics — retention, bonus breakdown, top
│   │   ├── withdrawals.py # GET/POST /withdrawals — список + approve/reject
│   │   ├── users.py       # GET /users — список + поиск
│   │   └── settings.py    # GET/POST /settings — бонусы, порог, welcome text
│   └── templates/
│       ├── base.html      # layout: sidebar + dark theme
│       ├── login.html
│       ├── dashboard.html
│       ├── analytics.html
│       ├── withdrawals.html
│       ├── users.html
│       └── settings.html
├── tests/
│   ├── conftest.py        # pytest fixtures: db session, bot mock
│   ├── test_referral.py   # unit tests для referral.py
│   ├── test_start.py      # handler tests
│   ├── test_withdrawal.py # handler tests
│   └── test_web.py        # FastAPI route tests
├── alembic/
│   ├── env.py
│   └── versions/
│       └── 001_initial.py
├── docker-compose.yml
├── bot/Dockerfile
├── web/Dockerfile
├── .env.example
└── requirements.txt
```

---

## Task 1: Scaffold проекта и зависимости

**Files:**
- Create: `moon666_bot/requirements.txt`
- Create: `moon666_bot/.env.example`
- Create: `moon666_bot/shared/config.py`

- [ ] **Шаг 1: Создать корневую директорию и requirements.txt**

```bash
mkdir -p moon666_bot/shared moon666_bot/bot/handlers moon666_bot/bot/services
mkdir -p moon666_bot/web/routes moon666_bot/web/templates
mkdir -p moon666_bot/tests moon666_bot/alembic/versions
```

Создать `moon666_bot/requirements.txt`:
```
aiogram==3.7.0
fastapi==0.111.0
uvicorn[standard]==0.29.0
sqlalchemy[asyncio]==2.0.30
asyncpg==0.29.0
alembic==1.13.1
apscheduler==3.10.4
pydantic-settings==2.2.1
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
jinja2==3.1.4
python-multipart==0.0.9
httpx==0.27.0
pytest==8.2.0
pytest-asyncio==0.23.6
aiosqlite==0.20.0
```

- [ ] **Шаг 2: Создать .env.example**

Создать `moon666_bot/.env.example`:
```env
# Telegram
BOT_TOKEN=7123456789:AAxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
CHANNEL_ID=-1001234567890
ADMIN_TG_ID=123456789

# Web admin
ADMIN_LOGIN=admin
ADMIN_PASSWORD=changeme
JWT_SECRET=change-this-secret-key

# Database
DATABASE_URL=postgresql+asyncpg://moon666:moon666pass@postgres:5432/moon666
DATABASE_URL_SYNC=postgresql://moon666:moon666pass@postgres:5432/moon666

# Bonus amounts (USDT)
BONUS_JOIN=0.20
BONUS_REACTION=0.01
BONUS_RETENTION=0.05
MIN_WITHDRAWAL=10.00
```

- [ ] **Шаг 3: Создать shared/config.py**

Создать `moon666_bot/shared/config.py`:
```python
from pydantic_settings import BaseSettings
from decimal import Decimal


class Settings(BaseSettings):
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

    class Config:
        env_file = ".env"


settings = Settings()
```

- [ ] **Шаг 4: Создать __init__.py во всех пакетах**

```bash
touch moon666_bot/shared/__init__.py
touch moon666_bot/bot/__init__.py
touch moon666_bot/bot/handlers/__init__.py
touch moon666_bot/bot/services/__init__.py
touch moon666_bot/web/__init__.py
touch moon666_bot/web/routes/__init__.py
touch moon666_bot/tests/__init__.py
```

- [ ] **Шаг 5: Установить зависимости**

```bash
cd moon666_bot
pip install -r requirements.txt
```

Ожидаем: все пакеты устанавливаются без ошибок.

- [ ] **Шаг 6: Commit**

```bash
git add moon666_bot/
git commit -m "chore: scaffold moon666 bot project structure"
```

---

## Task 2: Модели БД и database setup

**Files:**
- Create: `moon666_bot/shared/models.py`
- Create: `moon666_bot/shared/database.py`

- [ ] **Шаг 1: Написать тест для импорта моделей**

Создать `moon666_bot/tests/conftest.py`:
```python
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from shared.models import Base


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
```

Создать `moon666_bot/tests/test_models.py`:
```python
import pytest
from shared.models import User, Referral, Transaction, Withdrawal, ChannelReaction


def test_models_importable():
    assert User is not None
    assert Referral is not None
    assert Transaction is not None
    assert Withdrawal is not None
    assert ChannelReaction is not None
```

- [ ] **Шаг 2: Запустить тест — убедиться что FAIL**

```bash
cd moon666_bot
pytest tests/test_models.py -v
```

Ожидаем: `ModuleNotFoundError: No module named 'shared.models'`

- [ ] **Шаг 3: Создать shared/models.py**

Создать `moon666_bot/shared/models.py`:
```python
import enum
from decimal import Decimal
from datetime import datetime
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


class WithdrawalStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # Telegram user_id
    username: Mapped[str | None] = mapped_column(String(64))
    full_name: Mapped[str] = mapped_column(String(256))
    referred_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    balance_usdt: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    channel_joined_at: Mapped[datetime | None] = mapped_column(DateTime)

    referrals_made: Mapped[list["Referral"]] = relationship(
        "Referral", foreign_keys="Referral.referrer_id", back_populates="referrer"
    )
    transactions: Mapped[list["Transaction"]] = relationship("Transaction", back_populates="user")
    withdrawals: Mapped[list["Withdrawal"]] = relationship("Withdrawal", back_populates="user")


class Referral(Base):
    __tablename__ = "referrals"

    id: Mapped[int] = mapped_column(primary_key=True)
    referrer_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    referred_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), unique=True)
    join_bonus_paid: Mapped[bool] = mapped_column(Boolean, default=False)
    reaction_bonus_paid: Mapped[bool] = mapped_column(Boolean, default=False)
    retention_bonus_paid: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    referrer: Mapped["User"] = relationship("User", foreign_keys=[referrer_id], back_populates="referrals_made")
    referred: Mapped["User"] = relationship("User", foreign_keys=[referred_id])


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    amount_usdt: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    type: Mapped[TransactionType] = mapped_column(SAEnum(TransactionType))
    related_user_id: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    processed_at: Mapped[datetime | None] = mapped_column(DateTime)

    user: Mapped["User"] = relationship("User", back_populates="withdrawals")


class ChannelReaction(Base):
    __tablename__ = "channel_reactions"
    __table_args__ = (UniqueConstraint("user_id", name="uq_channel_reactions_user"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    post_id: Mapped[int] = mapped_column(BigInteger)
    reacted_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
```

- [ ] **Шаг 4: Создать shared/database.py**

Создать `moon666_bot/shared/database.py`:
```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from shared.config import settings

engine = create_async_engine(settings.database_url, echo=False)
async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncSession:
    async with async_session_maker() as session:
        yield session
```

- [ ] **Шаг 5: Запустить тесты — убедиться что PASS**

```bash
cd moon666_bot
pytest tests/test_models.py -v
```

Ожидаем: `PASSED tests/test_models.py::test_models_importable`

- [ ] **Шаг 6: Commit**

```bash
git add moon666_bot/shared/
git add moon666_bot/tests/
git commit -m "feat: add SQLAlchemy models and database setup"
```

---

## Task 3: Alembic миграции

**Files:**
- Create: `moon666_bot/alembic.ini`
- Create: `moon666_bot/alembic/env.py`
- Create: `moon666_bot/alembic/versions/001_initial.py`

- [ ] **Шаг 1: Инициализировать Alembic**

```bash
cd moon666_bot
alembic init alembic
```

- [ ] **Шаг 2: Настроить alembic/env.py**

Заменить содержимое `moon666_bot/alembic/env.py`:
```python
import asyncio
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context
from shared.models import Base
from shared.config import settings

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url_sync)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Шаг 3: Создать первую миграцию**

```bash
cd moon666_bot
alembic revision --autogenerate -m "initial"
```

Ожидаем: создан файл `alembic/versions/xxxx_initial.py` с таблицами users, referrals, transactions, withdrawals, channel_reactions.

- [ ] **Шаг 4: Commit**

```bash
git add moon666_bot/alembic/
git add moon666_bot/alembic.ini
git commit -m "feat: add alembic migrations"
```

---

## Task 4: Referral сервис (бизнес-логика)

**Files:**
- Create: `moon666_bot/bot/services/referral.py`
- Create: `moon666_bot/tests/test_referral.py`

- [ ] **Шаг 1: Написать тесты для referral сервиса**

Создать `moon666_bot/tests/test_referral.py`:
```python
import pytest
import pytest_asyncio
from decimal import Decimal
from sqlalchemy import select
from shared.models import User, Referral, Transaction, TransactionType
from bot.services.referral import award_join_bonus, award_reaction_bonus, award_retention_bonus


@pytest_asyncio.fixture
async def two_users(db_session):
    referrer = User(id=1001, full_name="Referrer", balance_usdt=Decimal("0.00"))
    referred = User(id=1002, full_name="Referred", balance_usdt=Decimal("0.00"))
    db_session.add_all([referrer, referred])
    await db_session.commit()

    ref = Referral(referrer_id=1001, referred_id=1002)
    db_session.add(ref)
    await db_session.commit()
    return referrer, referred, ref


@pytest.mark.asyncio
async def test_award_join_bonus_credits_referrer(db_session, two_users):
    referrer, referred, ref = two_users
    await award_join_bonus(db_session, referral=ref)

    await db_session.refresh(referrer)
    assert referrer.balance_usdt == Decimal("0.20")
    assert ref.join_bonus_paid is True


@pytest.mark.asyncio
async def test_award_join_bonus_not_paid_twice(db_session, two_users):
    referrer, referred, ref = two_users
    await award_join_bonus(db_session, referral=ref)
    await award_join_bonus(db_session, referral=ref)  # второй вызов

    await db_session.refresh(referrer)
    assert referrer.balance_usdt == Decimal("0.20")  # не задвоилось


@pytest.mark.asyncio
async def test_award_reaction_bonus(db_session, two_users):
    referrer, referred, ref = two_users
    await award_reaction_bonus(db_session, referral=ref)

    await db_session.refresh(referrer)
    assert referrer.balance_usdt == Decimal("0.01")
    assert ref.reaction_bonus_paid is True


@pytest.mark.asyncio
async def test_award_retention_bonus(db_session, two_users):
    referrer, referred, ref = two_users
    await award_retention_bonus(db_session, referral=ref)

    await db_session.refresh(referrer)
    assert referrer.balance_usdt == Decimal("0.05")
    assert ref.retention_bonus_paid is True


@pytest.mark.asyncio
async def test_transaction_created_on_bonus(db_session, two_users):
    referrer, referred, ref = two_users
    await award_join_bonus(db_session, referral=ref)

    result = await db_session.execute(
        select(Transaction).where(Transaction.user_id == 1001)
    )
    tx = result.scalar_one()
    assert tx.amount_usdt == Decimal("0.20")
    assert tx.type == TransactionType.referral_join
    assert tx.related_user_id == 1002
```

- [ ] **Шаг 2: Запустить тесты — убедиться что FAIL**

```bash
cd moon666_bot
pytest tests/test_referral.py -v
```

Ожидаем: `ModuleNotFoundError: No module named 'bot.services.referral'`

- [ ] **Шаг 3: Создать bot/services/referral.py**

Создать `moon666_bot/bot/services/referral.py`:
```python
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from shared.models import Referral, Transaction, TransactionType, User
from shared.config import settings


async def _credit(
    session: AsyncSession,
    referral: Referral,
    amount: Decimal,
    tx_type: TransactionType,
) -> None:
    referrer = await session.get(User, referral.referrer_id)
    referrer.balance_usdt += amount
    session.add(
        Transaction(
            user_id=referral.referrer_id,
            amount_usdt=amount,
            type=tx_type,
            related_user_id=referral.referred_id,
        )
    )
    await session.commit()


async def award_join_bonus(session: AsyncSession, referral: Referral) -> None:
    if referral.join_bonus_paid:
        return
    await _credit(session, referral, settings.bonus_join, TransactionType.referral_join)
    referral.join_bonus_paid = True
    await session.commit()


async def award_reaction_bonus(session: AsyncSession, referral: Referral) -> None:
    if referral.reaction_bonus_paid:
        return
    await _credit(session, referral, settings.bonus_reaction, TransactionType.referral_reaction)
    referral.reaction_bonus_paid = True
    await session.commit()


async def award_retention_bonus(session: AsyncSession, referral: Referral) -> None:
    if referral.retention_bonus_paid:
        return
    await _credit(session, referral, settings.bonus_retention, TransactionType.referral_retention)
    referral.retention_bonus_paid = True
    await session.commit()
```

- [ ] **Шаг 4: Запустить тесты — убедиться что PASS**

```bash
cd moon666_bot
pytest tests/test_referral.py -v
```

Ожидаем: все 5 тестов PASSED.

- [ ] **Шаг 5: Commit**

```bash
git add moon666_bot/bot/services/referral.py moon666_bot/tests/test_referral.py
git commit -m "feat: referral bonus service with tests"
```

---

## Task 5: Bot — /start handler и реферальный flow

**Files:**
- Create: `moon666_bot/bot/handlers/start.py`
- Create: `moon666_bot/bot/keyboards.py`
- Create: `moon666_bot/tests/test_start.py`

- [ ] **Шаг 1: Создать keyboards.py**

Создать `moon666_bot/bot/keyboards.py`:
```python
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
```

- [ ] **Шаг 2: Написать тест для start handler**

Создать `moon666_bot/tests/test_start.py`:
```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from decimal import Decimal
from sqlalchemy import select
from shared.models import User, Referral
from bot.handlers.start import cmd_start, callback_check_subscription


@pytest.mark.asyncio
async def test_new_user_created_on_start(db_session):
    message = AsyncMock()
    message.from_user.id = 2001
    message.from_user.username = "newuser"
    message.from_user.full_name = "New User"

    with patch("bot.handlers.start.get_session", return_value=db_session):
        await cmd_start(message, command=MagicMock(args=None), session=db_session)

    result = await db_session.execute(select(User).where(User.id == 2001))
    user = result.scalar_one_or_none()
    assert user is not None
    assert user.username == "newuser"


@pytest.mark.asyncio
async def test_referral_recorded_on_start(db_session):
    referrer = User(id=3001, full_name="Referrer", balance_usdt=Decimal("0.00"))
    db_session.add(referrer)
    await db_session.commit()

    message = AsyncMock()
    message.from_user.id = 3002
    message.from_user.username = "referred"
    message.from_user.full_name = "Referred User"

    with patch("bot.handlers.start.get_session", return_value=db_session):
        await cmd_start(message, command=MagicMock(args="3001"), session=db_session)

    result = await db_session.execute(
        select(Referral).where(Referral.referred_id == 3002)
    )
    ref = result.scalar_one_or_none()
    assert ref is not None
    assert ref.referrer_id == 3001
```

- [ ] **Шаг 3: Запустить — убедиться что FAIL**

```bash
cd moon666_bot
pytest tests/test_start.py -v
```

Ожидаем: `ModuleNotFoundError: No module named 'bot.handlers.start'`

- [ ] **Шаг 4: Создать bot/handlers/start.py**

Создать `moon666_bot/bot/handlers/start.py`:
```python
from aiogram import Router, Bot
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandObject
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models import User, Referral
from shared.database import get_session
from shared.config import settings
from bot.keyboards import main_menu_kb, check_subscription_kb
from bot.services.referral import award_join_bonus

router = Router()


async def get_or_create_user(session: AsyncSession, tg_user) -> tuple[User, bool]:
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


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject, session: AsyncSession):
    user, is_new = await get_or_create_user(session, message.from_user)

    # Если передан реферальный код и пользователь новый
    if is_new and command.args:
        try:
            referrer_id = int(command.args)
            referrer = await session.get(User, referrer_id)
            if referrer and referrer_id != user.id:
                user.referred_by = referrer_id
                ref = Referral(referrer_id=referrer_id, referred_id=user.id)
                session.add(ref)
                await session.commit()
        except (ValueError, TypeError):
            pass

    # Проверяем подписку на канал
    bot: Bot = message.bot
    try:
        member = await bot.get_chat_member(settings.channel_id, user.id)
        if member.status in ("member", "administrator", "creator"):
            await _on_subscription_confirmed(message, session, user, bot)
            return
    except Exception:
        pass

    bot_me = await bot.get_me()
    await message.answer(
        "🌙 Добро пожаловать в Moon666!\n\n"
        "Чтобы участвовать в реферальной программе, подпишись на канал:",
        reply_markup=check_subscription_kb(bot_me.username),
    )


@router.callback_query(lambda c: c.data == "check_subscription")
async def callback_check_subscription(callback: CallbackQuery, session: AsyncSession):
    user = await session.get(User, callback.from_user.id)
    if not user:
        await callback.answer("Сначала напиши /start", show_alert=True)
        return

    bot: Bot = callback.bot
    try:
        member = await bot.get_chat_member(settings.channel_id, user.id)
        if member.status not in ("member", "administrator", "creator"):
            await callback.answer("Ты ещё не подписан на канал 😕", show_alert=True)
            return
    except Exception:
        await callback.answer("Не удалось проверить. Попробуй позже.", show_alert=True)
        return

    await callback.message.delete()
    await _on_subscription_confirmed(callback.message, session, user, bot)
    await callback.answer()


async def _on_subscription_confirmed(message: Message, session: AsyncSession, user: User, bot: Bot):
    from datetime import datetime, timezone

    if not user.channel_joined_at:
        user.channel_joined_at = datetime.now(timezone.utc)
        await session.commit()

    # Начисляем бонус рефереру если есть
    if user.referred_by:
        result = await session.execute(
            select(Referral).where(Referral.referred_id == user.id)
        )
        ref = result.scalar_one_or_none()
        if ref:
            await award_join_bonus(session, ref)
            # Уведомляем реферера
            try:
                await bot.send_message(
                    ref.referrer_id,
                    f"🎉 По твоей ссылке подписался новый человек!\n"
                    f"💰 +{settings.bonus_join} USDT начислено на баланс.",
                )
            except Exception:
                pass

    await message.answer(
        f"✅ Подписка подтверждена!\n\n"
        f"🌙 <b>Moon666</b> — реферальная программа\n"
        f"Приглашай друзей и зарабатывай USDT!\n\n"
        f"Выбери действие:",
        reply_markup=main_menu_kb(),
        parse_mode="HTML",
    )
```

- [ ] **Шаг 5: Запустить тесты — убедиться что PASS**

```bash
cd moon666_bot
pytest tests/test_start.py -v
```

Ожидаем: 2 теста PASSED.

- [ ] **Шаг 6: Commit**

```bash
git add moon666_bot/bot/handlers/start.py moon666_bot/bot/keyboards.py moon666_bot/tests/test_start.py
git commit -m "feat: /start handler with referral tracking and subscription check"
```

---

## Task 6: Bot — кабинет, рефералы, ссылка, топ

**Files:**
- Create: `moon666_bot/bot/handlers/cabinet.py`

- [ ] **Шаг 1: Создать bot/handlers/cabinet.py**

Создать `moon666_bot/bot/handlers/cabinet.py`:
```python
from aiogram import Router
from aiogram.types import CallbackQuery
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from decimal import Decimal

from shared.models import User, Referral, Transaction
from shared.config import settings
from bot.keyboards import main_menu_kb

router = Router()

WITHDRAWAL_TARGET = settings.min_withdrawal


def _progress_bar(balance: Decimal, target: Decimal, width: int = 10) -> str:
    pct = min(float(balance / target), 1.0)
    filled = int(pct * width)
    bar = "█" * filled + "░" * (width - filled)
    return f"{bar} {int(pct * 100)}%"


@router.callback_query(lambda c: c.data == "cabinet")
async def cb_cabinet(callback: CallbackQuery, session: AsyncSession):
    user = await session.get(User, callback.from_user.id)
    if not user:
        await callback.answer("Сначала напиши /start")
        return

    # Считаем рефералов и заработок
    ref_count_result = await session.execute(
        select(func.count()).where(Referral.referrer_id == user.id)
    )
    ref_count = ref_count_result.scalar() or 0

    earned_result = await session.execute(
        select(func.sum(Transaction.amount_usdt)).where(Transaction.user_id == user.id)
    )
    total_earned = earned_result.scalar() or Decimal("0.00")

    balance = user.balance_usdt
    progress = _progress_bar(balance, WITHDRAWAL_TARGET)
    remaining = max(WITHDRAWAL_TARGET - balance, Decimal("0.00"))

    bot_me = await callback.bot.get_me()
    ref_link = f"https://t.me/{bot_me.username}?start={user.id}"

    text = (
        f"🌙 <b>Moon666</b> · @{user.username or user.full_name}\n\n"
        f"┌─────────────────────────┐\n"
        f"│  <b>{balance:.2f} USDT</b>\n"
        f"│  {progress}\n"
        f"│  До вывода: {remaining:.2f} USDT\n"
        f"└─────────────────────────┘\n\n"
        f"👥 {ref_count} рефералов · 💰 заработано {total_earned:.2f} USDT\n\n"
        f"🔗 <code>{ref_link}</code>"
    )
    await callback.message.edit_text(text, reply_markup=main_menu_kb(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(lambda c: c.data == "my_referrals")
async def cb_my_referrals(callback: CallbackQuery, session: AsyncSession):
    result = await session.execute(
        select(Referral, User)
        .join(User, User.id == Referral.referred_id)
        .where(Referral.referrer_id == callback.from_user.id)
        .order_by(Referral.created_at.desc())
        .limit(20)
    )
    rows = result.all()

    if not rows:
        text = "👥 У тебя пока нет рефералов.\n\nПоделись своей ссылкой!"
    else:
        lines = ["👥 <b>Мои рефералы:</b>\n"]
        for ref, referred_user in rows:
            earned = Decimal("0.00")
            if ref.join_bonus_paid:
                earned += settings.bonus_join
            if ref.reaction_bonus_paid:
                earned += settings.bonus_reaction
            if ref.retention_bonus_paid:
                earned += settings.bonus_retention
            name = f"@{referred_user.username}" if referred_user.username else referred_user.full_name
            lines.append(f"• {name} — +{earned:.2f} USDT")
        text = "\n".join(lines)

    await callback.message.edit_text(text, reply_markup=main_menu_kb(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(lambda c: c.data == "my_link")
async def cb_my_link(callback: CallbackQuery):
    bot_me = await callback.bot.get_me()
    ref_link = f"https://t.me/{bot_me.username}?start={callback.from_user.id}"
    text = (
        f"🔗 <b>Твоя реферальная ссылка:</b>\n\n"
        f"<code>{ref_link}</code>\n\n"
        f"Поделись с друзьями! За каждого подписчика:\n"
        f"• +{settings.bonus_join} USDT — подписался\n"
        f"• +{settings.bonus_reaction} USDT — поставил реакцию\n"
        f"• +{settings.bonus_retention} USDT — остался 30 дней\n\n"
        f"Максимум <b>{settings.bonus_join + settings.bonus_reaction + settings.bonus_retention:.2f} USDT</b> с одного человека"
    )
    await callback.message.edit_text(text, reply_markup=main_menu_kb(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(lambda c: c.data == "top_referrals")
async def cb_top_referrals(callback: CallbackQuery, session: AsyncSession):
    result = await session.execute(
        select(User.username, User.full_name, func.count(Referral.id).label("cnt"))
        .join(Referral, Referral.referrer_id == User.id)
        .group_by(User.id, User.username, User.full_name)
        .order_by(func.count(Referral.id).desc())
        .limit(10)
    )
    rows = result.all()

    medals = ["🥇", "🥈", "🥉"] + ["🏅"] * 7
    lines = ["🏆 <b>Топ рефереров:</b>\n"]
    for i, (username, full_name, cnt) in enumerate(rows):
        name = f"@{username}" if username else full_name
        lines.append(f"{medals[i]} {name} — {cnt} реф.")

    if not rows:
        lines.append("Пока никого нет. Будь первым!")

    await callback.message.edit_text(
        "\n".join(lines), reply_markup=main_menu_kb(), parse_mode="HTML"
    )
    await callback.answer()
```

- [ ] **Шаг 2: Проверить импорт**

```bash
cd moon666_bot
python -c "from bot.handlers.cabinet import router; print('OK')"
```

Ожидаем: `OK`

- [ ] **Шаг 3: Commit**

```bash
git add moon666_bot/bot/handlers/cabinet.py
git commit -m "feat: cabinet handlers - balance, referrals, link, top"
```

---

## Task 7: Bot — вывод средств (FSM)

**Files:**
- Create: `moon666_bot/bot/handlers/withdrawal.py`
- Create: `moon666_bot/tests/test_withdrawal.py`

- [ ] **Шаг 1: Написать тест**

Создать `moon666_bot/tests/test_withdrawal.py`:
```python
import pytest
from decimal import Decimal
from sqlalchemy import select
from shared.models import User, Withdrawal, WithdrawalStatus
from bot.handlers.withdrawal import process_wallet_address


@pytest.mark.asyncio
async def test_withdrawal_created(db_session):
    user = User(id=5001, full_name="Rich User", balance_usdt=Decimal("15.00"))
    db_session.add(user)
    await db_session.commit()

    message_mock = __import__("unittest.mock", fromlist=["AsyncMock"]).AsyncMock()
    message_mock.from_user.id = 5001
    message_mock.text = "TQn8ixxxxxxxxxxxxxxxxxxxxxxxx3kF2"

    state_mock = __import__("unittest.mock", fromlist=["AsyncMock"]).AsyncMock()
    state_mock.get_data = __import__("unittest.mock", fromlist=["AsyncMock"]).AsyncMock(return_value={})

    await process_wallet_address(message_mock, state_mock, session=db_session)

    result = await db_session.execute(
        select(Withdrawal).where(Withdrawal.user_id == 5001)
    )
    w = result.scalar_one_or_none()
    assert w is not None
    assert w.status == WithdrawalStatus.pending
    assert w.wallet_address == "TQn8ixxxxxxxxxxxxxxxxxxxxxxxx3kF2"
```

- [ ] **Шаг 2: Запустить — убедиться что FAIL**

```bash
cd moon666_bot
pytest tests/test_withdrawal.py -v
```

- [ ] **Шаг 3: Создать bot/handlers/withdrawal.py**

Создать `moon666_bot/bot/handlers/withdrawal.py`:
```python
from aiogram import Router
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models import User, Withdrawal, WithdrawalStatus
from shared.config import settings
from bot.keyboards import main_menu_kb

router = Router()


class WithdrawalForm(StatesGroup):
    waiting_wallet = State()


@router.callback_query(lambda c: c.data == "withdrawal")
async def cb_withdrawal(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    user = await session.get(User, callback.from_user.id)
    if not user:
        await callback.answer("Сначала напиши /start")
        return

    if user.balance_usdt < settings.min_withdrawal:
        remaining = settings.min_withdrawal - user.balance_usdt
        await callback.answer(
            f"Минимальная сумма для вывода: {settings.min_withdrawal} USDT\n"
            f"Тебе не хватает ещё {remaining:.2f} USDT",
            show_alert=True,
        )
        return

    await state.set_state(WithdrawalForm.waiting_wallet)
    await callback.message.answer(
        f"💳 Введи адрес кошелька для вывода <b>{user.balance_usdt:.2f} USDT</b>:\n\n"
        f"Поддерживается: TRC20 (USDT), BEP20, ERC20\n\n"
        f"Отправь /cancel для отмены.",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(WithdrawalForm.waiting_wallet)
async def process_wallet_address(message: Message, state: FSMContext, session: AsyncSession):
    wallet = message.text.strip()

    if len(wallet) < 20:
        await message.answer("❌ Некорректный адрес. Попробуй ещё раз или /cancel для отмены.")
        return

    user = await session.get(User, message.from_user.id)
    if not user or user.balance_usdt < settings.min_withdrawal:
        await message.answer("❌ Недостаточно средств.")
        await state.clear()
        return

    withdrawal = Withdrawal(
        user_id=user.id,
        amount_usdt=user.balance_usdt,
        wallet_address=wallet,
        status=WithdrawalStatus.pending,
    )
    session.add(withdrawal)
    # Замораживаем баланс (не обнуляем до подтверждения)
    await session.commit()

    await state.clear()

    # Уведомляем владельца
    try:
        await message.bot.send_message(
            settings.admin_tg_id,
            f"💸 <b>Новая заявка на вывод!</b>\n\n"
            f"👤 @{user.username or user.full_name}\n"
            f"💰 {withdrawal.amount_usdt:.2f} USDT\n"
            f"💳 <code>{wallet}</code>\n\n"
            f"ID заявки: #{withdrawal.id}\n"
            f"Подтвердить в веб-панели.",
            parse_mode="HTML",
        )
    except Exception:
        pass

    await message.answer(
        f"✅ Заявка на вывод <b>{withdrawal.amount_usdt:.2f} USDT</b> принята!\n\n"
        f"Кошелёк: <code>{wallet}</code>\n\n"
        f"Мы обработаем её в течение 24 часов.",
        reply_markup=main_menu_kb(),
        parse_mode="HTML",
    )
```

- [ ] **Шаг 4: Запустить тесты — PASS**

```bash
cd moon666_bot
pytest tests/test_withdrawal.py -v
```

- [ ] **Шаг 5: Commit**

```bash
git add moon666_bot/bot/handlers/withdrawal.py moon666_bot/tests/test_withdrawal.py
git commit -m "feat: withdrawal FSM handler"
```

---

## Task 8: Bot — реакции и retention scheduler

**Files:**
- Create: `moon666_bot/bot/handlers/reactions.py`
- Create: `moon666_bot/bot/services/scheduler.py`

- [ ] **Шаг 1: Создать bot/handlers/reactions.py**

Создать `moon666_bot/bot/handlers/reactions.py`:
```python
from aiogram import Router
from aiogram.types import MessageReactionUpdated
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models import ChannelReaction, Referral
from shared.config import settings
from bot.services.referral import award_reaction_bonus

router = Router()


@router.message_reaction()
async def on_channel_reaction(event: MessageReactionUpdated, session: AsyncSession):
    # Только реакции в нашем канале
    if event.chat.id != settings.channel_id:
        return

    user_id = event.user.id if event.user else None
    if not user_id:
        return

    # Проверяем, была ли уже реакция от этого пользователя
    existing = await session.execute(
        select(ChannelReaction).where(ChannelReaction.user_id == user_id)
    )
    if existing.scalar_one_or_none():
        return  # уже засчитано

    # Сохраняем реакцию
    reaction = ChannelReaction(user_id=user_id, post_id=event.message_id)
    session.add(reaction)

    # Находим referral запись и начисляем бонус рефереру
    ref_result = await session.execute(
        select(Referral).where(Referral.referred_id == user_id)
    )
    ref = ref_result.scalar_one_or_none()
    if ref:
        await award_reaction_bonus(session, ref)
        try:
            await event.bot.send_message(
                ref.referrer_id,
                f"⚡ Твой реферал поставил реакцию на пост!\n"
                f"💰 +{settings.bonus_reaction} USDT начислено.",
            )
        except Exception:
            pass
    else:
        await session.commit()
```

- [ ] **Шаг 2: Создать bot/services/scheduler.py**

Создать `moon666_bot/bot/services/scheduler.py`:
```python
import asyncio
from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import async_session_maker
from shared.models import User, Referral
from shared.config import settings
from bot.services.referral import award_retention_bonus


async def check_retention(bot) -> None:
    """Проверяет пользователей, которым исполнилось 30 дней в канале."""
    async with async_session_maker() as session:
        threshold = datetime.now(timezone.utc) - timedelta(days=30)

        # Ищем рефералов где retention не выплачен и прошло 30 дней
        result = await session.execute(
            select(Referral, User)
            .join(User, User.id == Referral.referred_id)
            .where(
                Referral.retention_bonus_paid == False,
                User.channel_joined_at != None,
                User.channel_joined_at <= threshold,
            )
        )
        rows = result.all()

        for ref, referred_user in rows:
            # Проверяем что пользователь ещё в канале
            try:
                member = await bot.get_chat_member(settings.channel_id, referred_user.id)
                if member.status not in ("member", "administrator", "creator"):
                    continue
            except Exception:
                continue

            await award_retention_bonus(session, ref)

            # Уведомляем реферера
            try:
                await bot.send_message(
                    ref.referrer_id,
                    f"🎯 Твой реферал остался в канале 30 дней!\n"
                    f"💰 +{settings.bonus_retention} USDT начислено.",
                )
            except Exception:
                pass


def start_scheduler(bot) -> None:
    """Запускает APScheduler для retention check раз в час."""
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        check_retention,
        trigger="interval",
        hours=1,
        args=[bot],
        id="retention_check",
    )
    scheduler.start()
```

- [ ] **Шаг 3: Проверить импорты**

```bash
cd moon666_bot
python -c "from bot.handlers.reactions import router; from bot.services.scheduler import start_scheduler; print('OK')"
```

Ожидаем: `OK`

- [ ] **Шаг 4: Commit**

```bash
git add moon666_bot/bot/handlers/reactions.py moon666_bot/bot/services/scheduler.py
git commit -m "feat: reaction handler and retention scheduler"
```

---

## Task 9: Bot — main.py и точка входа

**Files:**
- Create: `moon666_bot/bot/main.py`

- [ ] **Шаг 1: Создать bot/main.py**

Создать `moon666_bot/bot/main.py`:
```python
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
from bot.services.scheduler import start_scheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def on_startup(bot: Bot):
    # Создаём таблицы если нет (в проде используем alembic)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await bot.set_my_commands([
        BotCommand(command="start", description="Главное меню"),
        BotCommand(command="cancel", description="Отмена"),
    ])
    start_scheduler(bot)
    logger.info("Bot started")


async def main():
    bot = Bot(token=settings.bot_token)
    dp = Dispatcher(storage=MemoryStorage())

    dp.include_router(start_router)
    dp.include_router(cabinet_router)
    dp.include_router(withdrawal_router)
    dp.include_router(reactions_router)

    dp.startup.register(on_startup)

    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Шаг 2: Проверить импорт**

```bash
cd moon666_bot
python -c "import bot.main; print('OK')"
```

Ожидаем: `OK` (без запуска polling)

- [ ] **Шаг 3: Commit**

```bash
git add moon666_bot/bot/main.py
git commit -m "feat: bot entry point with all routers"
```

---

## Task 10: Web — auth и базовый layout

**Files:**
- Create: `moon666_bot/web/auth.py`
- Create: `moon666_bot/web/main.py`
- Create: `moon666_bot/web/templates/base.html`
- Create: `moon666_bot/web/templates/login.html`

- [ ] **Шаг 1: Создать web/auth.py**

Создать `moon666_bot/web/auth.py`:
```python
from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from jose import JWTError, jwt
from passlib.context import CryptContext

from shared.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 часа


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=ALGORITHM)


def verify_token(token: str) -> bool:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
        return payload.get("sub") == settings.admin_login
    except JWTError:
        return False


async def get_current_admin(request: Request):
    token = request.cookies.get("access_token")
    if not token or not verify_token(token):
        raise HTTPException(status_code=302, headers={"Location": "/login"})
    return True
```

- [ ] **Шаг 2: Создать web/templates/base.html**

Создать `moon666_bot/web/templates/base.html`:
```html
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🌙 Moon666 Admin</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
               background: #0f172a; color: #e2e8f0; min-height: 100vh; display: flex; }
        .sidebar { width: 200px; background: #1e293b; padding: 20px 0; flex-shrink: 0;
                   border-right: 1px solid #334155; min-height: 100vh; }
        .sidebar-brand { padding: 0 16px 20px; color: #a78bfa; font-weight: bold; font-size: 16px; }
        .sidebar a { display: block; padding: 10px 16px; color: #94a3b8; text-decoration: none;
                     font-size: 14px; border-left: 3px solid transparent; }
        .sidebar a:hover, .sidebar a.active { background: #312e81; color: #c4b5fd;
                                               border-left-color: #7c3aed; }
        .main { flex: 1; padding: 24px; overflow-y: auto; }
        .page-title { font-size: 22px; font-weight: bold; margin-bottom: 20px; color: #e2e8f0; }
        .card { background: #1e293b; border-radius: 10px; padding: 16px; margin-bottom: 16px; }
        .kpi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
                    gap: 12px; margin-bottom: 20px; }
        .kpi { background: #1e293b; border-radius: 10px; padding: 16px; text-align: center; }
        .kpi-value { font-size: 26px; font-weight: bold; margin-bottom: 4px; }
        .kpi-label { font-size: 12px; color: #64748b; text-transform: uppercase; letter-spacing: 1px; }
        table { width: 100%; border-collapse: collapse; font-size: 14px; }
        th { text-align: left; padding: 10px 12px; color: #64748b; font-size: 11px;
             text-transform: uppercase; border-bottom: 1px solid #334155; }
        td { padding: 10px 12px; border-bottom: 1px solid #1e293b; }
        tr:hover td { background: #1e3a5f22; }
        .badge { display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 11px; }
        .badge-pending { background: #451a03; color: #fb923c; }
        .badge-approved { background: #052e16; color: #4ade80; }
        .badge-rejected { background: #450a0a; color: #f87171; }
        .btn { padding: 6px 14px; border-radius: 6px; border: none; cursor: pointer; font-size: 13px; }
        .btn-green { background: #065f46; color: #34d399; }
        .btn-red { background: #450a0a; color: #f87171; }
        .btn-green:hover { background: #064e3b; }
        .btn-red:hover { background: #3b0a0a; }
        .period-filter { display: flex; gap: 8px; margin-bottom: 20px; flex-wrap: wrap; }
        .period-btn { padding: 6px 14px; border-radius: 6px; background: #1e293b; color: #94a3b8;
                      border: 1px solid #334155; cursor: pointer; font-size: 13px; text-decoration: none; }
        .period-btn.active { background: #312e81; color: #c4b5fd; border-color: #7c3aed; }
        input[type="text"], input[type="date"], input[type="number"] {
            background: #0f172a; border: 1px solid #334155; color: #e2e8f0;
            padding: 8px 12px; border-radius: 6px; font-size: 14px; }
        input:focus { outline: none; border-color: #7c3aed; }
    </style>
</head>
<body>
    <div class="sidebar">
        <div class="sidebar-brand">🌙 Moon666</div>
        <a href="/" class="{% if active == 'dashboard' %}active{% endif %}">📊 Дашборд</a>
        <a href="/analytics" class="{% if active == 'analytics' %}active{% endif %}">📈 Аналитика</a>
        <a href="/withdrawals" class="{% if active == 'withdrawals' %}active{% endif %}">📤 Выводы</a>
        <a href="/users" class="{% if active == 'users' %}active{% endif %}">👥 Пользователи</a>
        <a href="/settings" class="{% if active == 'settings' %}active{% endif %}">⚙️ Настройки</a>
        <a href="/logout" style="margin-top: auto; color: #64748b;">🚪 Выйти</a>
    </div>
    <div class="main">
        {% block content %}{% endblock %}
    </div>
</body>
</html>
```

- [ ] **Шаг 3: Создать web/templates/login.html**

Создать `moon666_bot/web/templates/login.html`:
```html
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <title>Moon666 Admin — Вход</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { background: #0f172a; color: #e2e8f0; display: flex; justify-content: center;
               align-items: center; min-height: 100vh; font-family: sans-serif; }
        .login-box { background: #1e293b; border-radius: 12px; padding: 40px; width: 320px; }
        h1 { margin-bottom: 24px; text-align: center; color: #a78bfa; }
        label { display: block; margin-bottom: 4px; font-size: 13px; color: #94a3b8; }
        input { width: 100%; background: #0f172a; border: 1px solid #334155; color: #e2e8f0;
                padding: 10px 12px; border-radius: 6px; font-size: 14px; margin-bottom: 16px; }
        button { width: 100%; padding: 10px; background: #7c3aed; color: white; border: none;
                 border-radius: 6px; font-size: 15px; cursor: pointer; }
        button:hover { background: #6d28d9; }
        .error { color: #f87171; font-size: 13px; margin-bottom: 12px; text-align: center; }
    </style>
</head>
<body>
    <div class="login-box">
        <h1>🌙 Moon666</h1>
        {% if error %}<p class="error">{{ error }}</p>{% endif %}
        <form method="post">
            <label>Логин</label>
            <input type="text" name="username" required>
            <label>Пароль</label>
            <input type="password" name="password" required>
            <button type="submit">Войти</button>
        </form>
    </div>
</body>
</html>
```

- [ ] **Шаг 4: Создать web/main.py**

Создать `moon666_bot/web/main.py`:
```python
from fastapi import FastAPI, Request, Form, Depends
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

from shared.config import settings
from web.auth import create_access_token, get_current_admin
from web.routes import dashboard, analytics, withdrawals, users, settings as settings_route

BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

app = FastAPI(title="Moon666 Admin")

app.include_router(dashboard.router)
app.include_router(analytics.router)
app.include_router(withdrawals.router)
app.include_router(users.router)
app.include_router(settings_route.router)


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    if username == settings.admin_login and password == settings.admin_password:
        token = create_access_token({"sub": username})
        response = RedirectResponse(url="/", status_code=302)
        response.set_cookie("access_token", token, httponly=True, max_age=86400)
        return response
    return templates.TemplateResponse(
        "login.html", {"request": request, "error": "Неверный логин или пароль"}
    )


@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie("access_token")
    return response
```

- [ ] **Шаг 5: Проверить импорт**

```bash
cd moon666_bot
python -c "from web.main import app; print('OK')"
```

- [ ] **Шаг 6: Commit**

```bash
git add moon666_bot/web/
git commit -m "feat: web admin base layout and auth"
```

---

## Task 11: Web — Dashboard с периодом и KPI

**Files:**
- Create: `moon666_bot/web/routes/dashboard.py`
- Create: `moon666_bot/web/templates/dashboard.html`

- [ ] **Шаг 1: Создать web/routes/dashboard.py**

Создать `moon666_bot/web/routes/dashboard.py`:
```python
from datetime import datetime, timedelta, timezone, date
from decimal import Decimal
from fastapi import APIRouter, Request, Depends, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from pathlib import Path

from shared.database import get_session
from shared.models import User, Transaction, Withdrawal, WithdrawalStatus
from web.auth import get_current_admin

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


def get_date_range(period: str, date_from: str | None, date_to: str | None):
    now = datetime.now(timezone.utc)
    if period == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "7d":
        start = now - timedelta(days=7)
    elif period == "30d":
        start = now - timedelta(days=30)
    elif period == "90d":
        start = now - timedelta(days=90)
    elif period == "custom" and date_from:
        start = datetime.fromisoformat(date_from).replace(tzinfo=timezone.utc)
        end = datetime.fromisoformat(date_to).replace(tzinfo=timezone.utc) if date_to else now
        return start, end
    else:
        start = now - timedelta(days=30)
    return start, now


@router.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    period: str = Query("30d"),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
    _: bool = Depends(get_current_admin),
):
    start, end = get_date_range(period, date_from, date_to)

    total_users = (await session.execute(select(func.count(User.id)))).scalar() or 0
    total_accrued = (await session.execute(
        select(func.sum(Transaction.amount_usdt)).where(Transaction.created_at.between(start, end))
    )).scalar() or Decimal("0.00")
    total_paid = (await session.execute(
        select(func.sum(Withdrawal.amount_usdt)).where(
            Withdrawal.status == WithdrawalStatus.approved,
            Withdrawal.processed_at.between(start, end),
        )
    )).scalar() or Decimal("0.00")
    pending_count = (await session.execute(
        select(func.count(Withdrawal.id)).where(Withdrawal.status == WithdrawalStatus.pending)
    )).scalar() or 0

    # Последние 5 заявок на вывод
    recent_withdrawals_result = await session.execute(
        select(Withdrawal, User)
        .join(User, User.id == Withdrawal.user_id)
        .where(Withdrawal.status == WithdrawalStatus.pending)
        .order_by(Withdrawal.created_at.desc())
        .limit(5)
    )
    recent_withdrawals = recent_withdrawals_result.all()

    # Рост подписчиков по неделям (последние 8 недель)
    growth = []
    for i in range(7, -1, -1):
        week_start = datetime.now(timezone.utc) - timedelta(weeks=i+1)
        week_end = datetime.now(timezone.utc) - timedelta(weeks=i)
        cnt = (await session.execute(
            select(func.count(User.id)).where(User.joined_at.between(week_start, week_end))
        )).scalar() or 0
        growth.append({"week": f"-{i+1}w", "count": cnt})

    return templates.TemplateResponse("dashboard.html", {
        "request": request, "active": "dashboard",
        "total_users": total_users, "total_accrued": total_accrued,
        "total_paid": total_paid, "pending_count": pending_count,
        "recent_withdrawals": recent_withdrawals,
        "growth": growth, "period": period,
        "date_from": date_from, "date_to": date_to,
    })
```

- [ ] **Шаг 2: Создать web/templates/dashboard.html**

Создать `moon666_bot/web/templates/dashboard.html`:
```html
{% extends "base.html" %}
{% block content %}
<div class="page-title">📊 Дашборд</div>

<div class="period-filter">
    <a href="/?period=today" class="period-btn {% if period == 'today' %}active{% endif %}">Сегодня</a>
    <a href="/?period=7d" class="period-btn {% if period == '7d' %}active{% endif %}">7 дней</a>
    <a href="/?period=30d" class="period-btn {% if period == '30d' %}active{% endif %}">30 дней</a>
    <a href="/?period=90d" class="period-btn {% if period == '90d' %}active{% endif %}">90 дней</a>
    <form method="get" style="display:flex;gap:6px;align-items:center;">
        <input type="hidden" name="period" value="custom">
        <input type="date" name="date_from" value="{{ date_from or '' }}">
        <input type="date" name="date_to" value="{{ date_to or '' }}">
        <button type="submit" class="btn btn-green">Применить</button>
    </form>
</div>

<div class="kpi-grid">
    <div class="kpi">
        <div class="kpi-value" style="color:#a78bfa">{{ total_users }}</div>
        <div class="kpi-label">Подписчиков</div>
    </div>
    <div class="kpi">
        <div class="kpi-value" style="color:#34d399">${{ "%.2f"|format(total_accrued) }}</div>
        <div class="kpi-label">Начислено</div>
    </div>
    <div class="kpi">
        <div class="kpi-value" style="color:#60a5fa">${{ "%.2f"|format(total_paid) }}</div>
        <div class="kpi-label">Выплачено</div>
    </div>
    <div class="kpi">
        <div class="kpi-value" style="color:#fbbf24">{{ pending_count }}</div>
        <div class="kpi-label">Заявок в очереди</div>
    </div>
</div>

<div class="card">
    <h3 style="margin-bottom:12px;font-size:14px;color:#94a3b8">⏳ Последние заявки на вывод</h3>
    {% if recent_withdrawals %}
    <table>
        <tr><th>Пользователь</th><th>Сумма</th><th>Кошелёк</th><th>Дата</th><th></th></tr>
        {% for w, u in recent_withdrawals %}
        <tr>
            <td>@{{ u.username or u.full_name }}</td>
            <td style="color:#fbbf24">${{ "%.2f"|format(w.amount_usdt) }}</td>
            <td><code style="font-size:12px">{{ w.wallet_address[:20] }}...</code></td>
            <td style="color:#64748b">{{ w.created_at.strftime('%d.%m %H:%M') }}</td>
            <td>
                <a href="/withdrawals?highlight={{ w.id }}" class="btn btn-green" style="text-decoration:none">Обработать →</a>
            </td>
        </tr>
        {% endfor %}
    </table>
    {% else %}
    <p style="color:#64748b">Нет активных заявок</p>
    {% endif %}
</div>
{% endblock %}
```

- [ ] **Шаг 3: Commit**

```bash
git add moon666_bot/web/routes/dashboard.py moon666_bot/web/templates/dashboard.html
git commit -m "feat: admin dashboard with KPI and period filter"
```

---

## Task 12: Web — Analytics, Withdrawals, Users, Settings

**Files:**
- Create: `moon666_bot/web/routes/analytics.py`
- Create: `moon666_bot/web/routes/withdrawals.py`
- Create: `moon666_bot/web/routes/users.py`
- Create: `moon666_bot/web/routes/settings.py`
- Create: `moon666_bot/web/notifications.py`
- Create: `moon666_bot/web/templates/analytics.html`
- Create: `moon666_bot/web/templates/withdrawals.html`
- Create: `moon666_bot/web/templates/users.html`
- Create: `moon666_bot/web/templates/settings.html`

- [ ] **Шаг 1: Создать web/notifications.py**

Создать `moon666_bot/web/notifications.py`:
```python
import httpx
from shared.config import settings


async def send_telegram_notification(user_id: int, text: str) -> bool:
    """Отправляет сообщение пользователю через Bot API."""
    url = f"https://api.telegram.org/bot{settings.bot_token}/sendMessage"
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url, json={"chat_id": user_id, "text": text, "parse_mode": "HTML"})
            return resp.status_code == 200
        except Exception:
            return False
```

- [ ] **Шаг 2: Создать web/routes/analytics.py**

Создать `moon666_bot/web/routes/analytics.py`:
```python
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from fastapi import APIRouter, Request, Depends, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from pathlib import Path

from shared.database import get_session
from shared.models import User, Referral, Transaction, TransactionType
from web.auth import get_current_admin
from web.routes.dashboard import get_date_range

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


@router.get("/analytics", response_class=HTMLResponse)
async def analytics(
    request: Request,
    period: str = Query("30d"),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
    _: bool = Depends(get_current_admin),
):
    start, end = get_date_range(period, date_from, date_to)

    # Retention воронка
    total_joined = (await session.execute(
        select(func.count(User.id)).where(User.channel_joined_at.between(start, end))
    )).scalar() or 0

    now = datetime.now(timezone.utc)
    retention_funnel = []
    for days in [7, 30, 60]:
        threshold = now - timedelta(days=days)
        still_in = (await session.execute(
            select(func.count(User.id)).where(
                User.channel_joined_at <= threshold,
                User.channel_joined_at >= start,
            )
        )).scalar() or 0
        pct = round(still_in / total_joined * 100) if total_joined > 0 else 0
        retention_funnel.append({"days": days, "count": still_in, "pct": pct})

    # Расход по типам
    bonus_breakdown = []
    for tx_type in TransactionType:
        total = (await session.execute(
            select(func.sum(Transaction.amount_usdt)).where(
                Transaction.type == tx_type,
                Transaction.created_at.between(start, end),
            )
        )).scalar() or Decimal("0.00")
        bonus_breakdown.append({"type": tx_type.value, "total": total})

    total_bonus = sum(b["total"] for b in bonus_breakdown) or Decimal("1.00")
    for b in bonus_breakdown:
        b["pct"] = round(float(b["total"] / total_bonus) * 100)

    # Стоимость подписчика
    new_users = (await session.execute(
        select(func.count(User.id)).where(User.joined_at.between(start, end))
    )).scalar() or 1
    total_spent = sum(b["total"] for b in bonus_breakdown)
    cost_per_user = round(float(total_spent / new_users), 4) if new_users > 0 else 0.0

    # Топ рефереров
    top_result = await session.execute(
        select(User.username, User.full_name, func.count(Referral.id).label("cnt"))
        .join(Referral, Referral.referrer_id == User.id)
        .where(Referral.created_at.between(start, end))
        .group_by(User.id, User.username, User.full_name)
        .order_by(func.count(Referral.id).desc())
        .limit(10)
    )
    top_referrers = top_result.all()

    return templates.TemplateResponse("analytics.html", {
        "request": request, "active": "analytics",
        "total_joined": total_joined, "retention_funnel": retention_funnel,
        "bonus_breakdown": bonus_breakdown, "cost_per_user": cost_per_user,
        "top_referrers": top_referrers, "period": period,
        "date_from": date_from, "date_to": date_to,
    })
```

- [ ] **Шаг 3: Создать web/routes/withdrawals.py**

Создать `moon666_bot/web/routes/withdrawals.py`:
```python
from datetime import datetime, timezone
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pathlib import Path

from shared.database import get_session
from shared.models import User, Withdrawal, WithdrawalStatus
from web.auth import get_current_admin
from web.notifications import send_telegram_notification

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


@router.get("/withdrawals", response_class=HTMLResponse)
async def withdrawals_page(
    request: Request,
    session: AsyncSession = Depends(get_session),
    _: bool = Depends(get_current_admin),
):
    result = await session.execute(
        select(Withdrawal, User)
        .join(User, User.id == Withdrawal.user_id)
        .order_by(Withdrawal.created_at.desc())
    )
    withdrawals = result.all()
    return templates.TemplateResponse("withdrawals.html", {
        "request": request, "active": "withdrawals", "withdrawals": withdrawals
    })


@router.post("/withdrawals/{withdrawal_id}/approve")
async def approve_withdrawal(
    withdrawal_id: int,
    session: AsyncSession = Depends(get_session),
    _: bool = Depends(get_current_admin),
):
    w = await session.get(Withdrawal, withdrawal_id)
    if w and w.status == WithdrawalStatus.pending:
        user = await session.get(User, w.user_id)
        w.status = WithdrawalStatus.approved
        w.processed_at = datetime.now(timezone.utc)
        # Списываем баланс
        user.balance_usdt -= w.amount_usdt
        await session.commit()
        await send_telegram_notification(
            w.user_id,
            f"✅ Твоя заявка на вывод <b>{w.amount_usdt:.2f} USDT</b> одобрена!\n"
            f"Средства отправлены на кошелёк <code>{w.wallet_address}</code>.",
        )
    return RedirectResponse(url="/withdrawals", status_code=302)


@router.post("/withdrawals/{withdrawal_id}/reject")
async def reject_withdrawal(
    withdrawal_id: int,
    session: AsyncSession = Depends(get_session),
    _: bool = Depends(get_current_admin),
):
    w = await session.get(Withdrawal, withdrawal_id)
    if w and w.status == WithdrawalStatus.pending:
        w.status = WithdrawalStatus.rejected
        w.processed_at = datetime.now(timezone.utc)
        await session.commit()
        await send_telegram_notification(
            w.user_id,
            f"❌ Твоя заявка на вывод <b>{w.amount_usdt:.2f} USDT</b> отклонена.\n"
            f"Обратись в поддержку если считаешь это ошибкой.",
        )
    return RedirectResponse(url="/withdrawals", status_code=302)
```

- [ ] **Шаг 4: Создать web/routes/users.py**

Создать `moon666_bot/web/routes/users.py`:
```python
from fastapi import APIRouter, Request, Depends, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from pathlib import Path

from shared.database import get_session
from shared.models import User, Referral
from web.auth import get_current_admin

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
        query = query.where(User.username.ilike(f"%{search}%"))

    result = await session.execute(query)
    users = result.all()

    return templates.TemplateResponse("users.html", {
        "request": request, "active": "users", "users": users, "search": search or ""
    })
```

- [ ] **Шаг 5: Создать web/routes/settings.py**

Создать `moon666_bot/web/routes/settings.py`:
```python
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from decimal import Decimal

from shared.config import settings as app_settings
from web.auth import get_current_admin

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(
    request: Request,
    _: bool = Depends(get_current_admin),
):
    return templates.TemplateResponse("settings.html", {
        "request": request, "active": "settings", "settings": app_settings, "saved": False
    })


@router.post("/settings")
async def settings_save(
    request: Request,
    bonus_join: str = Form(...),
    bonus_reaction: str = Form(...),
    bonus_retention: str = Form(...),
    min_withdrawal: str = Form(...),
    _: bool = Depends(get_current_admin),
):
    # Обновляем runtime значения (применяются до рестарта)
    app_settings.bonus_join = Decimal(bonus_join)
    app_settings.bonus_reaction = Decimal(bonus_reaction)
    app_settings.bonus_retention = Decimal(bonus_retention)
    app_settings.min_withdrawal = Decimal(min_withdrawal)

    return templates.TemplateResponse("settings.html", {
        "request": request, "active": "settings", "settings": app_settings, "saved": True
    })
```

- [ ] **Шаг 6: Создать шаблоны для analytics, withdrawals, users, settings**

Создать `moon666_bot/web/templates/analytics.html`:
```html
{% extends "base.html" %}
{% block content %}
<div class="page-title">📈 Аналитика</div>

<div class="period-filter">
    <a href="/analytics?period=7d" class="period-btn {% if period == '7d' %}active{% endif %}">7 дней</a>
    <a href="/analytics?period=30d" class="period-btn {% if period == '30d' %}active{% endif %}">30 дней</a>
    <a href="/analytics?period=90d" class="period-btn {% if period == '90d' %}active{% endif %}">90 дней</a>
    <form method="get" style="display:flex;gap:6px;align-items:center;">
        <input type="hidden" name="period" value="custom">
        <input type="date" name="date_from" value="{{ date_from or '' }}">
        <input type="date" name="date_to" value="{{ date_to or '' }}">
        <button type="submit" class="btn btn-green">Применить</button>
    </form>
</div>

<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px">
    <div class="card">
        <h3 style="font-size:13px;color:#94a3b8;margin-bottom:12px;text-transform:uppercase">🔻 Retention воронка</h3>
        <p style="color:#64748b;font-size:12px;margin-bottom:12px">Всего зашло за период: <b style="color:#e2e8f0">{{ total_joined }}</b></p>
        {% for r in retention_funnel %}
        <div style="margin-bottom:10px">
            <div style="display:flex;justify-content:space-between;margin-bottom:4px">
                <span style="color:#94a3b8;font-size:13px">День {{ r.days }}</span>
                <span style="color:#a78bfa">{{ r.count }} ({{ r.pct }}%)</span>
            </div>
            <div style="background:#0f172a;border-radius:4px;height:8px">
                <div style="background:linear-gradient(90deg,#7c3aed,#a78bfa);width:{{ r.pct }}%;height:8px;border-radius:4px"></div>
            </div>
        </div>
        {% endfor %}
    </div>

    <div class="card">
        <h3 style="font-size:13px;color:#94a3b8;margin-bottom:12px;text-transform:uppercase">💸 Расход по типам</h3>
        <p style="color:#64748b;font-size:12px;margin-bottom:12px">Стоимость подписчика: <b style="color:#fbbf24">${{ cost_per_user }}</b></p>
        {% for b in bonus_breakdown %}
        <div style="margin-bottom:10px">
            <div style="display:flex;justify-content:space-between;margin-bottom:4px">
                <span style="color:#94a3b8;font-size:13px">{{ b.type }}</span>
                <span style="color:#34d399">${{ "%.2f"|format(b.total) }} ({{ b.pct }}%)</span>
            </div>
            <div style="background:#0f172a;border-radius:4px;height:8px">
                <div style="background:#34d399;width:{{ b.pct }}%;height:8px;border-radius:4px"></div>
            </div>
        </div>
        {% endfor %}
    </div>
</div>

<div class="card">
    <h3 style="font-size:13px;color:#94a3b8;margin-bottom:12px;text-transform:uppercase">🏆 Топ рефереров</h3>
    <table>
        <tr><th>#</th><th>Пользователь</th><th>Рефералов</th></tr>
        {% for username, full_name, cnt in top_referrers %}
        <tr>
            <td style="color:#64748b">{{ loop.index }}</td>
            <td>@{{ username or full_name }}</td>
            <td style="color:#34d399">{{ cnt }}</td>
        </tr>
        {% endfor %}
    </table>
</div>
{% endblock %}
```

Создать `moon666_bot/web/templates/withdrawals.html`:
```html
{% extends "base.html" %}
{% block content %}
<div class="page-title">📤 Выводы</div>
<div class="card">
    <table>
        <tr><th>Пользователь</th><th>Сумма</th><th>Кошелёк</th><th>Дата</th><th>Статус</th><th>Действие</th></tr>
        {% for w, u in withdrawals %}
        <tr>
            <td>@{{ u.username or u.full_name }}</td>
            <td style="color:#fbbf24;font-weight:bold">${{ "%.2f"|format(w.amount_usdt) }}</td>
            <td><code style="font-size:12px">{{ w.wallet_address }}</code></td>
            <td style="color:#64748b">{{ w.created_at.strftime('%d.%m.%Y %H:%M') }}</td>
            <td><span class="badge badge-{{ w.status.value }}">{{ w.status.value }}</span></td>
            <td>
                {% if w.status.value == 'pending' %}
                <form method="post" action="/withdrawals/{{ w.id }}/approve" style="display:inline">
                    <button type="submit" class="btn btn-green">✅ Выплатить</button>
                </form>
                <form method="post" action="/withdrawals/{{ w.id }}/reject" style="display:inline;margin-left:4px">
                    <button type="submit" class="btn btn-red">❌</button>
                </form>
                {% else %}
                <span style="color:#64748b;font-size:12px">{{ w.processed_at.strftime('%d.%m %H:%M') if w.processed_at else '—' }}</span>
                {% endif %}
            </td>
        </tr>
        {% endfor %}
    </table>
</div>
{% endblock %}
```

Создать `moon666_bot/web/templates/users.html`:
```html
{% extends "base.html" %}
{% block content %}
<div class="page-title">👥 Пользователи</div>
<form method="get" style="margin-bottom:16px;display:flex;gap:8px">
    <input type="text" name="search" placeholder="Поиск по username..." value="{{ search }}">
    <button type="submit" class="btn btn-green">Найти</button>
</form>
<div class="card">
    <table>
        <tr><th>Пользователь</th><th>Баланс</th><th>Рефералов</th><th>Дата вступления</th></tr>
        {% for u, ref_count in users %}
        <tr>
            <td>@{{ u.username or u.full_name }}</td>
            <td style="color:#fbbf24">${{ "%.2f"|format(u.balance_usdt) }}</td>
            <td style="color:#34d399">{{ ref_count }}</td>
            <td style="color:#64748b">{{ u.joined_at.strftime('%d.%m.%Y') if u.joined_at else '—' }}</td>
        </tr>
        {% endfor %}
    </table>
</div>
{% endblock %}
```

Создать `moon666_bot/web/templates/settings.html`:
```html
{% extends "base.html" %}
{% block content %}
<div class="page-title">⚙️ Настройки</div>
{% if saved %}<div style="background:#052e16;color:#4ade80;padding:10px 16px;border-radius:8px;margin-bottom:16px">✅ Настройки сохранены</div>{% endif %}
<div class="card" style="max-width:400px">
    <form method="post">
        <h3 style="font-size:14px;color:#94a3b8;margin-bottom:16px">Бонусы (USDT)</h3>
        <label style="font-size:13px;color:#64748b;display:block;margin-bottom:4px">За реферала (вступление)</label>
        <input type="number" name="bonus_join" value="{{ settings.bonus_join }}" step="0.01" style="width:100%;margin-bottom:12px">
        <label style="font-size:13px;color:#64748b;display:block;margin-bottom:4px">За первую реакцию</label>
        <input type="number" name="bonus_reaction" value="{{ settings.bonus_reaction }}" step="0.01" style="width:100%;margin-bottom:12px">
        <label style="font-size:13px;color:#64748b;display:block;margin-bottom:4px">За удержание 30 дней</label>
        <input type="number" name="bonus_retention" value="{{ settings.bonus_retention }}" step="0.01" style="width:100%;margin-bottom:12px">
        <label style="font-size:13px;color:#64748b;display:block;margin-bottom:4px">Минимальная сумма вывода</label>
        <input type="number" name="min_withdrawal" value="{{ settings.min_withdrawal }}" step="0.01" style="width:100%;margin-bottom:20px">
        <button type="submit" class="btn btn-green" style="width:100%;padding:10px">Сохранить</button>
    </form>
</div>
{% endblock %}
```

- [ ] **Шаг 7: Запустить тест импортов**

```bash
cd moon666_bot
python -c "from web.routes import analytics, withdrawals, users, settings; print('OK')"
```

Ожидаем: `OK`

- [ ] **Шаг 8: Commit**

```bash
git add moon666_bot/web/
git commit -m "feat: web admin analytics, withdrawals, users, settings pages"
```

---

## Task 13: Docker и финальная сборка

**Files:**
- Create: `moon666_bot/docker-compose.yml`
- Create: `moon666_bot/bot/Dockerfile`
- Create: `moon666_bot/web/Dockerfile`

- [ ] **Шаг 1: Создать bot/Dockerfile**

Создать `moon666_bot/bot/Dockerfile`:
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY ../requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY .. .
CMD ["python", "-m", "bot.main"]
```

- [ ] **Шаг 2: Создать web/Dockerfile**

Создать `moon666_bot/web/Dockerfile`:
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY ../requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY .. .
CMD ["uvicorn", "web.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Шаг 3: Создать docker-compose.yml**

Создать `moon666_bot/docker-compose.yml`:
```yaml
version: "3.9"

services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: moon666
      POSTGRES_PASSWORD: moon666pass
      POSTGRES_DB: moon666
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U moon666"]
      interval: 5s
      timeout: 5s
      retries: 5

  bot:
    build:
      context: .
      dockerfile: bot/Dockerfile
    env_file: .env
    depends_on:
      postgres:
        condition: service_healthy
    restart: unless-stopped

  web:
    build:
      context: .
      dockerfile: web/Dockerfile
    env_file: .env
    ports:
      - "8000:8000"
    depends_on:
      postgres:
        condition: service_healthy
    restart: unless-stopped

volumes:
  pgdata:
```

- [ ] **Шаг 4: Создать .env из .env.example и заполнить**

```bash
cd moon666_bot
cp .env.example .env
# Открыть .env и заполнить BOT_TOKEN, CHANNEL_ID, ADMIN_TG_ID
```

- [ ] **Шаг 5: Запустить миграции**

```bash
cd moon666_bot
# Запустить postgres локально или через docker
docker-compose up -d postgres
# Дождаться готовности
sleep 5
alembic upgrade head
```

Ожидаем: `INFO [alembic.runtime.migration] Running upgrade -> xxxx, initial`

- [ ] **Шаг 6: Запустить все тесты**

```bash
cd moon666_bot
pytest tests/ -v
```

Ожидаем: все тесты PASSED.

- [ ] **Шаг 7: Запустить docker-compose**

```bash
cd moon666_bot
docker-compose up --build
```

Ожидаем:
- `bot` контейнер: `INFO Bot started`
- `web` контейнер: `Uvicorn running on http://0.0.0.0:8000`

- [ ] **Шаг 8: Проверить веб-панель**

Открыть http://localhost:8000 → должна появиться страница логина.  
Войти с `admin` / `changeme` → дашборд.

- [ ] **Шаг 9: Финальный commit**

```bash
git add moon666_bot/docker-compose.yml moon666_bot/bot/Dockerfile moon666_bot/web/Dockerfile
git commit -m "feat: docker-compose setup for bot + web + postgres"
```

---

## Self-Review

### Покрытие спека

| Требование из спека | Задача |
|---|---|
| 5 рефералов = 1 USDT (0.20 за реферала) | Task 4 |
| Бонус за реакцию (+0.01, разово) | Task 4, 8 |
| Бонус за удержание 30 дней (+0.05, разово) | Task 4, 8 |
| Вывод от 10 USDT, ручное подтверждение | Task 7, 12 |
| Личный кабинет Premium Dark + прогресс-бар | Task 6 |
| Топ рефереров | Task 6 |
| Уведомления в Telegram | Task 5, 7, 8, 12 |
| Веб: KPI + фильтр периодов | Task 11 |
| Веб: аналитика + retention воронка | Task 12 |
| Веб: управление выплатами | Task 12 |
| Веб: список пользователей + поиск | Task 12 |
| Веб: настройки бонусов | Task 12 |
| JWT auth для веб-панели | Task 10 |
| Docker deploy | Task 13 |
| Alembic миграции | Task 3 |

Все требования покрыты. ✅
