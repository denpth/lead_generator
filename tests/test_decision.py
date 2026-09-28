import json
from datetime import UTC, datetime

import httpx
from fastapi.testclient import TestClient

from app.config import get_settings
from app.dependencies import get_lead_decision_engine
from app.main import app
from app.models.lead import Lead, ResponsePriority
from app.services.decision import DecisionResult, LeadDecisionEngine


def make_lead() -> Lead:
    return Lead(
        id="eb21e501-197b-4f57-a157-57aa19e764bc",
        first_name="Private",
        last_name="Person",
        email="private@example.com",
        phone="5551234567",
        company="Acme",
        source="website",
        notes="Need a proposal before tomorrow morning.",
        created_at=datetime.now(UTC),
    )


def test_decision_uses_local_summary_and_minimizes_jev_state() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.host == "ollama":
            return httpx.Response(
                200,
                json={
                    "response": "Acme needs a proposal tomorrow; call 555-123-4567 or private@example.com."
                },
            )
        return httpx.Response(
            200,
            json={
                "model": "jev-1.13.0",
                "answers": {
                    "response_speed": {
                        "type": "choice",
                        "choice": "immediate",
                        "confidence": 0.91,
                    },
                    "requires_human_review": {"type": "noul", "noul": 0.05},
                },
            },
        )

    engine = LeadDecisionEngine(
        ollama_url="http://ollama:11434",
        ollama_model="qwen3:1.7b",
        ollama_timeout_seconds=1,
        typesafe_api_key="test-key",
        typesafe_api_url="https://api.typesafe.test/v1/systemone",
        jev_model="jev-1.13.0",
        jev_timeout_seconds=1,
        confidence_threshold=0.65,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = engine.decide(make_lead())

    assert result.priority == ResponsePriority.IMMEDIATE
    assert result.window_minutes == 15
    assert result.confidence == 0.91
    jev_body = requests[1].read().decode()
    summary_body = json.loads(requests[0].read())
    assert summary_body["think"] is False
    assert "Private" not in jev_body
    assert "private@example.com" not in jev_body
    assert "5551234567" not in jev_body
    assert "555-123-4567" not in jev_body


def test_missing_jev_key_routes_to_review_without_losing_summary() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"response": "A short factual summary."})

    engine = LeadDecisionEngine(
        ollama_url="http://ollama:11434",
        ollama_model="qwen3:1.7b",
        ollama_timeout_seconds=1,
        typesafe_api_key=None,
        typesafe_api_url="https://api.typesafe.test/v1/systemone",
        jev_model="jev-1.13.0",
        jev_timeout_seconds=1,
        confidence_threshold=0.65,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = engine.decide(make_lead())

    assert result.priority == ResponsePriority.REVIEW
    assert result.summary == "A short factual summary."
    assert "not configured" in (result.warning or "")


class StubDecisionEngine:
    def decide(self, _lead: Lead) -> DecisionResult:
        return DecisionResult(
            summary="A qualified website inquiry.",
            priority=ResponsePriority.PRIORITY,
            window_minutes=60,
            confidence=0.88,
            model="jev-test",
        )


def test_internal_decision_endpoint_is_authenticated_and_persists(client: TestClient) -> None:
    created = client.post("/leads", json={"email": "decision@example.com"}).json()
    app.dependency_overrides[get_lead_decision_engine] = lambda: StubDecisionEngine()

    unauthorized = client.post(f"/internal/leads/{created['id']}/decision")
    assert unauthorized.status_code == 401

    response = client.post(
        f"/internal/leads/{created['id']}/decision",
        headers={"X-Automation-Key": get_settings().automation_internal_key},
    )
    assert response.status_code == 200
    assert response.json()["route"] == "priority"
    saved = client.get(f"/leads/{created['id']}").json()
    assert saved["summary"] == "A qualified website inquiry."
    assert saved["response_priority"] == "priority"
    assert saved["response_window_minutes"] == 60
