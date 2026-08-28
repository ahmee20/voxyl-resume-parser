"""
app/services/llm.py — Swappable LLM client factory with automatic multi-provider fallback.

Default configuration:
- Primary: Groq (openai/gpt-oss-120b)
- Automatic Fallback: Ollama (minimax-m3:cloud or local)

Supports:
1. Groq (openai/gpt-oss-120b, llama-3.3-70b-versatile, etc.)
2. Ollama (minimax-m3:cloud, llama3, mistral, etc.)
3. Gemini (gemini-1.5-pro, gemini-1.5-flash)
4. Anthropic Claude (claude-3-5-sonnet)

Returns a standard LangChain BaseChatModel or RunnableWithFallbacks instance.
"""

import structlog
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.runnables import Runnable

from app.config import settings

log = structlog.get_logger(__name__)


def _build_ollama_llm(model: str | None, temperature: float) -> BaseChatModel:
    from langchain_ollama import ChatOllama

    chosen_model = model or settings.ollama_model
    log.info("llm_init", provider="ollama", model=chosen_model, base_url=settings.ollama_base_url)
    return ChatOllama(
        model=chosen_model,
        base_url=settings.ollama_base_url,
        temperature=temperature,
    )


def get_llm(
    provider: str | None = None,
    model: str | None = None,
    temperature: float = 0.0,
    enable_fallback: bool = True,
) -> BaseChatModel | Runnable:
    """
    Return a configured chat model instance based on active provider.
    Defaults to settings.llm_provider ('groq' with 'openai/gpt-oss-120b').
    When Groq is selected, automatically attaches Ollama as a fallback.
    """
    selected_provider = (provider or settings.llm_provider).lower()

    if selected_provider == "groq":
        chosen_model = model or settings.groq_model
        groq_api_key = settings.groq_api_key.strip() if settings.groq_api_key else ""

        from langchain_groq import ChatGroq

        log.info("llm_init", provider="groq", model=chosen_model)

        fallback_llms = []
        if enable_fallback:
            fallback_key = settings.groq_fallback_key.strip() if settings.groq_fallback_key else ""
            if fallback_key and fallback_key != groq_api_key:
                fallback_llms.append(
                    ChatGroq(
                        model=chosen_model,
                        api_key=fallback_key,
                        temperature=temperature,
                    )
                )
            try:
                fallback_llms.append(_build_ollama_llm(None, temperature))
            except Exception as e:
                log.warning("llm_fallback_init_failed", error=str(e))

        if not groq_api_key:
            log.warning("groq_api_key_empty_using_ollama_fallback", ollama_model=settings.ollama_model)
            return fallback_llms[0] if fallback_llms else _build_ollama_llm(None, temperature)

        primary_llm = ChatGroq(
            model=chosen_model,
            api_key=groq_api_key,
            temperature=temperature,
        )

        if fallback_llms:
            return primary_llm.with_fallbacks(fallback_llms)
        return primary_llm

    elif selected_provider == "ollama":
        return _build_ollama_llm(model, temperature)

    elif selected_provider == "gemini":
        chosen_model = model or settings.gemini_model
        from langchain_google_genai import ChatGoogleGenerativeAI

        log.info("llm_init", provider="gemini", model=chosen_model)
        return ChatGoogleGenerativeAI(
            model=chosen_model,
            google_api_key=settings.gemini_api_key,
            temperature=temperature,
        )

    elif selected_provider == "anthropic":
        chosen_model = model or "claude-3-5-sonnet-20241022"
        from langchain_anthropic import ChatAnthropic

        log.info("llm_init", provider="anthropic", model=chosen_model)
        return ChatAnthropic(
            model=chosen_model,
            api_key=settings.anthropic_api_key,
            temperature=temperature,
        )

    else:
        raise ValueError(
            f"Unsupported LLM provider '{selected_provider}'. "
            f"Supported options: 'groq', 'ollama', 'gemini', 'anthropic'."
        )
