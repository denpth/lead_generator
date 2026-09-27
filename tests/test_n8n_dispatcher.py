from datetime import UTC, datetime

import httpx

from app.models.lead import Lead
from app.services.n8n import N8nDispatcher


def make_lead() -> Lead:
    return Lead(
        first_name="Jane",
        last_name="Doe",
        email="jane@example.com",
        source="test",
        created_at=datetime.now(UTC),
    )


def test_dispatcher_retries_then_succeeds() -> None:
    statuses = iter([503, 502, 202])
    sleeps: list[float] = []

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(next(statuses))

    client = httpx.Client(transport=httpx.MockTransport(handler))
    dispatcher = N8nDispatcher(
        webhook_url="http://n8n.test/webhook/lead-intake",
        timeout_seconds=1,
        max_attempts=3,
        backoff_seconds=0.25,
        client=client,
        sleeper=sleeps.append,
    )

    result = dispatcher.dispatch(make_lead())

    assert result.success is True
    assert result.attempts == 3
    assert result.status_code == 202
    assert sleeps == [0.25, 0.5]


def test_dispatcher_reports_final_network_failure() -> None:
    sleeps: list[float] = []

    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    dispatcher = N8nDispatcher(
        webhook_url="http://n8n.test/webhook/lead-intake",
        timeout_seconds=1,
        max_attempts=2,
        backoff_seconds=0.1,
        client=client,
        sleeper=sleeps.append,
    )

    result = dispatcher.dispatch(make_lead())

    assert result.success is False
    assert result.attempts == 2
    assert result.status_code is None
    assert "ConnectError" in (result.error or "")
    assert sleeps == [0.1]


def test_dispatcher_does_not_retry_non_retryable_4xx() -> None:
    sleeps: list[float] = []

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(400)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    dispatcher = N8nDispatcher(
        webhook_url="http://n8n.test/webhook/lead-intake",
        timeout_seconds=1,
        max_attempts=3,
        backoff_seconds=0.25,
        client=client,
        sleeper=sleeps.append,
    )

    result = dispatcher.dispatch(make_lead())

    assert result.success is False
    assert result.attempts == 1
    assert result.status_code == 400
    assert sleeps == []


def test_network_failure_clears_status_from_previous_http_attempt() -> None:
    attempts = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(503)
        raise httpx.ConnectError("connection lost")

    dispatcher = N8nDispatcher(
        webhook_url="http://n8n.test/webhook/lead-intake",
        timeout_seconds=1,
        max_attempts=2,
        backoff_seconds=0,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        sleeper=lambda _delay: None,
    )

    result = dispatcher.dispatch(make_lead())

    assert result.success is False
    assert result.attempts == 2
    assert result.status_code is None
    assert "ConnectError" in result.error
