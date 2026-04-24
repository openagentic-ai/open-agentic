"""add reasoning_content to messages

Revision ID: a1b2c3d4e5f6
Revises: c3af2e8d41bb
Create Date: 2026-04-24 20:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "c3af2e8d41bb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("messages", sa.Column("reasoning_content", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("messages", "reasoning_content")
