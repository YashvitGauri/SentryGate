/*
 * Shared design of the team's progress-report decks (Progress Report 1 look):
 * warm cream slides, navy text, a gold accent, brick red for bad numbers and
 * green for good ones, Roboto, white rounded cards, "// 01 — SECTION" labels
 * and status pills.
 *
 * Each deck script only writes its own words and numbers:
 *   const { makeDeck, C } = require("./deck_common");
 *   const d = makeDeck("SentryGate · Progress Report 3");
 */

const pptxgen = require("pptxgenjs");

// ---- design tokens, sampled from Progress Report 1 -------------------------
const C = {
  CREAM: "F9F8F4", NAVY: "1B2433", GOLD: "C9A05A",
  RED: "B5452F", GREEN: "3F7A52", BLUE: "2D5A87", SLATE: "4A4F5A",
  TEXT: "1B2433", MUTED: "4A5260", FAINT: "6B7280",
  LINE: "E3DED2", ALT: "F3F1EA", WHITE: "FFFFFF", PILL: "F1EEE6",
  FONT: "Roboto", W: 13.333, H: 7.5, MX: 0.7,
};

function makeDeck(footer) {
  const { CREAM, NAVY, GOLD, MUTED, LINE, WHITE, FONT, W, MX } = C;
  const pres = new pptxgen();
  pres.layout = "LAYOUT_WIDE";
  pres.defineSlideMaster({ title: "CREAM", background: { color: CREAM } });
  pres.defineSlideMaster({ title: "NAVY", background: { color: NAVY } });

  const d = { pres, pageNo: 0 };
  d.slide = (notes, master = "CREAM") => {
    const s = pres.addSlide({ masterName: master });
    d.pageNo += 1;
    if (notes) s.addNotes(notes);
    if (master === "CREAM" && d.pageNo > 1) {
      s.addText(footer, { x: MX, y: 7.0, w: 5, h: 0.3, isTextBox: true, margin: 0,
        fontFace: FONT, fontSize: 9.5, color: MUTED });
      s.addText(String(d.pageNo).padStart(2, "0"), { x: W - 1.4, y: 7.0, w: 0.9, h: 0.3, isTextBox: true, margin: 0,
        fontFace: FONT, fontSize: 10, color: MUTED, align: "right" });
    }
    return s;
  };
  d.label = (s, text, y = 0.47) => {
    s.addText(text.toUpperCase(), { x: MX, y, w: 10, h: 0.3, isTextBox: true, margin: 0,
      fontFace: FONT, fontSize: 12, color: GOLD });
  };
  d.title = (s, text, y = 0.85) => {
    s.addText(text, { x: MX, y, w: W - 2 * MX, h: 0.75, isTextBox: true, margin: 0,
      fontFace: FONT, fontSize: 31, color: NAVY, valign: "middle" });
  };
  d.sub = (s, text, y = 1.7, italic = true, h = 0.5) => {
    s.addText(text, { x: MX, y, w: W - 2 * MX, h, isTextBox: true, margin: 0,
      fontFace: FONT, fontSize: 13.5, italic, color: MUTED, lineSpacingMultiple: 1.15, valign: "top" });
  };
  d.card = (s, x, y, w, h, fill = WHITE, line = LINE) => {
    s.addShape(pres.ShapeType.roundRect, { x, y, w, h, rectRadius: 0.07,
      fill: { color: fill }, line: { color: line, width: 1 } });
  };
  d.pill = (s, x, y, w, h, text, fill, color = WHITE) => {
    s.addShape(pres.ShapeType.roundRect, { x, y, w, h, rectRadius: h / 2, fill: { color: fill }, line: { color: fill, width: 0 } });
    s.addText(text, { x, y, w, h, isTextBox: true, margin: 0, fontFace: FONT, fontSize: 11,
      color, align: "center", valign: "middle" });
  };
  return d;
}

module.exports = { C, makeDeck };
