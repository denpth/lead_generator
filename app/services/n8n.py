from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

import httpx

from app.models.lead import Lead


@dataclass(frozen=True, slots=True)
class DispatchResult:
    success: bool
    attempts: int
    status_code: int | None = None
    error: str | None = None


class N8nDispatcher:
    def __init__(
        self,
        *,
        webhook_url: str,
        timeout_seconds: float,
        max_attempts: int,
        backoff_seconds: float,
        client: httpx.Client | None = None,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.webhook_url = webhook_url
        self.timeout_seconds = timeout_seconds
        self.max_attempts = max_attempts
        self.backoff_seconds = backoff_seconds
        self.client = client or httpx.Client()
        self.sleeper = sleeper

    def dispatch(self, lead: Lead) -> DispatchResult:
        payload = {
            "event": "lead.created",
            "event_id": f"lead.created:{lead.id}",
            "lead": {
                "id": str(lead.id),
                "first_name": lead.first_name,
                "last_name": lead.last_name,
                "email": lead.email,
                "phone": lead.phone,
                "company": lead.company,
                "source": lead.source,
                "notes": lead.notes,
                "created_at": lead.created_at.isoformat() if lead.created_at else None,
            },
        }

        last_status_code: int | None = None
        last_error: str | None = None

        for attempt in range(1, self.max_attempts + 1):
            try:
                response = self.client.post(
                    self.webhook_url,
                    json=payload,
                    headers={
                        "Content-Type": "application/json",
                        "X-Lead-Id": str(lead.id),
                        "X-Event-Id": payload["event_id"],
                    },
                    timeout=self.timeout_seconds,
                )
                last_status_code = response.status_code
                if 200 <= response.status_code < 300:
                    return DispatchResult(
                        success=True,
                        attempts=attempt,
                        status_code=response.status_code,
                    )
                last_error = f"n8n returned HTTP {response.status_code}"
                retryable = response.status_code in {408, 425, 429} or response.status_code >= 500
                if not retryable:
                    return DispatchResult(
                        success=False,
                        attempts=attempt,
                        status_code=response.status_code,
                        error=last_error,
                    )
            except httpx.HTTPError as exc:
                last_error = f"n8n request failed: {exc.__class__.__name__}: {exc}"

            if attempt < self.max_attempts:
                delay = self.backoff_seconds * (2 ** (attempt - 1))
                self.sleeper(delay)

        return DispatchResult(
            success=False,
            attempts=self.max_attempts,
            status_code=last_status_code,
            error=last_error or "n8n dispatch failed",
        )
