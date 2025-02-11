"""Create processing, artifacts and user_process tables

Revision ID: 4c9036656343
Revises: ebe8f264caf9
Create Date: 2024-03-19 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '4c9036656343'
down_revision: Union[str, None] = 'ebe8f264caf9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop existing enum types if they exist
    op.execute("""
        DROP TYPE IF EXISTS requesttype CASCADE;
        DROP TYPE IF EXISTS requeststatus CASCADE;
        DROP TYPE IF EXISTS processartifacttype CASCADE;
        DROP TYPE IF EXISTS processartifactformat CASCADE;
        DROP TYPE IF EXISTS userprocesssourcetype CASCADE;
    """)

    # Create enum types
    for enum_name, enum_values in [
        ('requesttype', "'audio', 'text', 'file', 'youtube'"),
        ('requeststatus', "'pending', 'processing', 'completed', 'failed'"),
        ('processartifacttype', "'transcription', 'summary'"),
        ('processartifactformat', "'text', 'srt', 'json'"),
        ('userprocesssourcetype', "'file', 'url'")
    ]:
        op.execute(f"CREATE TYPE {enum_name} AS ENUM ({enum_values})")

    # Create uprocess table
    op.create_table(
        'uprocess',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('type', sa.Enum('audio', 'text', 'file', 'youtube', name='requesttype'), nullable=False),
        sa.Column('status', sa.Enum('pending', 'processing', 'completed', 'failed', name='requeststatus'), nullable=False),
        sa.Column('request_data', postgresql.JSONB(), nullable=True),
        sa.Column('source_metadata', postgresql.JSONB(), nullable=False),
        sa.Column('source_type', sa.Enum('file', 'url', name='userprocesssourcetype'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id')),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), onupdate=sa.text('CURRENT_TIMESTAMP')),
    )
    op.create_index('ix_uprocess_id', 'uprocess', ['id'])

    # Create process_artifacts table
    op.create_table(
        'process_artifacts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('request_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('uprocess.id')),
        sa.Column('type', sa.Enum('transcription', 'summary', name='processartifacttype'), nullable=False),
        sa.Column('result', sa.Text()),
        sa.Column('result_format', sa.Enum('text', 'srt', 'json', name='processartifactformat'), nullable=False),
        sa.Column('lang', sa.String()),
        sa.Column('source_file', sa.String(), nullable=True),
        sa.Column('source_file_size', sa.Integer(), nullable=True),
        sa.Column('source_file_type', sa.String(), nullable=True),
        sa.Column('owner_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id')),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), onupdate=sa.text('CURRENT_TIMESTAMP')),
    )
    op.create_index('ix_process_artifacts_id', 'process_artifacts', ['id'])
    
    # Create GiST index for result column
    op.execute('CREATE EXTENSION IF NOT EXISTS pg_trgm')
    op.execute(
        'CREATE INDEX ix_process_artifacts_result_gist ON process_artifacts USING gist (result gist_trgm_ops)'
    )


def downgrade() -> None:
    # Drop tables
    op.drop_index('ix_process_artifacts_result_gist')
    op.drop_index('ix_process_artifacts_id')
    op.drop_table('process_artifacts')
    op.drop_index('ix_uprocess_id')
    op.drop_table('uprocess')

    # Drop enum types
    op.execute('DROP TYPE requesttype')
    op.execute('DROP TYPE requeststatus')
    op.execute('DROP TYPE processartifacttype')
    op.execute('DROP TYPE processartifactformat')
    op.execute('DROP TYPE userprocesssourcetype')
