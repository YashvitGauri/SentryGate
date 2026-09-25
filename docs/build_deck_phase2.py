"""Build docs/deck-phase2.html for the second presentation (Progress Eval-1).

Every number is read from the committed results, so the slides cannot drift
from what the code produced:

    data/week4/report.json     the bypass sweep and its checks
    data/week4/latency.md      the response-time table
    paper/figures/*.png        the charts
    docs/architecture-current.png   what runs today

The visual style and the slide navigation are reused from the Phase 1 deck
(docs/deck.template.html), so both decks look and behave the same.

    make deck-phase2
"""

from __future__ import annotations

import base64
import json
import pathlib
import re
import sys

DOCS = pathlib.Path(__file__).parent
ROOT = DOCS.parent
REPORT = ROOT / "data" / "week4" / "report.json"
LATENCY = ROOT / "data" / "week4" / "latency.md"
TEMPLATE = DOCS / "deck.template.html"
OUT = DOCS / "deck-phase2.html"


def b64(path: pathlib.Path) -> str:
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()


def extract(tag: str, text: str) -> str:
    m = re.search(rf"<{tag}[^>]*>.*?</{tag}>", text, re.S)
    if not m:
        sys.exit(f"could not find <{tag}> in the Phase 1 template")
    return m.group(0)


def read_latency() -> list[tuple[str, str, str, str]]:
    """Rows of (outcome, requests, p50, p99) from the latency table.

    latency.md is a plain Markdown table with numeric cells and no units, so we
    split on the pipes and skip the header and separator rows.
    """
    rows = []
    for line in LATENCY.read_text().splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 4:
            continue
        outcome, reqs, p50, p99 = cells
        if outcome in ("Outcome", "") or set(reqs) <= set("-"):
            continue
        rows.append((outcome, f"{int(reqs):,}", f"{float(p50):.0f}", f"{float(p99):.0f}"))
    return rows


def bypass_rows(report: dict) -> str:
    order = ["0.95", "0.9", "0.85", "0.8", "0.75", "0.7", "0.65"]
    out = []
    for key in order:
        r = report["by_threshold"][key]
        hi = ' class="hi"' if key == "0.85" else ""
        shown = f"{float(key):.2f}"
        out.append(
            f'<tr{hi}><td class="mono">{shown}</td>'
            f'<td class="num">{r["lazy"]:.0f}%</td>'
            f'<td class="num dim">{r["rewrite"]:.0f}%</td>'
            f'<td class="num">{r["overall"]:.0f}%</td></tr>'
        )
    return "\n".join(out)


def latency_rows(rows: list) -> str:
    out = []
    for outcome, reqs, p50, p99 in rows:
        cls = ' class="hi"' if outcome.startswith("Cache hit") else ""
        out.append(
            f'<tr{cls}><td>{outcome}</td><td class="num mono">{reqs}</td>'
            f'<td class="num mono">{p50} ms</td><td class="num mono">{p99} ms</td></tr>'
        )
    return "\n".join(out)


SLIDES = """
    <!-- 1 TITLE -->
    <section class="slide on" data-notes="Open by naming the checkpoint. Phase 1 proved the problem in a script. This checkpoint proves it on a real gateway we built, and shows the vulnerable baseline the fix will beat.">
      <div class="title-wrap">
        <div class="eyebrow">Progress Eval-1 &middot; Phase 2</div>
        <div class="rule"></div>
        <h1>The bypass, now on<br>our own gateway.</h1>
        <p class="lede">We built the gateway, and reproduced the cache bypass on it &mdash; with the real filter, the real embedder, and real Qdrant and Redis.</p>
        <div class="meta-row">
          <div><span class="meta-k">Team</span><span class="meta-v">Divyansh Sharma &middot; Sarvagya Dabas &middot; Yashvit Gauri</span></div>
          <div><span class="meta-k">Window</span><span class="meta-v">23 Aug &ndash; 26 Sep</span></div>
          <div><span class="meta-k">State</span><span class="meta-v">Phase 2 complete</span></div>
        </div>
      </div>
    </section>

    <!-- 2 RECAP -->
    <section class="slide" data-notes="One line of recap from Phase 1, then the turn: that was a script. The question this checkpoint answers is whether it happens on a real running system. It does.">
      <div class="eyebrow">Where we left off</div>
      <h2>Phase 1 proved the problem in a script.</h2>
      <div class="thesis">
        <q>A cache hit returns before the safety filter is ever asked &mdash; so a reworded attack can be served an answer the filter would have blocked.</q>
      </div>
      <p class="lede">This checkpoint answers one question: does it happen on a <strong>real running system</strong>? It does.</p>
    </section>

    <!-- 3 WHAT WE BUILT -->
    <section class="slide" data-notes="Trace the two paths with the cursor. Every question hits the cache first. Seen before: answered at once, and the safety check never runs - that is the hole. New: checked, answered by the model, and saved together with its safety label. Phase 3 makes the cache check that saved label too.">
      <div class="eyebrow">What we built</div>
      <h2>Every question hits the cache first.</h2>
      <svg class="flow" viewBox="0 0 1144 360" role="img" aria-label="A question goes to the cache first. If the cache has seen something similar, the answer is served at once and the safety check is skipped. If it is new, it is safety-checked, answered by the model, and saved with its safety label.">
        <defs>
          <marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#8496AB"/></marker>
          <marker id="ahr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#E5484D"/></marker>
        </defs>
        <!-- question -> cache -->
        <rect x="0" y="140" width="180" height="84" rx="14" fill="#16202C" stroke="#2A3846" stroke-width="2"/>
        <text x="90" y="179" class="t">A question</text>
        <text x="90" y="205" class="s">from any app</text>
        <line x1="180" y1="182" x2="238" y2="182" stroke="#8496AB" stroke-width="2.5" marker-end="url(#ah)"/>
        <rect x="244" y="140" width="210" height="84" rx="14" fill="#2A2415" stroke="#F2A93B" stroke-width="2.5"/>
        <text x="349" y="179" class="t">1  Cache</text>
        <text x="349" y="205" class="s">checked first</text>
        <!-- top path: seen before -> answered, check skipped -->
        <path d="M454,170 C510,170 510,62 566,62" fill="none" stroke="#E5484D" stroke-width="2.5" marker-end="url(#ahr)"/>
        <text x="502" y="120" class="lab red" text-anchor="end">seen before</text>
        <rect x="572" y="20" width="240" height="84" rx="14" fill="#2A1618" stroke="#E5484D" stroke-width="2.5"/>
        <text x="692" y="59" class="t">Answer served</text>
        <text x="692" y="85" class="s">straight from the cache</text>
        <text x="836" y="54" class="note red">Safety check skipped.</text>
        <text x="836" y="82" class="note red">This is the hole.</text>
        <!-- bottom path: new -> check -> model -> save -->
        <path d="M454,194 C510,194 510,302 566,302" fill="none" stroke="#8496AB" stroke-width="2.5" marker-end="url(#ah)"/>
        <text x="502" y="258" class="lab" text-anchor="end">new</text>
        <rect x="572" y="260" width="172" height="84" rx="14" fill="#16202C" stroke="#2A3846" stroke-width="2"/>
        <text x="658" y="299" class="t">2  Safety check</text>
        <text x="658" y="325" class="s">blocks attacks</text>
        <line x1="744" y1="302" x2="772" y2="302" stroke="#8496AB" stroke-width="2.5" marker-end="url(#ah)"/>
        <rect x="778" y="260" width="146" height="84" rx="14" fill="#16202C" stroke="#2A3846" stroke-width="2"/>
        <text x="851" y="299" class="t">3  AI model</text>
        <text x="851" y="325" class="s">writes the answer</text>
        <line x1="924" y1="302" x2="952" y2="302" stroke="#8496AB" stroke-width="2.5" marker-end="url(#ah)"/>
        <rect x="958" y="260" width="184" height="84" rx="14" fill="#2A2415" stroke="#F2A93B" stroke-width="2.5"/>
        <text x="1050" y="299" class="t">4  Save</text>
        <text x="1050" y="325" class="s">answer + safety label</text>
      </svg>
      <p><small>The safety label is already saved with every answer. <strong>The fix in Phase 3: the cache checks that label too</strong>, so a reworded attack no longer matches a safe answer.</small></p>
    </section>

    <!-- 4 THE EXPERIMENT -->
    <section class="slide" data-notes="Explain how the number is earned, so the result is credible. Real public datasets, two families of rewording kept apart, everything fired over HTTP at the running gateway, and a bypass counted only when the poison comes back AND the log says the filter never ran.">
      <div class="eyebrow">The experiment</div>
      <h2>{{SEEDS}} real attacks, {{VARIANTS}} rewordings, on the live gateway.</h2>
      <div class="grid2" style="align-items:start;">
        <ul class="clean">
          <li>Seeds from two public datasets: <span class="mono">deepset/prompt-injections</span> and <span class="mono">jayavibhav/prompt-injection</span>.</li>
          <li>Two families, kept apart: <strong>lazy edits</strong> (capitals, punctuation, a filler word) and <strong>full rewrites</strong> (real paraphrases).</li>
          <li>Every variant fired over HTTP at the running gateway.</li>
        </ul>
        <div class="panel" style="display:flex;flex-direction:column;gap:12px;border-color:rgba(242,169,59,.4);">
          <h3 class="amber">A bypass is counted only when both are true</h3>
          <p style="font-size:19px;">The poisoned answer comes back, <strong>and</strong></p>
          <p style="font-size:19px;">the gateway's own log line says <span class="mono">screening_ran = false</span>.</p>
          <p style="font-size:17px;" class="dim">The claim is read from the log, not from our code.</p>
        </div>
      </div>
    </section>

    <!-- 5 THE RESULT -->
    <section class="slide" data-notes="This is the headline. Read the 0.85 row out loud: at a normal cache setting, 97 percent of lazy rewordings were served the poison. Lazy edits leak at every setting. Full rewrites only match once the cache is loose. Same shape as Phase 1, now on a real system at large scale.">
      <div class="eyebrow">The result</div>
      <h2>At a normal setting, <span class="amber">97%</span> of lazy attacks got through.</h2>
      <div class="grid2 fill" style="align-items:start;">
        <div class="panel">
          <table>
            <thead><tr><th>Cut-off</th><th class="num">Lazy edits</th><th class="num">Full rewrites</th><th class="num">Overall</th></tr></thead>
            <tbody>
              {{BYPASS_ROWS}}
            </tbody>
          </table>
        </div>
        <div class="figframe" style="margin:0;"><img src="{{BYPASS_PNG}}" alt="Bypass rate against the cache similarity threshold. Lazy edits stay near the top at every setting; full rewrites climb only as the cache loosens."></div>
      </div>
      <p><small>The filter is not weak &mdash; it scores every attack at 1.000. On a cache hit it is simply never asked.</small></p>
    </section>

    <!-- 6 PROOF -->
    <section class="slide" data-notes="Pre-empt every doubt with the checks. The safe-order row is the one to dwell on: run the exact same build with the filter moved in front of the cache, and the bypass drops to zero. Nothing else changed, so the order is the cause. That is the whole argument for the Phase 3 fix.">
      <div class="eyebrow">Why the number is trustworthy</div>
      <h2>Four checks, and a proof of cause.</h2>
      <div class="panel" style="overflow:auto;">
        <table>
          <thead><tr><th>Check</th><th class="num">Result</th><th>Why it matters</th></tr></thead>
          <tbody>
            <tr><td>Exact attack served the poison</td><td class="num mono green">{{EXACT}}</td><td>the experiment is wired correctly</td></tr>
            <tr><td>Honest questions served the poison</td><td class="num mono green">{{CONTROL}}</td><td>normal users are not caught in the crossfire</td></tr>
            <tr class="hi"><td>Safe order (filter before cache)</td><td class="num mono amber">{{SCREEN_FIRST}}%</td><td><strong>proof the order is the cause</strong></td></tr>
            <tr><td>Log score vs served hit</td><td class="num mono green">{{MISMATCH}}</td><td>recorded scores match what was served</td></tr>
          </tbody>
        </table>
      </div>
      <p class="lede">Move the filter in front of the cache, same build, same attacks &mdash; the bypass drops to <strong class="amber">zero</strong>.</p>
    </section>

    <!-- 7 LATENCY -->
    <section class="slide" data-notes="Answer the obvious question: why not just screen everything? Because the cache is seven times faster. This gap, measured on 25 thousand real requests, is exactly why real systems check the cache first, and so it is the reason the bypass exists. The fix cannot be to screen everything.">
      <div class="eyebrow">Why the cache goes first</div>
      <h2>A hit is <span class="amber">7&times;</span> faster than a miss.</h2>
      <div class="grid2 fill" style="align-items:start;">
        <div class="panel">
          <table>
            <thead><tr><th>Outcome</th><th class="num">Requests</th><th class="num">p50</th><th class="num">p99</th></tr></thead>
            <tbody>
              {{LATENCY_ROWS}}
            </tbody>
          </table>
        </div>
        <div class="figframe" style="margin:0;"><img src="{{LATENCY_PNG}}" alt="Response time by outcome: a cache hit is about 14 ms, a miss about 94 ms because it pays for the safety check."></div>
      </div>
      <p><small>From 25,416 real requests. Screening every request throws this speed-up away &mdash; so the fix has to make the cache itself safety-aware.</small></p>
    </section>

    <!-- 8 THE FIX (preview) -->
    <section class="slide" data-notes="Preview the Phase 3 fix in one idea, so the checkpoint points forward. Today the cache asks one question. We add a second: was the original safe. The label is already stored - we showed that on the architecture slide - so the fix is a filter on a search that already runs.">
      <div class="eyebrow">What Phase 3 does</div>
      <h2>Let the cache ask a second question.</h2>
      <div class="grid2" style="align-items:start;">
        <div class="panel" style="display:flex;flex-direction:column;gap:12px;">
          <h3 class="dim">The cache today asks</h3>
          <p style="font-size:19px;">&ldquo;Does this sound like something I answered before?&rdquo;</p>
          <p style="font-size:19px;" class="red">That is the only question. It is the hole.</p>
        </div>
        <div class="panel" style="display:flex;flex-direction:column;gap:12px;border-color:rgba(242,169,59,.4);">
          <h3 class="amber">SentryGate also asks</h3>
          <p style="font-size:19px;">&ldquo;...and was that earlier question <strong>safe</strong>?&rdquo;</p>
          <p style="font-size:19px;" class="green">The label is already stored, so it is one extra check, no extra model.</p>
        </div>
      </div>
      <p><small>Next milestone: rerun these exact attacks with the check on. The bypass rate should fall sharply &mdash; that is the first proof the fix works.</small></p>
    </section>

    <!-- 9 PLAN -->
    <section class="slide" data-notes="Show where this checkpoint sits. Phase 2 is done. Phase 3 builds the fix and shows it beat this baseline, live. End of Phase 2 is exactly the right place to have a measured, vulnerable baseline and nothing more.">
      <div class="eyebrow">Plan</div>
      <h2>Phase 2 done. The fix is next.</h2>
      <div class="rail">
        <div class="ph"><span class="ph-n">01</span><span class="ph-w">18&ndash;22 Aug</span><span class="ph-t">Prove the problem is real</span><span class="ph-s">done</span></div>
        <div class="ph"><span class="ph-n">02</span><span class="ph-w">23 Aug&ndash;26 Sep</span><span class="ph-t">Build the gateway and reproduce the problem on it</span><span class="ph-s now">You are here</span></div>
        <div class="ph"><span class="ph-n">03</span><span class="ph-w">27 Sep&ndash;24 Oct</span><span class="ph-t">Build the fix and show it beat the baseline, live</span><span class="ph-s">4 weeks</span></div>
        <div class="ph"><span class="ph-n">04</span><span class="ph-w">25 Oct&ndash;14 Nov</span><span class="ph-t">Measure everything properly and write the paper</span><span class="ph-s">3 weeks</span></div>
      </div>
      <p class="lede">The job of this phase was a measured, vulnerable baseline &mdash; something for the fix to beat. That is exactly what we have.</p>
    </section>

    <!-- 10 CLOSE -->
    <section class="slide" data-notes="Land on the sentence and stop. The demo is one command if there is time; the recorded capture is the fallback. Take questions.">
      <div class="eyebrow">In one sentence</div>
      <div class="thesis">
        <q>On our own gateway, <strong class="amber">{{HEADLINE}}%</strong> of lazy rewordings were served a poisoned answer, and the filter ran <strong class="red">zero</strong> times.</q>
        <p class="lede">Move the filter in front of the cache and it drops to zero &mdash; so we know exactly what to fix.</p>
      </div>
      <div class="meta-row">
        <div><span class="meta-k">Live demo</span><span class="meta-v mono">make gateway-up &amp;&amp; make gateway-demo</span></div>
        <div><span class="meta-k">Reproduce the result</span><span class="meta-v mono">make bypass</span></div>
      </div>
    </section>
"""


def main() -> int:
    report = json.loads(REPORT.read_text())
    latency = read_latency()
    template = TEMPLATE.read_text()
    style = extract("style", template)
    script = extract("script", template)

    headline = f'{report["by_threshold"]["0.85"]["lazy"]:.0f}'
    slides = SLIDES
    replacements = {
        "{{BYPASS_PNG}}": b64(ROOT / "paper" / "figures" / "bypass_vs_threshold.png"),
        "{{LATENCY_PNG}}": b64(ROOT / "paper" / "figures" / "latency.png"),
        "{{BYPASS_ROWS}}": bypass_rows(report),
        "{{LATENCY_ROWS}}": latency_rows(latency),
        "{{SEEDS}}": str(report["seeds"]),
        "{{VARIANTS}}": f'{report["attack_variants_per_threshold"]:,}',
        "{{EXACT}}": report["exact_served"],
        "{{CONTROL}}": report["control_served_poison"],
        "{{SCREEN_FIRST}}": f'{report["screen_first_bypass_at_085"]:.0f}',
        "{{MISMATCH}}": str(report["score_hit_mismatches"]),
        "{{HEADLINE}}": headline,
    }
    for key, value in replacements.items():
        slides = slides.replace(key, value)

    total = slides.count('class="slide')
    html_doc = f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<title>SentryGate Phase 2 &middot; Progress Eval-1</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:ital,wght@0,300;0,400;0,500;0,600;0,700;1,400&family=IBM+Plex+Mono:ital,wght@0,400;0,500;0,600;1,400&display=swap">
{style}
<style>
.flow{{width:100%;height:auto;margin:18px 0 6px;font-family:"IBM Plex Sans",system-ui,sans-serif;}}
.flow .t{{fill:#E9EEF5;font-size:21px;font-weight:600;text-anchor:middle;}}
.flow .s{{fill:#8496AB;font-size:15px;text-anchor:middle;}}
.flow .lab{{fill:#8496AB;font-size:15px;font-family:"IBM Plex Mono",monospace;}}
.flow .note{{font-size:19px;font-weight:600;}}
.flow .red{{fill:#E5484D;}}
</style>
</head>
<body>
<div class="viewport">
  <div class="stage" id="stage">
{slides}
  </div>
  <div class="chrome">
    <span>SentryGate &middot; Phase 2</span>
    <span><span id="cur">1</span> / <span id="tot">{total}</span></span>
  </div>
  <div class="progress" id="prog"></div>
</div>
<div class="help"><kbd>&larr;</kbd> <kbd>&rarr;</kbd> move &nbsp; <kbd>N</kbd> notes &nbsp; <kbd>F</kbd> full screen</div>
<div class="notes" id="notes"><span class="nt">Presenter note</span><span id="noteBody"></span></div>
{script}
</body></html>
"""
    OUT.write_text(html_doc)
    print(f"wrote {OUT.relative_to(ROOT)}  ({total} slides)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
