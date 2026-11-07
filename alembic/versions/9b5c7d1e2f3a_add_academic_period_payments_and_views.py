"""add academic periods payments entitlements and daily views

Revision ID: 9b5c7d1e2f3a
Revises: 7a4c1e2b9d8f
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '9b5c7d1e2f3a'
down_revision: Union[str, Sequence[str], None] = '7a4c1e2b9d8f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'academic_periods',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('academic_session', sa.String(), nullable=False),
        sa.Column('semester', sa.String(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('academic_session', 'semester', name='uq_academic_period_session_semester'),
    )
    op.create_index('ix_academic_periods_id', 'academic_periods', ['id'])
    op.create_index('ix_academic_periods_active', 'academic_periods', ['is_active'])
    op.create_index(
        'uq_academic_periods_one_active',
        'academic_periods',
        ['is_active'],
        unique=True,
        postgresql_where=sa.text('is_active = true'),
        sqlite_where=sa.text('is_active = 1'),
    )

    op.create_table(
        'academic_period_switches',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('previous_period_id', sa.Integer(), nullable=True),
        sa.Column('new_period_id', sa.Integer(), nullable=False),
        sa.Column('admin_user_id', sa.Integer(), nullable=False),
        sa.Column('switched_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['previous_period_id'], ['academic_periods.id']),
        sa.ForeignKeyConstraint(['new_period_id'], ['academic_periods.id']),
        sa.ForeignKeyConstraint(['admin_user_id'], ['users.id']),
    )
    op.create_index('ix_academic_period_switches_id', 'academic_period_switches', ['id'])

    op.create_table(
        'payments',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('academic_period_id', sa.Integer(), nullable=False),
        sa.Column('reference', sa.String(), nullable=False),
        sa.Column('authorization_url', sa.String(), nullable=True),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('currency', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('paystack_transaction_id', sa.String(), nullable=True),
        sa.Column('paid_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['academic_period_id'], ['academic_periods.id']),
        sa.UniqueConstraint('reference'),
    )
    op.create_index('ix_payments_id', 'payments', ['id'])
    op.create_index('ix_payments_reference', 'payments', ['reference'])

    op.create_table(
        'entitlements',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('academic_period_id', sa.Integer(), nullable=False),
        sa.Column('payment_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['academic_period_id'], ['academic_periods.id']),
        sa.ForeignKeyConstraint(['payment_id'], ['payments.id']),
        sa.UniqueConstraint('user_id', 'academic_period_id', name='uq_entitlement_user_period'),
    )
    op.create_index('ix_entitlements_id', 'entitlements', ['id'])

    op.create_table(
        'daily_pq_views',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('past_question_id', sa.Integer(), nullable=False),
        sa.Column('view_date', sa.String(), nullable=False),
        sa.Column('viewed_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['past_question_id'], ['pqs.id'], ondelete='CASCADE'),
        sa.UniqueConstraint(
            'user_id', 'past_question_id', 'view_date',
            name='uq_daily_pq_view_user_question_date',
        ),
    )
    op.create_index('ix_daily_pq_views_id', 'daily_pq_views', ['id'])
    op.create_index('ix_daily_pq_views_user_date', 'daily_pq_views', ['user_id', 'view_date'])


def downgrade() -> None:
    op.drop_index('ix_daily_pq_views_user_date', table_name='daily_pq_views')
    op.drop_index('ix_daily_pq_views_id', table_name='daily_pq_views')
    op.drop_table('daily_pq_views')
    op.drop_index('ix_entitlements_id', table_name='entitlements')
    op.drop_table('entitlements')
    op.drop_index('ix_payments_reference', table_name='payments')
    op.drop_index('ix_payments_id', table_name='payments')
    op.drop_table('payments')
    op.drop_index('ix_academic_period_switches_id', table_name='academic_period_switches')
    op.drop_table('academic_period_switches')
    op.drop_index('uq_academic_periods_one_active', table_name='academic_periods')
    op.drop_index('ix_academic_periods_active', table_name='academic_periods')
    op.drop_index('ix_academic_periods_id', table_name='academic_periods')
    op.drop_table('academic_periods')
