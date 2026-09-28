"""Thread-safe in-memory cache for URL mappings."""

import threading
import time


class URLCache:
    """Store URL mappings with optional time-to-live expiration."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._items: dict[str, tuple[str, float | None]] = {}

    def get(self, key: str) -> str | None:
        """Return a cached value, evicting it first if it has expired."""
        with self._lock:
            item = self._items.get(key)
            if item is None:
                return None

            value, expires_at = item
            if expires_at is not None and expires_at <= time.time():
                del self._items[key]
                return None
            return value

    def set(self, key: str, value: str, ttl_seconds: int | None = 300) -> None:
        """Store a value with a TTL in seconds, or indefinitely when TTL is None."""
        expires_at = None if ttl_seconds is None else time.time() + ttl_seconds
        with self._lock:
            self._items[key] = (value, expires_at)

    def delete(self, key: str) -> None:
        """Remove a key if it exists."""
        with self._lock:
            self._items.pop(key, None)

    def clear(self) -> None:
        """Remove all cached entries."""
        with self._lock:
            self._items.clear()


cache = URLCache()
"""Shared in-memory cache instance."""