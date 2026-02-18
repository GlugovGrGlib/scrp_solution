"""Redis caching and rate limiting."""

from __future__ import annotations

import hashlib
import json
import time
from typing import TYPE_CHECKING, Any

import redis

from core.config import settings

if TYPE_CHECKING:
    from redis import Redis


class RedisCache:
    """Redis client for caching and rate limiting."""

    _instance: RedisCache | None = None
    _client: Redis[str] | None = None

    def __new__(cls) -> RedisCache:
        """Singleton pattern for connection reuse."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @property
    def client(self) -> Redis[str]:
        """Lazy connection initialization."""
        if self._client is None:
            self._client = redis.from_url(settings.redis_url, decode_responses=True)
        return self._client

    def get(self, key: str) -> dict[str, Any] | None:
        """Get cached JSON value."""
        data = self.client.get(key)
        return json.loads(data) if data else None

    def set(self, key: str, value: dict[str, Any], ttl: int | None = None) -> None:
        """Cache JSON value with optional TTL."""
        ttl = ttl or settings.cache_ttl_seconds
        self.client.setex(key, ttl, json.dumps(value))

    def rate_limit(self, key: str, limit: int) -> bool:
        """
        Check rate limit. Returns True if within limit.

        Uses sliding window counter pattern.
        """
        current = self.client.incr(key)
        if current == 1:
            self.client.expire(key, settings.rate_limit_window_seconds)
        return current <= limit

    def wait_for_rate_limit(self, key: str, limit: int) -> None:
        """Block until rate limit allows a request."""
        while not self.rate_limit(key, limit):
            time.sleep(0.1)

    def close(self) -> None:
        """Close Redis connection."""
        if self._client:
            self._client.close()
            self._client = None


def cache_key(prefix: str, identifier: str) -> str:
    """Generate cache key from prefix and identifier."""
    id_hash = hashlib.sha256(identifier.encode()).hexdigest()[:16]
    return f"{prefix}:{id_hash}"


def create_cache() -> RedisCache | None:
    """Create cache instance, returning None if Redis unavailable."""
    try:
        cache = RedisCache()
        cache.client.ping()
        return cache
    except redis.ConnectionError:
        return None
