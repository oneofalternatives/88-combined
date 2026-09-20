#!/usr/bin/env python3
"""Rebuild the 1988/1989 suburban working timetable as a paginated HTML book.

Implements spec/ocr-book-format.md.
"""
from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path

SRC = Path("sources/ocr-playground-download-20260920T112147Z/1988-1989_приг_раб.pdf")
OUT = Path("build/1988-1989-prigorodnye-rabochie.html")

SIGNATURE_RE = re.compile(r"^\d+\s*(—\s*\d+|\\?\*)$")
FOLIO_RE = re.compile(r"^\d{1,3}$")


# ---------------------------------------------------------------- input model
def load_pages(src: Path):
    pages = []
    n = 1
    while (src / f"pages/page-{n}" / "page-metadata.json").exists():
        pages.append(json.loads((src / f"pages/page-{n}" / "page-metadata.json").read_text()))
        n += 1
    return pages


def is_noise(block) -> bool:
    c = block["content"].strip()
    return not c or FOLIO_RE.match(c) is not None or SIGNATURE_RE.match(c) is not None


def split_halves(page):
    """Return [blocks] for a portrait page, or [left, right] for a spread."""
    w = page["dimensions"]["width"]
    h = page["dimensions"]["height"]
    blocks = [b for b in page["blocks"] if not is_noise(b)]
    if w < h:  # portrait cover
        return [blocks]
    mid = w / 2
    left, right = [], []
    for b in blocks:
        (left if (b["topLeftX"] + b["bottomRightX"]) / 2 < mid else right).append(b)
    return [left, right]


def group_rows(blocks):
    """Group blocks that sit on the same visual line (spec §5.3)."""
    blocks = sorted(blocks, key=lambda b: (b["topLeftY"], b["topLeftX"]))
    rows: list[list[dict]] = []
    for b in blocks:
        if rows:
            row = rows[-1]
            top, bot = b["topLeftY"], b["bottomRightY"]
            rtop = min(x["topLeftY"] for x in row)
            rbot = max(x["bottomRightY"] for x in row)
            overlap = min(bot, rbot) - max(top, rtop)
            shorter = min(bot - top, rbot - rtop) or 1
            same_line = overlap > 0.5 * shorter
            clear_x = all(b["topLeftX"] >= x["bottomRightX"] or b["bottomRightX"] <= x["topLeftX"]
                          for x in row)
            if same_line and clear_x and b["type"] != "table" and all(x["type"] != "table" for x in row):
                row.append(b)
                continue
        rows.append([b])
    for row in rows:
        row.sort(key=lambda b: b["topLeftX"])
    return rows


# ------------------------------------------------------------ markdown tables
def parse_table(md: str):
    raw = [ln.strip() for ln in md.splitlines() if ln.strip().startswith("|")]
    rows = []
    for ln in raw:
        cells = ln.strip().strip("|").split("|")
        cells = [c.strip() for c in cells]
        if all(set(c) <= set("-: ") and c for c in cells):
            rows.append(None)  # separator
            continue
        rows.append(cells)
    if not rows:
        return None
    width = max(len(r) for r in rows if r)
    body = []
    header_count = 0
    seen_sep = False
    for r in rows:
        if r is None:
            seen_sep = True
            header_count = len(body)
            continue
        body.append(r + [""] * (width - len(r)))
    if not seen_sep:
        header_count = 0
    # rows right after the separator that only carry приб./отпр. are still head
    while header_count < len(body):
        cells = [c for c in body[header_count] if c]
        if cells and all(re.match(r"^(приб|отпр)\.?$", c) for c in cells):
            header_count += 1
        else:
            break
    return body, header_count, width


def render_table(md: str) -> str:
    parsed = parse_table(md)
    if not parsed:
        return f"<pre>{html.escape(md)}</pre>"
    rows, header_count, width = parsed
    out = ["<table class='tt'>"]
    for i, cells in enumerate(rows):
        head = i < header_count
        tag = "th" if head else "td"
        if i == 0:
            out.append("<thead>" if header_count else "<tbody>")
        elif i == header_count:
            out.append("</thead><tbody>")
        out.append("<tr>")
        j = 0
        while j < width:
            text = cells[j]
            span = 1
            if head:  # empty header cells continue the previous train column
                while j + span < width and not cells[j + span]:
                    span += 1
            cls = " class='st'" if j == 0 else ""
            attr = f" colspan='{span}'" if span > 1 else ""
            out.append(f"<{tag}{cls}{attr}>{inline(text)}</{tag}>")
            j += span
        out.append("</tr>")
    out.append("</tbody></table>")
    return "".join(out)


def inline(text: str) -> str:
    t = html.escape(text)
    t = re.sub(r"\^\{\}\[\]", "", t)          # stray OCR superscript artefacts
    t = re.sub(r"\\([*_])", r"\1", t)          # unescape markdown escapes
    t = t.replace("\n", "<br>")
    return t


# -------------------------------------------------------------- block render
def render_block(b) -> str:
    t = b["type"]
    c = b["content"].strip()
    if t == "table":
        return render_table(c)
    if t == "title" or c.startswith("#"):
        level = len(c) - len(c.lstrip("#"))
        text = c.lstrip("# ").strip()
        tag = "h2" if level <= 1 else "h3"
        return f"<{tag}>{inline(text)}</{tag}>"
    if t == "list":
        items = "".join(f"<li>{inline(x)}</li>" for x in c.splitlines() if x.strip())
        return f"<ul class='stations'>{items}</ul>"
    if t == "header" or t == "footer":
        return f"<div class='runhead'>{inline(c)}</div>"
    paras = [p for p in re.split(r"\n\s*\n", c) if p.strip()]
    return "".join(f"<p>{inline(p.strip())}</p>" for p in paras)


def align_of(b, width):
    centre = (b["topLeftX"] + b["bottomRightX"]) / 2
    if centre < width * 0.38:
        return "l"
    if centre > width * 0.62:
        return "r"
    return "c"


def render_half(blocks, half_width, folio, side):
    parts = []
    for row in group_rows(blocks):
        if len(row) == 1:
            b = row[0]
            parts.append(f"<div class='blk a-{align_of(b, half_width)}'>{render_block(b)}</div>")
        else:
            cells = "".join(
                f"<div class='blk a-{align_of(b, half_width)}'>{render_block(b)}</div>" for b in row
            )
            parts.append(f"<div class='row'>{cells}</div>")
    folio_html = f"<div class='folio'>{folio}</div>" if folio is not None else ""
    return f"<div class='page {side}'><div class='content'>{''.join(parts)}</div>{folio_html}</div>"


# --------------------------------------------------------------------- output
CSS = """
:root{
  --ink:#1c1a17; --paper:#fbf8f1; --rule:#b9ae9a; --ground:#d8d3c8;
  --book: "PT Sans Narrow","Liberation Sans Narrow","DejaVu Sans Condensed",
          "Arial Narrow","Noto Sans",system-ui,sans-serif;
}
:root:not([data-theme="light"]) { }
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){ --ground:#26241f; }
}
:root[data-theme="dark"]{ --ground:#26241f; }
body{ background:var(--ground); color:var(--ink); font-family:var(--book);
      padding-block:24px; padding-left:16px; padding-right:16px; }
.book{ display:flex; flex-direction:column; align-items:center; gap:28px; max-width:1600px; margin:0 auto; }
.sheet{ display:flex; flex-direction:row; justify-content:center; gap:0;
        width:100%; max-width:1180px; }
.sheet.single{ max-width:590px; }
.page{ position:relative; background:var(--paper); color:var(--ink);
       flex:1 1 0; min-width:0; aspect-ratio:509/821;
       box-shadow:0 2px 10px rgba(0,0,0,.35); overflow:hidden;
       container-type:inline-size; }
.page.left{ border-right:1px solid var(--rule); }
.page.portrait{ aspect-ratio:683/1019; }
.content{ position:absolute; inset:3.2% 4% 6% 4%; overflow:hidden;
          font-size:2.2cqw; line-height:1.28; }
.blk{ margin:0 0 .45em 0; }
.row{ display:flex; gap:.6em; align-items:flex-start; justify-content:space-between; }
.row > .blk{ flex:0 1 auto; margin-bottom:.35em; }
.a-c{ text-align:center; } .a-r{ text-align:right; } .a-l{ text-align:left; }
h2{ font-size:1.5em; margin:.5em 0 .4em; text-align:center; letter-spacing:.04em; }
h3{ font-size:1.2em; margin:.4em 0 .35em; text-align:center; letter-spacing:.03em; }
p{ margin:0 0 .4em; text-align:justify; hyphens:auto; }
.runhead{ font-size:1.05em; letter-spacing:.06em; text-transform:uppercase; }
ul.stations{ list-style:none; margin:0; padding:0; }
ul.stations li{ line-height:1.22; }
table.tt{ font-family:var(--book); width:100%; border-collapse:collapse;
          table-layout:fixed; font-variant-numeric:tabular-nums; }
table.tt th, table.tt td{ border:1px solid var(--rule); padding:.03em .18em;
          text-align:center; line-height:1.15; white-space:nowrap;
          overflow:hidden; text-overflow:ellipsis; }
table.tt th{ font-weight:600; }
table.tt .st{ text-align:left; width:27%; }
.folio{ position:absolute; bottom:2%; font-size:2.2cqw; }
.page.left .folio{ left:4%; } .page.right .folio,.page.portrait .folio{ right:4%; }
@media (max-width:900px){
  .sheet{ flex-direction:column; align-items:center; gap:18px; }
  .page{ width:100%; }
  .page.left{ border-right:none; }
}
"""


def build(src: Path, out: Path):
    pages = load_pages(src)
    sheets = []
    for n, page in enumerate(pages, start=1):
        halves = split_halves(page)
        w = page["dimensions"]["width"]
        if len(halves) == 1:
            sheets.append(
                "<div class='sheet single'>"
                + render_half(halves[0], w, None, "portrait")
                + "</div>"
            )
            continue
        left_folio = 2 * n - 4
        right_folio = 2 * n - 3
        if n == 2:
            left_folio = right_folio = None
        sheets.append(
            "<div class='sheet'>"
            + render_half(halves[0], w / 2, left_folio, "left")
            + render_half(halves[1], w / 2, right_folio, "right")
            + "</div>"
        )
    doc = (
        "<title>Служебное расписание 1988/1989</title>\n"
        f"<style>{CSS}</style>\n"
        "<div class='book'>\n" + "\n".join(sheets) + "\n</div>\n"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(doc, encoding="utf-8")
    return len(pages), len(doc)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", type=Path, default=SRC)
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args()
    n, size = build(a.src, a.out)
    print(f"{n} scan pages -> {a.out} ({size/1024:.0f} KiB)")
