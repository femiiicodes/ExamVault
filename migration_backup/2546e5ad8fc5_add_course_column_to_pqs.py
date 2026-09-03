"""add course column to pqs

Revision ID: 2546e5ad8fc5
Revises: 3fbb96e4c253
Create Date: 2026-07-21 18:45:32.642011

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2546e5ad8fc5'
down_revision: Union[str, Sequence[str], None] = '3fbb96e4c253'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('pqs',sa.Column('course', sa.String))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('course')
