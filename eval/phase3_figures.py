"""Turn the Phase 3 results into a table and two charts.

Reads only data/phase3/ (results, benign results, and each arm's gateway
log) plus the Phase 2 screen-first run, so nothing here is hand-entered.

Every poison served is split in two:

    cache-caused   the filter blocks this exact text when asked (Phase 2
                   screen-first run), so the cache is why it got through
    filter miss    the filter lets this text through anyway, so no cache
                   defence can stop it; that is the filter's own limit

Writes:

    paper/figures/defence_poison_served.png   poison served, per arm and label
    paper/figures/defence_tradeoff.png        safety gained vs speed lost
    data/phase3/table.md                      the numbers as a Markdown table
    data/phase3/report.json                   the same numbers as data

Run inside the attacks image:  make defence-figures
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PHASE3 = ROOT / "data" / "phase3"
FIGURES = ROOT / "paper" / "figures"

ARMS = [
    ("base", "No defence"),
    ("filter", "Label match only"),
    ("recheck", "Re-check risky hits only"),
    ("both", "Label match + re-check risky hits"),
    ("all", "Label match + re-check every hit"),
]
LABELS = ["clean", "attack"]


def load(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def pct(part: int, whole: int) -> float:
    return round(100 * part / whole, 1) if whole else 0.0


def p50(values: list[float]) -> float | None:
    values = sorted(v for v in values if v is not None)
    return round(values[len(values) // 2], 1) if values else None


def filter_blocks() -> dict[str, bool]:
    """variant_id -> did the real filter block this text when asked directly?"""
    week4 = load(ROOT / "data" / "week4" / "results.jsonl")
    return {r["variant_id"]: r["status"] == 403 for r in week4
            if r["tag"] == "screen_first" and abs(r["threshold"] - 0.85) < 1e-9}


def build_report() -> dict:
    rows = [r for r in load(PHASE3 / "results.jsonl") if r["family"] != "exact"]
    blocks = filter_blocks()
    missing = sum(1 for r in rows if r["variant_id"] not in blocks)
    if missing:
        raise SystemExit(f"{missing} variants have no screen-first result in data/week4. Rerun make bypass.")
    benign = load(PHASE3 / "benign_results.jsonl")
    benign_summary = {s["tag"]: s for s in load(PHASE3 / "benign_summary.jsonl")}
    controls = load(PHASE3 / "controls_results.jsonl")

    arms = {}
    for tag, name in ARMS:
        arm_rows = [r for r in rows if r["tag"] == tag]
        if not arm_rows:
            continue
        served = {}
        for label in LABELS:
            at = [r for r in arm_rows if r["poison_label"] == label]
            served[label] = {
                "overall": pct(sum(r["served_poison"] for r in at), len(at)),
                "cache_caused": pct(sum(r["served_poison"] and blocks[r["variant_id"]] for r in at), len(at)),
                "filter_miss": pct(sum(r["served_poison"] and not blocks[r["variant_id"]] for r in at), len(at)),
                "lazy": pct(sum(r["served_poison"] for r in at if r["family"] == "lazy"),
                            sum(1 for r in at if r["family"] == "lazy")),
                "rewrite": pct(sum(r["served_poison"] for r in at if r["family"] == "rewrite"),
                               sum(1 for r in at if r["family"] == "rewrite")),
                "n": len(at),
            }
        honest = [r for r in benign if r["tag"] == tag]
        hits = [r for r in honest if r["hit"]]
        # Full answers from the log: honest misses that went to the model.
        log = load(PHASE3 / f"run-{tag}.jsonl")
        misses = [(line.get("latency_ms") or {}).get("total") for line in log
                  if (line.get("cache") or {}).get("outcome") == "miss" and line.get("status") == 200]
        arms[tag] = {
            "name": name,
            "served": served,
            "honest_hit_rate": pct(len(hits), len(honest)),
            "honest_hits_rechecked": pct(sum(1 for r in hits if r["reverified"]), len(hits)),
            "hit_p50_ms": p50([r["latency_ms"] for r in hits]),
            "miss_p50_ms": p50(misses),
            "honest_blocked_at_first_ask": benign_summary.get(tag, {}).get("blocked_at_first_ask"),
            "controls_served_poison": sum(1 for c in controls if c["tag"] == tag and c.get("served_poison")),
        }
    first = load(PHASE3 / "summary.jsonl")
    return {
        "threshold": 0.85,
        "seeds": len({r["seed_id"] for r in rows}),
        "filter_blocks_alone": pct(sum(blocks[r["variant_id"]] for r in rows if r["tag"] == "base"
                                       and r["poison_label"] == "clean"),
                                   sum(1 for r in rows if r["tag"] == "base" and r["poison_label"] == "clean")),
        "honest_questions": len({r["control_id"] for r in benign}),
        "arms": arms,
        "models": first[0].get("config") if first else {},
    }


def write_table(report: dict) -> str:
    lines = [
        "# Phase 3 result: the defence against cache poisoning",
        "",
        f"Threshold 0.85 (0.95 for risky kinds of question).  Seeds: {report['seeds']}.  "
        f"Honest questions: {report['honest_questions']}.  Provider: mock (no model called).",
        "",
        "Poison labelled clean = an attack that slipped past the filter once (the realistic case).",
        "Poison labelled attack = the filter flagged it when it was saved (the easy case).",
        "",
        f"The filter on its own blocks {report['filter_blocks_alone']:.1f}% of these rewordings.",
        "Cache-caused = poison served on a text the filter would have blocked. Only this part is the cache's fault.",
        "",
        "| Arm | Labelled clean: served | of which cache-caused | Labelled attack: served "
        "| of which cache-caused | Honest hit rate | Honest hits re-checked | Hit p50 | Miss p50 |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for tag, _ in ARMS:
        a = report["arms"].get(tag)
        if not a:
            continue
        lines.append(
            f"| {a['name']} | {a['served']['clean']['overall']:.1f}% | {a['served']['clean']['cache_caused']:.1f}% "
            f"| {a['served']['attack']['overall']:.1f}% | {a['served']['attack']['cache_caused']:.1f}% "
            f"| {a['honest_hit_rate']:.1f}% | {a['honest_hits_rechecked']:.0f}% "
            f"| {a['hit_p50_ms']} ms | {a['miss_p50_ms']} ms |"
        )
    lines += ["", "Checks:", ""]
    for tag, _ in ARMS:
        a = report["arms"].get(tag)
        if a:
            lines.append(f"- {a['name']}: honest questions served the poison: "
                         f"{a['controls_served_poison']} (must be zero).")
    return "\n".join(lines) + "\n"


def _style(ax, muted="#6e6e73"):
    ax.grid(True, axis="y", color="#e8e8ed", linewidth=0.8)
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_color("#d2d2d7")
    ax.tick_params(colors=muted, labelsize=9)


def draw_charts(report: dict) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ink, accent, warn = "#1d1d1f", "#0071e3", "#b45309"
    arms = [(tag, report["arms"][tag]) for tag, _ in ARMS if tag in report["arms"]]
    names = [a["name"].replace(" + ", "\n+ ") for _, a in arms]
    FIGURES.mkdir(parents=True, exist_ok=True)

    # 1. Poison served, per arm, for both labels, split by whose fault it is.
    fig, ax = plt.subplots(figsize=(8.6, 4.6), dpi=200)
    xs = list(range(len(arms)))
    width = 0.38
    grey = "#c7c7cc"
    for offset, label, colour in ((-width / 2, "clean", warn), (width / 2, "attack", accent)):
        cause = [a["served"][label]["cache_caused"] for _, a in arms]
        miss = [a["served"][label]["filter_miss"] for _, a in arms]
        pos = [x + offset for x in xs]
        ax.bar(pos, cause, width, color=colour,
               label=f"Cache-caused, poison saved as {label}" + (" (realistic)" if label == "clean" else " (easy)"))
        ax.bar(pos, miss, width, bottom=cause, color=grey,
               label="Filter misses it too (not the cache's fault)" if label == "clean" else None)
        for p_, c_, m_ in zip(pos, cause, miss):
            ax.text(p_, c_ + m_ + 1.5, f"{c_:.0f}%", ha="center", fontsize=8.5, color=colour, weight="bold")
    ax.set_xticks(xs)
    ax.set_xticklabels(names, fontsize=8, color=ink)
    ax.set_ylabel("Attacks served the poison (%)", fontsize=10, color=ink)
    ax.set_ylim(0, 112)
    ax.set_title("What each defence stops (threshold 0.85)", fontsize=12, color=ink, weight="bold", pad=22)
    ax.text(0.5, 1.02, "Coloured part and number: poison the filter would have stopped, so the cache's fault",
            transform=ax.transAxes, ha="center", fontsize=8.5, color="#6e6e73")
    ax.legend(frameon=False, fontsize=8, loc="upper right")
    _style(ax)
    fig.tight_layout()
    fig.savefig(FIGURES / "defence_poison_served.png", bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote {FIGURES / 'defence_poison_served.png'}")

    # 2. The trade-off: safety on the left, cost to honest users on the right.
    fig, (left, right) = plt.subplots(1, 2, figsize=(9.5, 4.2), dpi=200)
    clean = [a["served"]["clean"]["cache_caused"] for _, a in arms]
    left.barh(names, clean, color=warn)
    left.set_xlabel("Cache-caused poison, saved as clean (%)", fontsize=9, color=ink)
    left.set_xlim(0, 105)
    left.invert_yaxis()
    for i, v in enumerate(clean):
        left.text(v + 1.5, i, f"{v:.0f}%", va="center", fontsize=8, color=ink)
    left.set_title("Safety (lower is better)", fontsize=11, color=ink, weight="bold")

    hit_ms = [a["hit_p50_ms"] or 0 for _, a in arms]
    misses = sorted(a["miss_p50_ms"] for _, a in arms if a["miss_p50_ms"])
    miss_ms = misses[len(misses) // 2] if misses else 0
    right.barh(names, hit_ms, color=accent)
    right.axvline(miss_ms, color="#6e6e73", linestyle="--", linewidth=1)
    right.text(miss_ms + 2, 1.5, f"a miss: screening only, no model call (~{miss_ms:.0f} ms)",
               rotation=90, fontsize=7.5, color="#6e6e73", va="center")
    right.set_xlabel("Honest cache hit, median time (ms)", fontsize=9, color=ink)
    right.invert_yaxis()
    right.set_yticklabels([])
    for i, (v, (_, a)) in enumerate(zip(hit_ms, arms)):
        label = f"{v:.0f} ms, {a['honest_hit_rate']:.0f}% hits"
        if v > 0.5 * max(hit_ms):   # long bar: write inside it, clear of the dashed line
            right.text(v - 3, i, label, va="center", ha="right", fontsize=8, color="white", weight="bold")
        else:
            right.text(v + 2, i, label, va="center", fontsize=8, color=ink)
    right.set_xlim(0, max(hit_ms + [miss_ms]) * 1.35)
    right.set_title("Cost to honest users", fontsize=11, color=ink, weight="bold")
    for ax in (left, right):
        _style(ax)
        ax.grid(True, axis="x", color="#e8e8ed", linewidth=0.8)
        ax.grid(False, axis="y")
    left.tick_params(axis="y", labelsize=8, colors=ink)
    fig.tight_layout()
    fig.savefig(FIGURES / "defence_tradeoff.png", bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote {FIGURES / 'defence_tradeoff.png'}")


def main() -> int:
    if not (PHASE3 / "results.jsonl").exists():
        print("No results yet. Run the sweep first: make defence")
        return 1
    report = build_report()
    (PHASE3 / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    table = write_table(report)
    (PHASE3 / "table.md").write_text(table)
    print(table)
    draw_charts(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
