"""link pqs to courses and remove department

Revision ID: d2e4f6a8b0c1
Revises: c1a2b3c4d5e6
Create Date: 2026-08-28 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd2e4f6a8b0c1'
down_revision: Union[str, Sequence[str], None] = 'c1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('pqs', sa.Column('course_id', sa.Integer(), nullable=True))
    connection = op.get_bind()

    # Delete any PQ rows that don't have a course code
    connection.execute(sa.text(
        'DELETE FROM pqs WHERE course IS NULL'
    ))

    connection.execute(sa.text(
        'INSERT INTO courses (code, title) '
        'SELECT DISTINCT pqs.course, pqs.course '
        'FROM pqs '
        'WHERE pqs.course IS NOT NULL '
        'AND NOT EXISTS ('
        '    SELECT 1 FROM courses WHERE courses.code = pqs.course'
        ')'
    ))
    connection.execute(sa.text(
        'UPDATE pqs SET course_id = courses.id '
        'FROM courses WHERE pqs.course = courses.code'
    ))

    unmatched = connection.execute(sa.text(
        'SELECT COUNT(*) FROM pqs WHERE course_id IS NULL'
    )).scalar_one()
    if unmatched:
        raise RuntimeError(f'Cannot migrate {unmatched} PQ row(s) without a course code')

    with op.batch_alter_table('pqs') as batch_op:
        batch_op.alter_column('course_id', nullable=False)
        batch_op.create_foreign_key(
            'pqs_course_id_fkey', 'courses', ['course_id'], ['id'], ondelete='RESTRICT'
        )
        batch_op.drop_column('course')
        batch_op.drop_column('department')


def downgrade() -> None:
    with op.batch_alter_table('pqs') as batch_op:
        batch_op.add_column(sa.Column('course', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('department', sa.String(), nullable=True))
        batch_op.drop_constraint('pqs_course_id_fkey', type_='foreignkey')
        batch_op.drop_column('course_id')
