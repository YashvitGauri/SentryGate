"""Checks on the metrics summary. No network, no models.

The summary feeds the live demo and the latency figures, so it has to read the
real log and compute the obvious things correctly.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.metrics import percentile, summarise


def test_percentile_nearest_rank():
    assert percentile([], 50) == 0.0
    assert percentile([5], 99) == 5
    assert percentile([1, 2, 3, 4, 5], 50) == 3
    assert percentile([1, 2, 3, 4, 5], 100) == 5
    # p99 of 100 values 1..100 is the top value by nearest rank.
    assert percentile(list(range(1, 101)), 99) == 99


def row(status=200, outcome="miss", total_ms=10.0, screening_ran=True,
        block_reason=None, cost=0.0, tin=5, tout=5):
    return {
        "status": status,
        "cache": {"outcome": outcome},
        "latency_ms": {"total": total_ms},
        "screening_ran": screening_ran,
        "block_reason": block_reason,
        "cost_usd": cost,
        "tokens": {"in": tin, "out": tout},
    }


def test_summarise_counts_hits_misses_and_blocks():
    rows = [
        row(outcome="miss", total_ms=800),
        row(outcome="hit", total_ms=12, screening_ran=False),
        row(outcome="hit", total_ms=8, screening_ran=False),
        row(status=403, outcome="miss", block_reason="prompt_injection"),
    ]
    s = summarise(rows)
    assert s["requests"] == 4
    assert s["answered"] == 3
    assert s["blocked_as_injection"] == 1
    assert s["cache"]["hits"] == 2
    assert s["cache"]["misses"] == 1
    assert s["cache"]["hit_rate"] == pytest.approx(2 / 3, abs=1e-3)
    assert s["latency_ms"]["hit"]["p50"] <= s["latency_ms"]["miss"]["p50"]


def test_summarise_sums_tokens_and_cost():
    rows = [row(cost=0.001, tin=10, tout=20), row(cost=0.002, tin=5, tout=5)]
    s = summarise(rows)
    assert s["tokens"]["in"] == 15
    assert s["tokens"]["out"] == 25
    assert s["cost_usd"] == pytest.approx(0.003)


def test_summarise_empty_is_safe():
    s = summarise([])
    assert s["requests"] == 0
    assert s["cache"]["hit_rate"] == 0.0


@pytest.fixture
def gateway(tmp_path, monkeypatch):
    monkeypatch.setenv("PROVIDER_MODE", "mock")
    monkeypatch.setenv("SCREENING_SCORER", "stub")
    monkeypatch.setenv("CACHE_EMBEDDER", "stub")
    monkeypatch.setenv("CACHE_BACKEND", "memory")
    monkeypatch.setenv("SENTRYGATE_DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    from app.main import app

    with TestClient(app) as client:
        yield client
    get_settings.cache_clear()


def test_metrics_endpoint_reflects_real_traffic(gateway):
    def ask(prompt):
        gateway.post("/v1/chat/completions",
                     json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": prompt}]})

    ask("what is the capital of France?")
    ask("what is the capital of France?")  # a hit
    summary = gateway.get("/metrics/summary").json()
    assert summary["requests"] == 2
    assert summary["cache"]["hits"] == 1
    assert "config" in summary
