/*
 * Build docs/deck-phase2.pptx for the second presentation (Progress Eval-1).
 *
 * An editable PowerPoint twin of docs/deck-phase2.html: same story, same dark
 * amber theme, but the tables and charts are native PowerPoint objects the
 * team can edit. Numbers are read from the committed results so they match the
 * HTML deck and the paper.
 *
 *   data/week4/report.json   the bypass sweep and its checks
 *   data/week4/latency.md    the response-time table
 *   docs/architecture-current.png   what runs today
 *
 * Run:  make deck-phase2-pptx   (or: node docs/build_deck_phase2_pptx.js)
 */

const fs = require("fs");
const path = require("path");
const pptxgen = require("pptxgenjs");

const ROOT = path.join(__dirname, "..");
const report = JSON.parse(fs.readFileSync(path.join(ROOT, "data/week4/report.json"), "utf8"));

// ---- theme (matches the HTML deck) ----------------------------------------
const GROUND = "0E141C", PANEL = "16202C", LINE = "2A3846";
const INK = "E9EEF5", MUTED = "8496AB", AMBER = "F2A93B";
const RED = "E5484D", OK = "4CC38A", BLUE = "4C9AFF";
const SANS = "IBM Plex Sans", MONO = "IBM Plex Mono";
const W = 13.3, H = 7.5, MX = 0.7;

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";
pres.defineSlideMaster({ title: "DARK", background: { color: GROUND } });

function slide(notes) {
  const s = pres.addSlide({ masterName: "DARK" });
  if (notes) s.addNotes(notes);
  // footer
  s.addText("SentryGate · Phase 2", { x: MX, y: H - 0.42, w: 6, h: 0.3, isTextBox: true,
    fontFace: MONO, fontSize: 9, color: MUTED });
  return s;
}
function eyebrow(s, text) {
  s.addText(text.toUpperCase(), { x: MX, y: 0.55, w: 11, h: 0.35, isTextBox: true,
    fontFace: MONO, fontSize: 12, bold: true, color: AMBER, charSpacing: 2 });
}
function title(s, runs, y = 0.95) {
  s.addText(runs, { x: MX, y, w: W - 2 * MX, h: 1.2, isTextBox: true,
    fontFace: SANS, fontSize: 33, bold: true, color: INK, lineSpacingMultiple: 1.02 });
}
function note(s, text, y = H - 1.05) {
  s.addText(text, { x: MX, y, w: W - 2 * MX, h: 0.6, isTextBox: true,
    fontFace: SANS, fontSize: 12.5, color: MUTED, lineSpacingMultiple: 1.15 });
}

// ---- data -----------------------------------------------------------------
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

// ---- 1 TITLE --------------------------------------------------------------
(() => {
  const s = slide("Open by naming the checkpoint. Phase 1 proved the problem in a script. This one proves it on a real gateway we built, and shows the vulnerable baseline the fix will beat.");
  s.addText("PROGRESS EVAL-1  ·  PHASE 2", { x: MX, y: 2.1, w: 11, h: 0.4, isTextBox: true,
    fontFace: MONO, fontSize: 13, bold: true, color: AMBER, charSpacing: 2 });
  s.addShape(pres.ShapeType.rect, { x: MX, y: 2.65, w: 1.2, h: 0.05, fill: { color: AMBER } });
  s.addText("The bypass, now on\nour own gateway.", { x: MX, y: 2.85, w: 11, h: 1.9, isTextBox: true,
    fontFace: SANS, fontSize: 52, bold: true, color: INK, lineSpacingMultiple: 1.0 });
  s.addText("We built the gateway, and reproduced the cache bypass on it — with the real filter, the real embedder, and real Qdrant and Redis.",
    { x: MX, y: 4.85, w: 10.5, h: 0.8, isTextBox: true, fontFace: SANS, fontSize: 17, color: MUTED });
  const meta = [
    ["Team", "Divyansh Sharma · Sarvagya Dabas · Yashvit Gauri"],
    ["Window", "23 Aug – 26 Sep"],
    ["State", "Phase 2 complete"],
  ];
  meta.forEach(([k, v], i) => {
    const x = MX + i * 4.0;
    s.addText(k.toUpperCase(), { x, y: 5.9, w: 3.8, h: 0.3, isTextBox: true, fontFace: MONO, fontSize: 10, color: MUTED, charSpacing: 1 });
    s.addText(v, { x, y: 6.2, w: 3.8, h: 0.5, isTextBox: true, fontFace: SANS, fontSize: 12, bold: true, color: INK });
  });
})();

// ---- 2 RECAP --------------------------------------------------------------
(() => {
  const s = slide("One line of recap from Phase 1, then the turn: that was a script. The question this checkpoint answers is whether it happens on a real running system. It does.");
  eyebrow(s, "Where we left off");
  title(s, [{ text: "Phase 1 proved the problem in a script.", options: {} }]);
  s.addShape(pres.ShapeType.roundRect, { x: MX, y: 2.6, w: W - 2 * MX, h: 1.9, rectRadius: 0.08,
    fill: { color: PANEL }, line: { color: LINE, width: 1 } });
  s.addText([
    { text: "“A cache hit returns before the safety filter is ever asked", options: { color: INK } },
    { text: " — so a reworded attack can be served an answer the filter would have blocked.”", options: { color: INK } },
  ], { x: MX + 0.5, y: 2.85, w: W - 2 * MX - 1, h: 1.4, isTextBox: true, fontFace: SANS, fontSize: 24, italic: true, lineSpacingMultiple: 1.15, valign: "middle" });
  s.addText([
    { text: "This checkpoint answers one question: does it happen on a ", options: { color: MUTED } },
    { text: "real running system", options: { color: INK, bold: true } },
    { text: "? It does.", options: { color: MUTED } },
  ], { x: MX, y: 4.9, w: 11, h: 0.6, isTextBox: true, fontFace: SANS, fontSize: 18 });
})();

// ---- 3 WHAT WE BUILT ------------------------------------------------------
(() => {
  const s = slide("This is what runs today. The cache is checked before the filter, which is the hole. The safety label is already stored next to every answer, but the lookup does not use it yet - that is the Phase 3 fix. The greyed boxes are built for later.");
  eyebrow(s, "What we built");
  title(s, [{ text: "A real gateway. This is what runs today.", options: {} }]);
  const img = path.join(ROOT, "docs/architecture-current.png");
  const data = "image/png;base64," + fs.readFileSync(img).toString("base64");
  // white card behind the diagram so the light-background PNG sits cleanly
  s.addShape(pres.ShapeType.roundRect, { x: MX, y: 2.35, w: W - 2 * MX, h: 3.4, rectRadius: 0.06, fill: { color: "FFFFFF" } });
  s.addImage({ data, x: MX + 0.15, y: 2.5, w: W - 2 * MX - 0.3, h: 3.1, sizing: { type: "contain", w: W - 2 * MX - 0.3, h: 3.1 } });
  note(s, "OpenAI-compatible API behind nginx, in Docker. The cache is checked before the filter — that is the hole. The safety label is already saved with every answer, ready for the fix.");
})();

// ---- 4 THE EXPERIMENT -----------------------------------------------------
(() => {
  const s = slide("Explain how the number is earned. Real public datasets, two families of rewording kept apart, everything fired over HTTP at the running gateway, and a bypass counted only when the poison comes back AND the log says the filter never ran.");
  eyebrow(s, "The experiment");
  title(s, [
    { text: `${report.seeds} real attacks, `, options: { color: INK } },
    { text: `${report.attack_variants_per_threshold.toLocaleString()} rewordings`, options: { color: AMBER } },
    { text: ", on the live gateway.", options: { color: INK } },
  ]);
  const bullets = [
    { text: "Seeds from two public datasets: deepset/prompt-injections and jayavibhav/prompt-injection.", options: { bullet: { indent: 18 }, breakLine: true, paraSpaceAfter: 10 } },
    { text: "Two families, kept apart: lazy edits (capitals, punctuation, a filler word) and full rewrites (real paraphrases).", options: { bullet: { indent: 18 }, breakLine: true, paraSpaceAfter: 10 } },
    { text: "Every variant fired over HTTP at the running gateway.", options: { bullet: { indent: 18 } } },
  ];
  s.addText(bullets, { x: MX, y: 2.7, w: 6.2, h: 3, isTextBox: true, fontFace: SANS, fontSize: 16, color: INK, lineSpacingMultiple: 1.1 });
  s.addShape(pres.ShapeType.roundRect, { x: 7.4, y: 2.6, w: 5.2, h: 3.0, rectRadius: 0.08, fill: { color: PANEL }, line: { color: AMBER, width: 1.25 } });
  s.addText("A BYPASS IS COUNTED ONLY WHEN BOTH ARE TRUE", { x: 7.7, y: 2.85, w: 4.6, h: 0.5, isTextBox: true, fontFace: MONO, fontSize: 11, bold: true, color: AMBER, charSpacing: 1 });
  s.addText([
    { text: "The poisoned answer comes back, and\n", options: { color: INK } },
    { text: "the gateway's own log says ", options: { color: INK } },
    { text: "screening_ran = false", options: { color: OK, fontFace: MONO } },
    { text: ".\n\n", options: {} },
    { text: "The claim is read from the log, not from our code.", options: { color: MUTED, fontSize: 13 } },
  ], { x: 7.7, y: 3.35, w: 4.6, h: 2.0, isTextBox: true, fontFace: SANS, fontSize: 16, lineSpacingMultiple: 1.1 });
})();

// ---- 5 THE RESULT ---------------------------------------------------------
(() => {
  const s = slide("The headline. Read the 0.85 row: at a normal cache setting, 97 percent of lazy rewordings were served the poison. Lazy edits leak at every setting. Full rewrites only match once the cache is loose. Same shape as Phase 1, at large scale on a real system.");
  eyebrow(s, "The result");
  title(s, [
    { text: "At a normal setting, ", options: { color: INK } },
    { text: `${headline}%`, options: { color: AMBER } },
    { text: " of lazy attacks got through.", options: { color: INK } },
  ]);
  // table
  const head = ["Cut-off", "Lazy", "Rewrite", "Overall"].map((t) => ({ text: t,
    options: { bold: true, color: MUTED, fontFace: MONO, fontSize: 11, fill: { color: GROUND }, valign: "middle" } }));
  const rows = [head];
  THR.forEach((k) => {
    const r = byT(k);
    const hi = k === "0.85";
    const bg = hi ? "1E2A38" : GROUND;
    const cell = (txt, col, align) => ({ text: txt, options: { color: col, fontFace: MONO, fontSize: 13, bold: hi,
      fill: { color: bg }, valign: "middle", align: align || "center" } });
    rows.push([
      cell(Number(k).toFixed(2), hi ? AMBER : INK, "left"),
      cell(`${Math.round(r.lazy)}%`, hi ? AMBER : INK),
      cell(`${Math.round(r.rewrite)}%`, MUTED),
      cell(`${Math.round(r.overall)}%`, INK),
    ]);
  });
  s.addTable(rows, { x: MX, y: 2.7, w: 5.4, colW: [1.5, 1.3, 1.3, 1.3], rowH: 0.34,
    border: { type: "solid", color: LINE, pt: 0.5 }, align: "center", valign: "middle" });
  // chart
  const chartData = [
    { name: "Lazy edits", labels: THR, values: THR.map((k) => Math.round(byT(k).lazy)) },
    { name: "Full rewrites", labels: THR, values: THR.map((k) => Math.round(byT(k).rewrite)) },
  ];
  s.addChart(pres.ChartType.line, chartData, {
    x: 6.4, y: 2.5, w: 6.2, h: 3.6, showTitle: false, showLegend: true, legendPos: "b", legendColor: MUTED, legendFontFace: SANS, legendFontSize: 11,
    chartColors: [AMBER, BLUE], lineSize: 3, lineDataSymbol: "circle", lineDataSymbolSize: 7,
    catAxisLabelColor: MUTED, catAxisLabelFontFace: MONO, catAxisLabelFontSize: 10, catAxisLineColor: LINE,
    valAxisLabelColor: MUTED, valAxisLabelFontFace: MONO, valAxisLabelFontSize: 10, valAxisMinVal: 0, valAxisMaxVal: 100,
    valGridLine: { color: LINE, size: 0.5 }, catGridLine: { style: "none" },
    valAxisTitle: "Served from poison (%)", showValAxisTitle: true, valAxisTitleColor: MUTED, valAxisTitleFontFace: SANS, valAxisTitleFontSize: 11,
  });
  note(s, "The filter is not weak — it scores every attack at 1.000. On a cache hit it is simply never asked.");
})();

// ---- 6 PROOF --------------------------------------------------------------
(() => {
  const s = slide("Pre-empt every doubt with the checks. The safe-order row is the one to dwell on: run the exact same build with the filter moved in front of the cache, and the bypass drops to zero. Nothing else changed, so the order is the cause. That is the whole argument for the Phase 3 fix.");
  eyebrow(s, "Why the number is trustworthy");
  title(s, [{ text: "Four checks, and a proof of cause.", options: {} }]);
  const gray = { color: MUTED, fontFace: SANS, fontSize: 13, valign: "middle", fill: { color: PANEL } };
  const dark = { fill: { color: GROUND }, valign: "middle" };
  const cell = (t, o = {}) => ({ text: t, options: { color: INK, fontFace: SANS, fontSize: 14, valign: "middle", fill: { color: GROUND }, ...o } });
  const rows = [
    [{ text: "Check", options: { ...gray, bold: true, fontFace: MONO, fontSize: 11, fill: { color: GROUND } } },
     { text: "Result", options: { ...gray, bold: true, fontFace: MONO, fontSize: 11, fill: { color: GROUND }, align: "center" } },
     { text: "Why it matters", options: { ...gray, bold: true, fontFace: MONO, fontSize: 11, fill: { color: GROUND } } }],
    [cell("Exact attack served the poison"), cell(report.exact_served, { color: OK, fontFace: MONO, align: "center" }), cell("the experiment is wired correctly", { color: MUTED })],
    [cell("Honest questions served the poison"), cell(report.control_served_poison, { color: OK, fontFace: MONO, align: "center" }), cell("normal users are not caught in the crossfire", { color: MUTED })],
    [cell("Safe order (filter before cache)", { fill: { color: "1E2A38" }, bold: true }), cell(`${Math.round(report.screen_first_bypass_at_085)}%`, { color: AMBER, fontFace: MONO, align: "center", bold: true, fill: { color: "1E2A38" } }), cell("proof the order is the cause", { color: INK, bold: true, fill: { color: "1E2A38" } })],
    [cell("Log score vs served hit"), cell(String(report.score_hit_mismatches), { color: OK, fontFace: MONO, align: "center" }), cell("recorded scores match what was served", { color: MUTED })],
  ];
  s.addTable(rows, { x: MX, y: 2.7, w: W - 2 * MX, colW: [4.6, 1.6, 5.7], rowH: 0.5,
    border: { type: "solid", color: LINE, pt: 0.5 }, valign: "middle" });
  s.addText([
    { text: "Move the filter in front of the cache, same build, same attacks — the bypass drops to ", options: { color: MUTED } },
    { text: "zero", options: { color: AMBER, bold: true } },
    { text: ".", options: { color: MUTED } },
  ], { x: MX, y: 6.0, w: 11.5, h: 0.6, isTextBox: true, fontFace: SANS, fontSize: 17 });
})();

// ---- 7 LATENCY ------------------------------------------------------------
(() => {
  const s = slide("Answer the obvious question: why not just screen everything? Because the cache is seven times faster. This gap, from 25 thousand real requests, is exactly why real systems check the cache first, and so it is the reason the bypass exists.");
  eyebrow(s, "Why the cache goes first");
  title(s, [
    { text: "A hit is ", options: { color: INK } },
    { text: "7×", options: { color: AMBER } },
    { text: " faster than a miss.", options: { color: INK } },
  ]);
  // table
  const head = ["Outcome", "Requests", "p50", "p99"].map((t) => ({ text: t, options: { bold: true, color: MUTED, fontFace: MONO, fontSize: 11, fill: { color: GROUND }, valign: "middle" } }));
  const rows = [head];
  LAT.forEach((r) => {
    const hi = r.outcome.startsWith("Cache hit");
    const bg = hi ? "1E2A38" : GROUND;
    rows.push([
      { text: r.outcome, options: { color: hi ? AMBER : INK, fontFace: SANS, fontSize: 13, bold: hi, fill: { color: bg }, valign: "middle" } },
      { text: r.reqs.toLocaleString(), options: { color: INK, fontFace: MONO, fontSize: 13, align: "right", fill: { color: bg }, valign: "middle" } },
      { text: `${Math.round(r.p50)} ms`, options: { color: INK, fontFace: MONO, fontSize: 13, align: "right", fill: { color: bg }, valign: "middle" } },
      { text: `${Math.round(r.p99)} ms`, options: { color: MUTED, fontFace: MONO, fontSize: 13, align: "right", fill: { color: bg }, valign: "middle" } },
    ]);
  });
  s.addTable(rows, { x: MX, y: 2.8, w: 5.6, colW: [2.3, 1.3, 1.0, 1.0], rowH: 0.42, border: { type: "solid", color: LINE, pt: 0.5 }, valign: "middle" });
  // grouped bar chart p50 vs p99
  const cats = LAT.map((r) => r.outcome.replace(" (screen + model)", "").replace("Blocked attack", "Blocked"));
  const barData = [
    { name: "p50", labels: cats, values: LAT.map((r) => Math.round(r.p50)) },
    { name: "p99", labels: cats, values: LAT.map((r) => Math.round(r.p99)) },
  ];
  s.addChart(pres.ChartType.bar, barData, {
    x: 6.6, y: 2.5, w: 6.0, h: 3.5, barDir: "col", barGrouping: "clustered", showTitle: false,
    showLegend: true, legendPos: "b", legendColor: MUTED, legendFontFace: SANS, legendFontSize: 11,
    chartColors: [AMBER, "7A5A2E"], showValue: true, dataLabelColor: INK, dataLabelFontFace: MONO, dataLabelFontSize: 9, dataLabelPosition: "outEnd",
    catAxisLabelColor: MUTED, catAxisLabelFontFace: SANS, catAxisLabelFontSize: 10, catAxisLineColor: LINE,
    valAxisLabelColor: MUTED, valAxisLabelFontFace: MONO, valAxisLabelFontSize: 10,
    valGridLine: { color: LINE, size: 0.5 }, catGridLine: { style: "none" },
    valAxisTitle: "Response time (ms)", showValAxisTitle: true, valAxisTitleColor: MUTED, valAxisTitleFontFace: SANS, valAxisTitleFontSize: 11,
  });
  note(s, "From 25,416 real requests. Screening every request throws this speed-up away — so the fix has to make the cache itself safety-aware.");
})();

// ---- 8 THE FIX ------------------------------------------------------------
(() => {
  const s = slide("Preview the Phase 3 fix in one idea. Today the cache asks one question. We add a second: was the original safe. The label is already stored, so the fix is a filter on a search that already runs.");
  eyebrow(s, "What Phase 3 does");
  title(s, [{ text: "Let the cache ask a second question.", options: {} }]);
  // two panels
  s.addShape(pres.ShapeType.roundRect, { x: MX, y: 2.7, w: 5.7, h: 2.6, rectRadius: 0.08, fill: { color: PANEL }, line: { color: LINE, width: 1 } });
  s.addText("THE CACHE TODAY ASKS", { x: MX + 0.35, y: 2.95, w: 5, h: 0.4, isTextBox: true, fontFace: MONO, fontSize: 11, color: MUTED, charSpacing: 1 });
  s.addText("“Does this sound like something I answered before?”", { x: MX + 0.35, y: 3.4, w: 5.0, h: 1.0, isTextBox: true, fontFace: SANS, fontSize: 17, color: INK });
  s.addText("That is the only question. It is the hole.", { x: MX + 0.35, y: 4.5, w: 5.0, h: 0.6, isTextBox: true, fontFace: SANS, fontSize: 15, color: RED });
  s.addShape(pres.ShapeType.roundRect, { x: 6.9, y: 2.7, w: 5.7, h: 2.6, rectRadius: 0.08, fill: { color: PANEL }, line: { color: AMBER, width: 1.25 } });
  s.addText("SENTRYGATE ALSO ASKS", { x: 7.25, y: 2.95, w: 5, h: 0.4, isTextBox: true, fontFace: MONO, fontSize: 11, color: AMBER, charSpacing: 1 });
  s.addText([{ text: "“…and was that earlier question ", options: { color: INK } }, { text: "safe", options: { color: INK, bold: true } }, { text: "?”", options: { color: INK } }], { x: 7.25, y: 3.4, w: 5.0, h: 1.0, isTextBox: true, fontFace: SANS, fontSize: 17 });
  s.addText("The label is already stored, so it is one extra check, no extra model.", { x: 7.25, y: 4.5, w: 5.0, h: 0.7, isTextBox: true, fontFace: SANS, fontSize: 15, color: OK });
  note(s, "Next milestone: rerun these exact attacks with the check on. The bypass rate should fall sharply — the first proof the fix works.");
})();

// ---- 9 PLAN ---------------------------------------------------------------
(() => {
  const s = slide("Show where this checkpoint sits. Phase 2 is done. Phase 3 builds the fix and shows it beat this baseline, live. End of Phase 2 is exactly the right place to have a measured, vulnerable baseline and nothing more.");
  eyebrow(s, "Plan");
  title(s, [{ text: "Phase 2 done. The fix is next.", options: {} }]);
  const phases = [
    ["01", "18–22 Aug", "Prove the problem is real", "done", OK],
    ["02", "23 Aug–26 Sep", "Build the gateway and reproduce the problem on it", "You are here", AMBER],
    ["03", "27 Sep–24 Oct", "Build the fix and show it beat the baseline, live", "4 weeks", MUTED],
    ["04", "25 Oct–14 Nov", "Measure everything and write the paper", "3 weeks", MUTED],
  ];
  phases.forEach((p, i) => {
    const x = MX + i * 3.05;
    s.addShape(pres.ShapeType.roundRect, { x, y: 2.8, w: 2.85, h: 2.5, rectRadius: 0.06, fill: { color: PANEL }, line: { color: p[0] === "02" ? AMBER : LINE, width: p[0] === "02" ? 1.25 : 1 } });
    s.addText(p[0], { x: x + 0.25, y: 3.0, w: 2.3, h: 0.6, isTextBox: true, fontFace: MONO, fontSize: 26, bold: true, color: p[4] });
    s.addText(p[1], { x: x + 0.25, y: 3.65, w: 2.4, h: 0.3, isTextBox: true, fontFace: MONO, fontSize: 10, color: MUTED });
    s.addText(p[2], { x: x + 0.25, y: 3.95, w: 2.4, h: 1.0, isTextBox: true, fontFace: SANS, fontSize: 12, color: INK, lineSpacingMultiple: 1.05 });
    s.addText(p[3], { x: x + 0.25, y: 4.95, w: 2.4, h: 0.3, isTextBox: true, fontFace: MONO, fontSize: 10, bold: true, color: p[4] });
  });
  note(s, "The job of this phase was a measured, vulnerable baseline — something for the fix to beat. That is exactly what we have.");
})();

// ---- 10 CLOSE -------------------------------------------------------------
(() => {
  const s = slide("Land on the sentence and stop. The demo is one command if there is time; the recorded capture is the fallback. Take questions.");
  eyebrow(s, "In one sentence");
  s.addShape(pres.ShapeType.roundRect, { x: MX, y: 2.2, w: W - 2 * MX, h: 2.5, rectRadius: 0.08, fill: { color: PANEL }, line: { color: LINE, width: 1 } });
  s.addText([
    { text: "On our own gateway, ", options: { color: INK } },
    { text: `${headline}%`, options: { color: AMBER, bold: true } },
    { text: " of lazy rewordings were served a poisoned answer, and the filter ran ", options: { color: INK } },
    { text: "zero", options: { color: RED, bold: true } },
    { text: " times.", options: { color: INK } },
  ], { x: MX + 0.5, y: 2.5, w: W - 2 * MX - 1, h: 1.4, isTextBox: true, fontFace: SANS, fontSize: 26, bold: true, valign: "middle", lineSpacingMultiple: 1.1 });
  s.addText("Move the filter in front of the cache and it drops to zero — so we know exactly what to fix.", { x: MX + 0.5, y: 3.95, w: 11, h: 0.6, isTextBox: true, fontFace: SANS, fontSize: 15, color: MUTED });
  const cmds = [["Live demo", "make gateway-up && make gateway-demo"], ["Reproduce the result", "make bypass"]];
  cmds.forEach(([k, v], i) => {
    const x = MX + i * 6.0;
    s.addText(k.toUpperCase(), { x, y: 5.4, w: 5.8, h: 0.3, isTextBox: true, fontFace: MONO, fontSize: 10, color: MUTED, charSpacing: 1 });
    s.addText(v, { x, y: 5.7, w: 5.8, h: 0.4, isTextBox: true, fontFace: MONO, fontSize: 13, color: INK });
  });
})();

const out = path.join(ROOT, "docs/deck-phase2.pptx");
pres.writeFile({ fileName: out }).then(() => console.log("wrote docs/deck-phase2.pptx (10 slides)"));
