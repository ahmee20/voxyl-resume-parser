"""add user_id to jobs and update unique constraint

Revision ID: 002_add_user_id_to_jobs
Revises: 001_initial_schema
Create Date: 2026-08-27 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '002_add_user_id_to_jobs'
down_revision: Union[str, None] = '001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add user_id column to jobs table. Keep this migration idempotent because
    # local/Supabase schemas may have been partially synced outside Alembic.
    op.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS user_id INTEGER;")
    op.execute(
        """
        UPDATE jobs
        SET user_id = (SELECT id FROM users ORDER BY id ASC LIMIT 1)
        WHERE user_id IS NULL;
        """
    )
    op.execute("ALTER TABLE jobs ALTER COLUMN user_id SET DEFAULT 1;")
    op.execute("ALTER TABLE jobs ALTER COLUMN user_id SET NOT NULL;")
    op.execute("CREATE INDEX IF NOT EXISTS ix_jobs_user_id ON jobs (user_id);")

    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'fk_jobs_user_id_users'
                  AND conrelid = 'jobs'::regclass
            ) THEN
                ALTER TABLE jobs
                ADD CONSTRAINT fk_jobs_user_id_users
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
            END IF;
        END $$;
        """
    )

    # 2. Replace the old global URL dedupe with user-scoped dedupe.
    op.execute("ALTER TABLE jobs DROP CONSTRAINT IF EXISTS uq_jobs_url;")
    op.execute("ALTER TABLE jobs DROP CONSTRAINT IF EXISTS jobs_url_key;")
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'uq_jobs_user_url'
                  AND conrelid = 'jobs'::regclass
            ) THEN
                ALTER TABLE jobs
                ADD CONSTRAINT uq_jobs_user_url UNIQUE (user_id, url);
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE jobs DROP CONSTRAINT IF EXISTS uq_jobs_user_url;")
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'uq_jobs_url'
                  AND conrelid = 'jobs'::regclass
            ) THEN
                ALTER TABLE jobs
                ADD CONSTRAINT uq_jobs_url UNIQUE (url);
            END IF;
        END $$;
        """
    )
    op.execute("ALTER TABLE jobs DROP CONSTRAINT IF EXISTS fk_jobs_user_id_users;")
    op.execute("DROP INDEX IF EXISTS ix_jobs_user_id;")
    op.drop_column('jobs', 'user_id')
