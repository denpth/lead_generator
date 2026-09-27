from functools import lru_cache

from app.config import get_settings
from app.services.n8n import N8nDispatcher


@lru_cache
def get_n8n_dispatcher() -> N8nDispatcher:
    settings = get_settings()
    return N8nDispatcher(
        webhook_url=settings.n8n_webhook_url,
        timeout_seconds=settings.n8n_webhook_timeout_seconds,
        max_attempts=settings.n8n_webhook_max_attempts,
        backoff_seconds=settings.n8n_webhook_backoff_seconds,
    )
