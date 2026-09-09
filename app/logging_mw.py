"""One line per request, written to a JSONL file.

This file is the data source for every number in Phases 3 and 4: cache hit
rate, money saved, p50 and p99 latency, the bypass rate, and the ablation
table. It exists this early on purpose. Week 4 has to claim "the filter never
ran", and the only honest evidence for that is a log line saying so.

Two fields carry most of the weight:

    screening_ran   false on a cache hit is the whole finding
    config          every line says which settings produced it, so one file
                    can be split into experiment arms later without anyone
                    having to remember how each run was started

We never write the prompt text here. Only a hash and a length. The prompt
lives in the cache payload, where it is needed for attack forensics, and not
in a log we will paste into a report.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Paths that are plumbing, not traffic. Logging them would pollute every rate.
SKIP_PATHS = {"/healthz", "/docs", "/openapi.json", "/redoc", "/favicon.ico", "/v1/cache/clear"}


def client_key_id(auth_header: str | None) -> str:
    """Which caller this was, without storing their key."""
    if not auth_header:
        return "anonymous"
    digest = hashlib.sha256(auth_header.encode("utf-8")).hexdigest()[:8]
    return f"sha256:{digest}"


@dataclass
class RequestRecord:
    """Filled in as the request moves through the gateway, written once at the end.

    Fields default to the "did not happen" value, so a line is always complete
    and a reader never has to guess whether a missing key means off or broken.
    """

    request_id: str
    ts: str
    api_key_id: str = "anonymous"
    model_requested: str | None = None
    model_used: str | None = None
    prompt_hash: str | None = None
    prompt_len: int = 0

    screening_ran: bool = False
    verdict: dict[str, Any] | None = None

    cache_outcome: str = "disabled"   # disabled, miss, hit, bypassed
    cache_similarity: float | None = None
    cache_matched_id: str | None = None
    cache_threshold: float | None = None

    provider_source: str | None = None
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0

    status: int = 500
    block_reason: str | None = None

    latency_ms: dict[str, float] = field(default_factory=dict)
    config: dict[str, Any] = field(default_factory=dict)

    @contextmanager
    def stage(self, name: str) -> Iterator[None]:
        """Time one step. Use for screen, embed, cache and provider."""
        started = time.perf_counter()
        try:
            yield
        finally:
            self.latency_ms[name] = round((time.perf_counter() - started) * 1000, 2)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ts": self.ts,
            "request_id": self.request_id,
            "api_key_id": self.api_key_id,
            "model_requested": self.model_requested,
            "model_used": self.model_used,
            "prompt_hash": self.prompt_hash,
            "prompt_len": self.prompt_len,
            "screening_ran": self.screening_ran,
            "verdict": self.verdict,
            "cache": {
                "outcome": self.cache_outcome,
                "similarity": self.cache_similarity,
                "matched_id": self.cache_matched_id,
                "threshold": self.cache_threshold,
            },
            "provider": self.provider_source,
            "tokens": {"in": self.tokens_in, "out": self.tokens_out},
            "cost_usd": round(self.cost_usd, 8),
            "latency_ms": self.latency_ms,
            "status": self.status,
            "block_reason": self.block_reason,
            "config": self.config,
        }


class JsonlWriter:
    """Appends whole lines to one file.

    The handle stays open and every line is written in a single call, so two
    uvicorn workers appending at once cannot interleave half lines.
    """

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._handle = open(self.path, "a", encoding="utf-8")

    def write(self, payload: dict[str, Any]) -> None:
        line = json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"
        with self._lock:
            self._handle.write(line)
            self._handle.flush()

    def close(self) -> None:
        with self._lock:
            self._handle.close()


class RequestLogMiddleware(BaseHTTPMiddleware):
    """Starts the record, hands it to the route, writes it whatever happens.

    The writer and the config are read off app.state at request time, not
    stored here, because startup is the only place settings are read.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        writer: JsonlWriter | None = getattr(request.app.state, "log_writer", None)
        if writer is None or request.url.path in SKIP_PATHS:
            return await call_next(request)

        record = RequestRecord(
            request_id=request.headers.get("x-request-id") or _new_id(),
            ts=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            api_key_id=client_key_id(request.headers.get("authorization")),
            config=request.app.state.settings.as_log_dict(),
        )
        request.state.record = record

        started = time.perf_counter()
        try:
            response = await call_next(request)
            record.status = response.status_code
            response.headers["X-SentryGate-Request-Id"] = record.request_id
            return response
        except Exception:
            record.status = 500
            record.block_reason = "unhandled_error"
            raise
        finally:
            record.latency_ms["total"] = round((time.perf_counter() - started) * 1000, 2)
            writer.write(record.to_dict())


def _new_id() -> str:
    import uuid

    return uuid.uuid4().hex
