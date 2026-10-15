"""Phase 3: limit how hard one caller can push the gateway.

Two limits, each per caller (the hashed API key, or "anonymous"):

    RATE_LIMIT_RPM          requests per minute, counting cache hits too.
                            The Phase 2 attack fires hundreds of rewordings
                            to probe the cache; this slows that down.
    TOKEN_BUDGET_PER_DAY    model tokens per day, counting only paid calls
                            (a cache hit costs nothing, so it is free).

0 turns a limit off. Both are off by default.

Counts live in Redis, so they hold across gateway restarts and across
several gateway copies. With no Redis, a memory store keeps the gateway
working (counts then reset on restart; the log says which one ran).
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str | None = None       # rate_limited or token_budget
    limit: int = 0
    remaining: int = 0
    retry_after_s: int = 0


class MemoryCounter:
    def __init__(self):
        self._data: dict[str, tuple[int, float]] = {}
        self._lock = threading.Lock()
        self.backend = "memory"

    def incr(self, key: str, amount: int, ttl_s: int) -> int:
        now = time.time()
        with self._lock:
            value, expires = self._data.get(key, (0, now + ttl_s))
            if expires <= now:
                value, expires = 0, now + ttl_s
            value += amount
            self._data[key] = (value, expires)
            return value

    def get(self, key: str) -> int:
        with self._lock:
            value, expires = self._data.get(key, (0, 0.0))
            return value if expires > time.time() else 0


class RedisCounter:
    def __init__(self, url: str):
        import redis  # lazy, like the cache

        self.client = redis.Redis.from_url(url, socket_connect_timeout=2)
        self.client.ping()
        self.backend = "redis"

    def incr(self, key: str, amount: int, ttl_s: int) -> int:
        pipe = self.client.pipeline()
        pipe.incrby(key, amount)
        pipe.expire(key, ttl_s, nx=True)
        return int(pipe.execute()[0])

    def get(self, key: str) -> int:
        return int(self.client.get(key) or 0)


class RateLimiter:
    def __init__(self, rpm: int, tokens_per_day: int, counter):
        self.rpm = rpm
        self.tokens_per_day = tokens_per_day
        self.counter = counter

    @property
    def enabled(self) -> bool:
        return self.rpm > 0 or self.tokens_per_day > 0

    def check(self, caller: str) -> Decision:
        """Count this request, and say whether it may go ahead."""
        if self.tokens_per_day > 0:
            used = self.counter.get(f"sg:tokens:{caller}:{date.today().isoformat()}")
            if used >= self.tokens_per_day:
                return Decision(False, "token_budget", self.tokens_per_day, 0, _seconds_to_midnight())
        if self.rpm > 0:
            minute = int(time.time() // 60)
            count = self.counter.incr(f"sg:rpm:{caller}:{minute}", 1, 120)
            if count > self.rpm:
                return Decision(False, "rate_limited", self.rpm, 0, 60 - int(time.time()) % 60)
            return Decision(True, None, self.rpm, self.rpm - count)
        return Decision(True)

    def spend(self, caller: str, tokens: int) -> None:
        """Add the tokens a paid call used to the caller's daily total."""
        if self.tokens_per_day > 0 and tokens > 0:
            self.counter.incr(f"sg:tokens:{caller}:{date.today().isoformat()}", tokens, 2 * 86400)


def _seconds_to_midnight() -> int:
    now = time.localtime()
    return max(1, 86400 - (now.tm_hour * 3600 + now.tm_min * 60 + now.tm_sec))


def build_rate_limiter(settings) -> tuple[RateLimiter, dict]:
    counter = MemoryCounter()
    info = {"rpm": settings.rate_limit_rpm, "tokens_per_day": settings.token_budget_per_day}
    if (settings.rate_limit_rpm or settings.token_budget_per_day) and settings.cache_backend != "memory":
        try:
            counter = RedisCounter(settings.redis_url)
        except Exception as exc:  # no Redis: keep working, and say so
            info["fallback_reason"] = f"{type(exc).__name__}: {str(exc)[:160]}"
    info["backend"] = counter.backend
    return RateLimiter(settings.rate_limit_rpm, settings.token_budget_per_day, counter), info
