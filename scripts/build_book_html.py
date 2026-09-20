#!/usr/bin/env python3
"""Render the 1988/1989 suburban working timetable as a paginated HTML book.

Layout logic lives in book_model.py; this file only adds the screen stylesheet.
See spec/ocr-book-format.md.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from book_model import SRC, fit_scale, render_half, sheets

OUT = Path("build/1988-1989-prigorodnye-rabochie.html")


CSS = """
:root{
  --ink:#1c1a17; --paper:#fbf8f1; --rule:#b9ae9a; --ground:#d8d3c8;
  --book: "PT Sans Narrow","Liberation Sans Narrow","DejaVu Sans Condensed",
          "Arial Narrow","Noto Sans",system-ui,sans-serif;
  --mono: "DejaVu Sans Mono","Liberation Mono","Noto Sans Mono",
          ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
}
:root:not([data-theme="light"]) { }
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){ --ground:#26241f; }
}
:root[data-theme="dark"]{ --ground:#26241f; }
body{ background:var(--ground); color:var(--ink); font-family:var(--book);
      padding-block:24px; padding-left:16px; padding-right:16px; }
.book{ display:flex; flex-direction:column; align-items:center; gap:28px; max-width:1600px; margin:0 auto; }
.sheet{ display:flex; flex-direction:row; justify-content:center; gap:10px;
        width:100%; max-width:1180px; }
.sheet.single{ max-width:590px; }
.page{ position:relative; background:var(--paper); color:var(--ink);
       flex:1 1 0; min-width:0; aspect-ratio:509/821;
       box-shadow:0 2px 10px rgba(0,0,0,.35); overflow:hidden;
       container-type:inline-size; }
.page.portrait{ aspect-ratio:683/1019; }
.content{ position:absolute; inset:3.2% 4% 6% 4%; overflow:hidden;
          font-size:calc(2.1cqw * var(--fit, 1)); line-height:1.28; }
.blk{ margin:0 0 .45em 0; }
.row{ display:flex; gap:.6em; align-items:flex-start; justify-content:space-between; }
.row > .blk{ flex:0 1 auto; margin-bottom:.35em; }
.a-c{ text-align:center; } .a-r{ text-align:right; } .a-l{ text-align:left; }
h2{ font-size:1.5em; margin:.5em 0 .4em; text-align:center; letter-spacing:.04em; }
h3{ font-size:1.2em; margin:.4em 0 .35em; text-align:center; letter-spacing:.03em; }
p{ margin:0 0 .4em; text-align:justify; hyphens:auto; }
.a-c p{ text-align:center; }
.a-r p{ text-align:right; }

.runhead{ font-size:1.05em; letter-spacing:.06em; text-transform:uppercase; }
ul.stations{ list-style:none; margin:0; padding:0; }
ul.stations li{ line-height:1.22; }
table.tt{ font-family:var(--mono); width:100%; border-collapse:collapse;
          table-layout:fixed; font-variant-numeric:tabular-nums; }
table.tt th, table.tt td{ border:1px solid var(--rule); padding:.03em .12em;
          text-align:center; line-height:1.15; white-space:nowrap;
          overflow:hidden; text-overflow:ellipsis; }
table.tt th{ font-weight:600; text-align:center; }
table.tt td{ text-align:left; }
table.tt .st{ text-align:left; width:29%; }
table.tt.prose th, table.tt.prose td{ white-space:normal; }
table.tt.prose{ table-layout:auto; }
table.tt.prose .st{ width:auto; }

.folio{ position:absolute; bottom:2%; font-size:calc(2.1cqw * var(--fit, 1)); }
.page.left .folio{ left:4%; } .page.right .folio,.page.portrait .folio{ right:4%; }
@media (max-width:900px){
  .sheet{ flex-direction:column; align-items:center; gap:18px; }
  .page{ width:100%; }
}
"""


def with_fit(markup: str, blocks) -> str:
    """Shrink a half page whose content would otherwise overflow the sheet."""
    scale = fit_scale(blocks)
    if scale >= 1.0:
        return markup
    return markup.replace("<div class='content'>",
                          f"<div class='content' style='--fit:{scale:.3f}'>", 1)


def build(src: Path, out: Path):
    body = []
    for sheet in sheets(src):
        cls = "sheet single" if sheet["kind"] == "cover" else "sheet"
        halves = "".join(with_fit(render_half(*h), h[0]) for h in sheet["halves"])
        body.append(f"<div class='{cls}'>{halves}</div>")
    doc = (
        "<title>Служебное расписание 1988/1989</title>\n"
        f"<style>{CSS}</style>\n"
        "<div class='book'>\n" + "\n".join(body) + "\n</div>\n"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(doc, encoding="utf-8")
    return len(body), len(doc)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", type=Path, default=SRC)
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args()
    n, size = build(a.src, a.out)
    print(f"{n} sheets -> {a.out} ({size/1024:.0f} KiB)")
