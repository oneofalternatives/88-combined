#!/usr/bin/env python3
"""Shared model for the 1988/1989 suburban working timetable.

Two halves, one per stage of the pipeline: the OCR export is parsed and
repaired for scripts/extract.py, and attempts/final-NN — the hand-corrected
result — is parsed and rendered to HTML for scripts/build_book_pdf.py. Nothing
renders the OCR directly; see spec/ocr-book-format.md.
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

SIGNATURE_RE = re.compile(r"^\d+\s*(—\s*\d+|\\?\*)$")
FOLIO_RE = re.compile(r"^\d{1,3}$")


# ---------------------------------------------------------------- input model
def _camel(x):
    """API responses use top_left_x; the playground export, topLeftX."""
    if isinstance(x, dict):
        return {re.sub(r"_(\w)", lambda m: m.group(1).upper(), k): _camel(v) for k, v in x.items()}
    return [_camel(v) for v in x] if isinstance(x, list) else x


def load_pages(src: Path):
    """Pages of an OCR attempt: a playground export, or ocr.py's page-NN.json."""
    pages = []
    n = 1
    while True:
        if (f := src / f"pages/page-{n}" / "page-metadata.json").exists():
            pages.append(json.loads(f.read_text()))
        elif (f := src / f"page-{n:02d}.json").exists():
            pages.append(_camel(json.loads(f.read_text())["pages"][0]))
        else:
            return pages
        n += 1


def is_noise(block) -> bool:
    c = block["content"].strip()
    return not c or FOLIO_RE.match(c) is not None or SIGNATURE_RE.match(c) is not None


def split_halves(page):
    """Return [blocks] for a portrait page, or [left, right] for a spread."""
    w = page["dimensions"]["width"]
    h = page["dimensions"]["height"]
    blocks = [b for b in page["blocks"] if not is_noise(b)]
    if w < h:  # portrait cover
        return [repair(blocks)]
    mid = w / 2
    left, right = [], []
    for b in blocks:
        (left if (b["topLeftX"] + b["bottomRightX"]) / 2 < mid else right).append(b)
    return [repair(left), repair(right)]


# ------------------------------------------------------- OCR damage repair
# A timetable column whose train times are all blank defeats the OCR: it loses
# the column count. The damage comes in two shapes, both repaired here against
# the "№ поездов" header block, which survives intact and carries the true
# width: a table emitted too narrow, and a station column demoted to loose
# list/text blocks. See spec/ocr-book-format.md.
TIME_RE = re.compile(r"\d[.,]\d")


def header_width(blocks):
    """Column count of this half page, from its train-number header."""
    for b in blocks:
        if b["type"] == "table" and "№ поездов" in b["content"]:
            parsed = parse_table(b["content"].strip())
            if parsed and parsed[2] > 3:
                return parsed[2]
    return None


def station_span(blocks):
    """x-range of the station column, from the header block."""
    for b in blocks:
        if b["type"] == "table" and "№ поездов" in b["content"]:
            return b["topLeftX"], b["bottomRightX"] - b["topLeftX"]
    return None, None


def is_station_block(b, left, span) -> bool:
    """A stray block that is really a station name in the station column.

    Route captions and footnotes also arrive as text, but they sit well to the
    right and run wide; a disintegrated row of times is excluded outright.
    """
    if b["type"] not in ("list", "text"):
        return False
    if TIME_RE.search(b["content"]):
        return False
    return (b["topLeftX"] - left <= 0.12 * span
            and b["bottomRightX"] - b["topLeftX"] <= 0.30 * span)


def as_table(run, width):
    """Fuse a run of station blocks into one table of blank time cells."""
    names = []
    for b in run:
        names += [ln.strip() for ln in b["content"].splitlines() if ln.strip()]
    pad = " |" * (width - 1)
    return {
        "type": "table",
        "content": "\n".join(f"|  {n} |{pad}" for n in names),
        "topLeftX": min(b["topLeftX"] for b in run),
        "topLeftY": min(b["topLeftY"] for b in run),
        "bottomRightX": max(b["bottomRightX"] for b in run),
        "bottomRightY": max(b["bottomRightY"] for b in run),
    }


def repair(blocks):
    """Restore the true column count across one half page."""
    width = header_width(blocks)
    if not width:
        return blocks
    left, span = station_span(blocks)
    out, run = [], []
    for b in sorted(blocks, key=lambda b: (b["topLeftY"], b["topLeftX"])):
        if is_station_block(b, left, span):
            run.append(b)
            continue
        if run:
            out.append(as_table(run, width))
            run = []
        if b["type"] == "table":
            parsed = parse_table(b["content"].strip())
            if parsed and parsed[2] < width:
                b = dict(b, content=pad_table(b["content"].strip(), width))
        out.append(b)
    if run:
        out.append(as_table(run, width))
    return out


def pad_table(md: str, width: int) -> str:
    """Widen a table the OCR emitted short, keeping its separator row."""
    lines = []
    for ln in md.splitlines():
        t = ln.strip()
        if not t.startswith("|"):
            lines.append(ln)
            continue
        cells = [c.strip() for c in t.strip("|").split("|")]
        if len(cells) < width:
            fill = "---" if all(set(c) <= set("-: ") and c for c in cells) else ""
            cells += [fill] * (width - len(cells))
        lines.append("|  " + " | ".join(cells) + "  |")
    return "\n".join(lines)


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
    # A row right after the separator that only carries приб./отпр. is still
    # head: the book stacks train numbers over a приб./отпр. pair, and GFM can
    # mark just one row as heading, so the OCR leaves the second one in the
    # body. Its first cell is the station column's own label ("Разд. пункты"),
    # so only the cells beyond it are tested.
    while header_count < len(body):
        cells = [c for c in body[header_count][1:] if c]
        if cells and all(re.match(r"^(приб|отпр)\.?$", c, re.I) for c in cells):
            header_count += 1
        else:
            break
    return body, header_count, width


def inline(text: str) -> str:
    t = html.escape(text)
    t = re.sub(r"\^\{\}\[\]", "", t)          # stray OCR superscript artefacts
    t = re.sub(r"\\([*_])", r"\1", t)          # unescape markdown escapes
    t = t.replace("\n", "<br>")
    return t


# A half page holds roughly this many table rows at the nominal font size;
# calibrated against the densest chapter-I timetable (46 rows, ~88% full).
ROW_CAPACITY = 47.0


# ------------------------------------------------------------- book pages as input
# From here down the input is attempts/final-NN/page-NN.md, not the OCR: the hand-corrected
# source of truth. Its tables are markdown-LIKE (see extract.as_markdown) --
# "=" rules the head, "-" rules the interior, a one-cell row is a full-width
# band -- so they are read here rather than by parse_table, which speaks GFM.
RULE_CHARS = set("-=: ")


def parse_book_table(md: str):
    """{items, width, header_rows} for one table of a book page."""
    raw = []
    for ln in md.splitlines():
        t = ln.strip()
        if not t.startswith("|"):
            continue
        cells = [c.strip() for c in t.strip("|").split("|")]
        if cells and all(c and set(c) <= RULE_CHARS for c in cells):
            raw.append(("head_rule" if any("=" in c for c in cells) else "rule", None))
        else:
            raw.append(("cells", cells))
    width = max((len(c) for k, c in raw if k == "cells"), default=0)
    items, header_rows, seen = [], 0, 0
    for kind, cells in raw:
        if kind == "head_rule":
            header_rows = seen
        elif kind == "rule":
            items.append({"kind": "rule"})
        elif len(cells) == 1 and width > 1:
            items.append({"kind": "band", "text": cells[0]})
        else:
            items.append({"kind": "row", "cells": cells + [""] * (width - len(cells))})
            seen += 1
    n = 0
    for it in items:  # the first header_rows data rows are the heading
        if it["kind"] == "row":
            if n < header_rows:
                it["kind"] = "head"
            n += 1
    return {"items": items, "width": width, "header_rows": header_rows}


def parse_book_page(text: str):
    """{sheet, kind, shapes, halves:[{folio, items}]} for one book page file."""
    lines = text.splitlines()
    meta, i = {}, 0
    if lines and lines[0].strip() == "---":
        i = 1
        while i < len(lines) and lines[i].strip() != "---":
            k, _, v = lines[i].partition(":")
            meta[k.strip()] = v.strip()
            i += 1
        i += 1
    halves, buf = [], None
    for ln in lines[i:]:
        if ln.startswith("## page"):
            folio = ln[len("## page"):].strip()
            buf = {"folio": int(folio) if folio.isdigit() else None, "lines": []}
            halves.append(buf)
        elif buf is not None:
            buf["lines"].append(ln)
    for h in halves:
        h["items"] = book_items(h.pop("lines"))
    return {
        "sheet": int(meta.get("sheet", 0) or 0),
        "kind": meta.get("kind", "spread"),
        "shapes": [s.strip() for s in meta.get("shapes", "").strip("[] ").split(",") if s.strip()],
        "halves": halves,
    }


def book_items(lines):
    """One half page as a list of blocks, blank-line separated."""
    items, buf = [], []

    def flush():
        text = "\n".join(buf).strip()
        buf.clear()
        if not text:
            return
        if text.startswith("|"):
            items.append({"kind": "table", "table": parse_book_table(text)})
        elif text.startswith("#"):
            items.append({"kind": "heading", "text": text.lstrip("# ").strip()})
        else:
            items.append({"kind": "para", "text": text})

    for ln in lines:
        buf.append(ln) if ln.strip() else flush()
    flush()
    # Paragraphs above the first table are the caption printed over it: train
    # numbers and route. Below it they are ordinary prose (notes, contents).
    if any(it["kind"] == "table" for it in items):
        for it in items:
            if it["kind"] == "table":
                break
            if it["kind"] == "para":
                it["kind"] = "caption"
    return items


def render_book_table(t) -> str:
    cls = "tt" if t["width"] > 3 else "tt prose"
    out = [f"<table class='{cls}'>"]
    opened_head = opened_body = False
    ruled = False
    for it in t["items"]:
        if it["kind"] == "rule":
            ruled = True
            continue
        klass = " class='ruled'" if ruled else ""
        ruled = False
        if it["kind"] == "band":
            if not opened_body:
                out.append("</thead>" if opened_head else "")
                out.append("<tbody>")
                opened_body = True
            out.append(f"<tr class='band{' ruled' if klass else ''}'>"
                       f"<td colspan='{t['width']}'>{inline(it['text'])}</td></tr>")
            continue
        head = it["kind"] == "head"
        if head and not opened_head:
            out.append("<thead>")
            opened_head = True
        if not head and not opened_body:
            out.append("</thead>" if opened_head else "")
            out.append("<tbody>")
            opened_body = True
        tag = "th" if head else "td"
        cells = it["cells"]
        out.append(f"<tr{klass}>")
        j = 0
        while j < t["width"]:
            span = 1
            if head:  # an empty header cell continues the train column beside it
                while j + span < t["width"] and not cells[j + span]:
                    span += 1
            st = " class='st'" if j == 0 else ""
            attr = f" colspan='{span}'" if span > 1 else ""
            out.append(f"<{tag}{st}{attr}>{inline(cells[j])}</{tag}>")
            j += span
        out.append("</tr>")
    out.append("</tbody>" if opened_body else "</thead>" if opened_head else "")
    out.append("</table>")
    return "".join(x for x in out if x)


def render_book_half(items, folio, side) -> str:
    parts = []
    for it in items:
        if it["kind"] == "table":
            parts.append(f"<div class='blk'>{render_book_table(it['table'])}</div>")
        elif it["kind"] == "caption":
            parts.append(f"<div class='blk a-c'><div class='runhead'>"
                         f"{inline(it['text'])}</div></div>")
        elif it["kind"] == "heading":
            parts.append(f"<div class='blk a-c'><h3>{inline(it['text'])}</h3></div>")
        else:
            paras = "".join(f"<p>{inline(p.strip())}</p>"
                            for p in re.split(r"\n\s*\n", it["text"]) if p.strip())
            parts.append(f"<div class='blk a-l'>{paras}</div>")
    folio_html = f"<div class='folio'>{folio}</div>" if folio is not None else ""
    return (f"<div class='page {side}'><div class='content'>"
            f"{''.join(parts)}</div>{folio_html}</div>")


def estimate_book_rows(items) -> float:
    """Content height of a book half page, in table rows (cf. estimate_rows)."""
    rows = 0.0
    for it in items:
        if it["kind"] == "table":
            rows += sum(1 for x in it["table"]["items"] if x["kind"] != "rule")
        elif it["kind"] == "heading":
            rows += 2.0
        else:
            lines = sum(max(1, len(p) / 60)
                        for p in re.split(r"\n\s*\n", it["text"]) if p.strip())
            rows += 0.9 * lines + 0.4
    return rows


def book_fit_scale(items) -> float:
    needed = estimate_book_rows(items)
    return min(1.0, ROW_CAPACITY / needed) if needed > ROW_CAPACITY else 1.0


def book_sheets(src: Path):
    """Yield one dict per sheet, shaped like sheets() but read from book pages."""
    n = 1
    while (src / f"page-{n:02d}.md").exists():
        page = parse_book_page((src / f"page-{n:02d}.md").read_text())
        halves = page["halves"]
        if page["kind"] == "cover" or len(halves) < 2:
            yield {"kind": "cover",
                   "halves": [(halves[0]["items"], halves[0]["folio"], "portrait")]}
        else:
            yield {"kind": "spread", "halves": [
                (halves[0]["items"], halves[0]["folio"], "left"),
                (halves[1]["items"], halves[1]["folio"], "right")]}
        n += 1
