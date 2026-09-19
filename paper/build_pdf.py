"""Build paper/SentryGate-paper.pdf from paper/paper.md.

The Markdown file is the only source.
This script never adds words of its own, so the PDF cannot say anything the
paper does not.

Needs:
    pip install markdown
    Google Chrome (used headless to print the page to PDF)

Run:
    make paper-pdf
"""

from __future__ import annotations

import html
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    import markdown
except ImportError:
    sys.exit("Needs the markdown package:  pip install markdown")

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "paper.md"
OUTPUT = HERE / "SentryGate-paper.pdf"

CSS = """
@page {
  size: A4;
  margin: 24mm 22mm 24mm 22mm;
  @bottom-left  { content: "SentryGate · Progress draft"; font: 8pt -apple-system, "Helvetica Neue", Arial, sans-serif; color: #86868b; }
  @bottom-right { content: counter(page); font: 8pt -apple-system, "Helvetica Neue", Arial, sans-serif; color: #86868b; }
}
@page :first {
  @bottom-left  { content: none; }
  @bottom-right { content: none; }
}

:root {
  --ink: #1d1d1f;
  --muted: #6e6e73;
  --faint: #86868b;
  --hair: #d2d2d7;
  --surface: #f5f5f7;
  --accent: #0071e3;
}

* { box-sizing: border-box; }

html { -webkit-print-color-adjust: exact; print-color-adjust: exact; }

body {
  margin: 0;
  background: #fff;
  color: var(--ink);
  font-family: -apple-system, "SF Pro Text", "Helvetica Neue", Arial, sans-serif;
  font-size: 10.5pt;
  line-height: 1.6;
  letter-spacing: -0.003em;
  -webkit-font-smoothing: antialiased;
}

/* ---------- cover ---------- */
.cover {
  height: 247mm;
  display: flex;
  flex-direction: column;
  justify-content: center;
  break-after: page;
}
.cover .eyebrow {
  font-size: 9pt;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--accent);
  margin: 0 0 14pt;
}
.cover h1 {
  font-family: -apple-system, "SF Pro Display", "Helvetica Neue", Arial, sans-serif;
  font-size: 40pt;
  line-height: 1.05;
  font-weight: 700;
  letter-spacing: -0.025em;
  margin: 0 0 12pt;
}
.cover h1 + p {
  font-size: 19pt;
  line-height: 1.3;
  font-weight: 400;
  color: var(--muted);
  letter-spacing: -0.012em;
  margin: 0 0 44pt;
}
.cover p { margin: 0 0 6pt; }
.cover p:nth-of-type(2) strong { font-weight: 600; font-size: 11pt; }
.cover p:last-of-type strong { font-weight: 600; color: var(--muted); }
.cover p:nth-of-type(3) { color: var(--muted); font-size: 10pt; margin-bottom: 56pt; }
.cover p:last-of-type {
  max-width: 118mm;
  color: var(--faint);
  font-size: 9pt;
  line-height: 1.55;
  border-top: 0.5pt solid var(--hair);
  padding-top: 12pt;
  margin-top: auto;
}

/* ---------- headings ---------- */
h2, h3 {
  font-family: -apple-system, "SF Pro Display", "Helvetica Neue", Arial, sans-serif;
  break-after: avoid;
  letter-spacing: -0.018em;
}
h2 {
  font-size: 19pt;
  line-height: 1.2;
  font-weight: 700;
  margin: 30pt 0 10pt;
}
h3 {
  font-size: 12.5pt;
  font-weight: 600;
  margin: 20pt 0 6pt;
}
h2.newpage { break-before: page; margin-top: 0; }

p { margin: 0 0 9pt; orphans: 3; widows: 3; }
p.lead > strong {
  display: block;
  font-size: 10.5pt;
  font-weight: 600;
  margin-top: 14pt;
  margin-bottom: -4pt;
}

hr { border: 0; height: 0; margin: 0; }

ul, ol { margin: 0 0 10pt; padding-left: 16pt; }
li { margin: 0 0 4pt; padding-left: 2pt; }
li::marker { color: var(--faint); }

code {
  font-family: "SF Mono", Menlo, Consolas, monospace;
  font-size: 8.8pt;
  background: var(--surface);
  border-radius: 4pt;
  padding: 1pt 4pt;
}

/* ---------- tables ---------- */
table {
  width: 100%;
  border-collapse: collapse;
  margin: 6pt 0 16pt;
  font-size: 9.5pt;
  break-inside: avoid;
}
th {
  text-align: left;
  font-size: 7.5pt;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--faint);
  padding: 0 10pt 6pt 0;
  border-bottom: 0.75pt solid var(--ink);
}
td {
  padding: 6pt 10pt 6pt 0;
  border-bottom: 0.5pt solid var(--hair);
  vertical-align: top;
}
tr:last-child td { border-bottom: 0; }
td strong { font-weight: 600; }

/* ---------- pending notes ---------- */
blockquote {
  margin: 10pt 0 16pt;
  padding: 11pt 14pt 11pt 14pt;
  background: var(--surface);
  border-radius: 10pt;
  font-size: 9.5pt;
  line-height: 1.5;
  color: var(--muted);
  break-inside: avoid;
}
blockquote p { margin: 0; }
blockquote strong:first-child {
  display: block;
  font-size: 7.5pt;
  font-weight: 600;
  letter-spacing: 0.07em;
  text-transform: uppercase;
  color: var(--accent);
  margin-bottom: 3pt;
}

/* ---------- the one line to remember ---------- */
p.pull {
  font-family: -apple-system, "SF Pro Display", "Helvetica Neue", Arial, sans-serif;
  font-size: 17pt;
  line-height: 1.3;
  font-weight: 600;
  letter-spacing: -0.015em;
  margin: 18pt 0 22pt;
  max-width: 125mm;
}

/* ---------- figures ---------- */
figure {
  margin: 12pt 0 18pt;
  break-inside: avoid;
}
figure img {
  display: block;
  width: 100%;
  border-radius: 10pt;
  border: 0.5pt solid var(--hair);
  padding: 5pt;
  background: #fff;
}
figcaption {
  font-size: 8.5pt;
  line-height: 1.45;
  color: var(--faint);
  margin-top: 7pt;
  max-width: 140mm;
}
"""


def render(md_text: str) -> str:
    return markdown.markdown(md_text, extensions=["tables", "attr_list"], output_format="html5")


def to_figures(body: str) -> str:
    """A paragraph holding one image becomes a figure, with its alt text as the caption."""

    def repl(match: re.Match) -> str:
        src, alt = match.group("src"), html.unescape(match.group("alt"))
        path = (HERE / src).resolve()
        if not path.exists():
            sys.exit(f"Image not found: {src}")
        return (f'<figure><img src="{path.as_uri()}" alt="{html.escape(alt)}">'
                f"<figcaption>{html.escape(alt)}</figcaption></figure>")

    pattern = re.compile(r'<p><img alt="(?P<alt>[^"]*)" src="(?P<src>[^"]+)"\s*/?></p>')
    return pattern.sub(repl, body)


def build_html() -> str:
    text = SOURCE.read_text(encoding="utf-8")
    # Everything above the first rule is the cover.
    cover_md, _, body_md = text.partition("\n---\n")
    # The progress report and the list of what is left each open on a fresh page.
    body_md = re.sub(r"^(## 1[12]\. .*)$", r"\1 {: .newpage }", body_md, flags=re.M)
    cover = render(cover_md)
    body = to_figures(render(body_md))
    # A paragraph that is nothing but bold text is a small heading. CSS alone cannot
    # tell that apart from a sentence with one bold word, so it is marked here.
    body = re.sub(r"<p><strong>([^<]*)</strong></p>", r'<p class="lead"><strong>\1</strong></p>', body)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>SentryGate · Verdict-Tagged Semantic Caching</title>
<style>{CSS}</style></head>
<body>
<section class="cover"><div class="eyebrow">SentryGate</div>{cover}</section>
<main>{body}</main>
</body></html>"""


def find_chrome() -> str:
    candidates = {
        "Darwin": ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"],
        "Windows": [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ],
    }.get(platform.system(), [])
    candidates += [shutil.which(n) or "" for n in ("google-chrome", "chromium", "chromium-browser", "chrome")]
    for path in candidates:
        if path and os.path.exists(path):
            return path
    sys.exit("Google Chrome not found. Install it, or set CHROME to its path.")


def main() -> int:
    chrome = os.environ.get("CHROME") or find_chrome()
    with tempfile.TemporaryDirectory() as tmp:
        page = Path(tmp) / "paper.html"
        page.write_text(build_html(), encoding="utf-8")
        subprocess.run(
            [chrome, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
             "--allow-file-access-from-files", f"--print-to-pdf={OUTPUT}", page.as_uri()],
            check=True, capture_output=True, timeout=120,
        )
    print(f"wrote {OUTPUT.relative_to(HERE.parent)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
