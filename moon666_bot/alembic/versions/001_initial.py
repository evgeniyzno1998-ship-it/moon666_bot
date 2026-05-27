"""initial

Revision ID: a1b2c3d4
Revises:
Create Date: 2026-05-26

"""
from alembic import op
import sqlalchemy as sa


revision = 'a1b2c3d4'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'users',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('username', sa.String(length=64), nullable=True),
        sa.Column('full_name', sa.String(length=256), nullable=False),
        sa.Column('referred_by', sa.BigInteger(), nullable=True),
        sa.Column('balance_usdt', sa.Numeric(precision=10, scale=2), server_default='0', nullable=False),
        sa.Column('joined_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('channel_joined_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['referred_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table(
        'referrals',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('referrer_id', sa.BigInteger(), nullable=False),
        sa.Column('referred_id', sa.BigInteger(), nullable=False),
        sa.Column('join_bonus_paid', sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column('reaction_bonus_paid', sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column('retention_bonus_paid', sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['referrer_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['referred_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('referred_id')
    )
    op.create_index('ix_referrals_referrer_id', 'referrals', ['referrer_id'])
    op.create_table(
        'transactions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('amount_usdt', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('type', sa.Enum('referral_join', 'referral_reaction', 'referral_retention', name='transactiontype'), nullable=False),
        sa.Column('related_user_id', sa.BigInteger(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_transactions_user_id', 'transactions', ['user_id'])
    op.create_index('ix_transactions_created_at', 'transactions', ['created_at'])
    op.create_table(
        'withdrawals',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('amount_usdt', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('wallet_address', sa.String(length=256), nullable=False),
        sa.Column('status', sa.Enum('pending', 'approved', 'rejected', name='withdrawalstatus'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_withdrawals_status', 'withdrawals', ['status'])
    op.create_table(
        'channel_reactions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('post_id', sa.BigInteger(), nullable=False),
        sa.Column('reacted_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', name='uq_channel_reactions_user')
    )


def downgrade() -> None:
    op.drop_table('channel_reactions')
    op.drop_index('ix_withdrawals_status', table_name='withdrawals')
    op.drop_table('withdrawals')
    op.drop_index('ix_transactions_created_at', table_name='transactions')
    op.drop_index('ix_transactions_user_id', table_name='transactions')
    op.drop_table('transactions')
    op.drop_index('ix_referrals_referrer_id', table_name='referrals')
    op.drop_table('referrals')
    op.drop_table('users')
    op.execute("DROP TYPE IF EXISTS transactiontype")
    op.execute("DROP TYPE IF EXISTS withdrawalstatus")
