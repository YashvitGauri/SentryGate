/*
 * Build docs/deck-phase2.pptx — the second-presentation deck.
 *
 * A light, minimalist, Apple-styled PowerPoint. White slides, generous space,
 * one idea per slide, restrained colour, native (editable) tables and charts,
 * and a simple hand-drawn diagram instead of a busy one.
 *
 * Numbers are read from the committed results so they match the paper:
 *   data/week4/report.json   the bypass sweep and its checks
 *   data/week4/latency.md    the response-time table
 *
 * Run:  make deck-phase2-pptx
 */

const fs = require("fs");
const path = require("path");
const pptxgen = require("pptxgenjs");

const ROOT = path.join(__dirname, "..");
const report = JSON.parse(fs.readFileSync(path.join(ROOT, "data/week4/report.json"), "utf8"));

// ---- Apple-ish light palette ----------------------------------------------
const INK = "1D1D1F";      // near-black text
const SUB = "6E6E73";      // secondary text
const FAINT = "86868B";    // tertiary
const HAIR = "D2D2D7";     // hairlines
const SURFACE = "F5F5F7";  // light card
const BG = "FFFFFF";
const BLUE = "0071E3";     // primary accent
const BLUELT = "CFE4FB";   // light blue (p99, highlight)
const HILITE = "EAF3FF";   // row highlight
const ORANGE = "FF9500";   // the persistent lazy-edit line
const GREEN = "34C759";    // checks / safe
const RED = "FF3B30";      // attack / the hole

const FONT = "Helvetica Neue";
const MONO = "Menlo";
const W = 13.3, H = 7.5, MX = 0.9;

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";
pres.defineSlideMaster({ title: "LIGHT", background: { color: BG } });

function slide(notes) {
  const s = pres.addSlide({ masterName: "LIGHT" });
  if (notes) s.addNotes(notes);
  s.addText("SentryGate", { x: MX, y: H - 0.45, w: 4, h: 0.3, isTextBox: true, margin: 0,
    fontFace: FONT, fontSize: 9, color: FAINT });
  return s;
}
function eyebrow(s, text) {
  s.addText(text.toUpperCase(), { x: MX, y: 0.62, w: 11, h: 0.35, isTextBox: true, margin: 0,
    fontFace: FONT, fontSize: 12, bold: true, color: BLUE, charSpacing: 1.5 });
}
function title(s, runs, y = 1.02) {
  s.addText(runs, { x: MX, y, w: W - 2 * MX, h: 1.1, isTextBox: true, margin: 0,
    fontFace: FONT, fontSize: 32, bold: true, color: INK, lineSpacingMultiple: 1.03 });
}
function explain(s, text, y = H - 1.15, color = SUB) {
  s.addText(text, { x: MX, y, w: W - 2 * MX, h: 0.7, isTextBox: true, margin: 0,
    fontFace: FONT, fontSize: 13, color, lineSpacingMultiple: 1.2 });
}

// ---- data helpers ---------------------------------------------------------
const THR = ["0.95", "0.9", "0.85", "0.8", "0.75", "0.7", "0.65"];
const byT = (k) => report.by_threshold[k];
const headline = Math.round(byT("0.85").lazy);
function readLatency() {
  const md = fs.readFileSync(path.join(ROOT, "data/week4/latency.md"), "utf8");
  const rows = [];
  for (const line of md.split("\n")) {
    if (!line.trim().startsWith("|")) continue;
    const c = line.replace(/^\||\|$/g, "").split("|").map((x) => x.trim());
    if (c.length !== 4 || c[0] === "Outcome" || /^-+$/.test(c[1])) continue;
    rows.push({ outcome: c[0], reqs: Number(c[1]), p50: Number(c[2]), p99: Number(c[3]) });
  }
  return rows;
}
const LAT = readLatency();

// small rounded box for the diagram
function box(s, x, y, w, h, opts = {}) {
  s.addShape(pres.ShapeType.roundRect, { x, y, w, h, rectRadius: 0.09,
    fill: { color: opts.fill || SURFACE }, line: { color: opts.line || HAIR, width: opts.lw || 1 } });
}
function boxText(s, x, y, w, h, runs, opts = {}) {
  box(s, x, y, w, h, opts);
  s.addText(runs, { x: x + 0.08, y, w: w - 0.16, h, isTextBox: true, margin: 4,
    fontFace: FONT, fontSize: opts.fs || 12.5, color: opts.color || INK, align: "center",
    valign: "middle", lineSpacingMultiple: 1.02, bold: opts.bold || false });
}
function arrow(s, x, y, w, h, color = FAINT) {
  s.addShape(pres.ShapeType.line, { x, y, w, h, line: { color, width: 1.5, endArrowType: "triangle" } });
}

// ---- 1 TITLE --------------------------------------------------------------
(() => {
  const s = slide("Open by naming the checkpoint. Phase 1 proved the problem in a script. This one proves it on a real gateway we built, and shows the vulnerable baseline the fix will beat.");
  s.addText("PROGRESS EVAL-1   ·   PHASE 2", { x: MX, y: 2.15, w: 11, h: 0.4, isTextBox: true, margin: 0,
    fontFace: FONT, fontSize: 13, bold: true, color: BLUE, charSpacing: 1.5 });
  s.addText("The bypass, now on\nour own gateway.", { x: MX, y: 2.7, w: 11.2, h: 2.0, isTextBox: true, margin: 0,
    fontFace: FONT, fontSize: 54, bold: true, color: INK, lineSpacingMultiple: 1.0 });
  s.addText("We built the gateway, and reproduced the cache bypass on it — with the real filter, the real embedder, and real Qdrant and Redis.",
    { x: MX, y: 4.85, w: 9.8, h: 0.8, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 17, color: SUB, lineSpacingMultiple: 1.2 });
  s.addShape(pres.ShapeType.line, { x: MX, y: 6.05, w: W - 2 * MX, h: 0, line: { color: HAIR, width: 1 } });
  const meta = [["Team", "Divyansh Sharma · Sarvagya Dabas · Yashvit Gauri"], ["Window", "23 Aug – 26 Sep"], ["State", "Phase 2 complete"]];
  meta.forEach(([k, v], i) => {
    const x = MX + i * 4.0;
    s.addText(k.toUpperCase(), { x, y: 6.25, w: 3.8, h: 0.3, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 10, color: FAINT, charSpacing: 1 });
    s.addText(v, { x, y: 6.55, w: 3.8, h: 0.5, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 12, bold: true, color: INK });
  });
})();

// ---- 2 RECAP --------------------------------------------------------------
(() => {
  const s = slide("One line of recap from Phase 1, then the turn: that was a script. The question this checkpoint answers is whether it happens on a real running system. It does.");
  eyebrow(s, "Where we left off");
  title(s, [{ text: "Phase 1 proved the problem in a script.", options: {} }]);
  s.addShape(pres.ShapeType.roundRect, { x: MX, y: 2.7, w: W - 2 * MX, h: 2.0, rectRadius: 0.1, fill: { color: SURFACE }, line: { color: SURFACE, width: 0 } });
  s.addText("“A cache hit returns before the safety filter is ever asked — so a reworded attack can be served an answer the filter would have blocked.”",
    { x: MX + 0.6, y: 2.9, w: W - 2 * MX - 1.2, h: 1.6, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 25, color: INK, lineSpacingMultiple: 1.18, valign: "middle" });
  s.addText([
    { text: "This checkpoint answers one question: does it happen on a ", options: { color: SUB } },
    { text: "real running system", options: { color: INK, bold: true } },
    { text: "? It does.", options: { color: SUB } },
  ], { x: MX, y: 5.1, w: 11, h: 0.6, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 18, lineSpacingMultiple: 1.2 });
})();

// ---- 3 WHAT WE BUILT (simple native diagram) ------------------------------
(() => {
  const s = slide("This is what runs today, in plain terms. A question hits the cache first. If the cache has seen something similar, it answers at once and the safety check is skipped - that is the hole. Only on a miss does the safety check run, then the model, and the answer is saved with its safety label for later.");
  eyebrow(s, "What we built");
  title(s, [{ text: "A real gateway — and where the hole is.", options: {} }]);

  const bh = 0.9;                 // box height
  const spineY = 3.95;            // vertical centre of the question/cache spine
  const topY = 2.6, botY = 5.05;  // the two lane box tops
  const topMid = topY + bh / 2, botMid = botY + bh / 2;

  // Question -> Cache (on the centre spine)
  boxText(s, MX, spineY - bh / 2, 1.9, bh, [{ text: "A question", options: {} }], { fs: 13 });
  arrow(s, MX + 1.9, spineY, 0.5, 0, FAINT);
  boxText(s, MX + 2.4, spineY - bh / 2, 2.3, bh,
    [{ text: "Cache", options: { bold: true } }, { text: "\nchecked first", options: { color: SUB, fontSize: 10.5 } }],
    { fill: HILITE, line: BLUE, lw: 1.5, color: INK });

  const cacheR = MX + 4.7;        // right edge of the cache box
  const laneX = MX + 6.1;         // left edge of the lane boxes

  // Top lane: a match is served, and the check is skipped (the hole)
  s.addShape(pres.ShapeType.line, { x: cacheR, y: spineY, w: laneX - cacheR, h: topMid - spineY,
    line: { color: RED, width: 1.75, endArrowType: "triangle" } });
  s.addText("match", { x: cacheR + 0.05, y: (spineY + topMid) / 2 - 0.32, w: 1.2, h: 0.28, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 10, color: RED, align: "center" });
  boxText(s, laneX, topY, 2.5, bh, [{ text: "Answer served", options: { bold: true } }], { fill: "FFF0EE", line: RED, color: INK, fs: 13 });
  s.addText("The safety check is skipped — the hole.", { x: laneX + 2.65, y: topMid - 0.35, w: 3.1, h: 0.7, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 12, color: RED, align: "left", valign: "middle", lineSpacingMultiple: 1.05, bold: true });

  // Bottom lane: a miss is screened, then answered by the model
  s.addShape(pres.ShapeType.line, { x: cacheR, y: spineY, w: laneX - cacheR, h: botMid - spineY,
    line: { color: FAINT, width: 1.75, endArrowType: "triangle" } });
  s.addText("no match", { x: cacheR + 0.05, y: (spineY + botMid) / 2 - 0.02, w: 1.2, h: 0.28, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 10, color: FAINT, align: "center" });
  boxText(s, laneX, botY, 2.5, bh, [{ text: "Safety check", options: { bold: true } }], { color: INK, fs: 13 });
  arrow(s, laneX + 2.5, botMid, 0.5, 0, FAINT);
  boxText(s, laneX + 3.0, botY, 1.9, bh, [{ text: "Model", options: { bold: true } }], { color: INK, fs: 13 });

  explain(s, "The safety check sits after the cache. When the cache finds a match it answers first and the check never runs — which is exactly what a reworded attack exploits.", H - 0.95);
})();

// ---- 4 THE EXPERIMENT -----------------------------------------------------
(() => {
  const s = slide("Explain how the number is earned. Real public datasets, two families of rewording kept apart, everything fired over HTTP at the running gateway, and a bypass counted only when the poison comes back AND the log says the filter never ran.");
  eyebrow(s, "The experiment");
  title(s, [
    { text: `${report.seeds} real attacks, `, options: { color: INK } },
    { text: `${report.attack_variants_per_threshold.toLocaleString()} rewordings`, options: { color: BLUE } },
    { text: ", on the live gateway.", options: { color: INK } },
  ]);
  const bullets = [
    { text: "Seeds from two public datasets of real prompt-injection attacks.", options: { bullet: { indent: 16 }, breakLine: true, paraSpaceAfter: 12 } },
    { text: "Two families, kept apart: lazy edits (a capital, a full stop, a filler word) and full rewrites (real paraphrases).", options: { bullet: { indent: 16 }, breakLine: true, paraSpaceAfter: 12 } },
    { text: "Every variant fired at the running gateway over HTTP, exactly like a real user.", options: { bullet: { indent: 16 } } },
  ];
  s.addText(bullets, { x: MX, y: 2.75, w: 6.2, h: 3, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 16, color: INK, lineSpacingMultiple: 1.15 });
  s.addShape(pres.ShapeType.roundRect, { x: 7.5, y: 2.6, w: 5.1, h: 3.05, rectRadius: 0.1, fill: { color: SURFACE }, line: { color: SURFACE, width: 0 } });
  s.addText("WE ONLY COUNT A REAL BYPASS", { x: 7.85, y: 2.9, w: 4.5, h: 0.4, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 11, bold: true, color: BLUE, charSpacing: 1 });
  s.addText([
    { text: "The poisoned answer comes back,\nand ", options: { color: INK } },
    { text: "the gateway's own log says the filter did not run.", options: { color: INK, bold: true } },
    { text: "\n\nThe claim is read from the log, not from our word.", options: { color: SUB, fontSize: 13 } },
  ], { x: 7.85, y: 3.35, w: 4.4, h: 2.1, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 16, lineSpacingMultiple: 1.2 });
})();

// ---- 5 THE RESULT ---------------------------------------------------------
(() => {
  const s = slide("The headline. Read the 0.85 row: at a normal cache setting, 97 percent of lazy rewordings were served the poison. Lazy edits leak at every setting. Full rewrites only match once the cache is loose. Same shape as Phase 1, at large scale on a real system.");
  eyebrow(s, "The result");
  title(s, [
    { text: "At a normal setting, ", options: { color: INK } },
    { text: `${headline}%`, options: { color: BLUE } },
    { text: " of lazy attacks got through.", options: { color: INK } },
  ]);
  const head = ["Cache cut-off", "Lazy", "Rewrite", "Overall"].map((t, i) => ({ text: t,
    options: { bold: true, color: FAINT, fontFace: FONT, fontSize: 11, align: i ? "center" : "left", valign: "middle", fill: { color: BG }, border: [{ pt: 0, color: BG }, { pt: 0, color: BG }, { pt: 1, color: HAIR }, { pt: 0, color: BG }] } }));
  const rows = [head];
  THR.forEach((k) => {
    const r = byT(k);
    const hi = k === "0.85";
    const bg = hi ? HILITE : BG;
    const c = (txt, col, align) => ({ text: txt, options: { color: col, fontFace: FONT, fontSize: 13, bold: hi, align: align || "center", valign: "middle", fill: { color: bg }, border: [{ pt: 0, color: bg }, { pt: 0, color: bg }, { pt: 0.5, color: HAIR }, { pt: 0, color: bg }] } });
    rows.push([
      c(Number(k).toFixed(2) + (hi ? "  ·  typical" : ""), hi ? BLUE : INK, "left"),
      c(`${Math.round(r.lazy)}%`, hi ? BLUE : INK),
      c(`${Math.round(r.rewrite)}%`, SUB),
      c(`${Math.round(r.overall)}%`, INK),
    ]);
  });
  s.addTable(rows, { x: MX, y: 2.75, w: 5.6, colW: [2.6, 1.0, 1.0, 1.0], rowH: 0.36, valign: "middle" });
  const chartData = [
    { name: "Lazy edits", labels: THR, values: THR.map((k) => Math.round(byT(k).lazy)) },
    { name: "Full rewrites", labels: THR, values: THR.map((k) => Math.round(byT(k).rewrite)) },
  ];
  s.addChart(pres.ChartType.line, chartData, {
    x: 6.9, y: 2.55, w: 5.7, h: 3.5, showTitle: false, showLegend: true, legendPos: "b", legendColor: SUB, legendFontFace: FONT, legendFontSize: 11,
    chartColors: [ORANGE, BLUE], lineSize: 3, lineDataSymbol: "circle", lineDataSymbolSize: 7,
    catAxisLabelColor: FAINT, catAxisLabelFontFace: FONT, catAxisLabelFontSize: 10, catAxisLineColor: HAIR,
    valAxisLabelColor: FAINT, valAxisLabelFontFace: FONT, valAxisLabelFontSize: 10, valAxisMinVal: 0, valAxisMaxVal: 100, valAxisMajorUnit: 25,
    valGridLine: { color: "E8E8ED", size: 0.75 }, catGridLine: { style: "none" }, valAxisLineColor: BG,
  });
  explain(s, "Lazy edits get through at every setting — even the strictest a real product would use. Full rewrites only match once the cache is loosened. The filter is not weak; on a cache hit it is simply never asked.", H - 1.0);
})();

// ---- 6 PROOF --------------------------------------------------------------
(() => {
  const s = slide("Pre-empt every doubt with the checks. The safe-order row is the one to dwell on: run the exact same build with the filter moved in front of the cache, and the bypass drops to zero. Nothing else changed, so the order is the cause. That is the whole argument for the Phase 3 fix.");
  eyebrow(s, "Why the number is trustworthy");
  title(s, [{ text: "Four checks, and a proof of cause.", options: {} }]);
  const hstyle = { bold: true, color: FAINT, fontFace: FONT, fontSize: 11, valign: "middle", fill: { color: BG }, border: [{ pt: 0, color: BG }, { pt: 0, color: BG }, { pt: 1, color: HAIR }, { pt: 0, color: BG }] };
  const cell = (t, o = {}) => ({ text: t, options: { color: INK, fontFace: FONT, fontSize: 14, valign: "middle", fill: { color: o._bg || BG }, border: [{ pt: 0, color: o._bg || BG }, { pt: 0, color: o._bg || BG }, { pt: 0.5, color: HAIR }, { pt: 0, color: o._bg || BG }], align: o.align || "left", bold: o.bold || false, ...(o.color ? { color: o.color } : {}) } });
  const rows = [
    [{ text: "Check", options: hstyle }, { text: "Result", options: { ...hstyle, align: "center" } }, { text: "Why it matters", options: hstyle }],
    [cell("Exact attack served the poison"), cell(report.exact_served, { color: GREEN, align: "center", bold: true }), cell("the experiment is wired correctly", { color: SUB })],
    [cell("Honest questions served the poison"), cell(report.control_served_poison, { color: GREEN, align: "center", bold: true }), cell("normal users are not caught in the crossfire", { color: SUB })],
    [cell("Safe order: filter before cache", { _bg: HILITE, bold: true }), cell(`${Math.round(report.screen_first_bypass_at_085)}%`, { _bg: HILITE, color: BLUE, align: "center", bold: true }), cell("proof the order is the cause", { _bg: HILITE, bold: true })],
    [cell("Log score vs served hit"), cell(String(report.score_hit_mismatches), { color: GREEN, align: "center", bold: true }), cell("recorded scores match what was served", { color: SUB })],
  ];
  s.addTable(rows, { x: MX, y: 2.75, w: W - 2 * MX, colW: [4.6, 1.7, 5.2], rowH: 0.52, valign: "middle" });
  explain(s, "The safe-order row is the key one: the exact same build, with the filter moved in front of the cache, gives a 0% bypass. Nothing else changed — so the order is the cause, and the order is what Phase 3 fixes.", H - 0.95);
})();

// ---- 7 LATENCY ------------------------------------------------------------
(() => {
  const s = slide("Answer the obvious question: why not just screen everything? Because the cache is seven times faster. This gap, from 25 thousand real requests, is exactly why real systems check the cache first, and so it is the reason the bypass exists.");
  eyebrow(s, "Why the cache is checked first");
  title(s, [
    { text: "A hit is ", options: { color: INK } },
    { text: "7× faster", options: { color: BLUE } },
    { text: " than a miss.", options: { color: INK } },
  ]);
  const head = ["Outcome", "Requests", "p50", "p99"].map((t, i) => ({ text: t, options: { bold: true, color: FAINT, fontFace: FONT, fontSize: 11, align: i ? "right" : "left", valign: "middle", fill: { color: BG }, border: [{ pt: 0, color: BG }, { pt: 0, color: BG }, { pt: 1, color: HAIR }, { pt: 0, color: BG }] } }));
  const rows = [head];
  LAT.forEach((r) => {
    const hi = r.outcome.startsWith("Cache hit");
    const bg = hi ? HILITE : BG;
    const c = (t, col, align) => ({ text: t, options: { color: col, fontFace: FONT, fontSize: 13, bold: hi, align: align || "right", valign: "middle", fill: { color: bg }, border: [{ pt: 0, color: bg }, { pt: 0, color: bg }, { pt: 0.5, color: HAIR }, { pt: 0, color: bg }] } });
    rows.push([
      c(r.outcome, hi ? BLUE : INK, "left"),
      c(r.reqs.toLocaleString(), INK),
      c(`${Math.round(r.p50)} ms`, hi ? BLUE : INK),
      c(`${Math.round(r.p99)} ms`, SUB),
    ]);
  });
  s.addTable(rows, { x: MX, y: 2.85, w: 5.7, colW: [2.4, 1.5, 0.9, 0.9], rowH: 0.44, valign: "middle" });
  const cats = LAT.map((r) => r.outcome.replace(" (screen + model)", "").replace("Blocked attack", "Blocked"));
  const barData = [
    { name: "p50", labels: cats, values: LAT.map((r) => Math.round(r.p50)) },
    { name: "p99", labels: cats, values: LAT.map((r) => Math.round(r.p99)) },
  ];
  s.addChart(pres.ChartType.bar, barData, {
    x: 6.9, y: 2.55, w: 5.7, h: 3.4, barDir: "col", barGrouping: "clustered", showTitle: false,
    showLegend: true, legendPos: "b", legendColor: SUB, legendFontFace: FONT, legendFontSize: 11,
    chartColors: [BLUE, BLUELT], showValue: true, dataLabelColor: SUB, dataLabelFontFace: FONT, dataLabelFontSize: 9, dataLabelPosition: "outEnd",
    catAxisLabelColor: FAINT, catAxisLabelFontFace: FONT, catAxisLabelFontSize: 10, catAxisLineColor: HAIR,
    valAxisLabelColor: FAINT, valAxisLabelFontFace: FONT, valAxisLabelFontSize: 10, valAxisHidden: false,
    valGridLine: { color: "E8E8ED", size: 0.75 }, catGridLine: { style: "none" }, valAxisLineColor: BG,
  });
  explain(s, "A cache hit answers in about 14 ms; a miss pays the safety check and takes about 94 ms. Screening every request would throw that speed-up away — so the fix has to make the cache itself safety-aware.", H - 1.0);
})();

// ---- 8 THE FIX ------------------------------------------------------------
(() => {
  const s = slide("Preview the Phase 3 fix in one idea. Today the cache asks one question. We add a second: was the original safe. The label is already stored, so the fix is a filter on a search that already runs.");
  eyebrow(s, "What Phase 3 does");
  title(s, [{ text: "Let the cache ask a second question.", options: {} }]);
  s.addShape(pres.ShapeType.roundRect, { x: MX, y: 2.75, w: 5.65, h: 2.5, rectRadius: 0.1, fill: { color: SURFACE }, line: { color: SURFACE, width: 0 } });
  s.addText("THE CACHE TODAY ASKS", { x: MX + 0.4, y: 3.0, w: 5, h: 0.35, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 11, bold: true, color: FAINT, charSpacing: 1 });
  s.addText("“Does this sound like something I answered before?”", { x: MX + 0.4, y: 3.45, w: 4.9, h: 1.0, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 18, color: INK, lineSpacingMultiple: 1.1 });
  s.addText("That is the only question. It is the hole.", { x: MX + 0.4, y: 4.55, w: 4.9, h: 0.5, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 14, color: RED });
  s.addShape(pres.ShapeType.roundRect, { x: 7.05, y: 2.75, w: 5.55, h: 2.5, rectRadius: 0.1, fill: { color: HILITE }, line: { color: BLUE, width: 1.25 } });
  s.addText("SENTRYGATE ALSO ASKS", { x: 7.4, y: 3.0, w: 5, h: 0.35, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 11, bold: true, color: BLUE, charSpacing: 1 });
  s.addText([{ text: "“…and was that earlier question ", options: { color: INK } }, { text: "safe", options: { color: INK, bold: true } }, { text: "?”", options: { color: INK } }], { x: 7.4, y: 3.45, w: 4.9, h: 1.0, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 18, lineSpacingMultiple: 1.1 });
  s.addText("The safety label is already stored — so it is one extra check, no extra model.", { x: 7.4, y: 4.5, w: 4.9, h: 0.6, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 14, color: INK, lineSpacingMultiple: 1.1 });
  explain(s, "Next milestone: rerun these exact attacks with the second question turned on. The bypass rate should fall sharply — that is the first proof the fix works.", H - 0.95);
})();

// ---- 9 PLAN ---------------------------------------------------------------
(() => {
  const s = slide("Show where this checkpoint sits. Phase 2 is done. Phase 3 builds the fix and shows it beat this baseline, live. End of Phase 2 is exactly the right place to have a measured, vulnerable baseline and nothing more.");
  eyebrow(s, "Plan");
  title(s, [{ text: "Phase 2 done. The fix is next.", options: {} }]);
  const phases = [
    ["01", "18–22 Aug", "Prove the problem is real", "Done", GREEN, false],
    ["02", "23 Aug – 26 Sep", "Build the gateway and reproduce the problem on it", "You are here", BLUE, true],
    ["03", "27 Sep – 24 Oct", "Build the fix and show it beat the baseline, live", "4 weeks", FAINT, false],
    ["04", "25 Oct – 14 Nov", "Measure everything and write the paper", "3 weeks", FAINT, false],
  ];
  phases.forEach((p, i) => {
    const x = MX + i * 3.02;
    s.addShape(pres.ShapeType.roundRect, { x, y: 2.9, w: 2.8, h: 2.5, rectRadius: 0.08, fill: { color: p[5] ? HILITE : SURFACE }, line: { color: p[5] ? BLUE : SURFACE, width: p[5] ? 1.25 : 0 } });
    s.addText(p[0], { x: x + 0.28, y: 3.1, w: 2.3, h: 0.6, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 28, bold: true, color: p[4] });
    s.addText(p[1], { x: x + 0.28, y: 3.75, w: 2.4, h: 0.3, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 10, color: FAINT });
    s.addText(p[2], { x: x + 0.28, y: 4.05, w: 2.3, h: 1.1, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 12, color: INK, lineSpacingMultiple: 1.08 });
    s.addText(p[3], { x: x + 0.28, y: 5.05, w: 2.4, h: 0.3, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 10, bold: true, color: p[4] });
  });
  explain(s, "The job of this phase was a measured, vulnerable baseline — something concrete for the fix to beat. That is exactly what we have.", H - 0.9);
})();

// ---- 10 CLOSE -------------------------------------------------------------
(() => {
  const s = slide("Land on the sentence and stop. The demo is one command if there is time; the recorded capture is the fallback. Take questions.");
  eyebrow(s, "In one sentence");
  s.addText([
    { text: "On our own gateway, ", options: { color: INK } },
    { text: `${headline}%`, options: { color: BLUE, bold: true } },
    { text: " of lazy rewordings were served a poisoned answer,\nand the filter ran ", options: { color: INK } },
    { text: "zero", options: { color: RED, bold: true } },
    { text: " times.", options: { color: INK } },
  ], { x: MX, y: 2.5, w: W - 2 * MX, h: 2.0, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 34, bold: true, lineSpacingMultiple: 1.12 });
  s.addText("Move the filter in front of the cache and it drops to zero — so we know exactly what to fix.", { x: MX, y: 4.95, w: 11, h: 0.6, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 17, color: SUB });
  s.addShape(pres.ShapeType.line, { x: MX, y: 5.8, w: W - 2 * MX, h: 0, line: { color: HAIR, width: 1 } });
  const cmds = [["Live demo", "make gateway-up  &&  make gateway-demo"], ["Reproduce the result", "make bypass"]];
  cmds.forEach(([k, v], i) => {
    const x = MX + i * 6.0;
    s.addText(k.toUpperCase(), { x, y: 6.0, w: 5.8, h: 0.3, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 10, color: FAINT, charSpacing: 1 });
    s.addText(v, { x, y: 6.3, w: 5.8, h: 0.4, isTextBox: true, margin: 0, fontFace: MONO, fontSize: 13, color: INK });
  });
})();

const out = path.join(ROOT, "docs/deck-phase2.pptx");
pres.writeFile({ fileName: out }).then(() => console.log("wrote docs/deck-phase2.pptx (10 slides, light theme)"));
