#!/usr/bin/env python3
"""Shared model for the 1988/1989 suburban working timetable.

Parses the Mistral OCR export into book pages and renders each block to HTML
per spec/ocr-book-format.md. Consumed by build_book_html.py (screen) and
build_book_pdf.py (print); both share this layout logic so the two outputs
never drift apart.
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

SRC = Path("sources/ocr-playground-download-20260920T112147Z/1988-1989_приг_раб.pdf")

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
    # Timetables are wide (a station column plus приб./отпр. pairs); a narrow
    # table is prose — the contents list — and its cells must wrap, not clip.
    cls = "tt" if width > 3 else "tt prose"
    out = [f"<table class='{cls}'>"]
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


def align_of(b, width, x_offset=0.0):
    centre = (b["topLeftX"] + b["bottomRightX"]) / 2 - x_offset
    if centre < width * 0.38:
        return "l"
    if centre > width * 0.62:
        return "r"
    return "c"


# A half page holds roughly this many table rows at the nominal font size;
# calibrated against the densest chapter-I timetable (46 rows, ~88% full).
ROW_CAPACITY = 47.0


def estimate_rows(blocks) -> float:
    """Rough content height of a half page, measured in table rows."""
    rows = 0.0
    for b in blocks:
        c = b["content"].strip()
        if b["type"] == "table":
            parsed = parse_table(c)
            rows += len(parsed[0]) if parsed else 0
        elif b["type"] == "list":
            rows += 0.85 * len([x for x in c.splitlines() if x.strip()])
        elif b["type"] == "title" or c.startswith("#"):
            rows += 2.0
        else:  # prose: ~60 characters to the line, plus paragraph spacing
            lines = sum(max(1, len(p) / 60) for p in re.split(r"\n\s*\n", c) if p.strip())
            rows += 0.9 * lines + 0.4
    return rows


def fit_scale(blocks) -> float:
    """Font scale that keeps an over-full half page from clipping."""
    needed = estimate_rows(blocks)
    return min(1.0, ROW_CAPACITY / needed) if needed > ROW_CAPACITY else 1.0


def render_half(blocks, half_width, folio, side, x_offset=0.0):
    parts = []
    for row in group_rows(blocks):
        if len(row) == 1:
            b = row[0]
            parts.append(f"<div class='blk a-{align_of(b, half_width, x_offset)}'>{render_block(b)}</div>")
        else:
            cells = "".join(
                f"<div class='blk a-{align_of(b, half_width, x_offset)}'>{render_block(b)}</div>" for b in row
            )
            parts.append(f"<div class='row'>{cells}</div>")
    folio_html = f"<div class='folio'>{folio}</div>" if folio is not None else ""
    return f"<div class='page {side}'><div class='content'>{''.join(parts)}</div>{folio_html}</div>"


# ----------------------------------------------------------------- pagination
def sheets(src: Path):
    """Yield one dict per physical sheet of the book.

    {'kind': 'cover'|'spread', 'halves': [(blocks, half_width, folio, side), ...]}
    """
    for n, page in enumerate(load_pages(src), start=1):
        halves = split_halves(page)
        w = page["dimensions"]["width"]
        if len(halves) == 1:
            yield {"kind": "cover", "halves": [(halves[0], w, None, "portrait", 0.0)]}
            continue
        left_folio, right_folio = 2 * n - 4, 2 * n - 3
        if n == 2:  # inside front cover + title page carry no printed folio
            left_folio = right_folio = None
        yield {
            "kind": "spread",
            "halves": [
                (halves[0], w / 2, left_folio, "left", 0.0),
                (halves[1], w / 2, right_folio, "right", w / 2),
            ],
        }
