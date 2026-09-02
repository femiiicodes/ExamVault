"""remove_department_and_college_columns

Revision ID: e3f5g6h7i8j9
Revises: d2e4f6a8b0c1
Create Date: 2026-08-31 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e3f5g6h7i8j9'
down_revision = 'd2e4f6a8b0c1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop the department and college columns from users table
    op.drop_column('users', 'department')
    op.drop_column('users', 'college')


def downgrade() -> None:
    # Recreate the department and college columns
    op.add_column('users', sa.Column('department', sa.String(), nullable=True))
    op.add_column('users', sa.Column('college', sa.String(), nullable=True))
