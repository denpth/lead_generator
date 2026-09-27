from fastapi.testclient import TestClient

from app.services.n8n import DispatchResult
from tests.conftest import StubDispatcher


def test_create_lead_validates_and_dispatches(client: TestClient, dispatcher: StubDispatcher) -> None:
    response = client.post(
        "/leads",
        json={
            "first_name": "  Jane ",
            "last_name": "Doe",
            "email": "jane@example.com",
            "company": "Acme",
            "source": "website",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["first_name"] == "Jane"
    assert body["email"] == "jane@example.com"
    assert body["status"] == "dispatched"
    assert body["dispatch_attempts"] == 1
    assert body["last_webhook_status_code"] == 200
    assert dispatcher.calls == 1

    fetched = client.get(f"/leads/{body['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["status"] == "dispatched"


def test_create_lead_requires_contact_method(client: TestClient) -> None:
    response = client.post("/leads", json={"first_name": "No Contact"})
    assert response.status_code == 422


def test_create_lead_forbids_unknown_fields(client: TestClient) -> None:
    response = client.post(
        "/leads",
        json={"email": "jane@example.com", "surprise": "not allowed"},
    )
    assert response.status_code == 422


def test_failed_dispatch_is_persisted_and_can_be_retried(
    client: TestClient, dispatcher: StubDispatcher
) -> None:
    dispatcher.results = [
        DispatchResult(success=False, attempts=3, status_code=503, error="n8n returned HTTP 503"),
        DispatchResult(success=True, attempts=1, status_code=202),
    ]

    created = client.post("/leads", json={"email": "retry@example.com"})
    assert created.status_code == 201
    first = created.json()
    assert first["status"] == "failed"
    assert first["dispatch_attempts"] == 3
    assert first["last_webhook_status_code"] == 503
    assert "503" in first["last_error"]

    retried = client.post(f"/leads/{first['id']}/retry")
    assert retried.status_code == 200
    second = retried.json()
    assert second["status"] == "dispatched"
    assert second["dispatch_attempts"] == 4
    assert second["last_error"] is None
    assert second["last_webhook_status_code"] == 202


def test_retry_rejects_non_failed_lead(client: TestClient) -> None:
    created = client.post("/leads", json={"email": "ok@example.com"})
    lead_id = created.json()["id"]

    response = client.post(f"/leads/{lead_id}/retry")
    assert response.status_code == 409
