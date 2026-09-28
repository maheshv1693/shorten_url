"""Integration tests for URL creation, redirects, and analytics endpoints."""

from collections.abc import Iterator
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1 import endpoints
from app.core.cache import cache
from app.db.models import Base
from app.db.repository import URLRepository
from app.db.session import get_db
from app.main import app
import app.main as main_module

@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """Provide an API client backed by an isolated in-memory database."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    test_session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    def override_get_db() -> Iterator[Session]:
        with test_session_factory() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    monkeypatch.setattr(endpoints, "SessionLocal", test_session_factory)
    monkeypatch.setattr(main_module, "init_db", lambda: None)
    cache.clear()

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    cache.clear()
    engine.dispose()


def test_create_url_returns_absolute_short_url(client: TestClient) -> None:
    """URL creation returns a short URL based on the request host."""
    response = client.post("/api/v1/urls", json={"url": "https://example.com/path"})

    assert response.status_code == 201
    body = response.json()
    assert body["short_code"]
    assert body["short_url"] == f"http://testserver/{body['short_code']}"
    assert body["original_url"] == "https://example.com/path"


@pytest.mark.parametrize("blank_alias", ["", "   "])
def test_blank_custom_alias_generates_code(
    client: TestClient,
    blank_alias: str,
) -> None:
    """Empty and whitespace-only aliases use automatic code generation."""
    response = client.post(
        "/api/v1/urls",
        json={"url": "https://example.com/path", "custom_alias": blank_alias},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["short_code"]
    assert body["short_url"].endswith(f"/{body['short_code']}")


def test_custom_alias_duplicate_returns_conflict(client: TestClient) -> None:
    """A duplicate custom alias produces the documented conflict response."""
    payload = {"url": "https://example.com", "custom_alias": "my-link"}

    assert client.post("/api/v1/urls", json=payload).status_code == 201
    response = client.post("/api/v1/urls", json=payload)

    assert response.status_code == 409
    assert response.json() == {"detail": "Alias already in use"}


def test_redirect_returns_temporary_redirect(client: TestClient) -> None:
    """A short code redirects with status 307 and records the click."""
    create_response = client.post(
        "/api/v1/urls",
        json={"url": "https://example.com/destination", "custom_alias": "go-there"},
    )

    with TestClient(app) as public_client:
        response = public_client.get("/go-there", follow_redirects=False)

    assert create_response.status_code == 201
    assert response.status_code == 307
    assert response.headers["location"] == "https://example.com/destination"


def test_expired_url_returns_gone(client: TestClient) -> None:
    """An expired persisted mapping returns HTTP 410."""
    with endpoints.SessionLocal() as db:
        URLRepository.create_url(
            db,
            "https://expired.example",
            custom_alias="expired",
            expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        )

    response = client.get("/expired", follow_redirects=False)

    assert response.status_code == 410
    assert response.json() == {"detail": "URL has expired"}


def test_unknown_short_code_returns_not_found(client: TestClient) -> None:
    """An unknown short code returns HTTP 404."""
    response = client.get("/does-not-exist", follow_redirects=False)

    assert response.status_code == 404
    assert response.json() == {"detail": "Short URL not found"}


def test_analytics_includes_redirect_click(client: TestClient) -> None:
    """A redirect click appears in the analytics response."""
    client.post(
        "/api/v1/urls",
        json={"url": "https://example.com", "custom_alias": "count-me"},
    )
    redirect_response = client.get(
        "/count-me",
        headers={"referer": "https://source.example", "user-agent": "test-client"},
        follow_redirects=False,
    )

    response = client.get("/api/v1/urls/count-me/analytics")

    assert redirect_response.status_code == 307
    assert response.status_code == 200
    body = response.json()
    assert body["short_code"] == "count-me"
    assert body["total_clicks"] == 1
    assert body["recent_clicks"][0]["referrer"] == "https://source.example"
    assert body["recent_clicks"][0]["user_agent"] == "test-client"


def test_health_reports_database_connection(client: TestClient) -> None:
    """Health check reports a successful database probe without authentication."""
    with TestClient(app) as public_client:
        response = public_client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "database": "connected",
        "version": "1.0.0",
    }


def test_health_reports_database_failure(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Health check returns a direct 503 payload when the probe fails."""
    def fail_execute(*args: object, **kwargs: object) -> None:
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(Session, "execute", fail_execute)

    response = client.get("/health")

    assert response.status_code == 503
    assert response.json() == {
        "status": "unhealthy",
        "database": "disconnected",
    }