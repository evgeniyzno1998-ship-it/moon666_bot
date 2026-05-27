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
    await award_join_bonus(db_session, referral=ref)  # second call

    await db_session.refresh(referrer)
    assert referrer.balance_usdt == Decimal("0.20")  # not doubled


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


@pytest.mark.asyncio
async def test_credit_raises_when_referrer_missing(db_session):
    referred = User(id=9998, full_name="Referred", balance_usdt=Decimal("0.00"))
    db_session.add(referred)
    await db_session.commit()
    # Referral with referrer_id 9999 — no such user exists
    # We can't insert it via FK-enforced SQLite easily, so test _credit directly
    from bot.services.referral import _credit
    from shared.models import TransactionType
    # Create a mock referral-like object
    class FakeReferral:
        referrer_id = 9999
        referred_id = 9998
        id = 99
    with pytest.raises(ValueError, match="9999"):
        await _credit(db_session, FakeReferral(), Decimal("0.20"), TransactionType.referral_join)
