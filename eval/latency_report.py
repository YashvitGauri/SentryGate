"""Latency of the gateway, from its own request logs.

Reads every Week 4 run log plus the demo log, splits requests by what happened
to them, and reports p50 and p99. This is the "how much does the gateway cost
per request" number, measured on real traffic, not guessed.

    hit      served from the cache. Embed the prompt, search, return.
    miss     screened, embedded, then the model (mock here) answered.
    blocked  screened and refused.

Writes:
    data/week4/latency.md            the table
    paper/figures/latency.png        the chart

Run inside the attacks image:  make figures  (or make eval)
"""

from __future__ import annotations

import json
from pathlib import Path

from app.metrics import percentile

ROOT = Path(__file__).resolve().parent.parent
WEEK4 = ROOT / "data" / "week4"
FIGURES = ROOT / "paper" / "figures"

# Order and colour for the three outcomes.
OUTCOMES = [
    ("hit", "Cache hit", "#0071e3"),
    ("miss", "Miss (screen + model)", "#b45309"),
    ("blocked", "Blocked attack", "#b91c1c"),
]


def load_logs() -> list[dict]:
    rows: list[dict] = []
    for path in sorted(WEEK4.glob("run-*.jsonl")) + [ROOT / "data" / "requests.jsonl"]:
        if path.exists():
            for line in path.read_text().splitlines():
                line = line.strip()
                if line:
                    try:
                        rows.append(json.loads(line))
                    except ValueError:
                        continue
    return rows


def classify(row: dict) -> str | None:
    if row.get("block_reason") == "prompt_injection":
        return "blocked"
    if row.get("status") != 200:
        return None
    return row.get("cache", {}).get("outcome")  # hit or miss


def total_ms(row: dict) -> float:
    return float(row.get("latency_ms", {}).get("total", 0.0))


def build(rows: list[dict]) -> dict:
    buckets: dict[str, list[float]] = {key: [] for key, _, _ in OUTCOMES}
    for row in rows:
        kind = classify(row)
        if kind in buckets and row.get("latency_ms"):
            buckets[kind].append(total_ms(row))
    return {
        key: {
            "n": len(v),
            "p50": percentile(v, 50),
            "p99": percentile(v, 99),
        }
        for key, v in buckets.items()
    }


def write_table(stats: dict) -> str:
    lines = [
        "# Gateway latency, from the request logs",
        "",
        "Measured on the Week 4 traffic. Provider was mock, so a miss's model time"
        " is the mock reply, not a real model.",
        "",
        "| Outcome | Requests | p50 (ms) | p99 (ms) |",
        "|---|---|---|---|",
    ]
    for key, label, _ in OUTCOMES:
        s = stats[key]
        lines.append(f"| {label} | {s['n']} | {s['p50']:.1f} | {s['p99']:.1f} |")
    hit, miss = stats["hit"], stats["miss"]
    if hit["n"] and miss["n"]:
        lines += [
            "",
            f"A cache hit answers in about {hit['p50']:.0f} ms at the median.",
            f"A miss pays the safety check on top, at about {miss['p50']:.0f} ms.",
            "That gap is exactly why real systems check the cache first, and why the"
            " bypass exists.",
        ]
    return "\n".join(lines) + "\n"


def draw_chart(stats: dict) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    present = [(k, label, colour) for k, label, colour in OUTCOMES if stats[k]["n"]]
    labels = [label for _, label, _ in present]
    p50 = [stats[k]["p50"] for k, _, _ in present]
    p99 = [stats[k]["p99"] for k, _, _ in present]
    colours = [colour for _, _, colour in present]

    x = range(len(present))
    fig, ax = plt.subplots(figsize=(7, 4.2), dpi=200)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    width = 0.38
    ax.bar([i - width / 2 for i in x], p50, width, color=colours, label="p50")
    ax.bar([i + width / 2 for i in x], p99, width, color=colours, alpha=0.45, label="p99")

    ax.set_ylabel("Response time (ms)", fontsize=11, color="#1d1d1f")
    ax.set_title("Gateway latency by outcome", fontsize=13, color="#1d1d1f", weight="bold", pad=12)
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, fontsize=9, color="#6e6e73")
    ax.grid(True, axis="y", color="#e8e8ed", linewidth=0.8)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_color("#d2d2d7")
    ax.tick_params(colors="#6e6e73", labelsize=9)
    # Solid vs faded is p50 vs p99; a small note explains it.
    ax.text(0.99, 0.97, "solid = p50, faded = p99", transform=ax.transAxes,
            ha="right", va="top", fontsize=8, color="#86868b")

    FIGURES.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(FIGURES / "latency.png", bbox_inches="tight")
    print(f"  wrote {FIGURES / 'latency.png'}")


def main() -> int:
    rows = load_logs()
    if not rows:
        print("No logs found. Run make bypass, or start the gateway and send some requests.")
        return 1
    stats = build(rows)
    (WEEK4 / "latency.md").write_text(write_table(stats))
    draw_chart(stats)
    print(write_table(stats))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
