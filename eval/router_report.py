"""Turn the router run into a table: money saved, and where the router was wrong.

Reads data/router/results.jsonl (written by attacks/run_router.py) and the
failover log line. Writes data/router/table.md and data/router/report.json.

Run inside the attacks image:  python -m eval.router_report
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "router"


def load(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def build_report() -> dict:
    rows = load(OUT / "results.jsonl")
    router = [r for r in rows if r["arm"] == "router" and r["status"] == 200]
    strong = [r for r in rows if r["arm"] == "strong" and r["status"] == 200]
    both = {r["id"] for r in router} & {r["id"] for r in strong}
    router = [r for r in router if r["id"] in both]
    strong = [r for r in strong if r["id"] in both]

    def total(rs):
        return round(sum(r["cost_usd"] or 0 for r in rs), 6)

    agree = sum(1 for r in router if (r["tier"] == "strong") == (r["label"] == "hard"))
    failover = load(OUT / "failover.jsonl")

    def mean_cost(rs, label):
        picked = [r["cost_usd"] or 0 for r in rs if r["label"] == label]
        return sum(picked) / len(picked) if picked else 0.0

    # What the saving would be for other mixes of easy and hard traffic, from
    # the measured average cost of each kind. A projection, not a measurement.
    mix = {}
    for easy_share in (0.5, 0.8, 0.9):
        def per_q(rs):
            return easy_share * mean_cost(rs, "easy") + (1 - easy_share) * mean_cost(rs, "hard")
        mix[f"{int(easy_share * 100)}% easy"] = (round(100 * (1 - per_q(router) / per_q(strong)), 1)
                                                if per_q(strong) else 0.0)

    def median_ms(rs):
        values = sorted(r["provider_ms"] for r in rs if r["provider_ms"] is not None)
        return round(values[len(values) // 2]) if values else None

    return {
        "projected_saving_by_mix": mix,
        "model_ms_p50": {"cheap": median_ms([r for r in router if r["tier"] == "cheap"]),
                         "strong": median_ms(strong)},
        "questions": len(both),
        "easy": sum(1 for r in router if r["label"] == "easy"),
        "hard": sum(1 for r in router if r["label"] == "hard"),
        "blocked_or_failed": sum(1 for r in rows if r["status"] != 200),
        "router_cost_usd": total(router),
        "strong_cost_usd": total(strong),
        "saved_pct": round(100 * (1 - total(router) / total(strong)), 1) if total(strong) else 0.0,
        "sent_to_strong": sum(1 for r in router if r["tier"] == "strong"),
        "agrees_with_our_label": agree,
        "hard_sent_cheap": [r["id"] for r in router if r["label"] == "hard" and r["tier"] != "strong"],
        "easy_sent_strong": [r["id"] for r in router if r["label"] == "easy" and r["tier"] == "strong"],
        "cost_by_label": {
            label: {"router": total([r for r in router if r["label"] == label]),
                    "strong": total([r for r in strong if r["label"] == label])}
            for label in ("easy", "hard")
        },
        "failover": {
            "failed_model": failover[0].get("failover") if failover else None,
            "answered_by": failover[0].get("model_used") if failover else None,
            "status": failover[0].get("status") if failover else None,
        },
    }


def write_table(r: dict) -> str:
    lines = [
        "# Phase 3 result: the difficulty router",
        "",
        f"{r['questions']} questions ({r['easy']} easy, {r['hard']} hard, labelled by us). "
        "Live calls through OpenRouter.",
        "",
        "| | Always strong model | Router | Saved |",
        "|---|---|---|---|",
        f"| All questions | ${r['strong_cost_usd']:.5f} | ${r['router_cost_usd']:.5f} | {r['saved_pct']:.0f}% |",
    ]
    for label in ("easy", "hard"):
        c = r["cost_by_label"][label]
        saved = f"{100 * (1 - c['router'] / c['strong']):.0f}%" if c["strong"] else "-"
        lines.append(f"| {label.title()} questions | ${c['strong']:.5f} | ${c['router']:.5f} | {saved} |")
    lines += [
        "",
        "Projected saving for other traffic mixes, from the measured average cost of each kind:",
        "",
        "| Traffic mix | Saved |",
        "|---|---|",
        *[f"| {k} | {v:.0f}% |" for k, v in r["projected_saving_by_mix"].items()],
        "",
        f"Model response time, median: cheap {r['model_ms_p50']['cheap']} ms, "
        f"strong {r['model_ms_p50']['strong']} ms.",
        "",
        f"- Router sent {r['sent_to_strong']} of {r['questions']} to the strong model.",
        f"- Router agreed with our label on {r['agrees_with_our_label']} of {r['questions']}.",
        f"- Hard questions sent to the cheap model: {', '.join(r['hard_sent_cheap']) or 'none'}.",
        f"- Easy questions sent to the strong model: {', '.join(r['easy_sent_strong']) or 'none'}.",
        f"- Requests blocked or failed: {r['blocked_or_failed']}.",
        f"- Failover: {r['failover']['failed_model']} failed, answered by "
        f"{r['failover']['answered_by']} (status {r['failover']['status']}).",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    if not (OUT / "results.jsonl").exists():
        print("No router results yet. Run: bash attacks/router_live.sh")
        return 1
    report = build_report()
    (OUT / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    table = write_table(report)
    (OUT / "table.md").write_text(table)
    print(table)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
