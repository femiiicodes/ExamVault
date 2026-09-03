"""add cascade delete constraints

Revision ID: c1a2b3c4d5e6
Revises: b1aa33cef98d
Create Date: 2026-08-14 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1a2b3c4d5e6'
down_revision: Union[str, Sequence[str], None] = 'b1aa33cef98d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - add cascade delete and set null constraints."""
    # Drop existing FK constraints
    op.drop_constraint('pqs_uploader_id_fkey', 'pqs', type_='foreignkey')
    op.drop_constraint('users_programme_id_fkey', 'users', type_='foreignkey')
    op.drop_constraint('programme_courses_programme_id_fkey', 'programme_courses', type_='foreignkey')
    op.drop_constraint('programme_courses_course_id_fkey', 'programme_courses', type_='foreignkey')
    
    # Recreate FK constraints with proper on_delete behavior
    # pqs.uploader_id -> users.id: SET NULL when user is deleted
    op.create_foreign_key(
        'pqs_uploader_id_fkey',
        'pqs',
        'users',
        ['uploader_id'],
        ['id'],
        ondelete='SET NULL'
    )
    
    # users.programme_id -> programmes.id: SET NULL when programme is deleted
    op.create_foreign_key(
        'users_programme_id_fkey',
        'users',
        'programmes',
        ['programme_id'],
        ['id'],
        ondelete='SET NULL'
    )
    
    # programme_courses.programme_id -> programmes.id: CASCADE delete
    op.create_foreign_key(
        'programme_courses_programme_id_fkey',
        'programme_courses',
        'programmes',
        ['programme_id'],
        ['id'],
        ondelete='CASCADE'
    )
    
    # programme_courses.course_id -> courses.id: CASCADE delete
    op.create_foreign_key(
        'programme_courses_course_id_fkey',
        'programme_courses',
        'courses',
        ['course_id'],
        ['id'],
        ondelete='CASCADE'
    )


def downgrade() -> None:
    """Downgrade schema - revert to previous FK constraints."""
    # Drop the new constraints
    op.drop_constraint('pqs_uploader_id_fkey', 'pqs', type_='foreignkey')
    op.drop_constraint('users_programme_id_fkey', 'users', type_='foreignkey')
    op.drop_constraint('programme_courses_programme_id_fkey', 'programme_courses', type_='foreignkey')
    op.drop_constraint('programme_courses_course_id_fkey', 'programme_courses', type_='foreignkey')
    
    # Recreate original constraints without on_delete clause
    op.create_foreign_key(
        'pqs_uploader_id_fkey',
        'pqs',
        'users',
        ['uploader_id'],
        ['id']
    )
    op.create_foreign_key(
        'users_programme_id_fkey',
        'users',
        'programmes',
        ['programme_id'],
        ['id']
    )
    op.create_foreign_key(
        'programme_courses_programme_id_fkey',
        'programme_courses',
        'programmes',
        ['programme_id'],
        ['id']
    )
    op.create_foreign_key(
        'programme_courses_course_id_fkey',
        'programme_courses',
        'courses',
        ['course_id'],
        ['id']
    )
