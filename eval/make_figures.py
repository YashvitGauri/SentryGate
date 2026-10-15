"""Turn the Week 4 results into a table and a chart.

Reads only data/week4/results.jsonl and summary.jsonl, so nothing here is
hand-entered. Writes:

    paper/figures/bypass_vs_threshold.png   the chart for the paper
    data/week4/table.md                     the numbers as a Markdown table
    data/week4/report.json                  the same numbers as data

Run inside the attacks image:  make figures
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEEK4 = ROOT / "data" / "week4"
FIGURES = ROOT / "paper" / "figures"

FAMILIES = ["lazy", "rewrite"]
THRESHOLDS = [0.95, 0.90, 0.85, 0.80, 0.75, 0.70, 0.65]


def load(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def rate(rows: list[dict]) -> float:
    return round(100 * sum(r["bypass"] for r in rows) / len(rows), 1) if rows else 0.0


def build_report(rows: list[dict], summaries: list[dict]) -> dict:
    cache_first = [r for r in rows if r["tag"] == "cache_first" and r["family"] != "exact"]
    by_threshold: dict[float, dict] = {}
    for t in THRESHOLDS:
        at_t = [r for r in cache_first if abs(r["threshold"] - t) < 1e-9]
        by_threshold[t] = {
            "overall": rate(at_t),
            **{fam: rate([r for r in at_t if r["family"] == fam]) for fam in FAMILIES},
            "n": len(at_t),
        }

    screen_first = [r for r in rows if r["tag"] == "screen_first" and r["family"] != "exact"]
    exact = [r for r in rows if r["tag"] == "cache_first" and r["family"] == "exact"]
    zero_screen = sum(1 for r in cache_first if r["bypass"] and r["screening_ran"] is False)
    controls = load(WEEK4 / "controls_results.jsonl")
    control_first = [c for c in controls if c["tag"] == "cache_first"]

    return {
        "by_threshold": {str(k): v for k, v in by_threshold.items()},
        "seeds": len({r["seed_id"] for r in cache_first}),
        "attack_variants_per_threshold": by_threshold[THRESHOLDS[0]]["n"] if cache_first else 0,
        "exact_served": f"{sum(r['served_poison'] for r in exact)}/{len(exact)}",
        "screen_first_bypass_at_085": rate([r for r in screen_first if abs(r["threshold"] - 0.85) < 1e-9]),
        "confirmed_bypasses_have_zero_screening": zero_screen,
        "control_served_poison": f"{sum(c.get('served_poison', False) for c in control_first)}/{len(control_first)}",
        "score_hit_mismatches": sum(s.get("score_hit_mismatches", 0) for s in summaries),
        "models": (summaries[0].get("config") if summaries else {}),
    }


def write_table(report: dict) -> str:
    lines = [
        "# Week 4 result: bypass rate on our own gateway",
        "",
        f"Seeds: {report['seeds']}.  "
        f"Attack variants per threshold: {report['attack_variants_per_threshold']}.  "
        f"Provider: mock (no model called).",
        "",
        "| Threshold | Lazy edits | Full rewrites | Overall |",
        "|---|---|---|---|",
    ]
    for t in THRESHOLDS:
        row = report["by_threshold"][str(t)]
        lines.append(f"| {t:.2f} | {row['lazy']:.0f}% | {row['rewrite']:.0f}% | {row['overall']:.0f}% |")
    lines += [
        "",
        "Checks:",
        "",
        f"- Exact seed served the poison: {report['exact_served']} (must be all).",
        f"- Confirmed bypasses whose log says the filter never ran: "
        f"{report['confirmed_bypasses_have_zero_screening']}.",
        f"- Honest questions served the poison: {report['control_served_poison']} (must be zero).",
        f"- Safe order (screen first) bypass at 0.85: "
        f"{report['screen_first_bypass_at_085']:.0f}% (must be zero).",
        f"- Log score vs hit disagreements: {report['score_hit_mismatches']} (must be zero).",
    ]
    return "\n".join(lines) + "\n"


def draw_chart(report: dict) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    thresholds = THRESHOLDS
    lazy = [report["by_threshold"][str(t)]["lazy"] for t in thresholds]
    rewrite = [report["by_threshold"][str(t)]["rewrite"] for t in thresholds]

    ink, muted, accent, warn = "#1d1d1f", "#6e6e73", "#0071e3", "#b45309"
    fig, ax = plt.subplots(figsize=(7, 4.2), dpi=200)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    ax.plot(thresholds, lazy, "-o", color=warn, linewidth=2.4, markersize=6, label="Lazy edits")
    ax.plot(thresholds, rewrite, "-o", color=accent, linewidth=2.4, markersize=6, label="Full rewrites")

    ax.set_xlabel("Cache similarity threshold", fontsize=11, color=ink)
    ax.set_ylabel("Attacks served from poison (%)", fontsize=11, color=ink)
    ax.set_title("Cache bypass on our own gateway", fontsize=13, color=ink, weight="bold", pad=12)
    ax.set_ylim(-3, 103)
    ax.set_xlim(0.97, 0.63)  # strict on the left, loose on the right
    ax.set_xticks(thresholds)
    ax.grid(True, color="#e8e8ed", linewidth=0.8)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_color("#d2d2d7")
    ax.tick_params(colors=muted, labelsize=9)
    ax.legend(frameon=False, fontsize=10, loc="center right")

    FIGURES.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(FIGURES / "bypass_vs_threshold.png", bbox_inches="tight")
    print(f"  wrote {FIGURES / 'bypass_vs_threshold.png'}")


def main() -> int:
    rows = load(WEEK4 / "results.jsonl")
    summaries = load(WEEK4 / "summary.jsonl")
    if not rows:
        print("No results yet. Run the sweep first: make bypass")
        return 1
    report = build_report(rows, summaries)
    (WEEK4 / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    (WEEK4 / "table.md").write_text(write_table(report))
    draw_chart(report)
    print(write_table(report))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
