import pytest
from decimal import Decimal
from sqlalchemy import select
from shared.models import User, Referral, ChannelReaction
from bot.handlers.reactions import on_channel_reaction


@pytest.mark.asyncio
async def test_first_reaction_saves_record(db_session):
    """First reaction from a user saves ChannelReaction row."""
    user = User(id=7001, full_name="Reactor", balance_usdt=Decimal("0.00"))
    db_session.add(user)
    await db_session.commit()

    from unittest.mock import AsyncMock, MagicMock
    event = MagicMock()
    event.chat.id = -1001234567890
    event.user.id = 7001
    event.message_id = 42
    event.bot = AsyncMock()

    import bot.handlers.reactions as reactions_mod
    from unittest.mock import patch
    with patch.object(reactions_mod.settings, 'channel_id', -1001234567890):
        await on_channel_reaction(event, db_session)

    result = await db_session.execute(
        select(ChannelReaction).where(ChannelReaction.user_id == 7001)
    )
    cr = result.scalar_one_or_none()
    assert cr is not None
    assert cr.post_id == 42


@pytest.mark.asyncio
async def test_second_reaction_ignored(db_session):
    """Second reaction from same user is ignored (deduplication)."""
    user = User(id=7002, full_name="Reactor2", balance_usdt=Decimal("0.00"))
    cr = ChannelReaction(user_id=7002, post_id=10)
    db_session.add_all([user, cr])
    await db_session.commit()

    from unittest.mock import AsyncMock, MagicMock
    event = MagicMock()
    event.chat.id = -1001234567890
    event.user.id = 7002
    event.message_id = 20  # different post, same user — still rejected by unique constraint
    event.bot = AsyncMock()

    import bot.handlers.reactions as reactions_mod
    from unittest.mock import patch
    with patch.object(reactions_mod.settings, 'channel_id', -1001234567890):
        await on_channel_reaction(event, db_session)

    # Still only one ChannelReaction row
    result = await db_session.execute(
        select(ChannelReaction).where(ChannelReaction.user_id == 7002)
    )
    rows = result.scalars().all()
    assert len(rows) == 1
    assert rows[0].post_id == 10  # original row unchanged


@pytest.mark.asyncio
async def test_reaction_credits_referrer(db_session):
    """Reaction from referred user credits the referrer."""
    referrer = User(id=8001, full_name="Referrer", balance_usdt=Decimal("0.00"))
    referred = User(id=8002, full_name="Referred", balance_usdt=Decimal("0.00"))
    db_session.add_all([referrer, referred])
    await db_session.commit()

    ref = Referral(referrer_id=8001, referred_id=8002)
    db_session.add(ref)
    await db_session.commit()

    from unittest.mock import AsyncMock, MagicMock
    event = MagicMock()
    event.chat.id = -1001234567890
    event.user.id = 8002
    event.message_id = 99
    event.bot = AsyncMock()

    import bot.handlers.reactions as reactions_mod
    from unittest.mock import patch
    with patch.object(reactions_mod.settings, 'channel_id', -1001234567890):
        await on_channel_reaction(event, db_session)

    await db_session.refresh(referrer)
    assert referrer.balance_usdt == Decimal("0.01")
    assert ref.reaction_bonus_paid is True


@pytest.mark.asyncio
async def test_reaction_wrong_channel_ignored(db_session):
    """Reactions in other channels are ignored."""
    user = User(id=9001, full_name="Other", balance_usdt=Decimal("0.00"))
    db_session.add(user)
    await db_session.commit()

    from unittest.mock import AsyncMock, MagicMock
    event = MagicMock()
    event.chat.id = -9999999999  # wrong channel
    event.user.id = 9001
    event.message_id = 1
    event.bot = AsyncMock()

    import bot.handlers.reactions as reactions_mod
    from unittest.mock import patch
    with patch.object(reactions_mod.settings, 'channel_id', -1001234567890):
        await on_channel_reaction(event, db_session)

    result = await db_session.execute(
        select(ChannelReaction).where(ChannelReaction.user_id == 9001)
    )
    assert result.scalar_one_or_none() is None
