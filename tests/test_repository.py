"""Tests for URL persistence and click analytics operations."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.base62 import ALPHABET
from app.db.models import Base, URL, URLClick
from app.db.repository import (
    MAX_CODE_GENERATION_ATTEMPTS,
    AliasAlreadyExistsError,
    URLRepository,
)


@pytest.fixture
def db() -> Session:
    """Create an isolated in-memory SQLite session for each test."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def test_create_url_generates_seven_character_base62_code(db: Session) -> None:
    """Generated short codes use seven Base62 characters."""
    url = URLRepository.create_url(db, "https://example.com")

    assert len(url.short_code) == 7
    assert set(url.short_code) <= set(ALPHABET)
    assert db.get(URL, url.id) is not None


def test_create_url_uses_custom_alias_and_rejects_duplicates(db: Session) -> None:
    """Custom aliases are persisted and duplicate values raise a clear error."""
    url = URLRepository.create_url(db, "https://example.com", custom_alias="my-link")

    assert url.short_code == "my-link"
    with pytest.raises(AliasAlreadyExistsError):
        URLRepository.create_url(db, "https://other.example", custom_alias="my-link")


def test_create_url_retries_generated_code_collision(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A unique-constraint collision retries with another generated code."""
    existing = URLRepository.create_url(db, "https://existing.example")
    generated_codes = iter([existing.short_code, "newCode"])
    monkeypatch.setattr(
        "app.db.repository._generate_short_code",
        lambda: next(generated_codes),
    )

    created = URLRepository.create_url(db, "https://new.example")

    assert created.short_code == "newCode"


def test_create_url_stops_after_three_generated_code_collisions(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Repeated generated-code collisions stop after the configured attempts."""
    existing = URLRepository.create_url(db, "https://existing.example")
    generated_codes: list[str] = []

    def generate_collision() -> str:
        generated_codes.append(existing.short_code)
        return existing.short_code

    monkeypatch.setattr("app.db.repository._generate_short_code", generate_collision)

    with pytest.raises(IntegrityError):
        URLRepository.create_url(db, "https://new.example")

    assert len(generated_codes) == MAX_CODE_GENERATION_ATTEMPTS


def test_get_by_short_code_only_returns_active_urls(db: Session) -> None:
    """Disabled URLs are hidden from short-code lookups."""
    url = URLRepository.create_url(db, "https://example.com", custom_alias="paused")

    assert URLRepository.get_by_short_code(db, "paused") is url
    url.is_active = False
    db.commit()
    assert URLRepository.get_by_short_code(db, "paused") is None


def test_record_click_and_get_analytics_limit_recent_events(db: Session) -> None:
    """Analytics count every event and return the 100 newest in order."""
    URLRepository.create_url(db, "https://example.com", custom_alias="popular")
    base_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
    db.add_all(
        URLClick(
            short_code="popular",
            clicked_at=base_time + timedelta(seconds=index),
            referrer="https://referrer.example",
            user_agent="pytest",
        )
        for index in range(101)
    )
    db.commit()
    URLRepository.record_click(db, "popular", ip_address="127.0.0.1")

    analytics = URLRepository.get_analytics(db, "popular")
    recent_clicks = analytics["recent_clicks"]

    assert analytics["total_clicks"] == 102
    assert isinstance(recent_clicks, list)
    assert len(recent_clicks) == 100
    assert recent_clicks[0].clicked_at > recent_clicks[-1].clicked_at