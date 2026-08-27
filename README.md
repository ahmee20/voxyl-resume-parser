# AI Job Application Autopilot

A portfolio project demonstrating full-stack AI engineering: an agentic pipeline that discovers jobs, tailors a resume per job using an LLM, and (optionally, with approval) applies on the user's behalf.

## Architecture

```
Google OAuth login
       │
       ▼
Resume Upload & Extraction
       │
       ▼
LangGraph Pipeline
  ├── plan_search_queries  (LLM)
  ├── scrape_jobs          (Apify)
  ├── enrich_jobs          (Apollo.io)
  ├── filter_relevant      (LLM)
  ├── persist_jobs         (DB)
  ├── analyze_gaps         (LLM)
  ├── tailor_resume        (LLM)
  ├── render_pdf           (PDF.co)
  ├── branch_send_mode     (conditional edge)
  │
  ├── [manual path]
  │    ├── present_variants
  │    └── upload_manual   → Google Drive
  │
  └── [auto path]
       ├── draft_email      (LLM)
       ├── review_loop
       │    ├── agent_ats_reviewer    (LLM)
       │    └── agent_factual_reviewer (LLM)
       ├── send_and_file    → Gmail + Drive
       └── manual_fallback  (if loop cap reached)
```

Every graph run is traced in **LangSmith**. Every LLM node writes to the `agent_runs` table for an in-app timeline view.

## Tech Stack

| Layer | Choice |
|---|---|
| API | FastAPI (Python 3.12) |
| Agent orchestration | LangGraph |
| LLM | Anthropic Claude (via LangChain `BaseChatModel`) |
| Tracing + evals | LangSmith |
| Database | PostgreSQL + SQLAlchemy 2.0 async + Alembic |
| Scheduler | APScheduler (in-process, 2-hour cron) |
| Auth | Google OAuth2/OIDC via Authlib |
| Job scraping | Apify |
| Enrichment | Apollo.io |
| Resume → PDF | PDF.co |
| Storage/email | Google Drive + Gmail (same OAuth grant) |
| UI | Jinja2 server-rendered templates |
| Config | pydantic-settings |

## Setup

### Prerequisites

- Python 3.12+
- Docker + Docker Compose (for Postgres)
- API keys for every service listed in `.env.example`

### 1. Clone & install

```bash
git clone <repo-url>
cd job-autopilot
python -m venv .venv
# Windows
.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env and fill in all required values
# See .env.example for instructions on obtaining each key
```

### 3. Start Postgres

```bash
docker-compose up -d db
```

### 4. Run migrations

```bash
alembic upgrade head
```

### 5. Start the app

```bash
uvicorn app.main:app --reload
# App available at http://localhost:8000
# Health check: http://localhost:8000/health
# API docs: http://localhost:8000/docs
```

### 6. Run tests

```bash
pytest
```

### 7. Run evals (LangSmith)

```bash
pytest -m eval
# or
make eval
```

## Obtaining API Keys

See `.env.example` — every variable has inline instructions for where to get it.

## Guardrails

- `send_mode` defaults to `manual` for all new users
- Auto-send requires explicit opt-in toggle per user
- Auto-send is capped at `MAX_AUTO_SENDS_PER_DAY` per user (default: 10)
- Never more than one send to the same company in a rolling window
- Review loop hard-capped at `REVIEW_LOOP_MAX_ATTEMPTS` (default: 3) — falls back to manual review if never approved
- OAuth refresh tokens are encrypted at rest (Fernet)
- Structured logging throughout; secrets scrubbed from log output

## Phase Status

- ✅ **Phase 0** — Scaffolding (complete)
- 🔄 **Phase 1** — Backend core (in progress)
- ⏳ **Phase 2** — Frontend (pending author sign-off after Phase 1 is demoable)

> The frontend (React/Vue/etc.) is explicitly out of scope for Phase 1. The UI is server-rendered Jinja2 templates sufficient to exercise every flow manually.

## Known Limitations / Future Work

- **Scheduler**: APScheduler runs in-process. For production, Celery + Redis is the correct answer — this is a deliberate scope trade-off documented here rather than built now.
- **Email delivery**: Only Gmail API is supported (same Google OAuth grant as auth). No SendGrid or other providers.
- **Storage**: Only Google Drive. No S3 or other providers.
