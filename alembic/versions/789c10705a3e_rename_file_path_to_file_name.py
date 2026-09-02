"""rename file_path to file_name

Revision ID: 789c10705a3e
Revises: e3f5g6h7i8j9
Create Date: 2026-09-01 15:28:33.513121

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '789c10705a3e'
down_revision: Union[str, Sequence[str], None] = 'e3f5g6h7i8j9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "pqs",
        "file_path",
        new_column_name="file_key"
    )

def upgrade() -> None:
    op.alter_column(
        "pqs",
        "file_path",
        new_column_name="file_key"
    )