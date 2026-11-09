"""Turn midterm/draft.md into midterm/midterm-draft.pdf.

Takes the paper from "## 1. Introduction" to the end of the references (the drafting note
at the top and the notes for later sections are left out), adds a title block, and has
Edge print it: 12-point type, one-inch margins, page numbers. Prints any [CHECK] or
[placeholder] still in the text, so nothing unfinished goes out unnoticed.

    .venv/Scripts/python.exe asr-capstone/midterm/make_pdf.py
"""
import re
from pathlib import Path

import markdown
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
DRAFT = HERE / "draft.md"
HTML = HERE / "midterm-draft.html"
PDF = HERE / "midterm-draft.pdf"

TITLE = "When the Best Score Is Not the Best Record"
SUBTITLE = "How speech recognition engines and human transcribers handle ambiguous speech"
BYLINE = "Noah Collin · DATA 698 Capstone, CUNY School of Professional Studies · Midterm draft, 8 November 2026"

CSS = """
@page { size: Letter; margin: 1in; }
body { font-family: "Times New Roman", Times, serif; font-size: 12pt; line-height: 1.15;
       color: #000; }
h1.title { font-size: 17pt; text-align: center; margin: 0 0 4pt; }
p.subtitle { font-size: 12.5pt; text-align: center; font-style: italic; margin: 0 0 6pt; }
p.byline { font-size: 10.5pt; text-align: center; margin: 0 0 18pt; }
h2 { font-size: 13.5pt; margin: 16pt 0 4pt; break-after: avoid; }
h3 { font-size: 12pt; margin: 12pt 0 3pt; break-after: avoid; }
p { margin: 0 0 7pt; text-align: left; }
ul { margin: 0 0 7pt; padding-left: 20pt; }
li { margin-bottom: 3pt; }
table { border-collapse: collapse; width: 100%; font-size: 9pt; line-height: 1.2;
        margin: 4pt 0 10pt; break-inside: avoid; }
th, td { border: 0.5pt solid #999; padding: 3pt 4pt; vertical-align: top; text-align: left; }
th { background: #eee; }
img { display: block; max-width: 5.6in; max-height: 3.4in; margin: 6pt auto 2pt; }
p.figure { break-inside: avoid; break-after: avoid; }
p.caption { font-size: 10pt; margin-bottom: 10pt; break-inside: avoid; }
p.caption.table { break-after: avoid; margin-bottom: 3pt; }
code { font-family: Consolas, monospace; font-size: 10pt; }
.refs p { padding-left: 0.4in; text-indent: -0.4in; font-size: 10.5pt; margin-bottom: 3pt; }
"""


def paper_text():
    text = DRAFT.read_text(encoding="utf-8")
    start = text.index("## 1. Introduction")
    end = text.index("## Notes for later sections")
    body = text[start:end].rstrip().rstrip("-").rstrip()
    return body


def to_html(body):
    html = markdown.markdown(body, extensions=["tables", "sane_lists"])
    # Captions: a paragraph starting "Figure n." or "Table n." gets the caption style.
    html = re.sub(r"<p>(Figure \d+\.)", r'<p class="caption"><b>\1</b>', html)
    html = re.sub(r"<p>(Table \d+\.)", r'<p class="caption table"><b>\1</b>', html)
    html = re.sub(r"<p>(<img [^>]+>)</p>", r'<p class="figure">\1</p>', html)
    # Hanging indent for the reference list.
    i = html.find("<h2>References</h2>")
    if i >= 0:
        html = html[:i] + '<div class="refs">' + html[i:] + "</div>"
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>{TITLE}</title>
<style>{CSS}</style></head><body>
<h1 class="title">{TITLE}</h1><p class="subtitle">{SUBTITLE}</p><p class="byline">{BYLINE}</p>
{html}</body></html>"""


def main():
    body = paper_text()
    left = re.findall(r"\[(?:CHECK[^\]]*|repository link)\]", body)
    HTML.write_text(to_html(body), encoding="utf-8")
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge")
        page = browser.new_page()
        page.goto(HTML.as_uri())
        page.wait_for_load_state("networkidle")
        page.pdf(path=str(PDF), format="Letter", print_background=True,
                 margin={"top": "1in", "bottom": "1in", "left": "1in", "right": "1in"},
                 display_header_footer=True, header_template="<span></span>",
                 footer_template='<div style="font-size:9pt;width:100%;text-align:center;'
                                 'font-family:Times New Roman">'
                                 '<span class="pageNumber"></span></div>')
        browser.close()
    HTML.unlink()
    print("wrote", PDF)
    words = len(body.split())
    print(f"{words:,} words from the introduction to the end of the references")
    if left:
        print(f"\nStill marked in the text ({len(left)}):")
        for m in left:
            print("  ", m[:110])


if __name__ == "__main__":
    main()
