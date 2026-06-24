"""Add video request type

Revision ID: add_video_request_type
Revises: optimize_process_artifacts
Create Date: 2026-06-20 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'add_video_request_type'
down_revision: Union[str, None] = 'optimize_process_artifacts'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE requesttype ADD VALUE IF NOT EXISTS 'VIDEO'")


def downgrade() -> None:
    pass
