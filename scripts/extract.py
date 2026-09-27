#!/usr/bin/env python3
"""Stage 1: Mistral OCR export -> one editable markdown file per scan.

The OCR chops a single printed timetable into several blocks and loses the
column count wherever train times are blank. Both are repaired here, once, by
reassembling each book page into ONE table whose width comes from the
"№ поездов" header. The result goes to attempts/extracted-NN. A copy of it in
attempts/final-NN is the source of truth from then on: it is hand-corrected
against the scans, and the builders read only it.

This is a one-way door -- it refuses to overwrite an edited file unless asked.
See spec/ocr-book-format.md.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import attempts
from book_model import (header_width, is_station_block, load_scans,
                        parse_table, split_halves, station_span)


# A lone-hour time ("7.10") is padded to "07.10" so the column sorts and reads
# as a fixed-width field; the half-minute suffix ("7.16,5") rides along. The
# leading \b keeps it off things like "О/п. 56 км", where no digit precedes.
HOUR_RE = re.compile(r"\b(\d)\.(\d{2})\b")
# OCR emphasis always wraps a whole cell ("**Огре**", "**7.45**"), and only
# that is stripped. Any other * is data: the book's footnote mark on train
# numbers, "6305*", "6301**", "6609*/6620*". Matching pairs inside a cell
# would read "6609*/6620*" as emphasis and lose both marks.
EMPHASIS_RE = re.compile(r"(\*\*|__|\*|_)(\S(?:.*\S)?)\1")
# The footnote mark: one or two asterisks after a train number or its type
# suffix -- "6305*", "6320** Д", "6533 Д*", "6870 ДР*".
MARKER_RE = re.compile(r"(?<=\d)\*{1,2}|(?<=\d Д)\*{1,2}|(?<=\d ДР)\*{1,2}")
# A wrapped station name: the book breaks a long name across two printed lines
# and the OCR reads them as two rows. The continuation is a bare kilometre
# marker sitting under a real stop. "856 км" also occurs as a real standalone
# stop, so every merge is reported for review.
KM_RE = re.compile(r"^\d+\s*км$")
# A change of railway, "Октябрьская ж. д.". The OCR gives it either as a title
# block or as a table row with every other cell empty; both are a divider.
RAILWAY_RE = re.compile(r"ж\.\s*д\.$")

# Blank in any data cell: the book prints an em dash where a train does not call.
BLANK = ("", "—", "-")


class Divider(list):
    """A heading printed across the table, e.g. a change of railway.

    It is a row of the table but not a stop, so it anchors nothing and must
    not be counted when the station column is re-paired with the data.
    """


def clean_cell(c: str, pad_time: bool = True) -> str:
    """Normalize one cell: plain font, zero-padded hours.

    `pad_time` is off for station and distance columns, which must never be
    reinterpreted as clock times.
    """
    c = c.strip()
    if m := EMPHASIS_RE.fullmatch(c):
        c = m.group(2)
    # Unescape after, so an escaped "\*" is never taken for emphasis.
    c = c.replace("\\*", "*").replace("\\_", "_")
    if pad_time:
        c = HOUR_RE.sub(r"0\1.\2", c)
    return c.strip()


# ---------------------------------------------------------------- page shapes
# Three table shapes appear in the book and each names itself in its header
# row, so the shape is detected rather than configured. Anything else is
# reported, never silently passed through -- a quiet fallback is what let a
# whole chapter sit unnormalized.
SHAPES = {
    # name: (header predicate, station column, columns never time-padded)
    "suburban": (lambda h: "№ поездов" in h[0], 0, {0}),
    "two-way": (lambda h: len(h) > 2 and "Раздельные пункты" in h[2], 2, {2}),
    "distance": (lambda h: "Раздельные пункты" in h[0]
                 and any("асстоян" in c for c in h), 0, {0, 1}),
}


def shape_of(blocks):
    """(name, station_col, protected_cols, width) for this half, or None."""
    for b in sorted(blocks, key=lambda b: b["topLeftY"]):
        if b["type"] != "table":
            continue
        parsed = parse_table(b["content"].strip())
        if not parsed:
            continue
        head = parsed[0][0]
        for name, (test, st, prot) in SHAPES.items():
            if test(head):
                return name, st, prot, parsed[2]
        return None  # a table we do not recognize: caller reports it
    return None


def caption(blocks, scan_h):
    """Train numbers and route names printed above the table.

    The OCR types these inconsistently as header or footer even when they sit
    at the top of the page, so they are selected by position, not by type.
    They carry the train identity -- dropping them would lose the semantics.

    Boxes on one printed line sit a few pixels apart vertically, so a block
    joins the line when its middle is above the line's bottom edge; each line
    then reads left to right.
    """
    top = [b for b in blocks
           if b["type"] in ("header", "footer") and b["topLeftY"] < 0.12 * scan_h]
    lines: list[list[dict]] = []
    for b in sorted(top, key=lambda b: b["topLeftY"]):
        mid = (b["topLeftY"] + b["bottomRightY"]) / 2
        if lines and mid < max(x["bottomRightY"] for x in lines[-1]):
            lines[-1].append(b)
        else:
            lines.append([b])
    return [" · ".join(clean_cell(b["content"])
                       for b in sorted(ln, key=lambda b: b["topLeftX"]))
            for ln in lines]


def half_rows(blocks, scan_h, scan, report):
    """Reassemble one book page into (rows, header_count, width, shape)."""
    shape = shape_of(blocks)
    if not shape:
        return None
    name, st_col, protected, width = shape
    left, span = station_span(blocks)
    rows: list[list[str]] = []
    header_count = 0
    for b in sorted(blocks, key=lambda b: (b["topLeftY"], b["topLeftX"])):
        if b["type"] in ("header", "footer"):
            continue
        if name == "suburban" and is_station_block(b, left, span):
            for ln in b["content"].splitlines():
                if ln.strip():
                    rows.append(cells_at(clean_cell(ln), st_col, width))
            continue
        if b["type"] == "title" or b["content"].strip().startswith("#"):
            # A divider printed across the table (e.g. a change of railway).
            # Kept in place as a row with every other cell blank.
            text = clean_cell(b["content"].lstrip("# ").strip())
            if text:
                rows.append(Divider(cells_at(text, st_col, width)))
            continue
        if b["type"] != "table":
            continue
        parsed = parse_table(b["content"].strip())
        if not parsed:
            continue
        body, hc, _ = parsed
        if not rows:  # only the first block carries the real header
            header_count = hc
        for r in body:
            r = [clean_cell(c, pad_time=i not in protected)
                 for i, c in enumerate(r[:width])]
            r += [""] * (width - len(r))
            # Only a railway name is sure to be a divider: any other name-only
            # row may be a stop whose times the OCR lost, left to realign().
            if RAILWAY_RE.search(r[st_col]) and not any(
                    c for i, c in enumerate(r) if i != st_col):
                r = Divider(r)
            rows.append(r)
    if name == "distance" and rows:
        rows = realign(rows, max(header_count, 1), st_col, 1, scan, report)
    return (rows, header_count, width, name) if rows else None



def realign(rows, header_count, st_col, dist_col, scan, report):
    """Re-pair the station column with the columns of times beside it.

    The OCR reads the two as independent streams, and either can slip:

    * the book wraps a long station name over two printed lines, so the name
      stream gains a line the data stream has no row for;
    * the OCR sometimes re-reads a run of names it has already taken, or
      trails off into name-only rows once the times stop resolving.

    Either way every later station is labelled with a neighbour's name, which
    is silent and total corruption -- so the streams are rebuilt separately and
    zipped back together rather than patched row by row. Each stream has its
    own rule: every printed line of the table is a row of it, except a wrapped
    continuation, which belongs to the name above and brings a row of its own
    only when it carries a distance; and a route never calls at the same stop
    twice, which is what lets a re-read name be told from a real one.
    Every repair is reported; nothing is guessed at.
    """
    out = list(rows[:header_count])
    seen: set[str] = set()

    def segment():
        return {"names": [], "data": []}

    # Dividers split the table: a stop never pairs across one.
    parts: list = [segment()]
    for r in rows[header_count:]:
        if isinstance(r, Divider):
            parts += [r, segment()]
            continue
        seg = parts[-1]
        r = [c.strip() for c in r]
        names = seg["names"]
        wrapped = (names and KM_RE.match(r[st_col]) and not KM_RE.match(names[-1]))
        if wrapped:
            names[-1] += f" {r[st_col]}"
            report.append(f"scan {scan}: joined wrapped name {names[-1]!r}")
            times = any(c not in BLANK for i, c in enumerate(r)
                        if i not in (st_col, dist_col))
            if r[dist_col] in BLANK or not times:
                # A stop of its own would carry both a distance and times. With
                # either missing this is a stray line, not a row: its cells stay
                # with the stop above.
                absorb(seg["data"], r, st_col, scan, report)
                continue
        elif r[st_col]:
            names.append(r[st_col])
        seg["data"].append([c if i != st_col else "" for i, c in enumerate(r)])

    for seg in parts:
        if isinstance(seg, Divider):
            out.append(seg)
            continue
        names, data = dedupe(seg["names"], seen, scan, report), seg["data"]
        # A row with neither a name nor a time is the OCR running off the foot
        # of the column, not a stop: it is the padding, so it goes first.
        data = data[:len(data) - trailing_blanks(data)]
        if len(names) != len(data):
            report.append(f"scan {scan}: {len(names)} station name(s) against "
                          f"{len(data)} row(s) of times; the tail of the shorter "
                          "column is missing from the scan")
        for i, row in enumerate(data):
            row[st_col] = names[i] if i < len(names) else ""
            out.append(row)
        for extra in names[len(data):]:
            # A stop the OCR named but gave no times: kept, blank, for the hand
            # pass -- dropping it would silently shorten the route.
            out.append(cells_at(extra, st_col, len(rows[0])))
    return out


def trailing_blanks(data) -> int:
    n = 0
    for row in reversed(data):
        if any(c not in BLANK for c in row):
            break
        n += 1
    return n


def dedupe(names, seen, scan, report):
    """Drop names the OCR read twice, keeping the first of each.

    Wraps are already rejoined by this point, which matters: the prefix of a
    wrap ("Блок пост") really does recur down the column, and it is the joined
    name that a route prints just once.
    """
    out = []
    for name in names:
        if name in seen:
            report.append(f"scan {scan}: dropped a second {name!r} -- the OCR "
                          "read part of the station column twice")
            continue
        seen.add(name)
        out.append(name)
    return out


def absorb(data, r, st_col, scan, report):
    """Fold cells that carry no distance into the stop printed above them.

    With no distance of their own they cannot be placed, so they are only
    allowed to fill blanks; anything that contradicts the row above is the
    OCR smearing two rows together and is dropped.
    """
    if not data:
        report.append(f"scan {scan}: DROPPED loose cells above the first stop: {r}")
        return
    prev = data[-1]
    clash = [i for i, c in enumerate(r)
             if i != st_col and c not in BLANK
             and prev[i] not in BLANK and prev[i] != c]
    if clash:
        report.append(f"scan {scan}: DROPPED cells with no distance, they "
                      "contradict the row above ("
                      + ", ".join(f"col {i}: {prev[i]} vs {r[i]}" for i in clash) + ")")
        return
    filled = [i for i, c in enumerate(r)
              if i != st_col and c not in BLANK and prev[i] in BLANK]
    for i in filled:
        prev[i] = r[i]
    if filled:
        report.append(f"scan {scan}: recovered "
                      + ", ".join(f"col {i}" for i in filled)
                      + " from cells with no distance of their own")


def cells_at(text, col, width):
    """A row carrying one value in `col` and blanks elsewhere."""
    r = [""] * width
    r[col] = text
    return r


def as_markdown(rows, header_count, width) -> str:
    """Column-aligned pipe table, so the file is comfortable to hand-edit.

    Markdown-LIKE, not GitHub-flavoured. GFM allows exactly one heading row and
    demands the rule on line two, which cannot express this book: a suburban
    table stacks train numbers over a приб./отпр. pair, so its heading is two
    rows deep. Here the head rule is written with "=" and falls below every
    heading row, interior rules are printed where the book rules its table, and
    a divider becomes a full-width band instead of a row of empty cells.
    book_model.parse_book_table reads it back.
    """
    body = [r for r in rows if not isinstance(r, Divider)]
    w = [max(len(r[i]) for r in body) for i in range(width)]
    inner = sum(w) + 3 * (width - 1)  # cells joined by " | "

    def rule(ch):
        return "|" + "|".join(ch * (w[j] + 2) for j in range(width)) + "|"

    head = max(header_count, 1)
    out = []
    for i, r in enumerate(rows):
        if isinstance(r, Divider):
            out.append(rule("-"))
            out.append("| " + next((c for c in r if c), "").ljust(inner) + " |")
            out.append(rule("-"))
            continue
        out.append("| " + " | ".join(c.ljust(w[j]) for j, c in enumerate(r)) + " |")
        if i + 1 == head:
            out.append(rule("="))
    return "\n".join(out)


def prose(blocks) -> str:
    """Fallback for pages with no timetable: keep the text, drop the geometry."""
    parts = []
    for b in sorted(blocks, key=lambda b: (b["topLeftY"], b["topLeftX"])):
        if b["type"] in ("header", "footer"):
            continue
        parts.append(b["content"].strip())
    return "\n\n".join(p for p in parts if p)


def stray_markup(cells, scan, report):
    """Report a * or _ left after cleaning that is not a footnote mark.

    It is either emphasis on part of a cell or a mark the book really prints;
    only the scan can tell, so it is kept as is and reported.
    """
    for c in cells:
        if re.search(r"[*_]", MARKER_RE.sub("", c)):
            report.append(f"scan {scan}: markup left in {c!r} -- check the scan")


def render_scan(scan, n, report) -> str:
    halves = split_halves(scan)
    scan_h = scan["dimensions"]["height"]
    spread = len(halves) == 2
    folios = [2 * n - 4, 2 * n - 3] if spread else [None]
    if n == 2:
        folios = [None, None]
    shapes = []
    body = []
    for half, folio in zip(halves, folios):
        body.append(f"## page {folio}" if folio is not None else "## page")
        body.append("")
        lines = caption(half, scan_h)
        stray_markup(lines, n, report)
        for line in lines:
            body.append(line)
            body.append("")
        built = half_rows(half, scan_h, n, report)
        if built:
            rows, hc, width, name = built
            stray_markup((c for r in rows for c in r), n, report)
            shapes.append(name)
            body.append(as_markdown(rows, hc, width))
        else:
            if any(b["type"] == "table" for b in half):
                report.append(f"scan {n}: unrecognized table shape")
                shapes.append("UNKNOWN")
            else:
                shapes.append("prose")
            body.append(prose(half))
        body.append("")
    head = [
        "---",
        f"scan: {n}",
        f"kind: {'spread' if spread else 'cover'}",
        f"folios: [{', '.join(str(f) for f in folios if f is not None)}]",
        f"shapes: [{', '.join(shapes)}]",
        "---",
        "",
    ]
    return "\n".join(head + body)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scans", nargs="*", type=int, help="scan numbers (default: all)")
    ap.add_argument("--force", action="store_true", help="overwrite existing files")
    ap.add_argument("--src", type=Path, required=True, help="OCR output directory")
    ap.add_argument("--dest", type=Path, required=True, help="scan files directory")
    args = ap.parse_args()
    # Output into attempts/extracted-NN makes an extraction: a finished input, a fresh
    # dir, and a manifest plus index entry once done.
    extracted = args.dest.parent == attempts.ROOT and args.dest.name.startswith("extracted-")
    if extracted:
        attempts.require_finished(args.src)
        if (args.dest / "manifest.json").exists():
            sys.exit(f"{args.dest}: already finished")

    scans = load_scans(args.src)
    if missing := [n for n in args.scans if n not in scans]:
        sys.exit(f"{args.src}: no scan {', '.join(map(str, missing))}")
    args.dest.mkdir(exist_ok=True)
    wanted = args.scans or list(scans)
    report: list[str] = []
    tally: dict[str, int] = {}
    for n in wanted:
        dest = args.dest / f"scan-{n:02d}.md"
        if dest.exists() and not args.force:
            print(f"skip {dest} (exists; --force to overwrite)")
            continue
        text = render_scan(scans[n], n, report)
        dest.write_text(text)
        for line in text.splitlines():
            if line.startswith("shapes:"):
                for name in line[8:].strip("[] ").split(","):
                    tally[name.strip()] = tally.get(name.strip(), 0) + 1
    print("halves by shape: " + ", ".join(f"{k}={v}" for k, v in sorted(tally.items())))
    if extracted:
        # Index first: if it fails, the dir stays unfinished and can be rerun.
        attempts.set_extracted(args.src.name, args.dest.name)
        attempts.finish(args.dest, {"ocr": str(args.src), "scans": len(wanted),
                                   "problems": len(report)})
    if report:
        print(f"\n{len(report)} PROBLEM(S) -- not guessed at, fix these:")
        for line in report:
            print("  " + line)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
