"""align database schema with current ORM models

Revision ID: 003_align_schema_with_models
Revises: 002_add_user_id_to_jobs
Create Date: 2026-08-27 18:30:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "003_align_schema_with_models"
down_revision: Union[str, None] = "002_add_user_id_to_jobs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Match app.models.resume.Resume
    op.execute("ALTER TABLE resumes ALTER COLUMN source_html DROP NOT NULL;")

    # Match app.models.job.Job
    op.execute("ALTER TABLE jobs ALTER COLUMN url TYPE TEXT;")
    op.execute("ALTER TABLE jobs ALTER COLUMN title TYPE VARCHAR(512);")
    op.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS is_qualified BOOLEAN DEFAULT TRUE;")
    op.execute("UPDATE jobs SET is_qualified = TRUE WHERE is_qualified IS NULL;")
    op.execute("ALTER TABLE jobs ALTER COLUMN is_qualified SET NOT NULL;")
    op.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS match_score INTEGER;")
    op.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS filter_reason TEXT;")
    op.execute("CREATE INDEX IF NOT EXISTS ix_jobs_company ON jobs (company);")

    # Match app.models.agent_run.AgentRun. Older migrations used status/state_snapshot
    # columns, but the current app reads/writes input/output snapshots instead.
    op.execute("ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS langsmith_run_id VARCHAR(255);")
    op.execute("ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS input JSONB;")
    op.execute("ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS output JSONB;")
    op.execute("ALTER TABLE agent_runs ALTER COLUMN latency_ms DROP NOT NULL;")
    op.execute("CREATE INDEX IF NOT EXISTS ix_agent_runs_node_name ON agent_runs (node_name);")
    op.execute("ALTER TABLE agent_runs DROP COLUMN IF EXISTS state_snapshot;")
    op.execute("ALTER TABLE agent_runs DROP COLUMN IF EXISTS error_message;")
    op.execute("ALTER TABLE agent_runs DROP COLUMN IF EXISTS status;")
    op.execute("DROP TYPE IF EXISTS run_status_enum;")


def downgrade() -> None:
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE run_status_enum AS ENUM ('running', 'success', 'failure');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
        """
    )
    op.execute("ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS status run_status_enum;")
    op.execute("UPDATE agent_runs SET status = 'success' WHERE status IS NULL;")
    op.execute("ALTER TABLE agent_runs ALTER COLUMN status SET NOT NULL;")
    op.execute("ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS state_snapshot JSONB;")
    op.execute("ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS error_message TEXT;")
    op.execute("DROP INDEX IF EXISTS ix_agent_runs_node_name;")
    op.execute("ALTER TABLE agent_runs ALTER COLUMN latency_ms SET NOT NULL;")
    op.execute("ALTER TABLE agent_runs DROP COLUMN IF EXISTS output;")
    op.execute("ALTER TABLE agent_runs DROP COLUMN IF EXISTS input;")
    op.execute("ALTER TABLE agent_runs DROP COLUMN IF EXISTS langsmith_run_id;")

    op.execute("DROP INDEX IF EXISTS ix_jobs_company;")
    op.execute("ALTER TABLE jobs DROP COLUMN IF EXISTS filter_reason;")
    op.execute("ALTER TABLE jobs DROP COLUMN IF EXISTS match_score;")
    op.execute("ALTER TABLE jobs DROP COLUMN IF EXISTS is_qualified;")
    op.execute("ALTER TABLE jobs ALTER COLUMN title TYPE VARCHAR(255);")
    op.execute("ALTER TABLE jobs ALTER COLUMN url TYPE VARCHAR(1024);")

    op.execute("ALTER TABLE resumes ALTER COLUMN source_html SET NOT NULL;")
