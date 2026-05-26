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


class WithdrawalStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # Telegram user_id
    username: Mapped[Optional[str]] = mapped_column(String(64))
    full_name: Mapped[str] = mapped_column(String(256))
    referred_by: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.id"))
    balance_usdt: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"), server_default="0")
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    channel_joined_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    referrals_made: Mapped[List["Referral"]] = relationship(
        "Referral", foreign_keys="Referral.referrer_id", back_populates="referrer"
    )
    transactions: Mapped[List["Transaction"]] = relationship("Transaction", back_populates="user")
    withdrawals: Mapped[List["Withdrawal"]] = relationship("Withdrawal", back_populates="user")


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
    related_user_id: Mapped[Optional[int]] = mapped_column(BigInteger)
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
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    user: Mapped["User"] = relationship("User", back_populates="withdrawals")


class ChannelReaction(Base):
    __tablename__ = "channel_reactions"
    __table_args__ = (UniqueConstraint("user_id", name="uq_channel_reactions_user"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    post_id: Mapped[int] = mapped_column(BigInteger)
    reacted_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
