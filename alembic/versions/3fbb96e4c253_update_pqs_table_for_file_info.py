"""update pqs table for file info

Revision ID: 3fbb96e4c253
Revises: 
Create Date: 2026-07-21 12:53:21.798992

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3fbb96e4c253'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('pqs') as batch_op:
        batch_op.add_column(sa.Column('file_path',sa.String))
        batch_op.add_column(sa.Column('time_created',sa.DateTime))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('pqs') as batch_op:
        batch_op.drop_column('file_path')
        batch_op.drop_column('date_created')
