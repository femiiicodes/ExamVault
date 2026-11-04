"""add auth sessions and security answers

Revision ID: 2f4c8a9d1b7e
Revises: 8cdd5537caf7
Create Date: 2026-10-31 16:55:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '2f4c8a9d1b7e'
down_revision: Union[str, Sequence[str], None] = '8cdd5537caf7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'auth_sessions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('token_hash', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('revoked_at', sa.DateTime(), nullable=True),
        sa.Column('is_persistent', sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token_hash'),
    )
    op.create_index(op.f('ix_auth_sessions_id'), 'auth_sessions', ['id'], unique=False)

    op.create_table(
        'security_answers',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('question_id', sa.String(), nullable=False),
        sa.Column('answer_hash', sa.String(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_security_answers_id'), 'security_answers', ['id'], unique=False)
    op.create_index(
        'uq_security_answers_user_question',
        'security_answers',
        ['user_id', 'question_id'],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index('uq_security_answers_user_question', table_name='security_answers')
    op.drop_index(op.f('ix_security_answers_id'), table_name='security_answers')
    op.drop_table('security_answers')
    op.drop_index(op.f('ix_auth_sessions_id'), table_name='auth_sessions')
    op.drop_table('auth_sessions')
