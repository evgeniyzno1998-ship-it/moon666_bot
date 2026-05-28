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

    # 2. Add manual_adjustment to transactiontype enum (PostgreSQL only)
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
