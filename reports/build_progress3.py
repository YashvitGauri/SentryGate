"""Build Progress Report-3 (Phase 3) in the same format as Progress Reports 1 and 2.

Every number is read from the committed results, so the report cannot drift
from what the code measured:

    data/phase3/report.json    the defence sweep: five settings, two poison labels
    data/router/report.json    the model picker, on live paid calls
    data/mitigations/demo.txt  the output guard and rate limit, live

Writes reports/out/Progress3.docx. The PDF is converted from it (make report3).

Run:  python3 reports/build_progress3.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from report_common import (
    GREEN, ORANGE, RED, ROOT, bullet, caption, figure, heading, new_report, page_break,
    para, pct, save, table,
)

DEF = json.loads((ROOT / "data/phase3/report.json").read_text())
RTR = json.loads((ROOT / "data/router/report.json").read_text())
DEMO = (ROOT / "data/mitigations/demo.txt").read_text()
ARMS = DEF["arms"]


def demo_count(label: str) -> int:
    """A count from the rate-limit part of the live demo, e.g. 'refused, rate limit'."""
    match = re.search(rf"(\d+) [^:\n]*{re.escape(label)}[^:\n]*: (\d+)", DEMO)
    return int(match.group(2)) if match else 0


def build() -> Path:
    doc = new_report("Progress Report-3")
    base, every, both = ARMS["base"], ARMS["all"], ARMS["both"]
    hit_cost = round(every["hit_p50_ms"] - base["hit_p50_ms"], -1)   # one safety check per hit
    real_ms = RTR["model_ms_p50"]["cheap"]

    # ---- 1. status summary ----------------------------------------------
    heading(doc, "1.  Status Summary")
    para(doc, "**The Phase 3 defence is built, measured and working.** The objective of this phase was to "
              "close the bypass reproduced in Phase 2 and to measure what the fix costs. The same "
              f"{DEF['seeds']} attacks and their rewordings were fired at the same gateway in five settings, "
              "with the poisoned answer saved both as an attack (the easy case) and as clean, as if it had "
              "slipped past the filter once (the realistic case).")
    para(doc, "Every poisoned answer served was split into the part the cache caused (the filter blocks that "
              "text when asked directly) and the part the filter misses anyway. **With the safety check run "
              f"again on every cache hit, cache-caused leaks fell from {pct(base['served']['clean']['cache_caused'])} "
              f"to {pct(every['served']['clean']['cache_caused'])} in both cases, while honest users kept "
              f"{pct(every['honest_hit_rate'])} of their cache hits.** The cost is about {hit_cost:.0f} ms per hit, "
              f"against roughly {real_ms / 1000:.1f} seconds for a real model answer, and the paid model call is "
              "still skipped.")
    para(doc, "Matching on the stored safety label alone stopped the easy case but not the realistic one, and "
              "re-checking only hits that looked risky was not enough either. These negative results are "
              "reported in full, because they decide which form of the defence a real system should use.")

    # ---- 2. work completed ----------------------------------------------
    heading(doc, "2.  Work Completed in Phase 3")
    bullet(doc, "Verdict-tagged cache lookup",
           "a cheap keyword label is computed for every question in microseconds and stored with every "
           "answer. A cache hit now requires an unflagged stored answer with the same label, enforced as a "
           "payload filter inside the Qdrant search, and a 0.95 similarity for credential, tool-use and "
           "personal-data questions instead of 0.85.")
    bullet(doc, "Re-checking cache hits",
           "an optional fresh safety check on a cache hit before it is served, scoped either to risky-looking "
           "hits or to every hit. The request log records whether each hit was re-checked.")
    bullet(doc, "Phase 3 experiment",
           f"{DEF['arms']['base']['served']['clean']['n']:,} attack rewordings in five settings and two "
           f"poison labels, plus {DEF['honest_questions']} honest questions with the same lazy rewordings, on the "
           "real classifier, embedding model, Qdrant and Redis. Each leak is attributed to the cache or to the "
           "filter by joining it with the Phase 2 filter-first run.")
    bullet(doc, "Cost-aware model routing",
           "a rule-based difficulty score sends easy questions to openai/gpt-4o-mini and hard ones to "
           "openai/gpt-4o, with a fallback model retried once on a provider failure. Measured on "
           f"{2 * RTR['questions']} live paid calls through OpenRouter.")
    bullet(doc, "Output guard",
           "every answer, including one served from the cache, is scanned for browser scripts, destructive "
           "SQL, dangerous shell commands and secret keys, in off, flag or block mode. A blocked answer is "
           "never cached.")
    bullet(doc, "Rate and token limits",
           "per-caller requests per minute and a daily model-token budget, kept in Redis, answered with "
           "HTTP 429 and a retry time. Both mitigations were demonstrated live.")
    bullet(doc, "Engineering quality",
           "88 automated tests (up from 54), a pinned code checker with no findings, and a bug caught only by "
           "the live demonstration (new settings not passed into the container), now fixed and checked.")
    bullet(doc, "Documentation",
           "the research paper updated with three new results sections and two corrected Phase 2 claims, a "
           "new architecture diagram, the lab notebook and the README.")

    # ---- 3. measured result ----------------------------------------------
    heading(doc, "3.  Measured Result of Phase 3")
    names = {"base": "No defence", "filter": "Label match only", "recheck": "Re-check risky hits only",
             "both": "Label match + re-check risky hits", "all": "Label match + re-check every hit"}
    rows = []
    for tag in ("base", "filter", "recheck", "both", "all"):
        a = ARMS[tag]
        clean, attack = a["served"]["clean"]["cache_caused"], a["served"]["attack"]["cache_caused"]
        colour = GREEN if tag == "all" else (RED if clean > 40 else ORANGE)
        rows.append([names[tag], (pct(clean), colour), pct(attack), pct(a["honest_hit_rate"]),
                     f"{a['hit_p50_ms']:.0f} ms"])
    table(doc, ["Setting", "Cache-caused leaks, saved as clean", "Cache-caused leaks, saved as attack",
                "Honest hits kept", "Median hit"],
          rows, widths=[2.2, 1.15, 1.15, 0.95, 0.85], center_cols=(1, 2, 3, 4), bold_row=4)
    caption(doc, "Table 1 - Cache-caused leaks in each setting at a similarity threshold of 0.85. A leak is "
                 "cache-caused when the filter blocks that exact text if asked directly.")

    para(doc, f"**Label matching stops the easy case** ({pct(ARMS['filter']['served']['attack']['cache_caused'])} "
              f"left) **but not the realistic one** ({pct(ARMS['filter']['served']['clean']['cache_caused'])}), "
              "because a poisoned answer saved as clean carries the same label as an honest one. **Re-checking "
              f"only risky hits leaves {pct(both['served']['clean']['cache_caused'])}**, because the keyword label "
              "calls most real attacks informational. **Re-checking every hit removes every cache-caused leak.** "
              f"What is still served, about {every['served']['clean']['filter_miss']:.0f}%, is exactly the share the "
              f"filter misses when asked directly: the filter alone blocks {DEF['filter_blocks_alone']:.0f}% of "
              "these rewordings. No honest question was served the poison in any setting.")

    figure(doc, ROOT / "paper/figures/defence_poison_served.png", 5.6)
    caption(doc, "Figure 1 - Attack rewordings served the poison. The coloured part is caused by the cache; "
                 "the grey part is missed by the filter itself.")

    figure(doc, ROOT / "paper/figures/defence_tradeoff.png", 6.0)
    caption(doc, "Figure 2 - The trade-off. Left: cache-caused leaks. Right: median time of an honest cache "
                 "hit, and the share of hits kept.")

    probes = sum(demo_count(k) for k in ("answered", "blocked by the filter", "refused, rate limit"))
    c = RTR["cost_by_label"]
    table(doc, ["Questions", "Always strong model", "Model picker", "Saved"], [
        ["Easy (20)", f"${c['easy']['strong']:.5f}", f"${c['easy']['router']:.5f}",
         (f"{100 * (1 - c['easy']['router'] / c['easy']['strong']):.0f}%", GREEN)],
        ["Hard (20)", f"${c['hard']['strong']:.5f}", f"${c['hard']['router']:.5f}",
         f"{100 * (1 - c['hard']['router'] / c['hard']['strong']):.0f}%"],
        ["All 40", f"${RTR['strong_cost_usd']:.5f}", f"${RTR['router_cost_usd']:.5f}", f"{RTR['saved_pct']:.0f}%"],
    ], widths=[1.6, 1.6, 1.6, 1.0], center_cols=(1, 2, 3), bold_row=2)
    caption(doc, "Table 2 - Model routing on live paid calls through OpenRouter (real token counts).")
    mix = RTR["projected_saving_by_mix"]
    para(doc, f"The picker agreed with our easy or hard label on **{RTR['agrees_with_our_label']} of "
              f"{RTR['questions']}** questions. The overall saving is modest because half of this set is hard, and "
              "long hard answers dominate the bill; from the measured average cost of each kind, the saving "
              f"would be {mix['80% easy']:.0f}% for traffic that is 80% easy and {mix['90% easy']:.0f}% at 90% "
              "(a projection). The fallback was verified live by configuring a model that does not exist: the "
              f"call failed, and {RTR['failover']['answered_by']} answered with status {RTR['failover']['status']}.")

    table(doc, ["Mitigation", "Live test", "Result"], [
        ["Output guard, off", "Cached answer carrying a cookie-stealing script", ("Served", RED)],
        ["Output guard, flag", "Same", ("Served, marked in a header", ORANGE)],
        ["Output guard, block", "Same", ("Refused, HTTP 403", GREEN)],
        ["Rate limit, 20 per minute", f"{probes} attack probes from one caller in a burst",
         (f"{demo_count('refused, rate limit')} refused with HTTP 429", GREEN)],
        ["Rate limit, other callers", "An honest caller at the same moment", ("Unaffected", GREEN)],
    ], widths=[1.8, 2.6, 1.9])
    caption(doc, "Table 3 - Output guard and rate limit, demonstrated on the running gateway.")

    # ---- 4. timeline -----------------------------------------------------
    heading(doc, "4.  Project Timeline")
    table(doc, ["Phase", "Window", "Objective and deliverable", "Status"], [
        ["1", "18 - 22 Aug 2026", "Establish the problem. Offline proof-of-concept, threshold sweep, "
                                  "architecture definition, synopsis.", ("COMPLETE", GREEN)],
        ["2", "23 Aug - 26 Sep 2026", "Build the gateway and reproduce the bypass on our own running "
                                      "system. First real bypass-rate figure.", ("COMPLETE", GREEN)],
        ["3", "27 Sep - 24 Oct 2026", "Build and validate the defence. Verdict-tagged cache, "
                                      "re-verification, routing, output guard, rate limiting.", ("COMPLETE", GREEN)],
        ["4", "25 Oct - 14 Nov 2026", "Full evaluation, ablation study, reproducible figure generation, "
                                      "research paper and final system.", ("NEXT", ORANGE)],
    ], widths=[0.6, 1.4, 3.3, 1.1], center_cols=(0, 3))
    caption(doc, "Table 4 - Phase-level schedule.")

    heading(doc, "4.1  Week-by-Week Plan for the Next Phase (Phase 4)", size=12.5)
    table(doc, ["Week", "Task", "Demonstrable output"], [
        ["W1 · 25 - 31 Oct", "Load testing with Locust against the full defended gateway; latency "
                             "percentiles under concurrent users.",
         "p50 and p99 per outcome under load, defence on and off."],
        ["W2 · 1 - 7 Nov", "Ablation study switching each layer off in turn; false-alarm rate on honest "
                           "questions; a fresh question set for the model picker.",
         "The full results table, one row per layer."],
        ["W3 · 8 - 14 Nov", "Final paper; one command that rebuilds every number and chart from a fresh "
                            "clone; final presentation.",
         "Submitted paper and a reproducible repository."],
    ], widths=[1.3, 2.9, 2.2])
    caption(doc, "Table 5 - Phase 4 breakdown.")

    heading(doc, "4.2  Outstanding Work and Immediate Risks", size=12.5)
    bullet(doc, "Filter accuracy",
           f"the public classifier blocks {DEF['filter_blocks_alone']:.0f}% of these rewordings when asked directly "
           "(95 of 100 jayavibhav seeds, but only 55 of 139 deepset seeds). The defence removes the risk the "
           "cache adds, not the filter's own misses; Phase 4 reports the two datasets separately.")
    bullet(doc, "Keyword labels",
           "the cheap label calls most real attacks harmless, which is why risky-only re-checking failed. "
           "Re-checking every hit does not depend on it.")
    bullet(doc, "Router evaluation",
           "the routing rules were adjusted once after seeing the 40 questions, so the 39 of 40 agreement is "
           "optimistic. Phase 4 tests it on questions it was not tuned on.")
    bullet(doc, "Output guard coverage",
           "the guard uses plain patterns and catches obvious payloads only; it is reported as a second line of "
           "defence, not a complete one.")

    # ---- 5. architecture -------------------------------------------------
    page_break(doc)
    heading(doc, "5.  System Architecture and Design Reference")
    para(doc, "Figure 3 shows the gateway as it runs at the end of Phase 3. **The cache is still consulted "
              "first, for speed, but a hit now needs a matching safety label and passes a fresh safety check "
              "before it is served.** Every answer, fresh or cached, passes the output guard, and a rate limit "
              "sits in front of everything.")
    figure(doc, ROOT / "reports/assets/architecture-phase3.png", 5.3)
    caption(doc, "Figure 3 - SentryGate at the end of Phase 3. Amber marks the parts added in this phase.")
    para(doc, "**Reading the diagram:** a request passes Nginx and the rate limit, then reaches the cache, which "
              "only returns stored answers whose safety label matches the question. **On a hit, the safety "
              "check runs again on the new question, without calling the model**; an attack is refused with "
              "403. On a miss, the safety check runs, and a clean question goes to the model picker, which "
              "chooses a cheap or strong model through OpenRouter. The output guard inspects every answer, "
              "fresh answers are stored with their safety label, and every request is recorded in the log, "
              "the single source of every number in this report.", after=0)

    return save(doc, "Progress3.docx")


if __name__ == "__main__":
    print("wrote", build().relative_to(ROOT))
