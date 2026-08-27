"""add saved user profile links

Revision ID: 004_add_user_profile_links
Revises: 003_align_schema_with_models
Create Date: 2026-08-27 19:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "004_add_user_profile_links"
down_revision: Union[str, None] = "003_align_schema_with_models"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS preferred_name VARCHAR(255);")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS github_url TEXT;")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS portfolio_url TEXT;")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS linkedin_url TEXT;")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS profile_completed BOOLEAN DEFAULT FALSE;")
    op.execute("UPDATE users SET profile_completed = FALSE WHERE profile_completed IS NULL;")
    op.execute("ALTER TABLE users ALTER COLUMN profile_completed SET NOT NULL;")


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS profile_completed;")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS linkedin_url;")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS portfolio_url;")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS github_url;")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS preferred_name;")
