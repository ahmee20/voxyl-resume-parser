# AI Job Application Autopilot — Implementation Plan

This document is the single source of truth for building this project. It is written
for an AI coding agent (Claude Code, Cursor, etc.) to read, plan against, and implement
from. Follow it in order. Do not skip the phase gate in Section 6.

---

## 1. Project goal

A portfolio project demonstrating full-stack AI engineering: an agentic pipeline that
discovers jobs, tailors a resume per job using an LLM, and (optionally, with approval)
applies on the user's behalf. The primary audience for this project is technical
interviewers reviewing the author's portfolio — code quality, architectural judgment,
and evaluation rigor matter more than feature count.

Two user flows, both supported by the same pipeline:

- **Auto mode**: daily/2-hourly cron discovers new jobs, tailors + generates a resume,
  drafts an email, runs it through an approval loop, and — only with explicit prior
  user opt-in — sends the email and files it in Drive.
- **Manual mode**: same pipeline, but stops before sending. The user is presented with
  a few resume/email variants and picks one, or just downloads the tailored resume.

## 2. Hard constraints (do not deviate)

1. **Backend first, completely, before any frontend work.** Build the FastAPI backend
   and a minimal server-rendered UI (Jinja2 templates + plain HTML/CSS, no JS framework)
   sufficient to exercise every flow manually. Do not start on a separate frontend
   (React, etc.) until the author explicitly signals to move on. See Section 6.
2. **Agent orchestration must use a real agent framework — not a hand-rolled state
   machine.** Use **LangGraph**. Rationale: it models this pipeline naturally as a graph
   with conditional edges (auto vs. manual branch, the feedback-loop retry edge), it has
   first-class LangSmith tracing, and it's Python-native alongside FastAPI. Every LLM-driven
   step (query planning, gap analysis, resume tailoring, approval agents) is a LangGraph
   node, not an inline function calling the LLM directly.
3. **Evaluation and observability must use LangSmith.** Every graph run must be traced.
   Every LLM node needs a corresponding LangSmith eval (Section 8). This is a required
   deliverable, not a stretch goal — it is one of the things that differentiates this
   project in a portfolio review.
4. **No API key, secret, or credential ever appears in code.** Everything is loaded from
   environment variables via a single `Settings` object (pydantic-settings). See Section 7
   for the `.env.example` template, which must ship with detailed comments.
5. **Auth is Google-only.** Sign-in is "Sign in with Google" (OpenID Connect) — no
   username/password, no other providers. The same OAuth grant must also authorize
   Gmail (send + read, to check for replies/bounces) and Drive (file read/write) scopes,
   so the user consents once. No other identity or storage provider is in scope (no S3,
   no SendGrid, no separate email account) — Gmail and Drive are the only mail/storage
   surfaces.
6. **Never auto-send without explicit, standing opt-in**, and even then, rate-limit it
   (Section 9). Default every new user to manual mode.

## 3. Tech stack

| Concern | Choice | Notes |
|---|---|---|
| Language | Python 3.12 | |
| API framework | FastAPI | async, OpenAPI docs for free — useful in a portfolio review |
| Agent orchestration | LangGraph | see constraint #2 |
| LLM abstraction | LangChain chat model interface | keep provider-swappable; default to Anthropic Claude via `ANTHROPIC_API_KEY`, but code against `BaseChatModel` so OpenAI is a one-line swap |
| Evaluation/tracing | LangSmith | traces + datasets + eval runs, see Section 8 |
| DB | PostgreSQL + SQLAlchemy 2.0 (async) + Alembic migrations | SQLite is fine for first local dev pass, but the models must be Postgres-clean since that's what a reviewer will expect to see |
| Scheduler | APScheduler (in-process) | Celery+Redis is the "real" production answer; call this out in the README as a known scaling limitation rather than building it now — scope discipline matters more here than infra completeness |
| Auth | Authlib (`authlib.integrations.starlette_client`) for Google OAuth2/OIDC | request `openid email profile https://www.googleapis.com/auth/gmail.send https://www.googleapis.com/auth/gmail.readonly https://www.googleapis.com/auth/drive.file` |
| Job scraping | Apify client (`apify-client`) | |
| Enrichment | Apollo.io REST API | |
| Resume → PDF | PDF.co API | LLM outputs HTML in the same layout as the uploaded resume; PDF.co renders it |
| Templating (server UI) | Jinja2 | |
| Config | `pydantic-settings` | single `Settings` class, `.env` loaded once at startup |
| Testing | `pytest`, `pytest-asyncio`, `httpx.AsyncClient` for API tests | |

## 4. Data model (Postgres, SQLAlchemy)

Rough schema — the agent should refine column types but keep these tables and
relationships:

- **users**: `id`, `google_sub` (unique), `email`, `name`, `oauth_refresh_token` (encrypted
  at rest — see Section 9), `send_mode` (`manual` | `auto`, default `manual`), `created_at`
- **resumes**: `id`, `user_id` FK, `version`, `source_text`, `source_html` (extracted layout),
  `is_base` (bool — the originally uploaded resume vs. a tailored version), `created_at`
- **jobs**: `id`, `source` (`apify`), `external_id`, `url` (unique, dedup key), `title`,
  `company`, `description`, `recruiter_email`, `posted_at`, `scraped_at`,
  `apollo_enrichment` (JSONB)
- **applications**: `id`, `user_id` FK, `job_id` FK, `resume_id` FK (tailored version used),
  `mode` (`auto` | `manual`), `status` (`discovered` → `tailoring` → `pending_approval` →
  `approved` → `sent` | `saved` → `failed`), `drive_folder_url`, `email_draft`,
  `approval_attempts`, `created_at`, `updated_at`
- **agent_runs**: `id`, `application_id` FK, `langsmith_run_id`, `node_name`, `input`,
  `output`, `latency_ms`, `created_at` — this table is what makes the observability story
  demoable even outside the LangSmith UI (e.g. in a simple `/applications/{id}` timeline view)

Unique constraint on `jobs.url` is the primary dedup mechanism — see Section 9.

## 5. LangGraph pipeline design

Model the pipeline as one LangGraph graph with these nodes. Each node is a LangGraph
node function, not a plain Python function called from a FastAPI route — routes only
trigger graph runs and read state.

1. `extract_resume` — parse the uploaded resume (PDF/DOCX) into text + a normalized HTML
   skeleton that captures the original layout/sections.
2. `plan_search_queries` — LLM node; given the base resume, proposes job-title/seniority
   search queries (e.g. "AI engineer", "senior software engineer").
3. `scrape_jobs` — tool node calling Apify with the planned queries.
4. `enrich_jobs` — tool node calling Apollo for company/recruiter contact enrichment.
5. `filter_relevant` — LLM or rule-based node filtering scraped jobs down to
   relevant/eligible ones before they hit the DB.
6. `persist_jobs` — write to `jobs` table, deduping on URL.
7. `analyze_gaps` — LLM node: job description + base resume → list of missing
   keywords/skills genuinely present in the candidate's real experience (must not invent
   experience — this constraint should be in the node's system prompt and checked by the
   eval in Section 8).
8. `tailor_resume` — LLM node: fills the identified gaps into the resume HTML, preserving
   the original resume's structure/formatting.
9. `render_pdf` — tool node calling PDF.co.
10. `branch_send_mode` — conditional edge: reads `user.send_mode`. Manual → go to
    `present_variants`. Auto → go to `draft_email`.
11. `present_variants` (manual path) — generates 2-3 resume/email variants, stops the
    graph, waits for user selection via the UI, then goes to `upload_manual`.
12. `upload_manual` (manual path) — uploads the chosen resume to Drive (root/no per-job
    folder, no email sent). Terminal node for manual path.
13. `draft_email` (auto path) — LLM node drafting the outreach email.
14. `review_loop` (auto path) — two LangGraph nodes run in parallel/sequence:
    - `agent_ats_reviewer` — scores keyword/ATS match and flags any invented claims
      against the source resume.
    - `agent_factual_reviewer` — checks the resume and email against the base resume for
      hallucinated experience, credentials, or contact info.
    Conditional edge loops back to `tailor_resume`/`draft_email` on rejection, up to a
    **hard cap of 3 attempts** (Section 9), then routes to `manual_fallback` if still
    unapproved.
15. `send_and_file` (auto path, approved) — sends via Gmail API, uploads resume +
    `email.txt` to a new per-job Drive folder, updates `applications.status`.
16. `manual_fallback` — if the auto loop never gets approved, downgrade this one
    application to manual review instead of silently failing or sending something unvetted.

Every node must emit a LangSmith trace with the `application_id` and `node_name` as
metadata, and write a row to `agent_runs`.

## 6. Build phases — respect the gate

**Phase 0 — scaffolding**: repo structure, `Settings`, DB models + Alembic, empty FastAPI
app with health check, LangGraph skeleton with stub nodes, LangSmith wired up end to end
on the stub graph before any real logic is added.

**Phase 1 — backend core (do this completely before Phase 2)**:
- Google OAuth login + session handling
- Resume upload + extraction
- Manual "run pipeline for a single pasted job description" endpoint (this de-risks the
  LLM nodes before scraping/cron complexity is added)
- Full LangGraph pipeline wired to real tools (Apify, Apollo, PDF.co, Gmail, Drive)
- Cron job (APScheduler, every 2 hours, `posted_at` within last 2 hours + URL dedup)
- Minimal Jinja2 UI: login, upload resume, view discovered jobs, view/approve pending
  applications, application history/timeline (reading from `agent_runs`)
- LangSmith datasets + eval suite (Section 8) passing on a fixed test set
- Tests for every route and every LangGraph node (mocking external APIs)

**Phase gate — STOP here.** Do not begin any separate frontend (React/Vue/etc.) or
redesign the UI beyond basic Jinja2 templates until the author explicitly says to
proceed. Phase 1 should be demoable end-to-end through the server-rendered UI first.

**Phase 2 — frontend (only after explicit go-ahead)**: to be scoped later.

## 7. `.env` handling

- All secrets load through one `Settings(BaseSettings)` class in `app/config.py`.
- Nothing in application code ever calls `os.environ` directly or hardcodes a key.
- Ship a `.env.example` (committed) with every variable documented inline — see the
  companion file `.env.example` for the exact template to use, including instructions
  for obtaining each of: Google OAuth client ID/secret, Anthropic API key, LangSmith API
  key, Apify API token, Apollo.io API key, PDF.co API key, DB URL, and the session
  secret key.
- The real `.env` is gitignored.

## 8. Evaluation strategy (LangSmith)

Every LLM node in Section 5 needs a LangSmith dataset + eval, not just tracing:

- `analyze_gaps` / `tailor_resume`: dataset of (base resume, job description) pairs with
  human-labeled "good tailored resume" examples. Evals: keyword coverage against the JD,
  and a **faithfulness/no-hallucination check** — does every claim in the tailored resume
  trace back to something in the source resume? (Use an LLM-as-judge eval for this, and
  treat any hallucination as a failing score — this is the single most important eval in
  the project, both technically and ethically.)
- `plan_search_queries`: eval against a labeled set of (resume → expected query set).
- `agent_ats_reviewer` / `agent_factual_reviewer`: precision/recall against a labeled set
  of resumes that contain known-bad injected hallucinations, to prove the reviewers
  actually catch them.
- `draft_email`: rubric-based LLM-as-judge (tone, relevance, no fabricated claims).

Wire these evals into a `make eval` / `pytest -m eval` command so they can be run on
demand and referenced in the README as a concrete, runnable artifact — this is the part
of the project most worth highlighting in interviews.

## 9. Guardrails (non-negotiable)

- `send_mode` defaults to `manual` for all new users; auto is an explicit opt-in toggle.
- Auto-send is rate-limited: hard cap per user per day (config via `.env`, e.g.
  `MAX_AUTO_SENDS_PER_DAY=10`), and never more than one send to the same company within
  a rolling window (dedup on `jobs.company` + recent `applications`).
- `review_loop` hard cap of 3 attempts before falling back to manual — never loop
  indefinitely, and never send something that was never approved.
- Job dedup is enforced at the DB level (`jobs.url` unique) in addition to the cron's
  2-hour time filter, since scraped "posted_at" timestamps aren't fully reliable.
- OAuth refresh tokens are encrypted at rest (e.g. `cryptography.Fernet` with a key from
  `.env`), never logged, never returned in any API response.
- Structured logging throughout (no `print`), with request IDs, and secrets scrubbed
  from log output.

## 10. Definition of done for Phase 1

- `docker-compose up` (Postgres + app) gets a fresh reviewer to a working login screen.
- A user can log in with Google, upload a resume, and manually trigger the pipeline
  against a pasted job description, ending in a downloadable tailored PDF.
- The cron path runs end-to-end against at least one real scrape in a demo/staging run.
- `pytest` passes, including the eval suite.
- README documents architecture, how to obtain every API key, how to run evals, and
  explicitly states the frontend is out of scope for this phase pending author sign-off.
