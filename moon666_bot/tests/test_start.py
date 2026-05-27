import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy import select
from shared.models import User, Referral
from bot.handlers.start import get_or_create_user


async def test_new_user_created_on_start(db_session):
    """get_or_create_user creates a new user when not found."""
    tg_user = MagicMock()
    tg_user.id = 2001
    tg_user.username = "newuser"
    tg_user.full_name = "New User"

    user, is_new = await get_or_create_user(db_session, tg_user)

    assert is_new is True
    assert user.id == 2001
    assert user.username == "newuser"

    # Verify persisted to DB
    result = await db_session.execute(select(User).where(User.id == 2001))
    db_user = result.scalar_one_or_none()
    assert db_user is not None


async def test_existing_user_not_duplicated(db_session):
    """get_or_create_user returns existing user without creating duplicate."""
    existing = User(id=2002, full_name="Existing", balance_usdt=Decimal("5.00"))
    db_session.add(existing)
    await db_session.commit()

    tg_user = MagicMock()
    tg_user.id = 2002
    tg_user.username = "existing"
    tg_user.full_name = "Existing"

    user, is_new = await get_or_create_user(db_session, tg_user)

    assert is_new is False
    assert user.id == 2002
    assert user.balance_usdt == Decimal("5.00")


async def test_referral_recorded_when_referrer_exists(db_session):
    """A Referral row is created when a valid referrer_id is passed."""
    referrer = User(id=3001, full_name="Referrer", balance_usdt=Decimal("0.00"))
    db_session.add(referrer)
    await db_session.commit()

    from bot.handlers.start import _record_referral
    new_user = User(id=3002, full_name="New", balance_usdt=Decimal("0.00"))
    db_session.add(new_user)
    await db_session.commit()

    await _record_referral(db_session, new_user, referrer_id_str="3001")

    result = await db_session.execute(
        select(Referral).where(Referral.referred_id == 3002)
    )
    ref = result.scalar_one_or_none()
    assert ref is not None
    assert ref.referrer_id == 3001


async def test_referral_not_recorded_for_self(db_session):
    """A user cannot refer themselves."""
    user = User(id=4001, full_name="Self", balance_usdt=Decimal("0.00"))
    db_session.add(user)
    await db_session.commit()

    from bot.handlers.start import _record_referral
    await _record_referral(db_session, user, referrer_id_str="4001")

    result = await db_session.execute(
        select(Referral).where(Referral.referred_id == 4001)
    )
    ref = result.scalar_one_or_none()
    assert ref is None
