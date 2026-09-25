/*
 * Build reports/out/SentryGate_Progress_Report_2.pptx.
 *
 * Same design as the team's Progress Report 1 deck: warm cream slides, navy
 * text, a gold accent, brick red for bad numbers and green for good ones,
 * Roboto, white rounded cards, "// 01 — SECTION" labels and status pills.
 * Same structure too, filled with Phase 2, plus one slide on latency.
 *
 * Numbers are read from the committed results:
 *   data/week4/report.json, data/week4/latency.md
 *
 * Run:  make report-pptx
 */

const fs = require("fs");
const path = require("path");
const pptxgen = require("pptxgenjs");

const ROOT = path.join(__dirname, "..");
const R = JSON.parse(fs.readFileSync(path.join(ROOT, "data/week4/report.json"), "utf8"));

// ---- design tokens, sampled from Progress Report 1 -------------------------
const CREAM = "F9F8F4", NAVY = "1B2433", GOLD = "C9A05A";
const RED = "B5452F", GREEN = "3F7A52", BLUE = "2D5A87", SLATE = "4A4F5A";
const TEXT = "1B2433", MUTED = "4A5260", FAINT = "6B7280";
const LINE = "E3DED2", ALT = "F3F1EA", WHITE = "FFFFFF", PILL = "F1EEE6";
const FONT = "Roboto";
const W = 13.333, H = 7.5, MX = 0.7;
const TOTAL = 11;

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";
pres.defineSlideMaster({ title: "CREAM", background: { color: CREAM } });
pres.defineSlideMaster({ title: "NAVY", background: { color: NAVY } });

let pageNo = 0;
function slide(notes, master = "CREAM") {
  const s = pres.addSlide({ masterName: master });
  pageNo += 1;
  if (notes) s.addNotes(notes);
  if (master === "CREAM" && pageNo > 1) {
    s.addText("SentryGate · Progress Report 2", { x: MX, y: 7.0, w: 5, h: 0.3, isTextBox: true, margin: 0,
      fontFace: FONT, fontSize: 9.5, color: MUTED });
    s.addText(String(pageNo).padStart(2, "0"), { x: W - 1.4, y: 7.0, w: 0.9, h: 0.3, isTextBox: true, margin: 0,
      fontFace: FONT, fontSize: 10, color: MUTED, align: "right" });
  }
  return s;
}
function label(s, text, y = 0.47) {
  s.addText(text.toUpperCase(), { x: MX, y, w: 10, h: 0.3, isTextBox: true, margin: 0,
    fontFace: FONT, fontSize: 12, color: GOLD });
}
function title(s, text, y = 0.85) {
  s.addText(text, { x: MX, y, w: W - 2 * MX, h: 0.75, isTextBox: true, margin: 0,
    fontFace: FONT, fontSize: 31, color: NAVY, valign: "middle" });
}
function sub(s, text, y = 1.7, italic = true, h = 0.5) {
  s.addText(text, { x: MX, y, w: W - 2 * MX, h, isTextBox: true, margin: 0,
    fontFace: FONT, fontSize: 13.5, italic, color: MUTED, lineSpacingMultiple: 1.15, valign: "top" });
}
function card(s, x, y, w, h, fill = WHITE, line = LINE) {
  s.addShape(pres.ShapeType.roundRect, { x, y, w, h, rectRadius: 0.07,
    fill: { color: fill }, line: { color: line, width: 1 } });
}
function pill(s, x, y, w, h, text, fill, color = WHITE) {
  s.addShape(pres.ShapeType.roundRect, { x, y, w, h, rectRadius: h / 2, fill: { color: fill }, line: { color: fill, width: 0 } });
  s.addText(text, { x, y, w, h, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 11,
    color, align: "center", valign: "middle" });
}

const byT = (k) => R.by_threshold[k];
const T085 = byT("0.85");
function latency() {
  const out = [];
  for (const line of fs.readFileSync(path.join(ROOT, "data/week4/latency.md"), "utf8").split("\n")) {
    if (!line.trim().startsWith("|")) continue;
    const c = line.replace(/^\||\|$/g, "").split("|").map((x) => x.trim());
    if (c.length !== 4 || c[0] === "Outcome" || /^-+$/.test(c[1])) continue;
    out.push({ outcome: c[0], n: Number(c[1]), p50: Number(c[2]), p99: Number(c[3]) });
  }
  return out;
}
const LAT = latency();
const HIT = LAT.find((r) => r.outcome.startsWith("Cache hit"));
const MISS = LAT.find((r) => r.outcome.startsWith("Miss"));
const NREQ = LAT.reduce((a, r) => a + r.n, 0);

// ---- 01 cover ---------------------------------------------------------------
(() => {
  const s = slide("Name the checkpoint. Phase 1 proved the problem in a script; Phase 2 built the gateway and proved it on our own running system.");
  s.addText("PROJECT PROGRESS REPORT · DEPARTMENT OF INFORMATION TECHNOLOGY", { x: MX, y: 0.62, w: 11, h: 0.3,
    isTextBox: true, margin: 0, fontFace: FONT, fontSize: 12.5, color: GOLD });
  s.addText("SentryGate", { x: MX, y: 2.35, w: 9, h: 1.05, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 62, color: NAVY });
  s.addText("A Security-Aware Semantic Caching Gateway for Large Language Model Applications", { x: MX, y: 3.45, w: 11.5, h: 0.5,
    isTextBox: true, margin: 0, fontFace: FONT, fontSize: 20, italic: true, color: MUTED });
  s.addShape(pres.ShapeType.line, { x: MX - 0.08, y: 4.15, w: 3.0, h: 0, line: { color: GOLD, width: 1 } });
  s.addText("PROGRESS REPORT — 2", { x: MX, y: 4.38, w: 6, h: 0.35, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 15, color: NAVY });
  const meta = [["TEAM", "Divyansh Sharma · Sarvagya Dabas · Yashvit Gauri"],
                ["PROGRAMME", "B.Tech Information Technology, Batch 2023–27"],
                ["SUPERVISOR", "Dr. Sandeep Singh"]];
  meta.forEach(([k, v], i) => {
    const y = 4.88 + i * 0.66;
    s.addText(k, { x: MX, y, w: 5, h: 0.24, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 11, color: GOLD });
    s.addText(v, { x: MX, y: y + 0.25, w: 8, h: 0.32, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 15, color: NAVY });
  });
  s.addText("Maharaja Surajmal Institute of Technology, New Delhi", { x: MX, y: 6.98, w: 8, h: 0.28, isTextBox: true, margin: 0,
    fontFace: FONT, fontSize: 11, color: MUTED });
})();

// ---- 02 status summary -------------------------------------------------------
(() => {
  const s = slide("Lead with the result. The bypass Phase 1 showed in a script is real on our own gateway, at scale, with real models. Then the proof of cause: filter first gives zero.");
  label(s, "// 01 — Status Summary");
  title(s, "Phase 2 is complete, on schedule");
  s.addText("The objective was to build the gateway and reproduce, on our own running system, the vulnerability that Phase 1 showed in a controlled script.",
    { x: MX, y: 1.8, w: 7.3, h: 1.0, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 15.5, italic: true, color: MUTED, lineSpacingMultiple: 1.25, valign: "top" });
  s.addText([
    { text: "On the live gateway, with the real classifier, the real embedding model and real Qdrant and Redis, ", options: { color: TEXT } },
    { text: "a semantic cache in front of the filter still serves poisoned answers to reworded attacks", options: { color: TEXT, bold: true } },
    { text: ", and the filter never runs.", options: { color: TEXT } },
  ], { x: MX, y: 3.05, w: 7.3, h: 1.4, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 16.5, lineSpacingMultiple: 1.35, valign: "top" });

  const cx = 8.35, cw = 4.35;
  card(s, cx, 1.6, cw, 4.6);
  s.addText("THE HEADLINE RESULT", { x: cx + 0.4, y: 1.92, w: 3.5, h: 0.26, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 11, color: GOLD });
  s.addText(`${T085.lazy.toFixed(1)}%`, { x: cx + 0.4, y: 2.2, w: 3.6, h: 0.8, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 46, color: RED });
  s.addText("of cheap rewordings served the poisoned answer at threshold 0.85, with the filter invoked zero times",
    { x: cx + 0.4, y: 3.0, w: 3.6, h: 0.6, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 11.5, color: MUTED, lineSpacingMultiple: 1.1, valign: "top" });
  s.addShape(pres.ShapeType.line, { x: cx + 0.3, y: 3.75, w: cw - 0.6, h: 0, line: { color: LINE, width: 1 } });
  s.addText(`${R.screen_first_bypass_at_085.toFixed(0)}%`, { x: cx + 0.4, y: 3.9, w: 3.6, h: 0.8, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 46, color: GREEN });
  s.addText("bypass once the filter sits in front of the cache: same build, same attacks",
    { x: cx + 0.4, y: 4.7, w: 3.6, h: 0.5, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 11.5, color: MUTED, lineSpacingMultiple: 1.1, valign: "top" });
  s.addShape(pres.ShapeType.line, { x: cx + 0.3, y: 5.3, w: cw - 0.6, h: 0, line: { color: LINE, width: 1 } });
  s.addText([
    { text: "The ordering is the cause. ", options: { color: TEXT } },
    { text: "That is what Phase 3 changes.", options: { color: RED, italic: true } },
  ], { x: cx + 0.4, y: 5.42, w: 3.7, h: 0.55, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 13, valign: "top" });
})();

// ---- 03 work completed --------------------------------------------------------
(() => {
  const s = slide("Six workstreams, one per card. The key one is 04: the bypass measured on the live gateway.");
  label(s, "// 02 — Work Completed");
  title(s, "Six workstreams closed in Phase 2");
  const items = [
    ["Gateway on Docker", "FastAPI with an OpenAI-compatible endpoint behind Nginx; mock, replay and live providers with a daily spend cap."],
    ["Screening layer", "deberta injection score and Presidio personal-data scan folded into one safety verdict; attacks refused with 403."],
    ["Baseline semantic cache", "Exact match in Redis, similarity in Qdrant. The verdict is stored with every answer but left unused: the vulnerable baseline."],
    ["Bypass on the live gateway", `${R.seeds} public attacks, ${R.attack_variants_per_threshold.toLocaleString()} rewordings, seven thresholds; every bypass confirmed from the log.`],
    ["Measurement and logging", `One JSONL line per request, a /metrics/summary endpoint, and latency from ${NREQ.toLocaleString()} logged requests.`],
    ["Live model and documentation", "A real call through OpenRouter, replayable for free; the paper draft, decks, and 54 automated tests."],
  ];
  const gx = 0.2, x0 = 0.6, cw = (12.1 - 2 * gx) / 3, ch = 2.3, gy = 0.25, y0 = 1.85;  // three columns inside the 12.1in content width
  items.forEach(([h, b], i) => {
    const x = x0 + (i % 3) * (cw + gx), y = y0 + Math.floor(i / 3) * (ch + gy);
    card(s, x, y, cw, ch);
    s.addText(String(i + 1).padStart(2, "0"), { x: x + 0.35, y: y + 0.25, w: 1, h: 0.45, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 24, color: GOLD });
    s.addText(h, { x: x + 0.35, y: y + 0.82, w: cw - 0.6, h: 0.35, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 15, color: NAVY });
    s.addText(b, { x: x + 0.35, y: y + 1.28, w: cw - 0.6, h: 0.9, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 11.5, color: MUTED, lineSpacingMultiple: 1.12, valign: "top" });
  });
})();

// ---- 04 measured result --------------------------------------------------------
(() => {
  const s = slide("Read each row. The filter never ran on a single confirmed bypass, and moving it first drops the bypass to zero.");
  label(s, "// 03 — Measured Result");
  title(s, "The bypass is real on our own system.");
  sub(s, `Phase 2 result on the running gateway at cache similarity threshold 0.85, from ${R.seeds} public attacks and ${R.attack_variants_per_threshold.toLocaleString()} rewordings.`);
  const rows = [
    ["Cheap rewordings served the poisoned answer", `${T085.lazy.toFixed(1)}%`, RED, "Near-total bypass at a normal production setting."],
    ["Filter invocations on those bypasses", "0", RED, "Read from the gateway's own log, for every case."],
    ["Same attacks, filter placed before the cache", `${R.screen_first_bypass_at_085.toFixed(0)}%`, GREEN, "The ordering is the cause: nothing else changed."],
    ["Honest questions served the poison", R.control_served_poison.replace("/", " / "), GREEN, "Legitimate users are not affected."],
  ];
  rows.forEach(([k, v, col, why], i) => {
    const y = 2.3 + i * 1.07;
    card(s, 0.6, y, 12.1, 0.9, i % 2 ? ALT : WHITE);
    s.addText(k, { x: 0.9, y, w: 4.9, h: 0.9, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 15, color: TEXT, valign: "middle" });
    s.addText(v, { x: 5.8, y, w: 1.8, h: 0.9, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 27, color: col, valign: "middle" });
    s.addText(why, { x: 7.8, y, w: 4.7, h: 0.9, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 12.5, italic: true, color: MUTED, valign: "middle" });
  });
})();

// ---- 05 threshold sweep ---------------------------------------------------------
(() => {
  const s = slide("The Phase 1 shape, now at scale. Cheap edits leak at every setting; paraphrases only once the cache is loose.");
  label(s, "// 04 — Threshold Sweep");
  title(s, "No threshold is secure and useful, now confirmed at scale");
  sub(s, `The cheapest attacks (a capital letter, a full stop, a filler word) get through at every threshold: ${byT("0.95").lazy.toFixed(0)}% even at the strictest. Full rewrites succeed only as the cache is loosened.`, 1.65, false, 0.6);
  const THR = ["0.95", "0.9", "0.85", "0.8", "0.75", "0.7", "0.65"];
  const labels = THR.map((k) => Number(k).toFixed(2));
  s.addChart(pres.ChartType.bar, [
    { name: "Cheap rewordings", labels, values: THR.map((k) => Math.round(byT(k).lazy)) },
    { name: "Full rewrites", labels, values: THR.map((k) => Math.round(byT(k).rewrite)) },
  ], {
    x: 0.6, y: 2.45, w: 7.4, h: 4.3, barDir: "col", barGrouping: "clustered", barGapWidthPct: 60,
    chartColors: [RED, GREEN], showTitle: true, title: "Bypass rate by attack type (%)", titleColor: TEXT, titleFontFace: FONT, titleFontSize: 13,
    showLegend: true, legendPos: "b", legendFontFace: FONT, legendFontSize: 11, legendColor: MUTED,
    showValue: true, dataLabelPosition: "outEnd", dataLabelFontFace: FONT, dataLabelFontSize: 9, dataLabelColor: MUTED,
    valAxisMinVal: 0, valAxisMaxVal: 110, valAxisMajorUnit: 20, valAxisLabelFontFace: FONT, valAxisLabelFontSize: 10, valAxisLabelColor: MUTED,
    catAxisLabelFontFace: FONT, catAxisLabelFontSize: 10, catAxisLabelColor: MUTED, catAxisLineColor: LINE,
    valGridLine: { color: LINE, size: 0.75 }, catGridLine: { style: "none" }, valAxisLineShow: false,
    valAxisTitle: "% bypass", showValAxisTitle: true, valAxisTitleFontFace: FONT, valAxisTitleFontSize: 10, valAxisTitleColor: MUTED,
    plotArea: { fill: { color: CREAM } },
  });
  const cx = 8.35, cw = 4.35;
  card(s, cx, 2.45, cw, 4.25);
  s.addText("READING THIS CHART", { x: cx + 0.4, y: 2.75, w: 3.5, h: 0.26, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 11, color: GOLD });
  s.addText([
    { text: "Strictest setting (0.95) → ", options: { color: TEXT } },
    { text: `still ${byT("0.95").lazy.toFixed(0)}% of cheap edits get through.`, options: { color: RED, bold: true, breakLine: true } },
    { text: " ", options: { breakLine: true } },
    { text: "Typical production (0.75–0.80) → ", options: { color: TEXT } },
    { text: `${byT("0.8").lazy.toFixed(0)}–${byT("0.75").lazy.toFixed(0)}% of cheap edits, ${byT("0.8").overall.toFixed(0)}–${byT("0.75").overall.toFixed(0)}% overall.`, options: { color: RED, bold: true, breakLine: true } },
    { text: " ", options: { breakLine: true } },
    { text: "So the remedy must change ", options: { color: TEXT } },
    { text: "how the cache decides a match", options: { color: TEXT, bold: true } },
    { text: ", not what it is tuned to.", options: { color: TEXT } },
  ], { x: cx + 0.4, y: 3.2, w: cw - 0.75, h: 3.2, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 14, lineSpacingMultiple: 1.3, valign: "top" });
})();

// ---- 06 latency -----------------------------------------------------------------
(() => {
  const s = slide("Answer the obvious objection: why not just screen every request? Because a hit is about seven times faster. That gap is why caches go first, and why the fix must live inside the cache.");
  label(s, "// 05 — Why the Cache Goes First");
  title(s, `A cache hit is ${Math.round(MISS.p50 / HIT.p50)}× faster than a miss`);
  sub(s, `Measured from ${NREQ.toLocaleString()} requests in the gateway's own log. A miss pays for the safety screen; a hit skips it.`);
  const cats = LAT.map((r) => r.outcome.replace(" (screen + model)", "").replace("Blocked attack", "Blocked"));
  s.addChart(pres.ChartType.bar, [
    { name: "p50 (typical)", labels: cats, values: LAT.map((r) => Math.round(r.p50)) },
    { name: "p99 (worst case)", labels: cats, values: LAT.map((r) => Math.round(r.p99)) },
  ], {
    x: 0.6, y: 2.4, w: 7.4, h: 4.35, barDir: "col", barGrouping: "clustered", barGapWidthPct: 70,
    chartColors: [NAVY, GOLD], showTitle: true, title: "Response time by outcome (ms)", titleColor: TEXT, titleFontFace: FONT, titleFontSize: 13,
    showLegend: true, legendPos: "b", legendFontFace: FONT, legendFontSize: 11, legendColor: MUTED,
    showValue: true, dataLabelPosition: "outEnd", dataLabelFontFace: FONT, dataLabelFontSize: 10, dataLabelColor: MUTED,
    valAxisLabelFontFace: FONT, valAxisLabelFontSize: 10, valAxisLabelColor: MUTED,
    catAxisLabelFontFace: FONT, catAxisLabelFontSize: 11, catAxisLabelColor: TEXT, catAxisLineColor: LINE,
    valGridLine: { color: LINE, size: 0.75 }, catGridLine: { style: "none" }, valAxisLineShow: false,
    plotArea: { fill: { color: CREAM } },
  });
  const cx = 8.35, cw = 4.35;
  card(s, cx, 2.4, cw, 4.3);
  s.addText("WHAT THIS MEANS", { x: cx + 0.4, y: 2.7, w: 3.5, h: 0.26, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 11, color: GOLD });
  s.addText(`${Math.round(HIT.p50)} ms`, { x: cx + 0.4, y: 3.0, w: 1.9, h: 0.65, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 32, color: NAVY });
  s.addText("cache hit", { x: cx + 0.4, y: 3.62, w: 1.9, h: 0.3, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 11.5, color: MUTED });
  s.addText(`${Math.round(MISS.p50)} ms`, { x: cx + 2.2, y: 3.0, w: 1.9, h: 0.65, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 32, color: RED });
  s.addText("miss, pays the screen", { x: cx + 2.2, y: 3.62, w: 1.9, h: 0.3, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 11.5, color: MUTED });
  s.addShape(pres.ShapeType.line, { x: cx + 0.3, y: 4.15, w: cw - 0.6, h: 0, line: { color: LINE, width: 1 } });
  s.addText([
    { text: "This gap is why production systems check the cache first, ", options: { color: TEXT } },
    { text: "and so why the bypass exists.", options: { color: TEXT, bold: true, breakLine: true } },
    { text: " ", options: { breakLine: true } },
    { text: "Screening every request would throw the speed-up away. ", options: { color: MUTED } },
    { text: "The fix has to make the cache itself safety-aware.", options: { color: RED, italic: true } },
  ], { x: cx + 0.4, y: 4.3, w: cw - 0.75, h: 2.25, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 13.5, lineSpacingMultiple: 1.25, valign: "top" });
})();

// ---- 07 architecture (native, simple) ----------------------------------------
(() => {
  const s = slide("Walk the two paths. A match is answered straight away and the screen is skipped - the hole. A miss is screened, answered, and saved with its verdict. Phase 3 makes the cache match on the verdict too.");
  label(s, "// 06 — System Architecture");
  title(s, "What runs today, and where the hole is");
  sub(s, "The safety verdict is already computed at screening and stored in Qdrant alongside every cached answer. Phase 3 turns the cache lookup into a verdict-filtered search, with no new model and no re-index.", 1.65, false, 0.65);

  const box = (x, y, w, h, head, body, fill = WHITE, line = LINE, headColor = NAVY) => {
    card(s, x, y, w, h, fill, line);
    s.addText([{ text: head, options: { color: headColor, bold: true, fontSize: 13.5, breakLine: !!body } },
               ...(body ? [{ text: body, options: { color: MUTED, fontSize: 10.5 } }] : [])],
      { x: x + 0.12, y, w: w - 0.24, h, isTextBox: true, margin: 0, fontFace: FONT, align: "center", valign: "middle", lineSpacingMultiple: 1.1 });
  };
  const arrow = (x, y, w, h, color = MUTED, dash = "solid") =>
    s.addShape(pres.ShapeType.line, { x, y, w, h, line: { color, width: 1.75, dashType: dash, endArrowType: "triangle" } });
  const tag = (x, y, text, color) => s.addText(text, { x, y, w: 1.3, h: 0.26, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 10.5, color, align: "center" });

  const spine = 4.55, bh = 0.95;
  box(0.6, spine - bh / 2, 1.85, bh, "A question", "via Nginx");
  arrow(2.45, spine, 0.45, 0);
  box(2.9, spine - bh / 2, 2.35, bh, "① Cache lookup", "checked first · Redis + Qdrant", "FBF3E4", GOLD);
  const cr = 5.25, lx = 6.35, topY = 3.1, botY = 5.25;
  arrow(cr, spine, lx - cr, topY + bh / 2 - spine, RED);
  tag(cr + 0.05, 3.55, "match", RED);
  box(lx, topY, 2.5, bh, "Answer served", "straight from the cache", "FBEDEA", RED, RED);
  s.addText([{ text: "② Safety screen is skipped.", options: { bold: true, breakLine: true } }, { text: "This is the hole measured in Week 4." }],
    { x: lx + 2.65, y: topY, w: 3.4, h: bh, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 12, color: RED, valign: "middle", lineSpacingMultiple: 1.15 });
  arrow(cr, spine, lx - cr, botY + bh / 2 - spine);
  tag(cr + 0.3, 4.72, "no match", MUTED);  // right of the line, clear of it
  box(lx, botY, 2.0, bh, "② Safety screen", "deberta + Presidio");
  arrow(lx + 2.0, botY + bh / 2, 0.35, 0);
  box(lx + 2.35, botY, 1.75, bh, "③ Model", "via OpenRouter");
  arrow(lx + 4.1, botY + bh / 2, 0.35, 0);
  box(lx + 4.45, botY, 1.9, bh, "④ Store", "answer + verdict", "FBF3E4", GOLD);
  s.addText("Figure 1 — Gold marks our contribution; red marks the bypass path; the verdict saved at ④ is what Phase 3 will match on.",
    { x: MX, y: 6.5, w: W - 2 * MX, h: 0.3, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 10.5, italic: true, color: MUTED, align: "center" });
})();

// ---- 08 timeline ------------------------------------------------------------------
(() => {
  const s = slide("Phase 2 is complete. Phase 3 starts tomorrow: build the defence and show it beats this baseline.");
  label(s, "// 07 — Timeline");
  title(s, "Project roadmap: August – November 2026");
  const phases = [
    ["18–22 AUG", "Phase 1 — Establish the Problem", "Offline proof-of-concept, threshold sweep, architecture definition, synopsis.", "COMPLETE", GREEN, WHITE, GREEN],
    ["23 AUG–26 SEP", "Phase 2 — Build the Gateway", "Reproduced the bypass on our own running system; first real bypass-rate figure.", "COMPLETE", GREEN, WHITE, GREEN],
    ["27 SEP–24 OCT", "Phase 3 — Build the Defence", "Verdict-tagged cache, re-verification, routing, output guard, rate limiting.", "NEXT", GOLD, WHITE, GOLD],
    ["25 OCT–14 NOV", "Phase 4 — Evaluate & Publish", "Full evaluation, ablation study, figure generation, research paper, final system.", "PLANNED", PILL, SLATE, SLATE],
  ];
  s.addShape(pres.ShapeType.line, { x: 1.55, y: 2.2, w: 0, h: 4.5, line: { color: LINE, width: 1.5 } });
  phases.forEach(([when, h, b, st, pf, pc, dot], i) => {
    const y = 1.95 + i * 1.18;
    s.addText(when, { x: 0.25, y: y + 0.08, w: 1.1, h: 0.45, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 10.5, color: MUTED, align: "right", valign: "top" });
    s.addShape(pres.ShapeType.ellipse, { x: 1.44, y: y + 0.12, w: 0.22, h: 0.22, fill: { color: dot }, line: { color: WHITE, width: 1.5 } });
    card(s, 1.95, y, 10.75, 0.95);
    s.addText(h, { x: 2.3, y: y + 0.12, w: 7, h: 0.35, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 16, color: NAVY });
    s.addText(b, { x: 2.3, y: y + 0.52, w: 7.3, h: 0.3, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 11.5, color: MUTED });
    pill(s, 9.7, y + 0.2, 2.85, 0.42, st, pf, pc);
  });
})();

// ---- 09 next phase plan -------------------------------------------------------------
(() => {
  const s = slide("Four weeks, one artefact each. Week 1 is the key result: the same attacks, with the defence on.");
  label(s, "// 08 — Next Phase Plan");
  title(s, "Week-by-week plan: Phase 3 (27 Sep – 24 Oct)");
  sub(s, "Every week concludes with one demonstrable artefact, which also serves as that week's update to the supervisor.");
  const weeks = [
    ["W1", "27 Sep–3 Oct", "Verdict-tagged cache", "Filtered Qdrant search on the stored verdict, with intent-dependent thresholds.", "The Week 4 attacks rerun: baseline and hardened, side by side.", true],
    ["W2", "4–10 Oct", "Re-verification & re-attack", "Re-check high-risk hits before serving; full re-attack; measure the hit ratio given up.", "The security-versus-efficiency trade-off chart.", false],
    ["W3", "11–17 Oct", "Cost-aware routing", "A difficulty estimator picks a cheap or frontier model; provider failover.", "Dollars saved against always-frontier, from the logs.", false],
    ["W4", "18–24 Oct", "Output guard & rate limit", "Scan replies for executable content; per-key token budgets against denial of wallet.", "Both mitigations triggered live.", false],
  ];
  const cw = 2.95, gx = 0.13, x0 = 0.6, y0 = 2.35, ch = 4.4;
  weeks.forEach(([wk, d, h, b, out, key], i) => {
    const x = x0 + i * (cw + gx);
    card(s, x, y0, cw, ch);
    s.addShape(pres.ShapeType.roundRect, { x, y: y0, w: cw, h: 0.62, rectRadius: 0.07, fill: { color: key ? GOLD : NAVY }, line: { color: key ? GOLD : NAVY, width: 0 } });
    s.addShape(pres.ShapeType.rect, { x, y: y0 + 0.4, w: cw, h: 0.22, fill: { color: key ? GOLD : NAVY }, line: { color: key ? GOLD : NAVY, width: 0 } });
    s.addText(wk, { x: x + 0.3, y: y0, w: 1.5, h: 0.62, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 17, color: WHITE, valign: "middle" });
    s.addText(d, { x, y: y0 + 0.78, w: cw, h: 0.26, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 11, color: GOLD, align: "center" });
    s.addText(h, { x: x + 0.28, y: y0 + 1.15, w: cw - 0.5, h: 0.62, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 15, color: NAVY, valign: "top" });
    s.addText(b, { x: x + 0.28, y: y0 + 1.85, w: cw - 0.5, h: 1.2, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 11, color: MUTED, lineSpacingMultiple: 1.15, valign: "top" });
    s.addShape(pres.ShapeType.line, { x: x + 0.2, y: y0 + 3.2, w: cw - 0.4, h: 0, line: { color: LINE, width: 1 } });
    s.addText("OUTPUT", { x: x + 0.28, y: y0 + 3.33, w: 2, h: 0.24, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 10, color: GOLD });
    s.addText(out, { x: x + 0.28, y: y0 + 3.6, w: cw - 0.5, h: 0.7, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 11, italic: true, color: TEXT, lineSpacingMultiple: 1.1, valign: "top" });
  });
})();

// ---- 10 risks ---------------------------------------------------------------------
(() => {
  const s = slide("Be plain about what is open. The provider problem is solved; the rest have a plan and a way to bound them.");
  label(s, "// 09 — Outstanding Work & Risks");
  title(s, "What's still open, and how it's bounded");
  const risks = [
    ["RESOLVED", GREEN, "Provider account", "The original provider rejected our key. Moved to OpenRouter with a base-URL change; the real call is recorded and replays for free."],
    ["PLANNED", GOLD, "Security-vs-efficiency trade-off", "Matching on the verdict gives up some cache hits. Intent-tiered thresholds and selective re-checks limit it; the curve is itself a result."],
    ["TRACKED", SLATE, "Intent label quality", "The defence is only as good as the intent labels it matches on. Intent is rule-based today; Phase 3 measures how often it is wrong."],
    ["MITIGATED", BLUE, "Environment reliability", "Docker Desktop on the dev machine stops at times. Every run is containerised and scripted, so a full rerun is one command."],
  ];
  risks.forEach(([st, col, h, b], i) => {
    const y = 1.85 + i * 1.25;
    card(s, 0.6, y, 12.1, 1.1);
    pill(s, 0.85, y + 0.18, 1.85, 0.42, st, col);
    s.addText(h, { x: 3.0, y, w: 3.3, h: 1.1, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 15, color: NAVY, valign: "middle" });
    s.addText(b, { x: 6.4, y, w: 6.05, h: 1.1, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 12, color: MUTED, lineSpacingMultiple: 1.15, valign: "middle" });
  });
})();

// ---- 11 thank you -------------------------------------------------------------------
(() => {
  const s = slide("Close on the result and take questions.", "NAVY");
  s.addText("Thank You", { x: MX, y: 2.6, w: 8, h: 0.95, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 52, color: WHITE });
  s.addText("Questions and discussion", { x: MX, y: 3.55, w: 8, h: 0.45, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 19, italic: true, color: "D5DAE3" });
  s.addShape(pres.ShapeType.line, { x: MX - 0.08, y: 4.15, w: 3.0, h: 0, line: { color: GOLD, width: 1 } });
  s.addText("SentryGate — Security-Aware Semantic Caching Gateway for LLM Applications", { x: MX, y: 4.42, w: 10, h: 0.32, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 14, color: "A5ADBB" });
  s.addText("Divyansh Sharma · Sarvagya Dabas · Yashvit Gauri", { x: MX, y: 4.82, w: 10, h: 0.32, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 14, color: "A5ADBB" });
  s.addText("NEXT REVIEW — 24 OCTOBER 2026", { x: MX, y: 6.85, w: 6, h: 0.3, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 12, color: GOLD });
})();

if (pageNo !== TOTAL) throw new Error(`expected ${TOTAL} slides, built ${pageNo}`);
const out = path.join(ROOT, "reports/out/SentryGate_Progress_Report_2.pptx");
fs.mkdirSync(path.dirname(out), { recursive: true });
pres.writeFile({ fileName: out }).then(() => console.log(`wrote reports/out/SentryGate_Progress_Report_2.pptx (${pageNo} slides)`));
