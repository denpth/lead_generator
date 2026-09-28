from fastapi.testclient import TestClient

from app.services.n8n import DispatchResult
from tests.conftest import StubDispatcher


def test_create_lead_validates_and_dispatches(
    client: TestClient, dispatcher: StubDispatcher
) -> None:
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


def test_partial_lead_with_email_is_valid(client: TestClient) -> None:
    response = client.post("/leads", json={"email": "minimal@example.com"})
    assert response.status_code == 201
    assert response.json()["first_name"] is None
    assert response.json()["created_at"]


def test_short_phone_rejected_without_persistence(client: TestClient) -> None:
    for phone in ["123", "(1) -- 2", "-------"]:
        response = client.post("/leads", json={"phone": phone})
        assert response.status_code == 422
        assert "at least 7 digits" in response.json()["detail"][0]["msg"]
    assert client.get("/leads").json()["total"] == 0


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


def test_list_leads_filters_searches_and_paginates(
    client: TestClient, dispatcher: StubDispatcher
) -> None:
    dispatcher.results = [
        DispatchResult(success=True, attempts=1, status_code=200),
        DispatchResult(success=False, attempts=3, error="offline"),
        DispatchResult(success=True, attempts=1, status_code=200),
    ]
    for email, company in [
        ("first@example.com", "Acme"),
        ("second@example.com", "Acme"),
        ("third@example.com", "100%_Real"),
    ]:
        assert client.post("/leads", json={"email": email, "company": company}).status_code == 201

    all_leads = client.get("/leads").json()
    assert all_leads["total"] == 3
    assert all_leads["counts"] == {"pending": 0, "dispatched": 2, "failed": 1}
    first = client.get("/leads?limit=1").json()
    second = client.get("/leads?limit=1&offset=1").json()
    assert first["total"] == second["total"] == 3
    assert first["items"][0]["id"] != second["items"][0]["id"]
    failed = client.get("/leads", params={"q": "aCmE", "status": "failed"}).json()
    assert failed["total"] == 1
    assert failed["items"][0]["email"] == "second@example.com"
    assert failed["counts"] == all_leads["counts"]
    literal = client.get("/leads", params={"q": "%_"}).json()
    assert literal["total"] == 1
    assert literal["items"][0]["company"] == "100%_Real"
    assert client.get("/leads?q=missing").json()["items"] == []


def test_list_leads_validates_pagination_and_status(client: TestClient) -> None:
    for query in ["limit=0", "limit=101", "offset=-1", "status=unknown"]:
        assert client.get(f"/leads?{query}").status_code == 422
    empty = client.get("/leads").json()
    assert empty == {
        "items": [],
        "total": 0,
        "counts": {"pending": 0, "dispatched": 0, "failed": 0},
    }
