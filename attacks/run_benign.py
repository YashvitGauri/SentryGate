"""Phase 3: how much does the defence cost honest users?

For each of the 100 honest questions in data/week4/controls.jsonl:

    1. clear the cache
    2. ask the question once (a miss: the answer gets screened and saved)
    3. ask the same lazy rewordings an attacker would use, and count hits

A good defence keeps these hits. Every hit lost is a paid model call that
the cache would have saved. Each request's latency comes from the gateway's
own log, so the re-check cost shows up there too.

Run against a gateway on real models (same setup as run_bypass.py):

    python attacks/run_benign.py --tag filter --out data/phase3 --expect verdict_filter=on
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "attacks"))

from generate_variants import LAZY_EDITS  # noqa: E402
from run_bypass import INPUTS, http_json, load_jsonl, read_log_tail, wait_healthy  # noqa: E402


def ask(base: str, text: str, log_path: Path) -> dict:
    line_no = len(log_path.read_text().splitlines()) if log_path.exists() else 0
    code, headers, _ = http_json(
        f"{base}/v1/chat/completions",
        {"model": "gpt-4o-mini", "messages": [{"role": "user", "content": text}]}, "POST",
    )
    req_id = headers.get("x-sentrygate-request-id")
    line = next((r for r in read_log_tail(log_path, line_no) if r.get("request_id") == req_id), {})
    cache = line.get("cache", {}) or {}
    return {
        "status": code,
        "cache": headers.get("x-sentrygate-cache", ""),
        "similarity": float(headers.get("x-sentrygate-similarity", 0.0) or 0.0),
        "cheap_intent": cache.get("cheap_intent"),
        "used_threshold": cache.get("threshold"),
        "reverified": line.get("reverified"),
        "screening_ran": line.get("screening_ran"),
        "latency_ms": (line.get("latency_ms") or {}).get("total"),
    }


def run(base: str, threshold: float, tag: str, out: Path, expect: dict, limit: int | None) -> dict:
    controls = load_jsonl(INPUTS / "controls.jsonl")[:limit] if limit else load_jsonl(INPUTS / "controls.jsonl")
    health = wait_healthy(base, threshold, "cache_first", expect)
    gateway_log = health.get("log_path", "/data/requests.jsonl")
    log_path = ROOT / "data" / gateway_log.split("/data/", 1)[-1]

    rows: list[dict] = []
    skipped = 0
    started = time.time()
    for n, c in enumerate(controls, 1):
        http_json(f"{base}/v1/cache/clear", {}, "POST")
        first = ask(base, c["text"], log_path)
        if first["status"] != 200:
            # The filter wrongly blocked an honest question, so nothing was saved.
            # Counted on its own: it is a Week 2 false positive, not a cache cost.
            skipped += 1
            continue
        seen = {c["text"]}
        for method, edit in LAZY_EDITS:
            text = edit(c["text"])
            if text in seen:
                continue
            seen.add(text)
            r = ask(base, text, log_path)
            rows.append({"tag": tag, "threshold": threshold, "control_id": c["control_id"],
                         "method": method, **r, "hit": r["cache"] == "hit"})
        if n % 25 == 0 or n == len(controls):
            print(f"  [benign {tag}] {n}/{len(controls)} questions  ({time.time() - started:.0f}s)")

    hits = sum(r["hit"] for r in rows)
    lat_hit = sorted(r["latency_ms"] for r in rows if r["hit"] and r["latency_ms"] is not None)
    summary = {
        "tag": tag, "threshold": threshold, "config": health.get("config", {}),
        "questions": len(controls), "blocked_at_first_ask": skipped,
        "rewordings": len(rows), "hits": hits,
        "hit_rate": round(hits / len(rows), 4) if rows else 0.0,
        "rechecked_hits": sum(1 for r in rows if r["hit"] and r["reverified"]),
        "hit_p50_ms": lat_hit[len(lat_hit) // 2] if lat_hit else None,
    }
    out.mkdir(parents=True, exist_ok=True)
    with (out / "benign_results.jsonl").open("a") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    with (out / "benign_summary.jsonl").open("a") as f:
        f.write(json.dumps(summary) + "\n")
    print(f"  [benign {tag}] hit rate {summary['hit_rate']:.1%} "
          f"({hits}/{len(rows)}), {summary['rechecked_hits']} hits re-checked, "
          f"{skipped} questions blocked at first ask")
    return summary


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base", default="http://127.0.0.1:8000")
    ap.add_argument("--threshold", type=float, default=0.85)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--out", default="data/phase3")
    ap.add_argument("--expect", action="append", default=[], metavar="KEY=VALUE")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()
    run(args.base, args.threshold, args.tag, ROOT / args.out,
        dict(e.split("=", 1) for e in args.expect), args.limit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
