from functools import lru_cache

from app.config import get_settings
from app.services.n8n import N8nDispatcher
from app.services.decision import LeadDecisionEngine


@lru_cache
def get_n8n_dispatcher() -> N8nDispatcher:
    settings = get_settings()
    return N8nDispatcher(
        webhook_url=settings.n8n_webhook_url,
        timeout_seconds=settings.n8n_webhook_timeout_seconds,
        max_attempts=settings.n8n_webhook_max_attempts,
        backoff_seconds=settings.n8n_webhook_backoff_seconds,
    )


@lru_cache
def get_lead_decision_engine() -> LeadDecisionEngine:
    settings = get_settings()
    return LeadDecisionEngine(
        ollama_url=settings.ollama_url,
        ollama_model=settings.ollama_model,
        ollama_timeout_seconds=settings.ollama_timeout_seconds,
        typesafe_api_key=settings.typesafe_api_key,
        typesafe_api_url=settings.typesafe_api_url,
        jev_model=settings.jev_model,
        jev_timeout_seconds=settings.jev_timeout_seconds,
        confidence_threshold=settings.decision_confidence_threshold,
    )
