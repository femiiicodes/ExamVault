"""update user model

Revision ID: 1a53100cd21d
Revises: 2546e5ad8fc5
Create Date: 2026-07-23 17:57:57.811545

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1a53100cd21d'
down_revision: Union[str, Sequence[str], None] = '2546e5ad8fc5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('users') as batch_op:
        batch_op.add_column(sa.Column('first_name',sa.String))
        batch_op.add_column(sa.Column('last_name',sa.String))
        


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_column('first_name')
        batch_op.drop_column('last_name')
        

