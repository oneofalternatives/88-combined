#!/usr/bin/env python3
"""Every train's arrival and departure at one station, in book order.

Reads a final-NN dir, writes one md table. Any cell it can't read rejects the
whole book: nothing is written, every such cell is listed, exit status 1.
See SPEC.md.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from book_model import parse_scan_file  # noqa: E402

# shape -> (station column, columns that never hold a time)
SHAPES = {
    "suburban": (0, {0}),
    "two-way": (2, {2}),
    "distance": (0, {0, 1}),
}
SKIP_SHAPES = {"prose"}
CAPTION_SHAPES = {"two-way", "distance"}   # train numbers come from the caption
HEADER_WORDS = {"приб.", "отпр.", "приб", "отпр", "прибытие", "отправление",
                "разд. пункты", "раздельные пункты", "№ поездов",
                "расстояние км", "расстояния км", "расстояние"}
PASS = {"—", "-", "–"}
# station -> pairs of stops joined by a link that skips it. A train timed at
# both ends of the pair, with only dashes at the station, goes round it.
BYPASSES = {"Рига-пасс.": [{"Яняварты", "Ошкалны"}]}
TIME_RE = re.compile(r"^(\d{1,2})\.(\d{2})(,5)?$")
DIGIT_RE = re.compile(r"\d")
MARK_RE = re.compile(r"⟨[^⟩]*⟩?")
OPTIONAL = {"table": "add the table number on the page as a column",
            "column": "add the train column's place in its table as a column",
            "train": "add the raw train-number cell as a column"}
# (mark, code in the output, how the book prints it), in output order
MARKS = [
    ("Д", "Д", "`Д` after the train number"),
    ("ДР", "ДР", "`ДР` after the train number"),
    ("*", "*", "`*` after the train number"),
    ("**", "**", "`**` after the train number, or `(По особому назначению)`"),
    ("weekends", "вых", "`По выходным дням` before the train number"),
    ("ДИЗЕЛЬНЫЙ", "ДИЗ", "`ДИЗЕЛЬНЫЙ` in the page caption"),
    ("Пригородный", "П", "`Пригородный п. №` in the caption"),
    ("weekdays", "w…", "`(по вторникам, …)` in the caption: the days, 1 = Mon … 7 = Sun"),
]
COLUMNS = ["scan", "page", "table", "column", "train", "number", "number2",
           "marks", "from", "to", "arrival", "departure",
           "status"]
# header titles kept short where the data is narrower than the column name
TITLES = {"scan": "sc", "page": "pg", "number": "no", "number2": "no2",
          "arrival": "arr", "departure": "dep"}


class Reject(Exception):
    pass


# ---------------------------------------------------------------- cells
def cell_kind(text):
    """blank, pass, time, note or bad. Times are kept as printed, never fixed."""
    t = text.strip()
    if not t:
        return "blank"
    if t in PASS:
        return "pass"
    if (m := TIME_RE.match(t)):
        h, mi = int(m[1]), int(m[2])
        return "bad" if mi > 59 or h > 24 or (h == 24 and mi) else "time"
    return "bad" if DIGIT_RE.search(t) else "note"


def seconds(text):
    m = TIME_RE.match(text.strip())
    return int(m[1]) * 3600 + int(m[2]) * 60 + (30 if m[3] else 0)


def status_of(arr, dep):
    """stops, passes or note for a station row; None if both cells are blank;
    raises Reject if the spec has no rule for the pair."""
    kinds = {cell_kind(arr), cell_kind(dep)}
    if kinds == {"blank"}:
        return None
    if "time" in kinds and kinds <= {"time", "pass", "blank"}:
        return "stops"
    if kinds == {"pass"}:
        return "passes"
    if kinds <= {"note", "blank"}:
        return "note"
    raise Reject(f"«{arr.strip()}» / «{dep.strip()}»: no rule for this pair of cells")


# ---------------------------------------------------------------- trains
NUMBER_RE = re.compile(r"(\d+)(?:/(\d+))?(\*\*|\*)?")
SUFFIX_RE = re.compile(r"\s+(ДР|Д)(?=\s|$)")
WEEKEND = "По выходным дням"
CAPTION_RE = re.compile(r"(Пригородный\s+)?п\.\s*№\s*")
SPECIAL_RE = re.compile(r"\s*\(По особому назначению\)")  # means **, even over a printed *
NAME_RE = re.compile(r"\s*«[^»]*»")                       # «СНЕЖОК»: dropped
DAYS = ["понедельникам", "вторникам", "средам", "четвергам", "пятницам",
        "субботам", "воскресеньям"]                        # 1 = Mon … 7 = Sun
DAYS_RE = re.compile(r"\(по\s+([^)]*)\)")
WEEKDAYS_RE = re.compile(r"w[1-7]+")


def parse_train(text, caption=False):
    """(number, number2, marks) of a train cell, or raise Reject with what is
    left over."""
    rest, marks = text.strip(), set()
    if caption:
        m = CAPTION_RE.match(rest)
        if not m:
            raise Reject(f"no «п. №» in caption: {text}")
        if m[1]:
            marks.add("Пригородный")
        rest = rest[m.end():]
    if rest.startswith(WEEKEND):
        marks.add("weekends")
        rest = rest[len(WEEKEND):].lstrip()
    m = NUMBER_RE.match(rest)
    if not m:
        raise Reject(f"no train number in: {text}")
    number, number2 = m[1], m[2] or ""
    if {len(number), len(number2)} == {3, 4}:
        # a local 6xx with a suburban number: only the local one is on the board
        number, number2 = min(number, number2, key=len), ""
    if m[3]:
        marks.add(m[3])
    rest = rest[m.end():]
    if (s := SUFFIX_RE.match(rest)):
        marks.add(s[1])
        rest = rest[s.end():]
    if (s := SPECIAL_RE.match(rest)):
        marks.discard("*")
        marks.add("**")
        rest = rest[s.end():]
    if (s := NAME_RE.match(rest)):
        rest = rest[s.end():]
    if rest.strip():
        raise Reject(f"left over \"{rest.strip()}\" in train cell \"{text}\"")
    return number, number2, marks


def caption_trains(items):
    """(train segments in caption order, marks that apply to all of them).

    A segment is one « · »-separated part of a caption line. Train segments
    hold «№»; the rest are routes and notes (ЕЖЕДНЕВНО), skipped, except
    ДИЗЕЛЬНЫЙ, which marks every train on the page."""
    segments = caption_segments(items)
    common = {"ДИЗЕЛЬНЫЙ"} if "ДИЗЕЛЬНЫЙ" in segments else set()
    return [s for s in segments if "№" in s], common


def caption_segments(items):
    return [s.strip() for it in items if it["kind"] == "caption"
            for s in re.split(r"[·\n]", it["text"]) if s.strip()]


def caption_days(items):
    """Weekday code of the page caption (`(по вторникам, …)` gives "w2467"),
    or "" when it names no days. It marks every train on the page. Raise
    Reject on a «(по …)» note that is not all day names."""
    notes = [s for s in caption_segments(items) if s.startswith("(по ")]
    if len(notes) > 1:
        raise Reject(f"{len(notes)} weekday notes in the caption: " + " / ".join(notes))
    if not notes:
        return ""
    m = DAYS_RE.fullmatch(notes[0])
    words = [w.strip() for w in m[1].split(",")] if m else []
    if not words or any(w not in DAYS for w in words):
        raise Reject(f"not a weekday note: {notes[0]}")
    return "w" + "".join(str(n) for n in sorted({DAYS.index(w) + 1 for w in words}))


def mark_list(marks):
    codes = []
    for m, code, _ in MARKS:
        if m == "weekdays":
            codes += sorted(x for x in marks if WEEKDAYS_RE.fullmatch(x))
        elif m in marks:
            codes.append(code)
    return ", ".join(codes)


# ---------------------------------------------------------------- tables
def column_pairs(width, protected):
    """(arrival col, departure col) per train, left to right."""
    cols = [c for c in range(width) if c not in protected]
    return [(cols[i], cols[i + 1] if i + 1 < len(cols) else None)
            for i in range(0, len(cols), 2)]


def is_header_row(cells):
    return sum(1 for c in cells if c.strip().lower() in HEADER_WORDS) >= 2


def direction(stops):
    """+1 down the page, -1 up it, None if neither fits: as validate.py's
    fit_direction, fewer backwards steps wins."""
    seq = [[seconds(c) for c in (a, d) if cell_kind(c) == "time"] for _, a, d in stops]
    seq = [s for s in seq if s]
    if len(seq) < 2:
        return 1

    def falls(order):
        times = [t for s in order for t in s]
        return sum(1 for a, b in zip(times, times[1:]) if b < a)

    down, up = falls(seq), falls(seq[::-1])
    if down != up:
        return 1 if down < up else -1
    return 1 if down == 0 else None


def goes_round(stops, i, status, station):
    """True when the train in this column never reaches the station at row i:
    a route note there, the station outside the train's timed run, or the
    nearest timed stops on each side joined by a link that skips it."""
    if status == "note":
        return True
    if status != "passes":
        return False
    timed = [k for k, s in enumerate(stops)
             if "time" in (cell_kind(s[1]), cell_kind(s[2]))]
    above = [k for k in timed if k < i]
    below = [k for k in timed if k > i]
    if not above or not below:
        return True
    ends = {stops[above[-1]][0], stops[below[0]][0]}
    return any(ends == pair for pair in BYPASSES.get(station, []))


def read_table(loc, table, shape, items, station, errors, seq=0):
    """Every train column of one table that holds any text, as dicts. A
    column whose train stops at or passes the station carries its output row
    in "row". Columns with a problem are left out, the problem goes in errors.
    loc: scan, page, table. seq: the page's place in the book."""
    st_col, protected = SHAPES[shape]
    rows = [it["cells"] for it in table["items"] if it["kind"] == "row"]
    if table["width"] <= st_col or not rows:
        return []
    hits = [i for i, r in enumerate(rows) if r[st_col].strip() == station]
    where = "scan {scan}, page {page}, table {table}".format(**loc)

    def err(msg, column=None, row=None, cell=None):
        at = where + (f", column {column}" if column else "")
        if row is not None:
            at += f", {rows[row][st_col].strip()} (r{row}" + \
                (f"c{cell})" if cell is not None else ")")
        errors.append(f"{at}: {msg}")

    for i, r in enumerate(rows):
        if is_header_row(r):
            err("a header inside the table body", row=i)
    pairs = column_pairs(table["width"], protected)
    if pairs and pairs[-1][1] is None:
        err("an odd number of time columns")
        return []
    trains = train_cells(table, pairs, shape, items, rows, err)
    if trains is None:
        return []
    try:
        days = caption_days(items)
    except Reject as e:
        err(str(e))
        return []

    out = []
    for n, (a, b) in enumerate(pairs, 1):
        if not any((r[a] + r[b]).strip() for r in rows):
            continue
        at_station = [i for i in hits if (rows[i][a] + rows[i][b]).strip()]
        before = len(errors)
        if len(at_station) > 1:
            err(f"{station} printed more than once", n, at_station[1])
        raw, caption, common = trains.get((a, b), (None, False, set()))
        if raw is None:
            err("no train number for this column", n)
        else:
            try:
                number, number2, marks = parse_train(raw, caption)
            except Reject as e:
                err(str(e), n)
        for i, r in enumerate(rows):
            for c in (a, b):
                if cell_kind(r[c]) == "bad":
                    err(f"«{r[c]}» is not a time", n, i, c)
        if at_station:
            i = at_station[0]
            try:
                status = status_of(rows[i][a], rows[i][b])
            except Reject as e:
                if not any(cell_kind(rows[i][c]) == "bad" for c in (a, b)):
                    err(str(e), n, i)
        stops = [(r[st_col].strip(), r[a], r[b]) for r in rows]
        d = direction(stops)
        if d is None:
            err("times fit neither direction", n)
        if len(errors) > before:
            continue
        timed = [s for s in stops if "time" in (cell_kind(s[1]), cell_kind(s[2]))]
        if d == -1:
            timed.reverse()
        col = {"where": f"{where}, column {n}", "number": number,
               "number2": number2, "timed": timed, "row": None,
               "has station": bool(hits), "seq": seq, "direction": d,
               "caption": caption_text(items) if caption else None}
        if at_station and not goes_round(stops, i, status, station):
            col["row"] = {
                **{k: str(v) for k, v in loc.items()},
                "column": str(n),
                "train": raw,
                "number": number,
                "number2": number2,
                "marks": mark_list(marks | common | ({days} if days else set())),
                "arrival": rows[i][a].strip() or "—",
                "departure": rows[i][b].strip() or "—",
                "status": status,
            }
        out.append(col)
    return out


# ---------------------------------------------------------------- whole runs
def caption_text(items):
    return tuple(it["text"] for it in items if it["kind"] == "caption")


def turns_page(a, b):
    """True when column a goes on in b on the next page, as a table split
    over two pages (186, 187): the page in the train's own direction (the
    one before for a bottom-up train) prints the same caption."""
    return (a["caption"] is not None and a["caption"] == b["caption"]
            and a["direction"] == b["direction"]
            and b["seq"] == a["seq"] + a["direction"])


def joins(end, start):
    """True when a column that ends at stop `end` goes on in one that starts
    at `start`: the same stop, and its arrival or departure printed the same."""
    return end[0] == start[0] and any(
        x.strip() == y.strip() and cell_kind(x) == "time"
        for x, y in zip(end[1:], start[1:]))


def link(columns, errors):
    """Fill "from" and "to" in the row of each column: its first and last
    stop, or past them in a table without the station, which the station's
    output would never show (Лиелварде—Айзкраукле on scans 48, 49). A column
    goes on in another when the train number is the same and the end stop of
    one is the start stop of the other, with a time in common, or the table
    goes on over the page. Two tables with the station are never linked:
    each is in the output as printed."""
    by_number = {}
    for k, c in enumerate(columns):
        for num in {c["number"], c["number2"]} - {""}:
            by_number.setdefault(num, []).append(k)
    after, before = {}, {}
    for k, c in enumerate(columns):
        if not c["timed"]:
            continue
        nums = {c["number"], c["number2"]} - {""}
        nxt = sorted({o for num in nums for o in by_number[num]
                      if o != k and columns[o]["timed"]
                      and not (c["has station"] and columns[o]["has station"])
                      and (joins(c["timed"][-1], columns[o]["timed"][0])
                           or turns_page(c, columns[o]))})
        if len(nxt) > 1:
            errors.append(f"{c['where']}: train {c['number']} goes on in "
                          f"{len(nxt)} columns: "
                          + "; ".join(columns[o]["where"] for o in nxt))
        elif nxt:
            o = nxt[0]
            if o in before:
                errors.append(f"{columns[o]['where']}: train {c['number']} "
                              f"comes from 2 columns: {columns[before[o]]['where']}; "
                              f"{c['where']}")
            after[k], before[o] = o, k

    def end_of(k, step):
        seen = {k}
        while k in step:
            k = step[k]
            if k in seen:
                return None
            seen.add(k)
        return k

    for k, c in enumerate(columns):
        if c["row"] is None:
            continue
        first, last = end_of(k, before), end_of(k, after)
        if first is None or last is None:
            errors.append(f"{c['where']}: train {c['number']} runs in a loop "
                          "from column to column")
            continue
        c["row"]["from"] = columns[first]["timed"][0][0]
        c["row"]["to"] = columns[last]["timed"][-1][0]


def train_cells(table, pairs, shape, items, rows, err):
    """{pair: (raw train cell, from a caption, caption-wide marks)}, or None
    when the caption doesn't match the column pairs."""
    if shape in CAPTION_SHAPES:
        segments, common = caption_trains(items)
        timed = [p for p in pairs
                 if any(cell_kind(r[c]) == "time" for r in rows for c in p)]
        if len(segments) == len(pairs):
            matched = pairs
        elif len(segments) == len(timed):
            matched = timed
        else:
            err(f"caption names {len(segments)} trains, the table has "
                f"{len(pairs)} column pairs, {len(timed)} with times")
            return None
        return {p: (s, True, common) for p, s in zip(matched, segments)}
    heads = [it["cells"] for it in table["items"] if it["kind"] == "head"]
    trains = {}
    for n, (a, b) in enumerate(pairs, 1):
        texts = [h[c].strip() for h in heads for c in (a, b)
                 if h[c].strip() and h[c].strip().lower() not in HEADER_WORDS]
        if len(texts) > 1:
            err(f"{len(texts)} train-number cells: {' / '.join(texts)}", n)
        elif texts:
            trains[(a, b)] = (texts[0], False, set())
    return trains


# ---------------------------------------------------------------- book
def scan_files(src):
    return sorted(src.glob("scan-*.md"), key=lambda p: int(re.findall(r"\d+", p.name)[0]))


def merge_marks(path, errors):
    """Every ⟨…⟩ left by merge.py: the book isn't finished."""
    folio = None
    for ln in path.read_text().splitlines():
        if ln.startswith("## page"):
            folio = ln[len("## page"):].strip()
        for m in MARK_RE.finditer(ln):
            errors.append(f"{path.name}, page {folio}: merge mark {m[0]}")


def stop_times(src, station):
    """(rows, errors) for the whole book."""
    columns, errors, seq = [], [], 0
    for path in scan_files(src):
        merge_marks(path, errors)
        parsed = parse_scan_file(path.read_text())
        for h, half in enumerate(parsed["halves"]):
            seq += 1
            shapes = parsed["shapes"]
            shape = shapes[h] if h < len(shapes) else None
            if shape in SKIP_SHAPES:
                continue
            if shape not in SHAPES:
                errors.append(f"scan {parsed['scan']}, page {half['folio']}: "
                              f"shape «{shape}», no rule for it")
                continue
            tables = [it["table"] for it in half["items"] if it["kind"] == "table"]
            for t, table in enumerate(tables, 1):
                loc = {"scan": parsed["scan"], "page": half["folio"], "table": t}
                columns += read_table(loc, table, shape, half["items"], station,
                                      errors, seq)
    link(columns, errors)
    return [c["row"] for c in columns if c["row"]], errors


def md_table(titles, rows):
    """Lines of an aligned table in the repo's style."""
    widths = [max(len(c) for c in col) for col in zip(titles, *rows)]

    def line(cells):
        return "| " + " | ".join(c.ljust(w) for c, w in zip(cells, widths)) + " |"

    return ([line(titles), "|" + "|".join("=" * (w + 2) for w in widths) + "|"]
            + [line(r) for r in rows])


def to_markdown(rows, station, src, extra=(), hide=()):
    cols = [c for c in COLUMNS
            if (c not in OPTIONAL or c in extra) and c not in hide]
    out = [f"# Stop times at {station}", "",
           f"From `{src}`, one row per train column, in book order.", ""]
    out += md_table([TITLES.get(c, c) for c in cols],
                    [[r[c] for c in cols] for r in rows])
    out += ["", "## Marks", ""]
    out += md_table(["mark", "printed in the book"],
                    [[code, form] for _, code, form in MARKS])
    return "\n".join(out) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("src", type=Path, help="an attempts/final-NN dir")
    ap.add_argument("--dest", type=Path, required=True, help="the md file to write")
    ap.add_argument("--station", default="Рига-пасс.")
    for name, text in OPTIONAL.items():
        ap.add_argument(f"--{name}", action="store_true", help=text)
    ap.add_argument("--no2", action="store_true",
                    help="add the no2 column; without it, a row with a no2 is an error")
    args = ap.parse_args(argv)
    if not scan_files(args.src):
        print(f"{args.src}: no scan-*.md files", file=sys.stderr)
        return 1
    rows, errors = stop_times(args.src, args.station)
    if not args.no2:
        errors += [f"scan {r['scan']}, page {r['page']}: train {r['number']} "
                   f"has no2 {r['number2']}, add --no2 to show it"
                   for r in rows if r["number2"]]
    if errors:
        for e in errors:
            print(e, file=sys.stderr)
        print(f"rejected: {len(errors)} problem(s), {args.dest} not written",
              file=sys.stderr)
        return 1
    if not rows:
        print(f"no train column has a row for {args.station}", file=sys.stderr)
        return 1
    args.dest.write_text(to_markdown(rows, args.station, args.src,
                                      [c for c in OPTIONAL if getattr(args, c)],
                                      [] if args.no2 else ["number2"]))
    print(f"{len(rows)} rows -> {args.dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
