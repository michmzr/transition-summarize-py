"""Optimize process_artifacts for large text

Revision ID: optimize_process_artifacts
Revises: 4c9036656343
Create Date: 2024-03-17 12:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'optimize_process_artifacts'
down_revision: Union[str, None] = '4c9036656343'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the existing index on result column if it exists
    op.execute('DROP INDEX IF EXISTS ix_process_artifacts_result')

    # Drop the GiST index if it exists
    op.execute('DROP INDEX IF EXISTS ix_process_artifacts_result_gist')

    # Make sure pg_trgm extension is created
    op.execute('CREATE EXTENSION IF NOT EXISTS pg_trgm')

    # Instead of using gin_trgm_ops which might not be available, use a simpler approach
    # Create a functional index on the first 1000 characters for text search
    op.execute('''
    CREATE INDEX ix_process_artifacts_result_substring 
    ON process_artifacts (substring(result, 1, 1000))
    ''')

    # Add a column for storing a hash of the content for quick lookups
    op.add_column('process_artifacts',
                  sa.Column('result_hash', sa.String(64), nullable=True))

    # Create index on the hash column
    op.create_index('ix_process_artifacts_result_hash',
                    'process_artifacts', ['result_hash'])

    # Update the table to use TOAST compression for large text
    op.execute('''
    ALTER TABLE process_artifacts 
    ALTER COLUMN result SET STORAGE EXTERNAL
    ''')


def downgrade() -> None:
    # Drop the new index and column
    op.drop_index('ix_process_artifacts_result_hash')
    op.drop_column('process_artifacts', 'result_hash')
    op.execute('DROP INDEX IF EXISTS ix_process_artifacts_result_substring')

    # Recreate the original index (though this might fail for large texts)
    op.execute(
        'CREATE INDEX ix_process_artifacts_result ON process_artifacts (result)')
