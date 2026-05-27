import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy import select
from shared.models import User, Withdrawal, WithdrawalStatus
from bot.handlers.withdrawal import process_wallet_address, WithdrawalForm


async def test_withdrawal_created(db_session):
    """Withdrawal record is created when user has sufficient balance."""
    user = User(id=5001, full_name="Rich User", balance_usdt=Decimal("15.00"))
    db_session.add(user)
    await db_session.commit()

    message_mock = AsyncMock()
    message_mock.from_user.id = 5001
    message_mock.text = "TQn8ixxxxxxxxxxxxxxxxxxxxxxxx3kF2"
    message_mock.bot = AsyncMock()

    state_mock = AsyncMock()
    state_mock.get_data = AsyncMock(return_value={})

    await process_wallet_address(message_mock, state_mock, session=db_session)

    result = await db_session.execute(
        select(Withdrawal).where(Withdrawal.user_id == 5001)
    )
    w = result.scalar_one_or_none()
    assert w is not None
    assert w.status == WithdrawalStatus.pending
    assert w.wallet_address == "TQn8ixxxxxxxxxxxxxxxxxxxxxxxx3kF2"
    assert w.amount_usdt == Decimal("15.00")


async def test_withdrawal_rejected_if_balance_too_low(db_session):
    """Withdrawal is not created if balance is below minimum."""
    user = User(id=5002, full_name="Poor User", balance_usdt=Decimal("3.00"))
    db_session.add(user)
    await db_session.commit()

    message_mock = AsyncMock()
    message_mock.from_user.id = 5002
    message_mock.text = "TQn8ixxxxxxxxxxxxxxxxxxxxxxxx3kF2"
    message_mock.bot = AsyncMock()

    state_mock = AsyncMock()
    state_mock.get_data = AsyncMock(return_value={})

    await process_wallet_address(message_mock, state_mock, session=db_session)

    result = await db_session.execute(
        select(Withdrawal).where(Withdrawal.user_id == 5002)
    )
    w = result.scalar_one_or_none()
    assert w is None
