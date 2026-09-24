"""Read the request log and summarise it.

This is the source for /metrics/summary, which the live demo shows on screen,
and for the latency figures. It reads the JSONL log the gateway writes, so the
numbers are always the real traffic, never hand-entered.

Reading the whole file on each call is fine here: the demo log is small, and a
summary that is always correct beats a running counter that can drift.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def percentile(values: list[float], p: float) -> float:
    """The p-th percentile by nearest rank. p is 0..100.

    Nearest rank, not interpolation, because it is simple to explain and a demo
    log is small enough that the difference does not matter.
    """
    if not values:
        return 0.0
    ordered = sorted(values)
    if p <= 0:
        return round(ordered[0], 2)
    rank = max(1, min(len(ordered), (int((p / 100) * len(ordered) + 0.999999))))
    return round(ordered[rank - 1], 2)


def read_log(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except ValueError:
                continue  # a half-written last line; skip rather than crash the demo
    return out


def summarise(rows: list[dict]) -> dict[str, Any]:
    total = len(rows)
    answered = [r for r in rows if r.get("status") == 200]
    hits = [r for r in answered if r.get("cache", {}).get("outcome") == "hit"]
    misses = [r for r in answered if r.get("cache", {}).get("outcome") == "miss"]
    blocked = [r for r in rows if r.get("block_reason") == "prompt_injection"]
    screened = [r for r in rows if r.get("screening_ran") is True]

    def latencies(group: list[dict]) -> list[float]:
        return [float(r.get("latency_ms", {}).get("total", 0.0)) for r in group if r.get("latency_ms")]

    hit_ms = latencies(hits)
    miss_ms = latencies(misses)

    return {
        "requests": total,
        "answered": len(answered),
        "blocked_as_injection": len(blocked),
        "screening_ran": len(screened),
        "cache": {
            "hits": len(hits),
            "misses": len(misses),
            "hit_rate": round(len(hits) / len(answered), 4) if answered else 0.0,
        },
        "latency_ms": {
            "hit": {"p50": percentile(hit_ms, 50), "p99": percentile(hit_ms, 99), "n": len(hit_ms)},
            "miss": {"p50": percentile(miss_ms, 50), "p99": percentile(miss_ms, 99), "n": len(miss_ms)},
        },
        "tokens": {
            "in": sum(int(r.get("tokens", {}).get("in", 0)) for r in rows),
            "out": sum(int(r.get("tokens", {}).get("out", 0)) for r in rows),
        },
        "cost_usd": round(sum(float(r.get("cost_usd", 0.0)) for r in rows), 6),
    }


def summarise_file(path: Path) -> dict[str, Any]:
    return summarise(read_log(path))
