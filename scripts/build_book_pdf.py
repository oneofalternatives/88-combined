#!/usr/bin/env python3
"""Render the 1988/1989 suburban working timetable as a print-ready PDF.

Shares all layout logic with the HTML build (book_model.py); only the
stylesheet differs — absolute print units instead of container queries, one PDF
page per physical sheet of the book. See spec/ocr-book-format.md.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from book_model import (BOOK, SRC, book_fit_scale, book_sheets, fit_scale,
                        render_book_half, render_half, sheets)

OUT = Path("build/1988-1989-prigorodnye-rabochie.pdf")

# Sheet geometry, taken from the scan dimensions (spec §2):
#   spread half 509x821 px @128 dpi -> 101.0 x 162.9 mm
#   cover      683x1019 px @159 dpi -> 109.1 x 162.8 mm
HALF_W_MM = 101.0
SPREAD_W_MM = 2 * HALF_W_MM
COVER_W_MM = 109.1
PAGE_H_MM = 162.9

CSS = f"""
@page spread {{ size: {SPREAD_W_MM}mm {PAGE_H_MM}mm; margin: 0; }}
@page cover  {{ size: {COVER_W_MM}mm {PAGE_H_MM}mm; margin: 0; }}

:root{{
  --ink:#1c1a17; --rule:#8d8471;
  --book: "Liberation Sans Narrow","DejaVu Sans","Noto Sans",sans-serif;
  --mono: "DejaVu Sans Mono","Liberation Mono","Noto Sans Mono",monospace;
}}
html, body {{ margin:0; padding:0; background:#fff; color:var(--ink);
              font-family:var(--book); }}

.sheet{{ position:relative; width:{SPREAD_W_MM}mm; height:{PAGE_H_MM}mm;
        page: spread; }}
.sheet.single{{ width:{COVER_W_MM}mm; page: cover; }}
.sheet + .sheet{{ break-before: page; }}

.page{{ position:absolute; top:0; height:{PAGE_H_MM}mm; width:{HALF_W_MM}mm;
       overflow:hidden; }}
.page.left{{ left:0; border-right:0.2pt solid var(--rule); }}
.page.right{{ left:{HALF_W_MM}mm; }}
.page.portrait{{ left:0; width:{COVER_W_MM}mm; }}

.content{{ position:absolute; top:5mm; left:4mm; right:4mm; bottom:9mm;
          overflow:hidden; font-size:calc(6.1pt * var(--fit, 1)); line-height:1.25; }}
.blk{{ margin:0 0 .45em 0; }}
.row{{ display:flex; gap:.6em; align-items:flex-start; justify-content:space-between; }}
.row > .blk{{ margin-bottom:.35em; }}
.a-c{{ text-align:center; }} .a-r{{ text-align:right; }} .a-l{{ text-align:left; }}

h2{{ font-size:1.5em; margin:.5em 0 .4em; text-align:center; letter-spacing:.04em; }}
h3{{ font-size:1.2em; margin:.4em 0 .35em; text-align:center; letter-spacing:.03em; }}
p{{ margin:0 0 .4em; text-align:justify; hyphens:auto; }}
.a-c p{{ text-align:center; }}
.a-r p{{ text-align:right; }}

.runhead{{ font-size:1.05em; letter-spacing:.06em; text-transform:uppercase; }}
ul.stations{{ list-style:none; margin:0; padding:0; }}
ul.stations li{{ line-height:1.22; }}

table.tt{{ font-family:var(--mono); width:100%; border-collapse:collapse;
          table-layout:fixed; font-size:.95em; }}
table.tt tr.ruled > *{{ border-top:1.4pt solid var(--ink); }}
table.tt tr.band > td{{ text-align:center; font-weight:600; letter-spacing:.04em; }}
table.tt th, table.tt td{{ border:0.2pt solid var(--rule); padding:.15em .12em;
          line-height:1.15; white-space:nowrap; overflow:hidden; }}
table.tt th{{ font-weight:600; text-align:center; }}
table.tt td{{ text-align:left; }}
table.tt .st{{ text-align:left; width:29%; }}
table.tt.prose th, table.tt.prose td{{ white-space:normal; }}
table.tt.prose{{ table-layout:auto; }}
table.tt.prose .st{{ width:auto; }}


.folio{{ position:absolute; bottom:3mm; font-size:6pt; }}
.page.left .folio{{ left:4mm; }}
.page.right .folio, .page.portrait .folio{{ right:4mm; }}
"""


def source(a):
    """(sheets, half renderer, fit estimator) for the chosen input.

    book/ is the default: it is the hand-corrected source of truth. --from-ocr
    renders the raw OCR export instead, which is what makes a correction
    visible -- build both and compare the same sheet.
    """
    if a.from_ocr:
        return sheets(a.src), render_half, fit_scale
    return book_sheets(a.book), render_book_half, book_fit_scale


def with_fit(markup: str, content, fit) -> str:
    """Shrink a half page whose content would otherwise overflow the sheet."""
    scale = fit(content)
    if scale >= 1.0:
        return markup
    return markup.replace("<div class='content'>",
                          f"<div class='content' style='--fit:{scale:.3f}'>", 1)


def build_html(a) -> str:
    body = []
    pages, render, fit = source(a)
    for sheet in pages:
        cls = "sheet single" if sheet["kind"] == "cover" else "sheet"
        halves = "".join(with_fit(render(*h), h[0], fit) for h in sheet["halves"])
        body.append(f"<div class='{cls}'>{halves}</div>")
    return (
        "<meta charset='utf-8'>"
        "<title>Служебное расписание 1988/1989</title>"
        f"<style>{CSS}</style>\n" + "\n".join(body) + "\n"
    )


def build(a, out: Path):
    from weasyprint import HTML  # imported late so --dump-html works without it

    out.parent.mkdir(parents=True, exist_ok=True)
    HTML(string=build_html(a), base_url=str(Path.cwd())).write_pdf(str(out))
    return out.stat().st_size


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", type=Path, default=BOOK)
    ap.add_argument("--src", type=Path, default=SRC)
    ap.add_argument("--from-ocr", action="store_true",
                    help="render the raw OCR export instead of book/")
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--dump-html", type=Path, help="write the print HTML and stop")
    a = ap.parse_args()
    if a.dump_html:
        a.dump_html.write_text(build_html(a), encoding="utf-8")
        print(f"print HTML -> {a.dump_html}")
    else:
        size = build(a, a.out)
        print(f"{a.out} ({size/1024/1024:.1f} MiB)")
