"""initial schema

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-08-26 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. Users Table ────────────────────────────────────────────────────────
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('google_sub', sa.String(length=255), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('oauth_refresh_token', sa.Text(), nullable=True),
        sa.Column(
            'send_mode',
            sa.Enum('manual', 'auto', name='send_mode_enum'),
            server_default='manual',
            nullable=False
        ),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email')
    )
    op.create_index(op.f('ix_users_google_sub'), 'users', ['google_sub'], unique=True)

    # ── 2. Resumes Table ──────────────────────────────────────────────────────
    op.create_table(
        'resumes',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('source_text', sa.Text(), nullable=False),
        sa.Column('source_html', sa.Text(), nullable=False),
        sa.Column('is_base', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_resumes_user_id'), 'resumes', ['user_id'], unique=False)

    # ── 3. Jobs Table ─────────────────────────────────────────────────────────
    op.create_table(
        'jobs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('source', sa.String(length=50), nullable=False),
        sa.Column('external_id', sa.String(length=255), nullable=True),
        sa.Column('url', sa.String(length=1024), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=True),
        sa.Column('company', sa.String(length=255), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('recruiter_email', sa.String(length=255), nullable=True),
        sa.Column('posted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('scraped_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            'apollo_enrichment',
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'),
            nullable=True
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('url')
    )
    op.create_index(op.f('ix_jobs_external_id'), 'jobs', ['external_id'], unique=False)

    # ── 4. Applications Table ─────────────────────────────────────────────────
    op.create_table(
        'applications',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('job_id', sa.Integer(), nullable=False),
        sa.Column('resume_id', sa.Integer(), nullable=True),
        sa.Column(
            'applied_status',
            sa.Enum('no', 'yes', 'manual', name='applied_status_enum'),
            server_default='no',
            nullable=False
        ),
        sa.Column(
            'mode',
            sa.Enum('auto', 'manual', name='application_mode_enum'),
            server_default='manual',
            nullable=False
        ),
        sa.Column(
            'status',
            sa.Enum('discovered', 'tailoring', 'pending_approval', 'approved', 'sent', 'saved', 'failed', name='application_status_enum'),
            server_default='discovered',
            nullable=False
        ),
        sa.Column('tailored_html', sa.Text(), nullable=True),
        sa.Column('rendered_pdf_url', sa.Text(), nullable=True),
        sa.Column('ats_score', sa.Integer(), nullable=True),
        sa.Column('gap_analysis', sa.Text(), nullable=True),
        sa.Column('drive_folder_url', sa.Text(), nullable=True),
        sa.Column('email_draft', sa.Text(), nullable=True),
        sa.Column('approval_attempts', sa.Integer(), server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['resume_id'], ['resumes.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_applications_job_id'), 'applications', ['job_id'], unique=False)
    op.create_index(op.f('ix_applications_user_id'), 'applications', ['user_id'], unique=False)

    # ── 5. Agent Runs Table ───────────────────────────────────────────────────
    op.create_table(
        'agent_runs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('application_id', sa.Integer(), nullable=False),
        sa.Column('node_name', sa.String(length=100), nullable=False),
        sa.Column(
            'status',
            sa.Enum('running', 'success', 'failure', name='run_status_enum'),
            nullable=False
        ),
        sa.Column(
            'state_snapshot',
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'),
            nullable=True
        ),
        sa.Column('latency_ms', sa.Integer(), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['application_id'], ['applications.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_agent_runs_application_id'), 'agent_runs', ['application_id'], unique=False)


def downgrade() -> None:
    op.drop_table('agent_runs')
    op.drop_table('applications')
    op.drop_table('jobs')
    op.drop_table('resumes')
    op.drop_table('users')
    # Clean up enums on Postgres
    op.execute("DROP TYPE IF EXISTS run_status_enum")
    op.execute("DROP TYPE IF EXISTS application_status_enum")
    op.execute("DROP TYPE IF EXISTS send_mode_enum")
