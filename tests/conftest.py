from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.dependencies import get_n8n_dispatcher
from app.main import app
from app.services.n8n import DispatchResult


class StubDispatcher:
    def __init__(self, results: list[DispatchResult] | None = None) -> None:
        self.results = list(results or [DispatchResult(success=True, attempts=1, status_code=200)])
        self.calls = 0

    def dispatch(self, _lead: object) -> DispatchResult:
        self.calls += 1
        if self.results:
            return self.results.pop(0)
        return DispatchResult(success=True, attempts=1, status_code=200)


@pytest.fixture
def session_factory() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture
def dispatcher() -> StubDispatcher:
    return StubDispatcher()


@pytest.fixture
def client(
    session_factory: sessionmaker[Session], dispatcher: StubDispatcher
) -> Generator[TestClient, None, None]:
    def override_db() -> Generator[Session, None, None]:
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_n8n_dispatcher] = lambda: dispatcher
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
