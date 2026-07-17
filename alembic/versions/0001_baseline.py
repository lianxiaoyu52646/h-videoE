"""baseline schema for mixed-mode refactor

Revision ID: 0001_baseline
Revises:
Create Date: 2026-07-16 12:16:00
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing SQLite users can keep using the runtime compatibility migration in
    # app/database.py, then `alembic stamp head` to adopt Alembic going forward.
    pass


def downgrade() -> None:
    pass
