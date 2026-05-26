import pytest
from shared.models import User, Referral, Transaction, Withdrawal, ChannelReaction


def test_models_importable():
    assert User is not None
    assert Referral is not None
    assert Transaction is not None
    assert Withdrawal is not None
    assert ChannelReaction is not None
