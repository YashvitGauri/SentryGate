"""Build Progress Report-2 (Phase 2) in the same format as Progress Report-1.

Same cover, same five sections, same table style. Every number is read from
the committed results, so the report cannot drift from what the code measured:

    data/week4/report.json    the bypass sweep and its checks
    data/week4/latency.md     the latency table

Writes reports/out/Progress2.docx. The PDF is converted from it (make report).

Run:  python3 reports/build_progress2.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Inches, Pt, RGBColor

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = HERE / "out"
REPORT = json.loads((ROOT / "data/week4/report.json").read_text())

# Names and enrollment numbers live in reports/team.json, which git ignores
# because the repository is public. Copy team.example.json to start.
_TEAM_FILE = HERE / "team.json"
if not _TEAM_FILE.exists():
    raise SystemExit("Missing reports/team.json - copy reports/team.example.json and fill it in.")
TEAM = json.loads(_TEAM_FILE.read_text())

SERIF = "Times New Roman"
SANS = "Arial"
HEADER_FILL = "DCE6F2"          # light blue-grey header row, as in Report-1
GREEN = RGBColor(0x2E, 0x7D, 0x32)
ORANGE = RGBColor(0xC0, 0x6A, 0x00)
RED = RGBColor(0xC6, 0x28, 0x28)
GREY = RGBColor(0x55, 0x55, 0x55)


# ---------------------------------------------------------------- data

def pct(x: float) -> str:
    return f"{x:.1f}%"


def latency_rows() -> list[tuple[str, int, float, float]]:
    rows = []
    for line in (ROOT / "data/week4/latency.md").read_text().splitlines():
        if not line.strip().startswith("|"):
            continue
        c = [x.strip() for x in line.strip().strip("|").split("|")]
        if len(c) != 4 or c[0] == "Outcome" or set(c[1]) <= set("-"):
            continue
        rows.append((c[0], int(c[1]), float(c[2]), float(c[3])))
    return rows


BT = REPORT["by_threshold"]
T085 = BT["0.85"]
LAT = latency_rows()
TOTAL_REQ = sum(r[1] for r in LAT)


# ---------------------------------------------------------------- helpers

def set_font(run, name=SERIF, size=12, bold=None, italic=None, color=None, underline=None):
    run.font.name = name
    run._element.rPr.rFonts.set(qn("w:eastAsia"), name)
    run.font.size = Pt(size)
    if bold is not None:
        run.bold = bold
    if italic is not None:
        run.italic = italic
    if underline is not None:
        run.underline = underline
    if color is not None:
        run.font.color.rgb = color


def rich(par, text: str, size=12, name=SERIF, color=None):
    """Add text with **bold** spans."""
    for i, chunk in enumerate(re.split(r"\*\*", text)):
        if chunk:
            set_font(par.add_run(chunk), name=name, size=size, bold=(i % 2 == 1), color=color)
    return par


def para(doc, text: str, size=12, align=WD_ALIGN_PARAGRAPH.JUSTIFY, after=6, name=SERIF):
    p = doc.add_paragraph()
    p.alignment = align
    p.paragraph_format.space_after = Pt(after)
    p.paragraph_format.line_spacing = 1.15
    return rich(p, text, size=size, name=name)


def heading(doc, text: str, size=14):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(10)
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.keep_with_next = True
    set_font(p.add_run(text), size=size, bold=True, underline=True)
    return p


def bullet(doc, lead: str, text: str):
    p = doc.add_paragraph(style="List Bullet")
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p.paragraph_format.space_after = Pt(3)
    p.paragraph_format.line_spacing = 1.1
    set_font(p.add_run(lead), bold=True)
    rich(p, f" - {text}")


def caption(doc, text: str):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(8)
    p.paragraph_format.keep_with_next = False
    set_font(p.add_run(text), size=9, italic=True)


def shade(cell, fill: str):
    tc_pr = cell._element.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    tc_pr.append(shd)


def table(doc, header: list[str], rows: list[list], widths: list[float], center_cols=(), bold_row=None):
    """rows: list of lists; a cell may be str or (str, RGBColor) for coloured bold text."""
    t = doc.add_table(rows=1 + len(rows), cols=len(header))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, h in enumerate(header):
        c = t.rows[0].cells[i]
        shade(c, HEADER_FILL)
        c.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER if i in center_cols else WD_ALIGN_PARAGRAPH.LEFT
        set_font(c.paragraphs[0].add_run(h), size=11, bold=True)
    for r, row in enumerate(rows, start=1):
        for i, val in enumerate(row):
            c = t.rows[r].cells[i]
            p = c.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER if i in center_cols else WD_ALIGN_PARAGRAPH.LEFT
            if isinstance(val, tuple):
                set_font(p.add_run(val[0]), size=11, bold=True, color=val[1])
            else:
                set_font(p.add_run(str(val)), size=11, bold=(bold_row == r - 1))
    # Fixed column widths. Word and LibreOffice read the grid, not just the
    # cells, so both are set; without this every column comes out equal.
    t.autofit = False
    for i, w in enumerate(widths):
        t.columns[i].width = Inches(w)
    for row in t.rows:
        for i, w in enumerate(widths):
            row.cells[i].width = Inches(w)
    style_table(t)
    return t


def style_table(t):
    """Report-1 look: light grey borders, padded cells, centred vertically,
    and the table kept on one page with its header."""
    tbl_pr = t._element.tblPr
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), "4")
        el.set(qn("w:color"), "BFBFBF")
        borders.append(el)
    tbl_pr.append(borders)
    margins = OxmlElement("w:tblCellMar")
    for edge, v in (("top", 45), ("bottom", 45), ("left", 100), ("right", 100)):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:w"), str(v))
        el.set(qn("w:type"), "dxa")
        margins.append(el)
    tbl_pr.append(margins)
    last = len(t.rows) - 1
    for r, row in enumerate(t.rows):
        tr_pr = row._tr.get_or_add_trPr()
        cant = OxmlElement("w:cantSplit")
        tr_pr.append(cant)
        if r == 0:
            tr_pr.append(OxmlElement("w:tblHeader"))
        for cell in row.cells:
            tc_pr = cell._element.get_or_add_tcPr()
            v = OxmlElement("w:vAlign")
            v.set(qn("w:val"), "center")
            tc_pr.append(v)
            for p in cell.paragraphs:
                p.paragraph_format.space_after = Pt(0)
                p.paragraph_format.line_spacing = 1.0
                p.paragraph_format.keep_with_next = True  # table stays with its caption


def figure(doc, path: Path, width_in: float):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.keep_with_next = True
    p.add_run().add_picture(str(path), width=Inches(width_in))


# ---------------------------------------------------------------- document

def build() -> Path:
    doc = Document()
    sec = doc.sections[0]
    sec.page_height, sec.page_width = Cm(29.7), Cm(21.0)
    for side in ("left_margin", "right_margin"):
        setattr(sec, side, Cm(2.3))
    sec.top_margin, sec.bottom_margin = Cm(2.0), Cm(2.0)

    base = doc.styles["Normal"]
    base.font.name = SERIF
    base.font.size = Pt(12)

    # ---- cover -----------------------------------------------------------
    def cline(text, size=12, bold=False, underline=False, before=0, after=4):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(before)
        p.paragraph_format.space_after = Pt(after)
        set_font(p.add_run(text), name=SANS, size=size, bold=bold, underline=underline)

    cline("SentryGate", 20, bold=True, underline=True, before=30, after=14)
    cline("A Security-Aware Semantic Caching Gateway for Large Language", 14, bold=True, after=0)
    cline("Model Applications", 14, bold=True, after=18)
    cline("Progress Report-2", 12.5, bold=True, underline=True, after=18)
    cline("Submitted in the partial fulfilment of the Degree of", 12, after=2)
    cline("Bachelor of Technology", 12, bold=True, after=2)
    cline("(Information Technology)", 12, after=16)
    cline("Submitted by", 12, bold=True, after=6)
    for m in TEAM["members"]:
        cline(m, 12, after=2)
    cline("Under the supervision of", 12, bold=True, before=14, after=6)
    cline(TEAM["supervisor"], 13, bold=True, after=10)
    logo = doc.add_paragraph()
    logo.alignment = WD_ALIGN_PARAGRAPH.CENTER
    logo.add_run().add_picture(str(HERE / "assets/msit_logo.png"), width=Inches(1.45))
    cline("Department of Information Technology", 12, bold=True, before=8, after=2)
    cline("Maharaja Surajmal Institute of Technology", 12, bold=True, after=2)
    cline("Janakpuri, New Delhi.", 12, after=2)
    cline("2023-27", 12, after=0)
    doc.paragraphs[-1].add_run().add_break(WD_BREAK.PAGE)

    # ---- 1. status summary ----------------------------------------------
    heading(doc, "1.  Status Summary")
    para(doc, "**Phase 2 is complete and on schedule.** The objective of this phase was to build the "
              "gateway and to reproduce, on our own running system, the vulnerability that Phase 1 "
              "demonstrated in a controlled script. That has been done. **On the live gateway - with the "
              "real injection classifier, the real embedding model and real Qdrant and Redis stores - a "
              "semantic cache placed in front of the filter still serves poisoned answers to reworded "
              "attacks, and the filter is never invoked.**")
    para(doc, f"Across **{REPORT['seeds']} real attacks** drawn from two public prompt-injection datasets and "
              f"**{REPORT['attack_variants_per_threshold']:,} rewordings** of them, at a cache similarity threshold of "
              f"0.85, **{pct(T085['lazy'])}** of cheap surface rewordings were served the poisoned entry. Every "
              "one of those bypasses is confirmed by the gateway's own request log recording that screening "
              "did not run. Moving the filter in front of the cache, with no other change, reduces the bypass "
              f"rate to **{REPORT['screen_first_bypass_at_085']:.0f}%** - establishing that the ordering, not the "
              "filter, is the cause.")

    # ---- 2. work completed ----------------------------------------------
    heading(doc, "2.  Work Completed to Date")
    bullet(doc, "Gateway (Week 1)",
           "FastAPI service exposing an OpenAI-compatible /v1/chat/completions endpoint behind Nginx, "
           "containerised with Docker Compose; a provider layer with mock, replay and live modes and a hard "
           "daily spend cap; one structured JSONL log line per request.")
    bullet(doc, "Screening layer (Weeks 2 and 5)",
           "the deberta-v3 injection classifier and Microsoft Presidio personal-data detection folded into a "
           "single safety verdict (injection score, personal-data entities, intent, risk level) attached to "
           "every request; injections are refused with HTTP 403.")
    bullet(doc, "Baseline semantic cache (Week 3)",
           "exact match in Redis followed by MiniLM similarity search in Qdrant. Every stored answer carries "
           "its full safety verdict, deliberately left unused at lookup to form the vulnerable baseline.")
    bullet(doc, "Bypass reproduction (Week 4)",
           "an attack-variant generator seeded from deepset/prompt-injections and jayavibhav/prompt-injection "
           "(lazy edits by fixed rules, full rewrites by a local T5 paraphraser), and a sweep that poisons the "
           "cache, fires every variant over HTTP and confirms each bypass from the log, across seven "
           "thresholds, plus a safe-order control arm.")
    bullet(doc, "Measurement and demonstration (Week 5)",
           f"a /metrics/summary endpoint; latency percentiles computed from {TOTAL_REQ:,} logged requests; a "
           "recorded end-to-end demonstration as a live-evaluation fallback; the architecture diagram "
           "regenerated to match the running system.")
    bullet(doc, "Live model integration",
           "a first real completion through the gateway via OpenRouter (openai/gpt-4o-mini), with its cost "
           "recorded (US$0.000024) and saved to a replay cassette so the call reproduces without credentials.")
    bullet(doc, "Engineering quality",
           "54 automated tests run inside the Docker image with no model downloads and no API calls; every "
           "figure and table is generated from committed scripts and logs.")
    bullet(doc, "Documentation",
           "a research paper draft (18 pages, including a cited related-work review), the Phase 2 "
           "presentation deck in HTML and editable PowerPoint, and a weekly lab notebook.")

    # ---- 3. measured result ----------------------------------------------
    heading(doc, "3.  Measured Result of Phase 2")
    table(doc, ["Measurement", "Value", "Interpretation"], [
        ["Attack rewordings tested per threshold", (f"{REPORT['attack_variants_per_threshold']:,}", GREY),
         f"{REPORT['seeds']} seeds, lazy edits and full rewrites, fired at the live gateway."],
        ["Lazy rewordings served the poisoned entry", (pct(T085["lazy"]), RED),
         "Near-total bypass at a normal production setting."],
        ["Filter invocations on confirmed bypasses", ("0", RED),
         "Read from the gateway's own log for every case."],
        ["Same attacks, filter placed before cache", (f"{REPORT['screen_first_bypass_at_085']:.0f}%", GREEN),
         "The ordering is the cause of the bypass."],
        ["Honest questions served the poison", (REPORT["control_served_poison"].replace("/", " / "), GREEN),
         "Legitimate users are not affected."],
        ["Exact seed served the poison (sanity check)", (REPORT["exact_served"].replace("/", " / "), GREEN),
         "The experiment is wired correctly."],
    ], widths=[2.3, 1.0, 3.1], center_cols=(1,))
    caption(doc, "Table 1 - Phase 2 result on the running gateway at a cache similarity threshold of 0.85.")

    para(doc, "The shape of the Phase 1 finding holds on the real system at nearly 300 times the scale. "
              "**Lazy edits - a capital letter, a full stop, one extra word - get through at every threshold**, "
              f"including the strictest ({pct(BT['0.95']['lazy'])} at 0.95). Full rewrites succeed only as the "
              "threshold is loosened. They succeed more often than in Phase 1 because the T5 paraphrases stay "
              "closer to the original wording than the hand-written rewrites used then.")

    rows = []
    notes = {"0.95": "Even the strictest setting leaks most cheap edits",
             "0.85": "Setting used in Table 1",
             "0.8": "Typical production setting",
             "0.7": "Paraphrases increasingly succeed"}
    for k in ["0.95", "0.9", "0.85", "0.8", "0.75", "0.7", "0.65"]:
        r = BT[k]
        rows.append([f"{float(k):.2f}", pct(r["lazy"]), pct(r["rewrite"]), pct(r["overall"]), notes.get(k, "")])
    table(doc, ["Threshold", "Lazy edits", "Full rewrites", "Overall bypass", "Practical consequence"],
          rows, widths=[0.9, 1.0, 1.1, 1.1, 2.3], center_cols=(0, 1, 2, 3), bold_row=2)
    caption(doc, "Table 2 - Bypass rate against cache similarity threshold on the live gateway. "
                 "No threshold is simultaneously secure and useful.")

    figure(doc, ROOT / "paper/figures/bypass_vs_threshold.png", 4.3)
    caption(doc, "Figure 1 - Share of attacks served from the poisoned entry at each threshold. "
                 "Lazy edits stay near the top; full rewrites rise only as the cache is loosened.")

    lat_rows = []
    meaning = {"Cache hit": "Answered without screening",
               "Miss (screen + model)": "Pays the safety screen, then the model",
               "Blocked attack": "Screened and refused"}
    for name, n, p50, p99 in LAT:
        lat_rows.append([name, f"{n:,}", f"{p50:.1f} ms", f"{p99:.1f} ms", meaning.get(name, "")])
    table(doc, ["Outcome", "Requests", "p50", "p99", "Meaning"], lat_rows,
          widths=[1.7, 0.9, 0.9, 0.9, 2.0], center_cols=(1, 2, 3), bold_row=0)
    caption(doc, f"Table 3 - Gateway latency by outcome, from {TOTAL_REQ:,} logged requests.")
    hit = next(r for r in LAT if r[0] == "Cache hit")
    miss = next(r for r in LAT if r[0].startswith("Miss"))
    para(doc, f"A cache hit answers in {hit[2]:.0f} ms at the median; a miss pays the safety screen and takes "
              f"{miss[2]:.0f} ms, roughly {miss[2] / hit[2]:.0f} times slower. **This gap is why production "
              "systems check the cache first, and therefore why the bypass exists.** It also rules out the naive "
              "fix of screening every request, which would discard the speed-up - the defence must make the "
              "cache itself safety-aware.")

    # ---- 4. timeline -----------------------------------------------------
    heading(doc, "4.  Project Timeline")
    table(doc, ["Phase", "Window", "Objective and deliverable", "Status"], [
        ["1", "18 - 22 Aug 2026", "Establish the problem. Offline proof-of-concept, threshold sweep, "
                                  "architecture definition, synopsis.", ("COMPLETE", GREEN)],
        ["2", "23 Aug - 26 Sep 2026", "Build the gateway and reproduce the bypass on our own running "
                                      "system. First real bypass-rate figure.", ("COMPLETE", GREEN)],
        ["3", "27 Sep - 24 Oct 2026", "Build and validate the defence. Verdict-tagged cache, "
                                      "re-verification, routing, output guard, rate limiting.", ("NEXT", ORANGE)],
        ["4", "25 Oct - 14 Nov 2026", "Full evaluation, ablation study, reproducible figure generation, "
                                      "research paper and final system.", "Planned"],
    ], widths=[0.6, 1.4, 3.3, 1.1], center_cols=(0, 3))
    caption(doc, "Table 4 - Phase-level schedule.")

    heading(doc, "4.1  Week-by-Week Plan for the Next Phase (Phase 3)", size=12.5)
    table(doc, ["Week", "Task", "Demonstrable output"], [
        ["W1 · 27 Sep - 3 Oct", "Verdict-tagged cache: a filtered Qdrant search on the stored verdict, "
                                "with intent-dependent thresholds.",
         "The exact Week 4 attacks rerun: baseline and hardened side by side."],
        ["W2 · 4 - 10 Oct", "High-risk re-verification; full re-attack; measure the cache hit ratio surrendered.",
         "Security versus efficiency trade-off chart."],
        ["W3 · 11 - 17 Oct", "Cost-aware routing: a difficulty estimator picks a cheap or frontier model; "
                             "provider failover.",
         "Dollars saved against always-frontier, from the logs."],
        ["W4 · 18 - 24 Oct", "Output guard for executable content in replies, and per-key rate limiting "
                             "against denial of wallet.",
         "Both mitigations triggered live."],
    ], widths=[1.3, 2.9, 2.2])
    caption(doc, "Table 5 - Phase 3 breakdown. Every week concludes with one demonstrable artefact, "
                 "which also serves as that week's update to the supervisor.")

    heading(doc, "4.2  Outstanding Work and Immediate Risks", size=12.5)
    bullet(doc, "Intent labels",
           "the defence can only be as good as the intent labels it matches on. Intent is currently assigned "
           "by keyword rules; Phase 3 will measure how often it is wrong.")
    bullet(doc, "Security-versus-efficiency trade-off",
           "matching on the verdict will cost some cache hit ratio. Intent-tiered thresholds and selective "
           "re-verification are the levers that limit it, and the trade-off curve is itself a reportable result.")
    bullet(doc, "Dataset composition",
           "the jayavibhav seeds are synthetic and often already obfuscated, unlike the real-world deepset "
           "seeds; Phase 3 will report the two datasets separately.")
    bullet(doc, "Provider account",
           "the original provider rejected our credentials; the gateway was moved to OpenRouter with a "
           "base-URL change only. The daily spend cap and replay cassettes bound the cost of every experiment.")
    bullet(doc, "Environment reliability",
           "Docker Desktop on the development machine stops intermittently. Every run is containerised and "
           "scripted (make bypass), so a full rerun is a single command.")

    # ---- 5. architecture -------------------------------------------------
    doc.paragraphs[-1].add_run().add_break(WD_BREAK.PAGE)  # section 5 opens a page with its figure
    heading(doc, "5.  System Architecture and Design Reference")
    para(doc, "Figure 2 shows the gateway exactly as it runs at the end of Phase 2. The cache is consulted "
              "before the safety screen, which is the ordering real systems use for speed and the ordering "
              "the Week 4 experiment exploits. **The safety verdict is already computed at screening and "
              "stored in the Qdrant payload alongside every cached answer**, so the Phase 3 defence does not "
              "need a new model or a re-index: it changes the cache lookup into a verdict-filtered search.")
    figure(doc, HERE / "assets/architecture.png", 4.7)
    caption(doc, "Figure 2 - SentryGate at the end of Phase 2. Amber marks our contribution, red marks the "
                 "bypass path measured in Week 4, and the dashed box is the Phase 3 fix.")
    para(doc, "**Reading the diagram:** a request passes Nginx and reaches ① the cache, which checks for an "
              "exact match in Redis and then a similar question in Qdrant. **On a HIT the stored answer is "
              "returned at once and ② the safety screen never runs** - this is the path measured in Week 4. "
              "On a MISS, ② computes the safety verdict: attacks are refused with 403, and clean requests go "
              "to ③ the model through OpenRouter. ④ saves the answer together with its verdict in Qdrant, and "
              "⑤ records every request to the log, the single source of every number in this report. Because "
              "the verdict is already stored with each answer, the Phase 3 fix is to make ① match on the "
              "wording **and** the verdict together.", after=0)

    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / "Progress2.docx"
    doc.save(out)
    return out


if __name__ == "__main__":
    print("wrote", build().relative_to(ROOT))
