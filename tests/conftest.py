"""Shared setup: scripts/ on the import path, paths to the frozen data, and
builders for small hand-made OCR pages and book/ pages.

The scripts use paths relative to the repo root (attempts/, book/). Tests pass
absolute paths, or chdir into a tmp dir that mimics the layout.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "scripts"
sys.path.insert(0, str(SCRIPTS))

# Frozen reference data. book/ is hand-corrected over time, so regression
# tests compare against medium-00, the untouched extractor output it came from.
OCR_00 = REPO / "attempts" / "ocr-00"
MEDIUM_00 = REPO / "attempts" / "medium-00"

# Spread geometry of the real scans (spec/ocr-book-format.md §2).
SPREAD = {"width": 1019, "height": 821}
COVER = {"width": 683, "height": 1019}

INDEX_HEAD = """# Attempts

| #   | source | renders | ocr | medium | note |
| --- | ------ | ------- | --- | ------ | ---- |
"""


def block(type_, content, x0, y0, x1, y1):
    """One OCR block, playground (camelCase) format."""
    return {"type": type_, "content": content, "topLeftX": x0, "topLeftY": y0,
            "bottomRightX": x1, "bottomRightY": y1}


def page(blocks, dims=SPREAD):
    return {"dimensions": dict(dims), "blocks": blocks}


SUBURBAN_TABLE = """\
|  № поездов | 6501 Д |   | 6601 |   |
| --- | --- | --- | --- | --- |
|   |  приб. | отпр. | приб. | отпр. |
|  Разд. пункты |  |  |  |  |
|  Лиелварде | — | 23.32 | — | 0.16 |
|  Кегумс | 23.37,5 | 23.38 | 0.21,5 | 0.22,5 |
|  Огре | 23.49 | 23.50 | 0.33,5 | 0.34,5 |"""


def suburban_spread():
    """A spread: a suburban timetable left, a notice right, plus noise."""
    return page([
        block("header", "п. № 6501", 40, 10, 150, 22),
        block("table", SUBURBAN_TABLE, 43, 30, 483, 400),
        block("footer", "6", 37, 749, 52, 764),            # folio: noise
        block("footer", "5 — 1055", 60, 790, 120, 800),     # signature: noise
        block("text", "Движение поездов по графику.", 560, 40, 950, 80),
        block("footer", "7", 962, 745, 977, 760),
    ])


# ------------------------------------------------------------- book/ pages
def book_table(rows, header_count=1):
    """A book/ table in the extractor's own format."""
    import extract
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    return extract.as_markdown(rows, header_count, width)


def book_page(sheet, halves, folios=None):
    """Text of a book/page-NN.md. halves: [(shape, [paragraph or table])]."""
    folios = folios or [2 * sheet - 4, 2 * sheet - 3][:len(halves)]
    out = ["---", f"sheet: {sheet}", f"kind: {'spread' if len(halves) == 2 else 'cover'}",
           f"folios: [{', '.join(map(str, folios))}]",
           f"shapes: [{', '.join(s for s, _ in halves)}]", "---", ""]
    for (_, parts), folio in zip(halves, folios):
        out += [f"## page {folio}", ""]
        for p in parts:
            out += [p, ""]
    return "\n".join(out)


def suburban_table(stations, *trains):
    """trains: per train, a list of (arr, dep) per station. Numbered 6001, 6003..."""
    rows = [["№ поездов"], [""]]
    for k in range(len(trains)):
        rows[0] += [str(6001 + 2 * k), ""]
        rows[1] += ["приб.", "отпр."]
    for i, st in enumerate(stations):
        row = [st]
        for t in trains:
            row += list(t[i])
        rows.append(row)
    return book_table(rows, header_count=2)


@pytest.fixture
def write_book(tmp_path):
    """Write book pages into tmp_path/book and return the dir."""
    d = tmp_path / "book"
    d.mkdir()

    def write(sheet, halves, folios=None):
        (d / f"page-{sheet:02d}.md").write_text(book_page(sheet, halves, folios))
        return d
    write.dir = d
    return write
