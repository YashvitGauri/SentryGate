/*
 * Build reports/out/SentryGate_Progress_Report_3.pptx, for the 24 October review.
 *
 * Same design and structure as Progress Report 2 (reports/deck_common.js),
 * filled with Phase 3: the defence, what it costs, two corrections to
 * Phase 2, the model picker, and the two live mitigations.
 *
 * Numbers are read from the committed results:
 *   data/phase3/report.json, data/router/report.json, data/mitigations/demo.txt
 *
 * Run:  make report3-pptx
 */

const fs = require("fs");
const path = require("path");
const { C, makeDeck } = require("./deck_common");

const ROOT = path.join(__dirname, "..");
const read = (p) => JSON.parse(fs.readFileSync(path.join(ROOT, p), "utf8"));
const DEF = read("data/phase3/report.json");
const RTR = read("data/router/report.json");
const DEMO = fs.readFileSync(path.join(ROOT, "data/mitigations/demo.txt"), "utf8");
const A = DEF.arms;

const { NAVY, GOLD, RED, GREEN, BLUE, SLATE, TEXT, MUTED, LINE, ALT, WHITE, PILL, FONT, W, MX, CREAM } = C;
const TOTAL = 14;

const D = makeDeck("SentryGate · Progress Report 3");
const { pres, slide, label, title, sub, card, pill } = D;

const p1 = (x) => `${x.toFixed(1)}%`;
const p0 = (x) => `${x.toFixed(0)}%`;
const NAMES = { base: "No defence", filter: "Label match only", recheck: "Re-check risky hits only",
                both: "Label match + re-check risky hits", all: "Label match + re-check every hit" };
const ORDER = ["base", "filter", "recheck", "both", "all"];
const HIT_COST = Math.round((A.all.hit_p50_ms - A.base.hit_p50_ms) / 10) * 10;
const REAL_S = (RTR.model_ms_p50.cheap / 1000).toFixed(1);
function demoCount(text) {
  const m = DEMO.match(new RegExp(`\\d+ ${text}: (\\d+)`));
  return m ? Number(m[1]) : 0;
}
const PROBES = ["answered", "blocked by the filter", "refused, rate limit"].reduce((a, k) => a + demoCount(k), 0);

// ---- 01 cover ---------------------------------------------------------------
(() => {
  const s = slide("Name the checkpoint. Phase 2 proved the hole on our own gateway; Phase 3 built the fix and measured what it costs.");
  s.addText("PROJECT PROGRESS REPORT · DEPARTMENT OF INFORMATION TECHNOLOGY", { x: MX, y: 0.62, w: 11, h: 0.3,
    isTextBox: true, margin: 0, fontFace: FONT, fontSize: 12.5, color: GOLD });
  s.addText("SentryGate", { x: MX, y: 2.35, w: 9, h: 1.05, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 62, color: NAVY });
  s.addText("A Security-Aware Semantic Caching Gateway for Large Language Model Applications", { x: MX, y: 3.45, w: 11.5, h: 0.5,
    isTextBox: true, margin: 0, fontFace: FONT, fontSize: 20, italic: true, color: MUTED });
  s.addShape(pres.ShapeType.line, { x: MX - 0.08, y: 4.15, w: 3.0, h: 0, line: { color: GOLD, width: 1 } });
  s.addText("PROGRESS REPORT — 3", { x: MX, y: 4.38, w: 6, h: 0.35, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 15, color: NAVY });
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
  const s = slide("Lead with the result: with every cache hit checked again, the leaks the cache causes go to zero, honest users keep their hits, and the model call is still skipped.");
  label(s, "// 01 — Status Summary");
  title(s, "The defence is built, and it works");
  s.addText("The objective was to close the bypass we reproduced in Phase 2, and to measure what the fix costs.",
    { x: MX, y: 1.8, w: 7.3, h: 0.9, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 15.5, italic: true, color: MUTED, lineSpacingMultiple: 1.25, valign: "top" });
  s.addText([
    { text: `The same ${DEF.seeds} attacks were fired at the same gateway in five settings. `, options: { color: TEXT } },
    { text: "With the safety check run again on every cache hit, every leak the cache caused was removed", options: { color: TEXT, bold: true } },
    { text: `, at about ${HIT_COST} ms per hit, against about ${REAL_S} s for a real model answer.`, options: { color: TEXT } },
  ], { x: MX, y: 2.85, w: 7.3, h: 1.7, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 16.5, lineSpacingMultiple: 1.35, valign: "top" });

  const cx = 8.35, cw = 4.35;
  card(s, cx, 1.6, cw, 4.6);
  s.addText("CACHE-CAUSED LEAKS", { x: cx + 0.4, y: 1.92, w: 3.5, h: 0.26, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 11, color: GOLD });
  s.addText(p1(A.base.served.clean.cache_caused), { x: cx + 0.4, y: 2.2, w: 1.9, h: 0.8, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 40, color: RED });
  s.addText("→", { x: cx + 2.05, y: 2.2, w: 0.4, h: 0.8, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 28, color: MUTED, align: "center", valign: "middle" });
  s.addText(p1(A.all.served.clean.cache_caused), { x: cx + 2.5, y: 2.2, w: 1.6, h: 0.8, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 40, color: GREEN });
  s.addText("no defence → re-check every hit, poison saved as clean (the realistic case)",
    { x: cx + 0.4, y: 3.0, w: 3.6, h: 0.6, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 11.5, color: MUTED, lineSpacingMultiple: 1.1, valign: "top" });
  s.addShape(pres.ShapeType.line, { x: cx + 0.3, y: 3.75, w: cw - 0.6, h: 0, line: { color: LINE, width: 1 } });
  s.addText(p1(A.all.honest_hit_rate), { x: cx + 0.4, y: 3.9, w: 3.6, h: 0.8, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 40, color: GREEN });
  s.addText("of honest cache hits kept, the same as with no defence",
    { x: cx + 0.4, y: 4.7, w: 3.6, h: 0.5, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 11.5, color: MUTED, lineSpacingMultiple: 1.1, valign: "top" });
  s.addShape(pres.ShapeType.line, { x: cx + 0.3, y: 5.3, w: cw - 0.6, h: 0, line: { color: LINE, width: 1 } });
  s.addText([
    { text: "Label matching alone was not enough. ", options: { color: TEXT } },
    { text: "The next slides show why.", options: { color: RED, italic: true } },
  ], { x: cx + 0.4, y: 5.42, w: 3.7, h: 0.55, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 13, valign: "top" });
})();

// ---- 03 work completed --------------------------------------------------------
(() => {
  const s = slide("Six workstreams, one per card. The key one is 03: the same attacks, in five settings, with every leak traced to the cache or the filter.");
  label(s, "// 02 — Work Completed");
  title(s, "Six workstreams closed in Phase 3");
  const items = [
    ["Verdict-tagged lookup", "A cheap keyword label on every question; a hit needs an unflagged answer with the same label, filtered inside the Qdrant search."],
    ["Re-checking cache hits", "A fresh safety check on a hit before it is served, for risky-looking hits or for every hit. The log says which."],
    ["The defence experiment", `${A.base.served.clean.n.toLocaleString()} attack rewordings, five settings, two poison labels, and ${DEF.honest_questions} honest questions.`],
    ["Cost-aware model picker", `Easy questions to gpt-4o-mini, hard to gpt-4o, with a fallback model. Measured on ${2 * RTR.questions} live paid calls.`],
    ["Output guard and rate limits", "Every answer scanned for scripts, SQL, shell and secrets; per-caller request and token limits in Redis."],
    ["Quality and documentation", "88 tests (up from 54), a code checker with no findings, the paper updated with three new results sections."],
  ];
  const gx = 0.2, x0 = 0.6, cw = (12.1 - 2 * gx) / 3, ch = 2.3, gy = 0.25, y0 = 1.85;
  items.forEach(([h, b], i) => {
    const x = x0 + (i % 3) * (cw + gx), y = y0 + Math.floor(i / 3) * (ch + gy);
    card(s, x, y, cw, ch);
    s.addText(String(i + 1).padStart(2, "0"), { x: x + 0.35, y: y + 0.25, w: 1, h: 0.45, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 24, color: GOLD });
    s.addText(h, { x: x + 0.35, y: y + 0.82, w: cw - 0.6, h: 0.35, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 15, color: NAVY });
    s.addText(b, { x: x + 0.35, y: y + 1.28, w: cw - 0.6, h: 0.9, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 11.5, color: MUTED, lineSpacingMultiple: 1.12, valign: "top" });
  });
})();

// ---- 04 measured result: the five settings ------------------------------------
(() => {
  const s = slide("Read down the clean column. Label matching barely helps when the poison was saved as clean. Re-checking only risky hits leaves a third. Re-checking every hit gives zero.");
  label(s, "// 03 — Measured Result");
  title(s, "Only re-checking every hit closes the hole");
  sub(s, "Cache-caused = poison served on a text the filter blocks when asked directly. Threshold 0.85, same attacks as Phase 2.");
  const cols = [
    { h: "Setting", x: 0.9, w: 4.2 },
    { h: "Saved as clean (realistic)", x: 5.1, w: 2.1 },
    { h: "Saved as attack (easy)", x: 7.2, w: 2.0 },
    { h: "Honest hits kept", x: 9.2, w: 1.8 },
    { h: "Median hit", x: 11.0, w: 1.5 },
  ];
  cols.forEach((c, i) => s.addText(c.h.toUpperCase(), { x: c.x, y: 2.3, w: c.w, h: 0.3, isTextBox: true, margin: 0,
    fontFace: FONT, fontSize: 10, color: GOLD, align: i ? "center" : "left" }));
  ORDER.forEach((tag, i) => {
    const a = A[tag], y = 2.7 + i * 0.8, last = tag === "all";
    card(s, 0.6, y, 12.1, 0.68, last ? "EEF5EF" : (i % 2 ? ALT : WHITE), last ? GREEN : LINE);
    const clean = a.served.clean.cache_caused;
    const vals = [NAMES[tag], p1(clean), p1(a.served.attack.cache_caused), p1(a.honest_hit_rate), `${Math.round(a.hit_p50_ms)} ms`];
    const colours = [NAVY, last ? GREEN : (clean > 40 ? RED : GOLD), a.served.attack.cache_caused < 5 ? GREEN : RED, TEXT, last ? GOLD : TEXT];
    vals.forEach((v, j) => s.addText(v, { x: cols[j].x, y, w: cols[j].w, h: 0.68, isTextBox: true, margin: 0, fontFace: FONT,
      fontSize: j ? 17 : 14, bold: last, color: colours[j], align: j ? "center" : "left", valign: "middle" }));
  });
})();

// ---- 05 why: chart --------------------------------------------------------------
(() => {
  const s = slide("Two kinds of leak. The coloured part is the cache's fault; the grey part the filter misses even when asked. The safe setting removes all of the first and none of the second.");
  label(s, "// 04 — Why the Simple Fixes Fail");
  title(s, "The cache's fault, separated from the filter's");
  s.addImage({ path: path.join(ROOT, "paper/figures/defence_poison_served.png"), x: 0.6, y: 1.8, w: 7.5, h: 7.5 * 899 / 1699 });
  const cx = 8.35, cw = 4.35;
  card(s, cx, 1.8, cw, 7.5 * 899 / 1699);
  s.addText("READING THIS CHART", { x: cx + 0.4, y: 2.1, w: 3.5, h: 0.26, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 11, color: GOLD });
  s.addText([
    { text: "Label match: ", options: { color: TEXT, bold: true } },
    { text: "stops poison saved as an attack, but a poison saved as clean looks like any honest answer.", options: { color: TEXT, breakLine: true } },
    { text: " ", options: { breakLine: true } },
    { text: "Risky-only re-check: ", options: { color: TEXT, bold: true } },
    { text: "the keyword label calls most real attacks harmless, so most are never re-checked.", options: { color: TEXT, breakLine: true } },
    { text: " ", options: { breakLine: true } },
    { text: "Every-hit re-check: ", options: { color: GREEN, bold: true } },
    { text: `zero cache-caused leaks. The grey ${p0(A.all.served.clean.filter_miss)} left is what the filter misses on its own.`, options: { color: TEXT } },
  ], { x: cx + 0.4, y: 2.5, w: cw - 0.75, h: 4.0, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 13, lineSpacingMultiple: 1.25, valign: "top" });
})();

// ---- 06 the cost -----------------------------------------------------------------
(() => {
  const s = slide("Answer the objection from Phase 2: screening costs time. It does, about 90 ms per hit. But the expensive part a cache saves is the model call, and that is still skipped.");
  label(s, "// 05 — What the Defence Costs");
  title(s, `About ${HIT_COST} ms per hit, and still no model call`);
  sub(s, "Median time for an honest cache hit, by setting, against a real model answer from the live router run.");
  const labels = [...ORDER.map((t) => NAMES[t].replace("Label match + re-check", "Match + re-check")), "Real model answer"];
  s.addChart(pres.ChartType.bar, [
    { name: "Median time (ms)", labels, values: [...ORDER.map((t) => Math.round(A[t].hit_p50_ms)), Math.round(RTR.model_ms_p50.cheap)] },
  ], {
    x: 0.6, y: 2.4, w: 7.4, h: 4.35, barDir: "bar", chartColors: [NAVY],
    showValue: true, dataLabelPosition: "outEnd", dataLabelFontFace: FONT, dataLabelFontSize: 10, dataLabelColor: MUTED,
    valAxisLabelFontFace: FONT, valAxisLabelFontSize: 10, valAxisLabelColor: MUTED, valAxisMinVal: 0, valAxisMaxVal: 2500, valAxisMajorUnit: 500,
    catAxisLabelFontFace: FONT, catAxisLabelFontSize: 10.5, catAxisLabelColor: TEXT, catAxisLineColor: LINE, catAxisOrientation: "maxMin",
    valGridLine: { color: LINE, size: 0.75 }, catGridLine: { style: "none" }, valAxisLineShow: false,
    showLegend: false, plotArea: { fill: { color: CREAM } },
  });
  const cx = 8.35, cw = 4.35;
  card(s, cx, 2.4, cw, 4.3);
  s.addText("WHAT THIS MEANS", { x: cx + 0.4, y: 2.7, w: 3.5, h: 0.26, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 11, color: GOLD });
  s.addText(`${Math.round(A.all.hit_p50_ms)} ms`, { x: cx + 0.4, y: 3.0, w: 1.9, h: 0.65, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 32, color: GOLD });
  s.addText("safe cache hit", { x: cx + 0.4, y: 3.62, w: 1.9, h: 0.3, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 11.5, color: MUTED });
  s.addText(`${REAL_S} s`, { x: cx + 2.2, y: 3.0, w: 1.9, h: 0.65, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 32, color: RED });
  s.addText("real model answer", { x: cx + 2.2, y: 3.62, w: 1.9, h: 0.3, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 11.5, color: MUTED });
  s.addShape(pres.ShapeType.line, { x: cx + 0.3, y: 4.15, w: cw - 0.6, h: 0, line: { color: LINE, width: 1 } });
  s.addText([
    { text: "In Phase 2 we said screening every request throws the speed-up away. ", options: { color: MUTED } },
    { text: "That holds for misses. ", options: { color: MUTED, breakLine: true } },
    { text: " ", options: { breakLine: true } },
    { text: "For hits, the safety check is cheap next to the model call, ", options: { color: TEXT } },
    { text: "and the hit is still free.", options: { color: GREEN, bold: true } },
  ], { x: cx + 0.4, y: 4.3, w: cw - 0.75, h: 2.25, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 13.5, lineSpacingMultiple: 1.25, valign: "top" });
})();

// ---- 07 corrections ----------------------------------------------------------------
(() => {
  const s = slide("Be upfront: two things we said in Phase 2 were too strong. Both are corrected in the paper.");
  label(s, "// 06 — Two Corrections to Phase 2");
  title(s, "What the new numbers changed");
  const rows = [
    ["WE SAID", "The filter scored every attack at 1.000.",
     "TRUE FOR", "The Phase 1 demo attack only.",
     "NOW", `On the public attacks it blocks ${p0(DEF.filter_blocks_alone)} of rewordings: 95 of 100 jayavibhav seeds, but only 55 of 139 deepset ones.`],
    ["WE SAID", "Filter-first gives 0% bypass.",
     "TRUE FOR", "Bypass = poison served and the filter never ran. With the filter first, it always runs.",
     "NOW", "About 30% of rewordings are still served poison there, because the filter itself lets them through. We now report that part separately."],
  ];
  rows.forEach((r, i) => {
    const y = 1.95 + i * 2.45;
    card(s, 0.6, y, 12.1, 2.2);
    [[r[0], r[1], 0.95, 3.4, NAVY], [r[2], r[3], 4.55, 3.6, MUTED], [r[4], r[5], 8.35, 4.1, TEXT]].forEach(([k, v, x, w, col], j) => {
      s.addText(k, { x, y: y + 0.3, w, h: 0.26, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 10.5, color: j === 2 ? GREEN : GOLD });
      s.addText(v, { x, y: y + 0.62, w, h: 1.4, isTextBox: true, margin: 0, fontFace: FONT, fontSize: j === 0 ? 16 : 13, color: col,
        italic: j === 0, lineSpacingMultiple: 1.15, valign: "top" });
    });
  });
})();

// ---- 08 router ------------------------------------------------------------------------
(() => {
  const s = slide("Real money, real calls. Easy questions get 92% cheaper. The overall saving depends on how much of the traffic is easy.");
  label(s, "// 07 — Cost-Aware Model Picker");
  title(s, "Easy questions cost 92% less");
  sub(s, `${RTR.questions} questions (${RTR.easy} easy, ${RTR.hard} hard), each sent twice through OpenRouter: once with the picker, once always to the strong model.`);
  const c = RTR.cost_by_label;
  const rows = [
    ["Easy questions", c.easy.strong, c.easy.router, GREEN],
    ["Hard questions", c.hard.strong, c.hard.router, TEXT],
    [`All ${RTR.questions}`, RTR.strong_cost_usd, RTR.router_cost_usd, TEXT],
  ];
  ["", "ALWAYS GPT-4O", "MODEL PICKER", "SAVED"].forEach((h, j) => s.addText(h, { x: [0.9, 3.3, 5.0, 6.7][j], y: 2.45, w: 1.7, h: 0.3,
    isTextBox: true, margin: 0, fontFace: FONT, fontSize: 10, color: GOLD, align: j ? "center" : "left" }));
  rows.forEach(([k, strong, router, col], i) => {
    const y = 2.85 + i * 0.85;
    card(s, 0.6, y, 7.4, 0.72, i % 2 ? ALT : WHITE);
    const saved = `${Math.round(100 * (1 - router / strong))}%`;
    [[k, 0.9, 2.4, NAVY, 14, "left"], [`$${strong.toFixed(5)}`, 3.3, 1.7, MUTED, 14, "center"],
     [`$${router.toFixed(5)}`, 5.0, 1.7, MUTED, 14, "center"], [saved, 6.7, 1.1, col, 20, "center"]].forEach(([v, x, w, colr, fs, al]) =>
      s.addText(v, { x, y, w, h: 0.72, isTextBox: true, margin: 0, fontFace: FONT, fontSize: fs, color: colr, align: al, valign: "middle" }));
  });
  s.addText(`Half this set is hard, and long hard answers are most of the bill. At 80% easy traffic the saving would be ${p0(RTR.projected_saving_by_mix["80% easy"])}, at 90% ${p0(RTR.projected_saving_by_mix["90% easy"])} (a projection).`,
    { x: 0.6, y: 5.55, w: 7.4, h: 0.9, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 12, italic: true, color: MUTED, lineSpacingMultiple: 1.15, valign: "top" });
  const cx = 8.35, cw = 4.35;
  card(s, cx, 2.45, cw, 4.2);
  s.addText("ALSO SHOWN LIVE", { x: cx + 0.4, y: 2.75, w: 3.5, h: 0.26, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 11, color: GOLD });
  s.addText(`${RTR.agrees_with_our_label} / ${RTR.questions}`, { x: cx + 0.4, y: 3.05, w: 3.6, h: 0.65, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 32, color: NAVY });
  s.addText("routed as we labelled them. The one miss still got a good answer.", { x: cx + 0.4, y: 3.7, w: 3.6, h: 0.5, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 11.5, color: MUTED, valign: "top" });
  s.addShape(pres.ShapeType.line, { x: cx + 0.3, y: 4.45, w: cw - 0.6, h: 0, line: { color: LINE, width: 1 } });
  s.addText([
    { text: "Failover: ", options: { color: TEXT, bold: true } },
    { text: "we named a model that does not exist. The call failed, the gateway retried on the fallback, and the user got a normal answer.", options: { color: TEXT } },
  ], { x: cx + 0.4, y: 4.6, w: cw - 0.75, h: 1.9, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 13, lineSpacingMultiple: 1.2, valign: "top" });
})();

// ---- 09 mitigations ------------------------------------------------------------------
(() => {
  const s = slide("Two more layers, both shown on the live gateway. The output guard even sees cached answers, which the input filter never did.");
  label(s, "// 08 — Output Guard and Rate Limit");
  title(s, "Two more safety layers, shown live");
  const panes = [
    ["OUTPUT GUARD", "A cached answer carrying a cookie-stealing script, asked with a reworded question.", [
      ["Off", "Script served from the cache", RED],
      ["Flag", "Served, marked in a header", GOLD],
      ["Block", "Refused with a 403", GREEN],
    ]],
    ["RATE LIMIT · 20 PER MINUTE", `${PROBES} attack probes from one caller in one burst, at a planted poisoned answer.`, [
      ["First 20", "Answered or blocked as normal", MUTED],
      ["The rest", `${demoCount("refused, rate limit")} refused with a 429`, GREEN],
      ["Other callers", "Unaffected", GREEN],
    ]],
  ];
  panes.forEach(([h, intro, rows], i) => {
    const x = 0.6 + i * 6.15, w = 5.95;
    card(s, x, 1.85, w, 4.85);
    s.addText(h, { x: x + 0.4, y: 2.15, w: w - 0.8, h: 0.28, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 11, color: GOLD });
    s.addText(intro, { x: x + 0.4, y: 2.5, w: w - 0.8, h: 0.8, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 13, italic: true, color: MUTED, lineSpacingMultiple: 1.15, valign: "top" });
    rows.forEach(([k, v, col], j) => {
      const y = 3.5 + j * 0.95;
      s.addShape(pres.ShapeType.roundRect, { x: x + 0.3, y, w: w - 0.6, h: 0.78, rectRadius: 0.07, fill: { color: j % 2 ? WHITE : ALT }, line: { color: LINE, width: 0.75 } });
      s.addText(k, { x: x + 0.55, y, w: 1.6, h: 0.78, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 14, color: NAVY, valign: "middle" });
      s.addText(v, { x: x + 2.1, y, w: w - 2.6, h: 0.78, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 14, color: col, bold: col !== MUTED, valign: "middle" });
    });
  });
})();

// ---- 10 architecture (native, simple) ----------------------------------------------
(() => {
  const s = slide("Walk the two paths again. The cache still goes first. A match is now checked again before it is served; a miss goes to the model picker. Every answer passes the output guard.");
  label(s, "// 09 — System Architecture");
  title(s, "What runs now: the hole is closed");
  sub(s, "The cache is still checked first, for speed. A hit now needs a matching label and passes a fresh safety check, without calling the model.", 1.65, false, 0.6);
  const box = (x, y, w, h, head, body, fill = WHITE, line = LINE, headColor = NAVY) => {
    card(s, x, y, w, h, fill, line);
    s.addText([{ text: head, options: { color: headColor, bold: true, fontSize: 13, breakLine: !!body } },
               ...(body ? [{ text: body, options: { color: MUTED, fontSize: 10 } }] : [])],
      { x: x + 0.1, y, w: w - 0.2, h, isTextBox: true, margin: 0, fontFace: FONT, align: "center", valign: "middle", lineSpacingMultiple: 1.1 });
  };
  const arrow = (x, y, w, h, color = MUTED) =>
    s.addShape(pres.ShapeType.line, { x, y, w, h, line: { color, width: 1.75, endArrowType: "triangle" } });
  const tag = (x, y, text, color) => s.addText(text, { x, y, w: 1.0, h: 0.26, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 10.5, color, align: "center" });
  const spine = 4.55, bh = 0.95;
  box(0.6, spine - bh / 2, 1.5, bh, "A question", "Nginx + rate limit");
  arrow(2.1, spine, 0.35, 0);
  box(2.45, spine - bh / 2, 2.1, bh, "① Cache lookup", "wording + safety label", "FBF3E4", GOLD);
  const cr = 4.55, lx = 5.45, topY = 3.0, botY = 5.15;
  arrow(cr, spine, lx - cr, topY + bh / 2 - spine, GREEN);
  tag(cr, 3.45, "match", GREEN);
  box(lx, topY, 2.55, bh, "② Re-check the hit", "same safety check, no model", "EEF5EF", GREEN, GREEN);
  arrow(cr, spine, lx - cr, botY + bh / 2 - spine);
  tag(cr + 0.2, 4.75, "no match", MUTED);
  box(lx, botY, 2.55, bh, "② Safety check", "deberta + Presidio");
  arrow(lx + 2.55, botY + bh / 2, 0.3, 0);
  box(lx + 2.85, botY, 1.75, bh, "③ Model picker", "cheap or strong", "FBF3E4", GOLD);
  const og = 10.55;
  arrow(lx + 2.55, topY + bh / 2, og - lx - 2.55, spine - topY - bh / 2, GREEN);
  arrow(lx + 4.6, botY + bh / 2, og - lx - 4.6, spine - botY - bh / 2);
  box(og, spine - bh / 2, 2.15, bh, "④ Output guard", "then store + log", "FBF3E4", GOLD);
  s.addText("Figure 1 — Gold and green mark what Phase 3 added. An attack is refused with 403 at either safety check.",
    { x: MX, y: 6.5, w: W - 2 * MX, h: 0.3, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 10.5, italic: true, color: MUTED, align: "center" });
})();

// ---- 11 timeline ------------------------------------------------------------------
(() => {
  const s = slide("Three phases done. Phase 4 measures everything properly and writes it up.");
  label(s, "// 10 — Timeline");
  title(s, "Project roadmap: August – November 2026");
  const phases = [
    ["18–22 AUG", "Phase 1 — Establish the Problem", "Offline proof-of-concept, threshold sweep, architecture definition, synopsis.", "COMPLETE", GREEN, WHITE, GREEN],
    ["23 AUG–26 SEP", "Phase 2 — Build the Gateway", "Reproduced the bypass on our own running system; first real bypass-rate figure.", "COMPLETE", GREEN, WHITE, GREEN],
    ["27 SEP–24 OCT", "Phase 3 — Build the Defence", "Verdict-tagged cache, re-checking, model picker, output guard, rate limits.", "COMPLETE", GREEN, WHITE, GREEN],
    ["25 OCT–14 NOV", "Phase 4 — Evaluate & Publish", "Load testing, ablation study, reproducible figures, research paper, final system.", "NEXT", GOLD, WHITE, GOLD],
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

// ---- 12 next phase plan -------------------------------------------------------------
(() => {
  const s = slide("Three weeks, one artefact each. Week 2 is the key one: the full results table, one row per layer.");
  label(s, "// 11 — Next Phase Plan");
  title(s, "Week-by-week plan: Phase 4 (25 Oct – 14 Nov)");
  sub(s, "Every week concludes with one demonstrable artefact, which also serves as that week's update to the supervisor.");
  const weeks = [
    ["W1", "25–31 Oct", "Load testing", "Locust against the full defended gateway; latency percentiles under many users at once.", "p50 and p99 per outcome under load, defence on and off.", false],
    ["W2", "1–7 Nov", "Ablation & false alarms", "Switch each layer off in turn; false-alarm rate on honest questions; a fresh question set for the picker.", "The full results table, one row per layer.", true],
    ["W3", "8–14 Nov", "Paper & reproducibility", "Final paper; one command rebuilds every number and chart from a fresh clone; final presentation.", "Submitted paper and a reproducible repository.", false],
  ];
  const cw = 3.95, gx = 0.125, x0 = 0.6, y0 = 2.35, ch = 4.4;
  weeks.forEach(([wk, d, h, b, out, key], i) => {
    const x = x0 + i * (cw + gx);
    card(s, x, y0, cw, ch);
    s.addShape(pres.ShapeType.roundRect, { x, y: y0, w: cw, h: 0.62, rectRadius: 0.07, fill: { color: key ? GOLD : NAVY }, line: { color: key ? GOLD : NAVY, width: 0 } });
    s.addShape(pres.ShapeType.rect, { x, y: y0 + 0.4, w: cw, h: 0.22, fill: { color: key ? GOLD : NAVY }, line: { color: key ? GOLD : NAVY, width: 0 } });
    s.addText(wk, { x: x + 0.3, y: y0, w: 1.5, h: 0.62, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 17, color: WHITE, valign: "middle" });
    s.addText(d, { x, y: y0 + 0.78, w: cw, h: 0.26, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 11, color: GOLD, align: "center" });
    s.addText(h, { x: x + 0.3, y: y0 + 1.15, w: cw - 0.6, h: 0.5, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 16, color: NAVY, valign: "top" });
    s.addText(b, { x: x + 0.3, y: y0 + 1.75, w: cw - 0.6, h: 1.3, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 12, color: MUTED, lineSpacingMultiple: 1.15, valign: "top" });
    s.addShape(pres.ShapeType.line, { x: x + 0.2, y: y0 + 3.2, w: cw - 0.4, h: 0, line: { color: LINE, width: 1 } });
    s.addText("OUTPUT", { x: x + 0.3, y: y0 + 3.33, w: 2, h: 0.24, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 10, color: GOLD });
    s.addText(out, { x: x + 0.3, y: y0 + 3.6, w: cw - 0.6, h: 0.7, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 12, italic: true, color: TEXT, lineSpacingMultiple: 1.1, valign: "top" });
  });
})();

// ---- 13 risks ---------------------------------------------------------------------
(() => {
  const s = slide("Be plain about the limits. None of them change the main result: re-checking every hit removes the risk the cache adds.");
  label(s, "// 12 — Outstanding Work & Risks");
  title(s, "What's still open, and how it's bounded");
  const risks = [
    ["KNOWN LIMIT", SLATE, "Filter accuracy", `The public filter blocks ${p0(DEF.filter_blocks_alone)} of these rewordings. Our fix removes the cache's extra risk, not the filter's own misses. Phase 4 reports each dataset.`],
    ["RESOLVED", GREEN, "Keyword labels", "The cheap label calls most real attacks harmless. Re-checking every hit does not depend on it, so the safe setting is unaffected."],
    ["PLANNED", GOLD, "Router evaluation", "The picker's rules were adjusted once on the same 40 questions, so 39 of 40 is optimistic. Phase 4 tests it on new questions."],
    ["TRACKED", BLUE, "Output guard coverage", "Plain patterns catch obvious payloads only. It is a second line of defence, not a complete one."],
  ];
  risks.forEach(([st, col, h, b], i) => {
    const y = 1.85 + i * 1.25;
    card(s, 0.6, y, 12.1, 1.1);
    pill(s, 0.85, y + 0.18, 1.85, 0.42, st, col);
    s.addText(h, { x: 3.0, y, w: 3.3, h: 1.1, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 15, color: NAVY, valign: "middle" });
    s.addText(b, { x: 6.4, y, w: 6.05, h: 1.1, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 12, color: MUTED, lineSpacingMultiple: 1.15, valign: "middle" });
  });
})();

// ---- 14 thank you -------------------------------------------------------------------
(() => {
  const s = slide("Close on the result and take questions.", "NAVY");
  s.addText("Thank You", { x: MX, y: 2.6, w: 8, h: 0.95, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 52, color: WHITE });
  s.addText("Questions and discussion", { x: MX, y: 3.55, w: 8, h: 0.45, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 19, italic: true, color: "D5DAE3" });
  s.addShape(pres.ShapeType.line, { x: MX - 0.08, y: 4.15, w: 3.0, h: 0, line: { color: GOLD, width: 1 } });
  s.addText("SentryGate — Security-Aware Semantic Caching Gateway for LLM Applications", { x: MX, y: 4.42, w: 10, h: 0.32, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 14, color: "A5ADBB" });
  s.addText("Divyansh Sharma · Sarvagya Dabas · Yashvit Gauri", { x: MX, y: 4.82, w: 10, h: 0.32, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 14, color: "A5ADBB" });
  s.addText("FINAL REVIEW — 14 NOVEMBER 2026", { x: MX, y: 6.85, w: 6, h: 0.3, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 12, color: GOLD });
})();

if (D.pageNo !== TOTAL) throw new Error(`expected ${TOTAL} slides, built ${D.pageNo}`);
const out = path.join(ROOT, "reports/out/SentryGate_Progress_Report_3.pptx");
fs.mkdirSync(path.dirname(out), { recursive: true });
pres.writeFile({ fileName: out }).then(() => console.log(`wrote reports/out/SentryGate_Progress_Report_3.pptx (${D.pageNo} slides)`));
