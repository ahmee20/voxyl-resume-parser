"""
app/config.py — Single source of truth for all configuration.

All values are loaded from environment variables (via .env at startup).
Application code must import `settings` from here — never call os.environ
directly or hardcode any key.
"""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Central settings object.  Every field maps 1-to-1 to a variable in .env.
    Field names use the exact same casing as the .env keys so pydantic-settings
    can match them without aliases.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,   # GOOGLE_CLIENT_ID == google_client_id
        extra="ignore",         # silently ignore unrecognised vars
    )

    # ── Google OAuth ──────────────────────────────────────────────────────────
    google_client_id: str
    google_client_secret: str
    google_redirect_uri: str = "https://voxyl-resume.onrender.com/auth/google/callback"
    frontend_url: str = "https://voxyl-resume.netlify.app/"
    supabase_pooler_url: str = ""

    # ── LLM Configuration ─────────────────────────────────────────────────────
    # Provider choices: "groq", "ollama", "gemini", "anthropic"
    llm_provider: str = "groq"

    # Ollama (Local / Cloud models — used as fallback or standalone)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "minimax-m3:cloud"

    # Groq API
    groq_api_key: str = ""
    groq_fallback_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"

    # Gemini API
    gemini_api_key: str = ""
    gemini_model: str = "gemini-1.5-pro"

    # Anthropic API (optional fallback)
    anthropic_api_key: str = ""

    # ── LangSmith ─────────────────────────────────────────────────────────────
    langchain_tracing_v2: bool = True
    langchain_api_key: str
    langchain_project: str = "job-application-autopilot"

    # ── Apify ─────────────────────────────────────────────────────────────────
    apify_api_token: str
    apify_actor_id: str = ""
    apify_max_results: int = 5

    # ── Apollo.io ─────────────────────────────────────────────────────────────
    apollo_api_key: str

    # ── PDF.co ────────────────────────────────────────────────────────────────
    pdfco_api_key: str
    pdfco_resume_template_id: int = 37621

    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/job_autopilot"
    )

    # ── App secrets ───────────────────────────────────────────────────────────
    session_secret_key: str
    token_encryption_key: str   # Fernet key for OAuth refresh token encryption

    # ── Guardrails ────────────────────────────────────────────────────────────
    max_auto_sends_per_day: int = 10
    review_loop_max_attempts: int = 3

    # ── Scheduler ─────────────────────────────────────────────────────────────
    scheduler_enabled: bool = True           # set False in tests or CI
    scheduler_interval_hours: int = 3        # autonomous discovery loop interval (3 hours)

    # ── Batch Pipeline ────────────────────────────────────────────────────────
    batch_parallel_workers: int = 10         # max concurrent job tailoring threads per batch


    @property
    def resolved_database_url(self) -> str:
        """Prefer the Supabase pooler URL when one is provided."""
        return self.supabase_pooler_url.strip() or self.database_url


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached Settings instance.  Use this everywhere instead of
    instantiating Settings() directly so .env is parsed exactly once."""
    return Settings()


# Module-level singleton for convenient import:  from app.config import settings
settings: Settings = get_settings()
