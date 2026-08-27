"""
app/main.py — FastAPI application entry point.

Responsibilities:
- Create the FastAPI app with metadata (title, version, docs URL).
- Register all API routers.
- Manage the application lifespan: DB engine warmup and APScheduler stub.
- Set LangSmith environment variables from settings (they must be set before
  any LangChain import resolves them, so we do it here at module load time).

Nothing in this file calls os.environ directly — all values come from settings.
"""

import asyncio
import os
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.logging_config import configure_logging

# ── LangSmith env vars must be set before langchain imports resolve them ──────
# Enable tracing ONLY if a genuine key is provided (not placeholder)
is_valid_langsmith_key = bool(
    settings.langchain_api_key
    and settings.langchain_api_key != "lsv2_pt_your_actual_key_here"
    and not settings.langchain_api_key.startswith("test-")
    and not settings.langchain_api_key.endswith("your_actual_key_here")
)

if is_valid_langsmith_key and settings.langchain_tracing_v2:
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_API_KEY"] = settings.langchain_api_key
    os.environ["LANGCHAIN_PROJECT"] = settings.langchain_project
else:
    os.environ["LANGCHAIN_TRACING_V2"] = "false"

from app.database import engine  # noqa: E402 — must come after env vars set
from app.api.health import router as health_router  # noqa: E402
from app.api.resumes import router as resumes_router  # noqa: E402
from app.api.auth import router as auth_router  # noqa: E402
from app.api.applications import router as applications_router  # noqa: E402
from app.api.jobs import router as jobs_router  # noqa: E402

log = structlog.get_logger(__name__)


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup / shutdown logic.

    Startup:
    - Configure structured logging.
    - Verify the DB engine can connect (fail fast rather than on first request).
    - Start APScheduler background discovery loop (if enabled).

    Shutdown:
    - Stop the APScheduler.
    - Dispose the DB engine connection pool.
    """
    from app.services.scheduler import start_scheduler, stop_scheduler

    configure_logging()
    log.info("startup", project=settings.langchain_project)

    # Warm up the DB connection pool & automatically ensure tables exist
    try:
        from sqlalchemy import text
        from app.database import Base
        import app.models  # noqa: F401
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            if "postgresql" in settings.database_url or "asyncpg" in settings.database_url:
                # Ensure enums exist
                await conn.execute(text("DO $$ BEGIN CREATE TYPE applied_status_enum AS ENUM ('no', 'yes', 'manual'); EXCEPTION WHEN duplicate_object THEN null; END $$;"))
                await conn.execute(text("DO $$ BEGIN CREATE TYPE application_mode_enum AS ENUM ('auto', 'manual'); EXCEPTION WHEN duplicate_object THEN null; END $$;"))
                await conn.execute(text("DO $$ BEGIN CREATE TYPE application_status_enum AS ENUM ('discovered', 'tailoring', 'pending_approval', 'approved', 'sent', 'saved', 'failed'); EXCEPTION WHEN duplicate_object THEN null; END $$;"))
                
                # Ensure applications columns exist
                await conn.execute(text("ALTER TABLE applications ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id) ON DELETE CASCADE;"))
                await conn.execute(text("ALTER TABLE applications ADD COLUMN IF NOT EXISTS job_id INTEGER REFERENCES jobs(id) ON DELETE CASCADE;"))
                await conn.execute(text("ALTER TABLE applications ADD COLUMN IF NOT EXISTS resume_id INTEGER REFERENCES resumes(id) ON DELETE SET NULL;"))
                await conn.execute(text("ALTER TABLE applications ADD COLUMN IF NOT EXISTS applied_status applied_status_enum DEFAULT 'no';"))
                await conn.execute(text("ALTER TABLE applications ADD COLUMN IF NOT EXISTS mode application_mode_enum DEFAULT 'manual';"))
                await conn.execute(text("ALTER TABLE applications ADD COLUMN IF NOT EXISTS status application_status_enum DEFAULT 'discovered';"))
                await conn.execute(text("ALTER TABLE applications ADD COLUMN IF NOT EXISTS tailored_html TEXT;"))
                await conn.execute(text("ALTER TABLE applications ADD COLUMN IF NOT EXISTS rendered_pdf_url TEXT;"))
                await conn.execute(text("ALTER TABLE applications ADD COLUMN IF NOT EXISTS ats_score INTEGER;"))
                await conn.execute(text("ALTER TABLE applications ADD COLUMN IF NOT EXISTS gap_analysis TEXT;"))
                await conn.execute(text("ALTER TABLE applications ADD COLUMN IF NOT EXISTS drive_folder_url TEXT;"))
                await conn.execute(text("ALTER TABLE applications ADD COLUMN IF NOT EXISTS email_draft TEXT;"))
                await conn.execute(text("ALTER TABLE applications ADD COLUMN IF NOT EXISTS approval_attempts INTEGER DEFAULT 0;"))

                # Ensure user profile columns exist for resume/email personalization
                await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS preferred_name VARCHAR(255);"))
                await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS preferred_roles JSONB DEFAULT '[]'::jsonb;"))
                await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS preferred_countries JSONB DEFAULT '[]'::jsonb;"))
                await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS github_url TEXT;"))
                await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS portfolio_url TEXT;"))
                await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS linkedin_url TEXT;"))
                await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS profile_completed BOOLEAN DEFAULT FALSE;"))
                await conn.execute(text("UPDATE users SET preferred_roles = COALESCE(preferred_roles, '[]'::jsonb);"))
                await conn.execute(text("UPDATE users SET preferred_countries = COALESCE(preferred_countries, '[]'::jsonb);"))
                await conn.execute(text("UPDATE users SET profile_completed = FALSE WHERE profile_completed IS NULL;"))
                await conn.execute(text("ALTER TABLE users ALTER COLUMN profile_completed SET NOT NULL;"))

                # Persist the original resume filename so it can be reused by the UI.
                await conn.execute(text("ALTER TABLE resumes ADD COLUMN IF NOT EXISTS filename VARCHAR(255);"))
                await conn.execute(text("UPDATE resumes SET filename = COALESCE(filename, 'resume-v' || version::text || '.pdf') WHERE filename IS NULL;"))

                # Add targeted indexes for the most common fetch patterns.
                await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_resumes_user_is_base_version ON resumes (user_id, is_base, version DESC);"))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_jobs_user_id_desc ON jobs (user_id, id DESC);"))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_applications_user_id_desc ON applications (user_id, id DESC);"))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_agent_runs_application_id_desc ON agent_runs (application_id, id DESC);"))
                
                # Ensure jobs columns exist
                await conn.execute(text("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS is_qualified BOOLEAN DEFAULT TRUE;"))
                await conn.execute(text("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS match_score INTEGER;"))
                await conn.execute(text("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS filter_reason TEXT;"))
        log.info("database_connected_and_tables_ready", url=settings.database_url.split("@")[-1])
    except Exception as exc:
        log.error("database_connection_failed", error=str(exc))
        # Don't crash startup — the health check will surface the error.

    # Start the background discovery scheduler
    if settings.scheduler_enabled:
        start_scheduler()

    log.info("app_ready", host="0.0.0.0", port=8000)

    yield

    # ── Shutdown ──────────────────────────────────────────────────────────────
    stop_scheduler()
    await engine.dispose()
    log.info("shutdown")


# ── App factory ───────────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    app = FastAPI(
        title="Voxyl",
        description=(
            "Agentic pipeline: discovers jobs, tailors resumes with LangGraph + Claude, "
            "and optionally applies on the user's behalf via Gmail. "
            "Every run is traced in LangSmith."
        ),
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # Session Middleware for signed HTTP-only cookies
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret_key,
        session_cookie="job_autopilot_session",
        max_age=14 * 24 * 3600,  # 14 days
        same_site="lax",
        https_only=False,  # Set to True in production HTTPS environments
    )

    # CORS — tighten in production
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://localhost:8000",
            "http://localhost:5173",
            "http://localhost:5174",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:5174",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Routers ───────────────────────────────────────────────────────────────
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(resumes_router)
    app.include_router(applications_router)
    app.include_router(jobs_router)

    return app


app = create_app()
