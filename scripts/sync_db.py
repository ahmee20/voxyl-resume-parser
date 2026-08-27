"""
scripts/sync_db.py — Comprehensive database schema synchronization for Supabase PostgreSQL.
"""

import asyncio
from sqlalchemy import text
from app.database import engine


async def sync_database():
    async with engine.begin() as conn:
        print("Synchronizing live database schema...")

        # 1. Create Enums if not exist
        enum_queries = [
            """
            DO $$ BEGIN
                CREATE TYPE applied_status_enum AS ENUM ('no', 'yes', 'manual');
            EXCEPTION
                WHEN duplicate_object THEN null;
            END $$;
            """,
            """
            DO $$ BEGIN
                CREATE TYPE application_mode_enum AS ENUM ('auto', 'manual');
            EXCEPTION
                WHEN duplicate_object THEN null;
            END $$;
            """,
            """
            DO $$ BEGIN
                CREATE TYPE application_status_enum AS ENUM ('discovered', 'tailoring', 'pending_approval', 'approved', 'sent', 'saved', 'failed');
            EXCEPTION
                WHEN duplicate_object THEN null;
            END $$;
            """,
        ]
        for q in enum_queries:
            await conn.execute(text(q))

        # 2. Check and alter applications columns
        app_columns = [
            "ALTER TABLE applications ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id) ON DELETE CASCADE;",
            "ALTER TABLE applications ADD COLUMN IF NOT EXISTS job_id INTEGER REFERENCES jobs(id) ON DELETE CASCADE;",
            "ALTER TABLE applications ADD COLUMN IF NOT EXISTS resume_id INTEGER REFERENCES resumes(id) ON DELETE SET NULL;",
            "ALTER TABLE applications ADD COLUMN IF NOT EXISTS applied_status applied_status_enum DEFAULT 'no';",
            "ALTER TABLE applications ADD COLUMN IF NOT EXISTS mode application_mode_enum DEFAULT 'manual';",
            "ALTER TABLE applications ADD COLUMN IF NOT EXISTS status application_status_enum DEFAULT 'discovered';",
            "ALTER TABLE applications ADD COLUMN IF NOT EXISTS tailored_html TEXT;",
            "ALTER TABLE applications ADD COLUMN IF NOT EXISTS rendered_pdf_url TEXT;",
            "ALTER TABLE applications ADD COLUMN IF NOT EXISTS ats_score INTEGER;",
            "ALTER TABLE applications ADD COLUMN IF NOT EXISTS gap_analysis TEXT;",
            "ALTER TABLE applications ADD COLUMN IF NOT EXISTS drive_folder_url TEXT;",
            "ALTER TABLE applications ADD COLUMN IF NOT EXISTS email_draft TEXT;",
            "ALTER TABLE applications ADD COLUMN IF NOT EXISTS approval_attempts INTEGER DEFAULT 0;",
            "ALTER TABLE applications ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW();",
            "ALTER TABLE applications ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();",
        ]
        for q in app_columns:
            try:
                await conn.execute(text(q))
            except Exception as e:
                print(f"Notice on application column: {e}")

        # 3. Check and alter jobs columns
        job_columns = [
            "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id) ON DELETE CASCADE DEFAULT 1;",
            "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS is_qualified BOOLEAN DEFAULT TRUE;",
            "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS match_score INTEGER;",
            "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS filter_reason TEXT;",
            "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS apollo_enrichment JSONB;",
            "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS recruiter_email VARCHAR(255);",
        ]
        for q in job_columns:
            try:
                await conn.execute(text(q))
            except Exception as e:
                print(f"Notice on job column: {e}")

        # 4. Check and alter resumes columns
        resume_columns = [
            "ALTER TABLE resumes ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id) ON DELETE CASCADE;",
            "ALTER TABLE resumes ADD COLUMN IF NOT EXISTS version INTEGER DEFAULT 1;",
            "ALTER TABLE resumes ADD COLUMN IF NOT EXISTS source_text TEXT;",
            "ALTER TABLE resumes ADD COLUMN IF NOT EXISTS source_html TEXT;",
            "ALTER TABLE resumes ADD COLUMN IF NOT EXISTS is_base BOOLEAN DEFAULT TRUE;",
            "ALTER TABLE resumes ADD COLUMN IF NOT EXISTS filename VARCHAR(255);",
        ]
        for q in resume_columns:
            try:
                await conn.execute(text(q))
            except Exception as e:
                print(f"Notice on resume column: {e}")

        await conn.execute(text("UPDATE resumes SET filename = COALESCE(filename, 'resume-v' || version::text || '.pdf') WHERE filename IS NULL;"))

        # 4. Check and alter users columns
        user_columns = [
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS preferred_name VARCHAR(255);",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS preferred_roles JSONB DEFAULT '[]'::jsonb;",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS preferred_countries JSONB DEFAULT '[]'::jsonb;",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS github_url TEXT;",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS portfolio_url TEXT;",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS linkedin_url TEXT;",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS profile_completed BOOLEAN DEFAULT FALSE;",
        ]
        for q in user_columns:
            try:
                await conn.execute(text(q))
            except Exception as e:
                print(f"Notice on user column: {e}")

        await conn.execute(text("UPDATE users SET preferred_roles = COALESCE(preferred_roles, '[]'::jsonb);"))
        await conn.execute(text("UPDATE users SET preferred_countries = COALESCE(preferred_countries, '[]'::jsonb);"))
        await conn.execute(text("UPDATE users SET profile_completed = FALSE WHERE profile_completed IS NULL;"))
        await conn.execute(text("ALTER TABLE users ALTER COLUMN profile_completed SET NOT NULL;"))

        # 5. Check and create / update agent_runs table
        await conn.execute(
            text(
                """
            CREATE TABLE IF NOT EXISTS agent_runs (
                id SERIAL PRIMARY KEY,
                application_id INTEGER REFERENCES applications(id) ON DELETE CASCADE,
                langsmith_run_id VARCHAR(255),
                node_name VARCHAR(100) NOT NULL,
                status VARCHAR(20) DEFAULT 'success',
                input JSONB,
                output JSONB,
                latency_ms INTEGER,
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
        """
            )
        )

        agent_run_columns = [
            "ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS langsmith_run_id VARCHAR(255);",
            "ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS input JSONB;",
            "ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS output JSONB;",
            "ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS latency_ms INTEGER;",
            "ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS node_name VARCHAR(100);",
            "ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'success';",
            "ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW();",
        ]
        for q in agent_run_columns:
            try:
                await conn.execute(text(q))
            except Exception as e:
                print(f"Notice on agent_runs column: {e}")

        print("Successfully synchronized all PostgreSQL tables, columns, and enums!")


if __name__ == "__main__":
    asyncio.run(sync_database())
