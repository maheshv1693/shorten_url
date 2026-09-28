"""Tests for the in-memory URL cache."""

import pytest

from app.core.cache import URLCache


@pytest.fixture
def cache() -> URLCache:
    """Provide an isolated cache for each test."""
    return URLCache()


def test_set_and_get_returns_cached_value(cache: URLCache) -> None:
    """A stored value can be retrieved before its TTL expires."""
    cache.set("abc123", "https://example.com")

    assert cache.get("abc123") == "https://example.com"


def test_get_missing_key_returns_none(cache: URLCache) -> None:
    """A cache miss returns None."""
    assert cache.get("missing") is None


def test_delete_removes_key(cache: URLCache) -> None:
    """Deleting a key makes subsequent lookups miss."""
    cache.set("abc123", "https://example.com")

    cache.delete("abc123")

    assert cache.get("abc123") is None


def test_expired_entry_is_evicted(cache: URLCache, monkeypatch: pytest.MonkeyPatch) -> None:
    """An entry past its absolute expiry is evicted when read."""
    current_time = 100.0
    monkeypatch.setattr("app.core.cache.time.time", lambda: current_time)
    cache.set("abc123", "https://example.com", ttl_seconds=5)

    current_time += 5

    assert cache.get("abc123") is None
    assert "abc123" not in cache._items


def test_none_ttl_does_not_expire(cache: URLCache, monkeypatch: pytest.MonkeyPatch) -> None:
    """An explicitly omitted TTL stores a value without an expiry."""
    monkeypatch.setattr("app.core.cache.time.time", lambda: 100.0)
    cache.set("abc123", "https://example.com", ttl_seconds=None)
    monkeypatch.setattr("app.core.cache.time.time", lambda: 10_000.0)

    assert cache.get("abc123") == "https://example.com"