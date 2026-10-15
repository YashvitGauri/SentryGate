"""Phase 3: does the difficulty router save money, and where does it go wrong?

Sends the 40 questions in data/router/questions.jsonl (20 easy, 20 hard,
labelled by us) through a live gateway, one arm at a time:

    router   ROUTER_MODE=difficulty: easy -> cheap model, hard -> strong model
    strong   ROUTER_MODE=fixed, every question asks for the strong model

The cache is cleared before each question, so every answer is a real paid
call and the two arms see the same questions. Real token counts and costs
come from the gateway's log line for each request.

    python attacks/run_router.py --arm router --expect router=difficulty
    python attacks/run_router.py --arm strong --model openai/gpt-4o --expect router=fixed
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "attacks"))

from run_bypass import http_json, load_jsonl, read_log_tail  # noqa: E402

OUT = ROOT / "data" / "router"


def wait_live(base: str, expect: dict) -> dict:
    for _ in range(120):
        try:
            _, _, health = http_json(f"{base}/healthz", timeout=5)
            if health.get("status") == "ok":
                break
        except Exception:
            pass
        time.sleep(2)
    else:
        sys.exit("Gateway did not become healthy.")
    config = health.get("config", {})
    problems = [f"{k} is {config.get(k)}, expected {v}" for k, v in expect.items() if str(config.get(k)) != v]
    if health.get("provider_mode") != "live":
        problems.append(f"provider_mode is {health.get('provider_mode')}, expected live")
    if problems:
        sys.exit("Gateway is not set up for this arm:\n  - " + "\n  - ".join(problems))
    return health


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base", default="http://127.0.0.1:8000")
    ap.add_argument("--arm", required=True, choices=("router", "strong"))
    ap.add_argument("--model", default="openai/gpt-4o-mini", help="model the client asks for")
    ap.add_argument("--expect", action="append", default=[], metavar="KEY=VALUE")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    health = wait_live(args.base, dict(e.split("=", 1) for e in args.expect))
    log_path = ROOT / "data" / health.get("log_path", "/data/requests.jsonl").split("/data/", 1)[-1]
    questions = load_jsonl(OUT / "questions.jsonl")[: args.limit]

    rows = []
    for q in questions:
        http_json(f"{args.base}/v1/cache/clear", {}, "POST")
        line_no = len(log_path.read_text().splitlines()) if log_path.exists() else 0
        code, headers, body = http_json(
            f"{args.base}/v1/chat/completions",
            {"model": args.model, "messages": [{"role": "user", "content": q["text"]}], "max_tokens": 400},
            "POST", timeout=120,
        )
        req_id = headers.get("x-sentrygate-request-id")
        line = next((r for r in read_log_tail(log_path, line_no) if r.get("request_id") == req_id), {})
        answer = (body.get("choices") or [{}])[0].get("message", {}).get("content", "") if code == 200 else ""
        rows.append({
            "arm": args.arm, "id": q["id"], "label": q["label"], "status": code,
            "tier": (line.get("route") or {}).get("tier"),
            "score": (line.get("route") or {}).get("score"),
            "reasons": (line.get("route") or {}).get("reasons"),
            "model_used": line.get("model_used"),
            "tokens_in": (line.get("tokens") or {}).get("in"),
            "tokens_out": (line.get("tokens") or {}).get("out"),
            "cost_usd": line.get("cost_usd"),
            "provider_ms": (line.get("latency_ms") or {}).get("provider"),
            "answer": answer,
        })
        print(f"  [{args.arm}] {q['id']}  {code}  {rows[-1]['model_used']}  ${rows[-1]['cost_usd']}")

    with (OUT / "results.jsonl").open("a") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    spent = sum(r["cost_usd"] or 0 for r in rows)
    print(f"  [{args.arm}] {len(rows)} questions, ${spent:.4f} total")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
