#!/usr/bin/env python3
"""Validate book/ against itself.

The book over-determines itself: the same leg is timed by dozens of trains, the
mileposts fix the distances, and arrival never follows departure. So the sheets
can be checked without any outside source. See validator.md.

Output is triage -- a ranked "look here", not a verdict. The data is unchecked
OCR. Nothing is repaired and nothing is guessed: every finding names the cell
and prints the evidence that made it suspicious, so it can be judged by eye
against the scan.

Reads book/ only, like the builder.
"""

import argparse
import json
import re
import sys
from difflib import SequenceMatcher
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from book_model import BOOK, parse_book_page  # noqa: E402
from extract import SHAPES  # noqa: E402

# Tuned by editing and re-running. Every threshold is a judgement about a
# 1988 timetable, not a constant of nature.
CONFIG = {
    "max_speed_kmh": 120.0,          # over this the data is impossible
    "speed_deviation_threshold": 3.5,  # modified z of a leg speed, book-wide
    "deviation_threshold": 3.5,      # modified z of a running time, same leg
    "ratio_threshold": 1.5,          # fallback when MAD is 0
    "dwell_deviation_threshold": 3.5,  # modified z of a dwell, same station
    "dwell_ratio_threshold": 2.0,    # fallback when MAD is 0
    "min_samples": 5,                # under this a leg/station gets no opinion
    "leg_min_diff_sec": 60,          # a running time this close to the median
    "dwell_min_diff_sec": 120,       # ...or a dwell this close, is not a finding
    "name_similarity": 0.7,          # two names this alike are one station misspelt
    "max_leg_km": 60.0,              # a bigger step is a mileposting reset,
                                     # not a leg: the real ones top out at 32
    "misalign_run": 3,               # findings in a row = one column finding
    "wrap_evening_after_h": 20,      # a midnight wrap leaves after this hour
    "wrap_morning_before_h": 8,      # ...and arrives before this one
    "wrap_max_dwell_min": 60,        # ...and, inside a stop, waits no longer:
                                     # the book's longest real dwell is 60
}

# Mileposting, per destination as the route caption prints it.
#
# Chapter XII prints a through route in more than one reckoning, and the
# numbering resets at the junction where it changes -- Рига—Пыталово counts
# *down* from 922,8 at Рига-пасс. to Плявиняс, and from there counts *up* from
# 0,0 again. So Рига-пасс. honestly has two mileposts (922,8 and 0,0), Плявиняс
# has two (810,6 and 0,0), and neither is damage. A kilometre means nothing
# across such a boundary: rule 3 does not measure a leg across one, and rule 5
# compares a station only against the sheets on its own reckoning.
#
# A destination listed here declares which reckonings its sheets may be printed
# in; a zone that lands outside them is reported. A sheet whose route the OCR
# lost (folios 188/189 print the train number and nothing else) is still placed
# by the band its kilometres fall in, and simply gets no such check.
#
# Every destination here is one of the eight in the chapter list on folio 181.
# All but Вентспилс are borne out by a sheet; that one is listed from the
# chapter and has no distance sheet in the book to check it against.
MILEPOSTING = {
    "Себеж": ("moscow",),
    "Даугавпилс": ("moscow", "daugavpils"),
    "Бигосово": ("moscow", "daugavpils"),
    "Пыталово": ("moscow", "riga"),
    "Лиепая": ("riga",),
    "Валга": ("riga",),
    "Вентспилс": ("riga",),
    "Пярну": ("riga",),
}
RECKONINGS = {      # name -> the kilometres that reckoning is printed in
    "moscow": (600.0, 930.0),       # Рига-пасс. 922,8 down to Себеж 616,3
    "daugavpils": (250.0, 600.0),   # Крустпилс up to Бигосово 472,8
    "riga": (0.0, 250.0),           # every line numbered from 0 at its own
}                                   # Riga-side origin, the Плявиняс branch too

DAY = 24 * 3600
# shape -> station column, columns that never hold a time. Taken from the
# extractor rather than restated here: a shape is detected, never configured,
# and a second copy of the station column is a second thing to keep in step.
SHAPE_RULES = {name: (station, protected)
               for name, (_, station, protected) in SHAPES.items()}
SPEED_SHAPES = {"distance"}     # the only sheets with a milepost column
SKIP_SHAPES = {"prose"}
HEADER_WORDS = {"приб.", "отпр.", "прибытие", "отправление",
                "разд. пункты", "раздельные пункты", "№ поездов",
                "расстояние км", "расстояние"}

TIME_RE = re.compile(r"^(\d{1,2})\.(\d{2})(,5)?$")
KM_RE = re.compile(r"^(\d{1,4})[.,](\d)$")
NUM_RE = re.compile(r"№\s*([\d/]+\*{0,2}(?:\s*[А-ЯЁ]{1,2}\b)?)")
DIGIT_RE = re.compile(r"\d")


# --------------------------------------------------------------- cell parsing

class Cell:
    """One table cell: a time, a pass (—), a blank, prose, or damage."""

    __slots__ = ("text", "kind", "sec")

    def __init__(self, text):
        self.text = text
        self.sec = None
        t = text.strip()
        if not t:
            self.kind = "blank"
        elif t in ("—", "-", "–"):
            self.kind = "pass"
        elif (m := TIME_RE.match(t)):
            h, mi, half = int(m[1]), int(m[2]), m[3]
            if mi > 59 or h > 24 or (h == 24 and mi):
                self.kind = "bad"   # 25.13, 7.71 -- shaped like a time, isn't
            else:
                self.kind = "time"
                self.sec = h * 3600 + mi * 60 + (30 if half else 0)
        elif DIGIT_RE.search(t):
            self.kind = "bad"       # digits that are not a time: damage
        else:
            self.kind = "note"      # «Следует до» / «Вецаки» -- printed prose

    @property
    def timed(self):
        return self.kind == "time"


def parse_km(text):
    m = KM_RE.match(text.strip())
    return int(m[1]) + int(m[2]) / 10 if m else None


def hhmm(sec):
    sec %= DAY
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}.{m:02d}" + (",5" if s else "")


def mmss(sec):
    sign = "-" if sec < 0 else ""
    sec = round(abs(sec))
    return f"{sign}{sec // 60}:{sec % 60:02d}"


# ------------------------------------------------------------------ findings

class Finding:
    """One place to look, with the evidence that pointed there."""

    def __init__(self, severity, score, rule, where, message, evidence=None):
        self.severity = severity        # 0 impossible, 1 deviation
        self.score = score              # magnitude, within a severity
        self.rules = {rule}
        self.where = where              # Where
        self.message = message
        self.evidence = evidence or {}
        # Ordered and unique: which cluster absorbs a finding must not depend
        # on the iteration order of a set of strings, or two runs over the same
        # book disagree.
        self.cells = tuple(dict.fromkeys(where.cells))

    def merge(self, other):
        """Several rules on one cell collapse to one finding, ranked up."""
        self.rules |= other.rules
        self.severity = min(self.severity, other.severity)
        self.score = max(self.score, other.score)
        self.cells = tuple(dict.fromkeys(self.cells + other.cells))
        self.message += "; " + other.message
        self.evidence.update(other.evidence)

    @property
    def rank(self):
        # Independent constraints rarely agree on an innocent cell.
        return (self.severity, -self.score * (1 + 0.5 * (len(self.rules) - 1)))

    def render(self):
        tag = "IMPOSSIBLE" if self.severity == 0 else "deviation"
        head = f"[{tag}] {self.where}"
        if len(self.rules) > 1:
            head += f"  ({len(self.rules)} rules agree)"
        named = ", ".join("structure" if r == 0 else str(r) for r in sorted(self.rules))
        lines = [head, f"    rule {named}: {self.message}"]
        if self.evidence:
            lines.append("    " + "  ".join(f"{k}={v}" for k, v in self.evidence.items()))
        return "\n".join(lines)

    def as_dict(self):
        return {"severity": self.severity, "score": round(self.score, 3),
                "rules": sorted(self.rules), "message": self.message,
                "evidence": self.evidence, **self.where.as_dict()}


class Where:
    """A location in book/, down to the cells involved."""

    def __init__(self, sheet, folio, shape, train, station=None, cells=()):
        self.sheet, self.folio, self.shape = sheet, folio, shape
        self.train, self.station = train, station
        # A cell is identified book-wide: the same (row, col) exists on every
        # sheet, and two findings are the same cell only on the same column.
        self.cells = tuple((sheet, folio, train, r, c) for r, c in cells)

    def __str__(self):
        s = f"page-{self.sheet:02d}.md folio {self.folio} [{self.shape}] п.№ {self.train}"
        if self.station:
            s += f" — {self.station}"
        if self.cells:
            s += "  " + ",".join(f"r{r}c{c}" for *_, r, c in self.cells)
        return s

    def as_dict(self):
        return {"sheet": self.sheet, "folio": self.folio, "shape": self.shape,
                "train": self.train, "station": self.station,
                "cells": [[r, c] for *_, r, c in self.cells]}


def modified_z(x, values):
    """0.6745*(x-med)/MAD, with the ratio fallback when MAD is 0.

    Median and MAD, not mean and sigma: the outliers are in the sample. MAD is
    often 0 here -- every train printed the same minute -- and then a ratio to
    the median is all that is left.
    """
    med = median(values)
    mad = median([abs(v - med) for v in values])
    if mad:
        return abs(0.6745 * (x - med) / mad), med, mad, "z"
    if not med or not x:
        # Every sample identical: anything different at all is the finding.
        return (0.0 if x == med else float("inf")), med, mad, "ratio"
    return (x / med if x > med else med / x), med, mad, "ratio"


def median(values):
    v = sorted(values)
    n = len(v)
    if not n:
        return 0.0
    return v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2


# ------------------------------------------------------------------- reading

class Stop:
    """One station on one train: its row, its arrival and its departure."""

    __slots__ = ("row", "station", "km", "zone", "arr", "dep", "cols",
                 "cum_arr", "cum_dep", "suspect")

    def __init__(self, row, station, km, arr, dep, cols, zone=0):
        self.row, self.station, self.km, self.zone = row, station, km, zone
        self.arr, self.dep, self.cols = arr, dep, cols
        self.cum_arr = self.cum_dep = None
        self.suspect = False    # a backwards step landed here; not a sample

    @property
    def served(self):
        return self.arr.kind != "blank" or self.dep.kind != "blank"

    @property
    def timed(self):
        return self.arr.timed or self.dep.timed

    def first(self):
        """The time the train is at this station, arrival preferred."""
        return self.cum_arr if self.cum_arr is not None else self.cum_dep

    def last(self):
        return self.cum_dep if self.cum_dep is not None else self.cum_arr


class Column:
    """One train's column pair on one half sheet."""

    def __init__(self, sheet, folio, shape, train, stops):
        self.sheet, self.folio, self.shape = sheet, folio, shape
        self.train, self.stops = train, stops
        self.direction = None       # +1 down the page, -1 up it, None no fit

    def where(self, stop=None, cells=()):
        return Where(self.sheet, self.folio, self.shape, self.train,
                     stop.station if stop else None, cells)

    def travel(self):
        order = self.stops if self.direction != -1 else list(reversed(self.stops))
        return [s for s in order if s.timed]


def pair_columns(width, protected):
    """Time columns come in приб./отпр. pairs; the station column splits them."""
    runs, cur = [], []
    for c in range(width):
        if c in protected:
            if cur:
                runs.append(cur)
            cur = []
        else:
            cur.append(c)
    if cur:
        runs.append(cur)
    pairs = []
    for run in runs:
        for i in range(0, len(run), 2):
            pairs.append((run[i], run[i + 1] if i + 1 < len(run) else None))
    return pairs


def is_header_row(cells, station_col):
    """A header the OCR repeated inside the body (e.g. sheet 32, folio 61)."""
    low = [c.strip().lower() for c in cells]
    if station_col < len(low) and low[station_col] in HEADER_WORDS:
        return True
    return sum(1 for c in low if c in HEADER_WORDS) >= 2


def train_names(items, pairs, shape, table_index, header_cells):
    """Train numbers: from the header row on suburban sheets, else the caption.

    Only used to name a finding, so a positional fallback is good enough.
    """
    if shape == "suburban" and header_cells:
        names = [header_cells.get(a) or header_cells.get(b) for a, b in pairs]
        if any(names):
            return [n or "?" for n in names]
    caps = [it["text"] for it in items if it["kind"] == "caption"]
    found = [n.strip() for c in caps for n in NUM_RE.findall(c)]
    if len(found) == len(pairs):
        return found
    return [f"?{table_index}.{i + 1}" for i in range(len(pairs))]


def read_half(sheet, folio, shape, items, report):
    """One half sheet: its train columns, and its (milepost, station) pairs."""
    station_col, protected = SHAPE_RULES[shape]
    destination = route_destination(items) if shape == "distance" else None
    declared = MILEPOSTING.get(destination)
    columns, mileposts = [], []
    for ti, it in enumerate(items):
        if it["kind"] != "table":
            continue
        t = it["table"]
        width = t["width"]
        if width <= station_col:
            continue
        pairs = pair_columns(width, protected)
        if not pairs:
            continue
        head = {}
        for r in t["items"]:
            if r["kind"] == "head":
                for i, c in enumerate(r["cells"]):
                    if c.strip() and c.strip().lower() not in HEADER_WORDS:
                        head.setdefault(i, c.strip())
        # A repeated header inside the body restarts the station list, so the
        # segments either side are separate runs and must not be compared. The
        # header rows carry the train numbers of the segment that follows them
        # -- on a sheet the OCR left without a head rule they are the only
        # place the numbers appear.
        segments, cur, cur_head = [], [], dict(head)
        for r in t["items"]:
            if r["kind"] != "row":
                continue
            cells = r["cells"]
            if is_header_row(cells, station_col):
                if cur:
                    segments.append((cur, cur_head))
                    cur, cur_head = [], dict(head)
                for i, c in enumerate(cells):
                    if c.strip() and c.strip().lower() not in HEADER_WORDS:
                        cur_head[i] = c.strip()
                continue
            cur.append(cells)
        if cur:
            segments.append((cur, cur_head))
        for seg_i, (seg, seg_head) in enumerate(segments):
            names = train_names(items, pairs, shape, ti, seg_head)
            zones = []
            if shape == "distance":
                kms = [parse_km(c[1]) if len(c) > 1 else None for c in seg]
                zones = km_zones(kms)
                mileposts += zone_mileposts(sheet, folio, shape, seg, kms, zones,
                                            destination, declared, report)
            for (a, b), name in zip(pairs, names):
                stops = []
                for ri, cells in enumerate(seg):
                    station = cells[station_col].strip() if station_col < len(cells) else ""
                    km = parse_km(cells[1]) if shape == "distance" and len(cells) > 1 else None
                    arr = Cell(cells[a] if a < len(cells) else "")
                    dep = Cell(cells[b] if b is not None and b < len(cells) else "")
                    stops.append(Stop(ri, station, km, arr, dep, (a, b),
                                      zones[ri] if zones else 0))
                if any(s.timed for s in stops):
                    label = name if len(segments) == 1 else f"{name} (part {seg_i + 1})"
                    columns.append(Column(sheet, folio, shape, label, stops))
    return columns, mileposts


def zone_mileposts(sheet, folio, shape, rows, kms, zones, destination, declared, report):
    """The (reckoning, milepost, station) pairs of one table, zone by zone.

    A zone the route does not declare is reported rather than filed: it is
    either a kilometre column that slipped its band or a route this config does
    not yet know.
    """
    out = []
    for zone in sorted(set(zones)):
        rows_in = [i for i, z in enumerate(zones) if z == zone]
        reckoning = reckoning_of([kms[i] for i in rows_in])
        known = [kms[i] for i in rows_in if kms[i] is not None]
        if reckoning is None or (declared and reckoning not in declared):
            if known:
                where = Where(sheet, folio, shape, "—", None,
                              [(rows_in[0], 1), (rows_in[-1], 1)])
                route = f"route «{destination}»" if destination else "route not printed"
                out_of = (f"{reckoning!r}, which {route} does not use"
                          if reckoning else "no one reckoning")
                report.append(Finding(
                    0, 3.0, 5, where,
                    f"mileposts {min(known):.1f}–{max(known):.1f} км fall in "
                    f"{out_of} — this zone is left out of rule 5",
                    {"declared": ", ".join(declared) if declared else "—"}))
            continue
        for i in rows_in:
            name = rows[i][0].strip() if rows[i] else ""
            if kms[i] is not None and name:
                where = Where(sheet, folio, shape, "—", name, [(i, 0), (i, 1)])
                out.append((reckoning, kms[i], name, where))
    return out


def km_zones(kms):
    """A zone index per row: the mileposting resets at a junction, mid-sheet.

    A reset shows up either as a step no leg could be (`max_leg_km`) or as the
    kilometres turning round. The row that carries the new number opens the new
    zone, and the direction is learnt again from inside it.
    """
    zones, zone, direction, prev = [], 0, 0, None
    for km in kms:
        if km is not None and prev is not None:
            step = km - prev
            d = (step > 0) - (step < 0)
            if abs(step) > CONFIG["max_leg_km"] or (d and direction and d != direction):
                zone += 1
                direction = 0
            elif d:
                direction = d
        if km is not None:
            prev = km
        zones.append(zone)
    return zones


def reckoning_of(kms):
    """Which of the book's reckonings these kilometres are printed in."""
    known = [k for k in kms if k is not None]
    if not known:
        return None
    names = {name for name, (lo, hi) in RECKONINGS.items()
             if all(lo <= k <= hi for k in known)}
    return names.pop() if len(names) == 1 else None


ROUTE_RE = re.compile(r"([А-ЯЁа-яё\-\. ]+)—([А-ЯЁа-яё\-\. ]+)")


def route_destination(items):
    """The far end of the route printed over the table («Рига—Себеж»)."""
    for it in items:
        if it["kind"] != "caption":
            continue
        for part in re.split(r"[·\n]", it["text"]):
            m = ROUTE_RE.search(part)
            if not m:
                continue
            ends = [e.strip(" .") for e in m.groups()]
            far = [e for e in ends if not e.startswith("Рига")]
            if len(far) == 1:
                return far[0]
    return None


def read_book(src, report):
    """All columns in the book, plus the (milepost, station) pairs."""
    columns, mileposts = [], []
    for path in sorted(src.glob("page-*.md"), key=lambda p: int(re.findall(r"\d+", p.name)[0])):
        page = parse_book_page(path.read_text())
        sheet = page["sheet"]
        shapes = page["shapes"]
        for i, half in enumerate(page["halves"]):
            shape = shapes[i] if i < len(shapes) else "UNKNOWN"
            folio = half["folio"]
            if shape in SKIP_SHAPES:
                continue
            if shape not in SHAPE_RULES:
                # Skipped **and reported**: a quiet fallback is what let a
                # whole chapter sit unnormalized.
                report.append(Finding(
                    0, 1.0, 0, Where(sheet, folio, shape, "—"),
                    f"shape {shape!r} — not checked, no rules apply to it"))
                continue
            cols, mps = read_half(sheet, folio, shape, half["items"], report)
            columns.extend(cols)
            mileposts.extend(mps)
    return columns, mileposts


# --------------------------------------------------------------------- rules

def rule0_bad_cells(col, out):
    """Non-time text in a time cell. Impossible by inspection, so ranked first."""
    for s in col.stops:
        for cell, c in ((s.arr, s.cols[0]), (s.dep, s.cols[1])):
            if cell.kind == "bad" and c is not None:
                out.append(Finding(0, 10.0, 0, col.where(s, [(s.row, c)]),
                                   f"{cell.text!r} is not a time"))


def fit_direction(col, out):
    """Direction is fitted per column pair, both ways; better fit wins."""
    seq = [s for s in col.stops if s.timed]
    if len(seq) < 2:
        col.direction = 1
        return
    def falls(order):
        times = [t for s in order for t in (s.arr.sec, s.dep.sec) if t is not None]
        return sum(1 for a, b in zip(times, times[1:]) if b < a)
    down, up = falls(seq), falls(list(reversed(seq)))
    if down < up:
        col.direction = 1
    elif up < down:
        col.direction = -1
    else:
        col.direction = 1 if down == 0 else None
        if down:
            # No fit is itself a finding: the column reads as badly one way as
            # the other, which is what a shuffled or misaligned column does.
            first, last = seq[0], seq[-1]
            out.append(Finding(
                0, 4.0 + down, 1,
                col.where(cells=[(first.row, first.cols[0]), (last.row, last.cols[0])]),
                f"times fit neither direction ({down} backwards steps each way)"))


def rule1_monotone(col, out):
    """Times increase along the direction of travel, on a cumulative clock.

    24.00 is midnight and night trains wrap, so one wrap is expected; a second
    one in a column is a finding. A backwards step that does not look like
    midnight is damage, and the day is *not* added for it -- the leg it belongs
    to is marked suspect instead, so a bad digit cannot pass a 24-hour running
    time into rule 4's sample.
    """
    order = col.travel()
    offset, prev, wraps = 0, None, 0
    for s in order:
        for attr, cell, c in (("cum_arr", s.arr, s.cols[0]), ("cum_dep", s.dep, s.cols[1])):
            if not cell.timed:
                continue
            v = cell.sec + offset
            if cell.sec == DAY and wraps == 0:
                # 24.00 is the wrap itself: it ends this day, so what
                # follows is on the next one, even inside a stop.
                offset += DAY
                v = cell.sec - DAY + offset
                wraps += 1
            if prev is not None and v < prev:
                at_stop = attr == "cum_dep" and s.cum_arr is not None
                midnight = (prev % DAY >= CONFIG["wrap_evening_after_h"] * 3600
                            and cell.sec <= CONFIG["wrap_morning_before_h"] * 3600
                            and (not at_stop
                                 or v + DAY - prev <= CONFIG["wrap_max_dwell_min"] * 60))
                if midnight and wraps == 0:
                    offset += DAY
                    v += DAY
                    wraps += 1
                else:
                    s.suspect = True
                    # A departure before its arrival is impossible (rule 2); a
                    # backwards step between stops is rule 1.
                    rule, what = (2, "departure before its arrival") if at_stop else \
                                 (1, "time steps backwards along the run")
                    detail = ""
                    if midnight and wraps:
                        detail = " — a second wrap in this column"
                    out.append(Finding(
                        0, 6.0 + (2.0 if wraps else 0.0), rule,
                        col.where(s, [(s.row, c)]),
                        f"{what}: {hhmm(prev)} then {cell.text}{detail}",
                        {"direction": "down the page" if col.direction != -1 else "up the page"}))
            setattr(s, attr, v)
            prev = v


def rule1_blanks(col, out):
    """Blanks should run contiguously to the ends of the column."""
    served = [i for i, s in enumerate(col.stops) if s.served]
    if not served:
        return
    for i in range(served[0], served[-1] + 1):
        s = col.stops[i]
        if s.served:
            continue
        prev_s, next_s = col.stops[i - 1], col.stops[i + 1]
        if prev_s.served and next_s.served:
            out.append(Finding(
                0, 5.0, 1, col.where(s, [(s.row, s.cols[0])]),
                "blank between two served stations — the train cannot skip a "
                "stop without a — (pass) mark"))


def rule2_dwells(col, dwells):
    """отпр. >= приб. at a stop. The sign is rule 1's job; here we collect the
    dwell so it can be ranked against the same station elsewhere -- junctions
    really do hold ten minutes."""
    for s in col.stops:
        if s.cum_arr is None or s.cum_dep is None or s.suspect:
            continue
        where = col.where(s, [(s.row, s.cols[0]), (s.row, s.cols[1])])
        dwells[s.station].append((s.cum_dep - s.cum_arr, where))


def rule3_speeds(col, speeds, out):
    """Implied speed, dkm/dt, on the distance sheets.

    The only rule that crosses the two number systems on the page: it ties the
    printed times to the printed mileposts.
    """
    order = [s for s in col.travel() if s.km is not None]
    for a, b in zip(order, order[1:]):
        t0, t1 = a.last(), b.first()
        if t0 is None or t1 is None or a.suspect or b.suspect:
            continue
        if a.zone != b.zone:
            continue    # the mileposting resets here; the difference is not a leg
        dkm = abs(a.km - b.km)
        dt = t1 - t0
        cells = [(a.row, a.cols[1] if a.cum_dep is not None else a.cols[0]),
                 (b.row, b.cols[0] if b.cum_arr is not None else b.cols[1])]
        where = col.where(a, cells)
        where.station = f"{a.station} → {b.station}"
        if dkm == 0:
            continue
        if dt <= 0:
            out.append(Finding(0, 9.0, 3, where,
                               f"{dkm:.1f} km covered in no time at all "
                               f"({hhmm(t0)} → {hhmm(t1)})"))
            continue
        kmh = dkm / (dt / 3600)
        if kmh > CONFIG["max_speed_kmh"]:
            out.append(Finding(
                0, 7.0 + kmh / CONFIG["max_speed_kmh"], 3, where,
                f"implied {kmh:.0f} km/h over {CONFIG['max_speed_kmh']:.0f} — "
                f"{dkm:.1f} km in {mmss(dt)} ({hhmm(t0)} → {hhmm(t1)})"))
        else:
            speeds.append((kmh, where, dkm, dt))


def rule4_legs(col, legs):
    """Group adjacent (station A, station B) pairs by name and direction.

    Each direction is its own sample. A leg can genuinely run slower one way --
    Засулаукс—Золитуде is 2:30 up and 4:45 down -- and pooling the two makes
    every train in the slower direction an outlier. Splitting also gives more
    legs an opinion, not fewer: twice the keys, and more of them clear
    `min_samples`.
    """
    order = col.travel()
    for a, b in zip(order, order[1:]):
        t0, t1 = a.last(), b.first()
        if t0 is None or t1 is None or not a.station or not b.station:
            continue
        if a.suspect or b.suspect or t1 < t0:
            continue    # already reported by rule 1; not evidence about the leg
        key = (a.station, b.station)
        cells = [(a.row, a.cols[1] if a.cum_dep is not None else a.cols[0]),
                 (b.row, b.cols[0] if b.cum_arr is not None else b.cols[1])]
        where = col.where(a, cells)
        where.station = f"{a.station} → {b.station}"
        legs[key].append((t1 - t0, where))


def score_group(samples, out, rule, z_key, ratio_key, min_diff, what, unit=mmss):
    """Score one pooled group (a leg, or a station's dwells) by modified z.

    n, median and MAD are reported with every finding: real legs vary, and the
    spread is how the finding is judged by eye.
    """
    if len(samples) < CONFIG["min_samples"]:
        return          # under min_samples a leg gets no opinion
    values = [v for v, *_ in samples]
    for value, where, *extra in samples:
        dev, med, mad, how = modified_z(value, values)
        limit = CONFIG[z_key] if how == "z" else CONFIG[ratio_key]
        if dev <= limit:
            continue
        if abs(value - med) < CONFIG[min_diff]:
            # The book prints to the half minute. A sample a printed tick from
            # the median is not evidence of anything, however tight the spread
            # -- and with MAD 0 the spread is as tight as it gets.
            continue
        out.append(Finding(
            1, dev, rule, where,
            f"{what} {unit(value)} against {unit(med)} elsewhere "
            f"({'modified z' if how == 'z' else 'ratio'} {dev:.1f})",
            {"n": len(values), "median": unit(med), "MAD": unit(mad)}))


def score_speeds(speeds, out):
    """A leg's implied speed against every other leg in the book.

    Rule 4 has no opinion on a leg only two trains run; the book-wide spread of
    speeds still does.
    """
    if len(speeds) < CONFIG["min_samples"]:
        return
    values = [v for v, *_ in speeds]
    for kmh, where, dkm, dt in speeds:
        dev, med, mad, how = modified_z(kmh, values)
        if how != "z" or dev <= CONFIG["speed_deviation_threshold"]:
            continue
        out.append(Finding(
            1, dev, 3, where,
            f"implied {kmh:.0f} km/h against {med:.0f} km/h book-wide "
            f"({dkm:.1f} km in {mmss(dt)}, modified z {dev:.1f})",
            {"n": len(values), "median": f"{med:.0f} km/h", "MAD": f"{mad:.1f}"}))


def same_station_misspelt(a, b):
    """Are these two names one station, typed twice?

    Lines reuse kilometre numbers -- 141,1 is Стренчи on the Valga line and
    Пярну-пасс. on the Pärnu one -- so a shared milepost only means damage when
    the two names are the same name.
    """
    def norm(x):
        return "".join(c for c in x.lower() if c.isalnum())
    if norm(a) == norm(b):
        return True
    return SequenceMatcher(None, norm(a), norm(b)).ratio() >= CONFIG["name_similarity"]


def rule5_mileposts(mileposts, out):
    """Distance -> station name agrees book-wide.

    Each milepost has one name and each name one milepost. The cheapest rule,
    almost no false positives, and it doubles as a spell-check on the station
    column.
    """
    by_km, by_name = defaultdict(list), defaultdict(list)
    for reckoning, km, name, where in mileposts:
        by_km[(reckoning, km)].append((name, where))
        by_name[(reckoning, name)].append((km, where))

    def report(groups, label, fmt, only_similar=False):
        for (reckoning, key), entries in sorted(groups.items()):
            counts = defaultdict(list)
            for other, where in entries:
                counts[other].append(where)
            if len(counts) < 2:
                continue
            best = max(counts, key=lambda k: len(counts[k]))
            for other, wheres in counts.items():
                if other == best or (only_similar and not same_station_misspelt(other, best)):
                    continue
                for where in wheres:
                    out.append(Finding(
                        0, 8.0 + len(counts[best]) - len(wheres), 5, where,
                        f"{label} {fmt(key)} is {fmt(other)} here but "
                        f"{fmt(best)} on {len(counts[best])} other "
                        f"{reckoning} sheet(s)",
                        {"variants": ", ".join(f"{fmt(k)}×{len(v)}" for k, v in counts.items())}))

    report(by_km, "milepost", lambda k: f"{k:.1f} км" if isinstance(k, float) else str(k),
           only_similar=True)
    report(by_name, "station", str)


# ------------------------------------------------------------------ collapse

def collapse(findings):
    """One cell, one finding; one bad column, one finding."""
    by_cell, clusters = {}, []
    for f in findings:
        hit = next((by_cell[c] for c in f.cells if c in by_cell), None)
        if hit is None:
            clusters.append(f)
            hit = f
        else:
            hit.merge(f)
        for c in hit.cells:
            by_cell[c] = hit
    clusters = list(dict.fromkeys(clusters))

    # A run of outliers in one column is one finding, not eight -- that is a
    # column misaligned by a row, which is worse than a bad digit.
    by_col = defaultdict(list)
    for f in clusters:
        owners = {(sheet, folio, train) for sheet, folio, train, _, _ in f.cells}
        if len(owners) == 1:
            cols = frozenset(c for *_, c in f.cells)
            by_col[(owners.pop(), cols)].append(f)
    out, absorbed = [], set()
    for key, group in by_col.items():
        group.sort(key=lambda f: min(r for *_, r, _ in f.cells))
        run = []
        for f in group + [None]:
            if f is not None and (not run or min(r for *_, r, _ in f.cells)
                                  <= max(r for *_, r, _ in run[-1].cells) + 1):
                run.append(f)
                continue
            if len(run) >= CONFIG["misalign_run"]:
                rows = sorted({r for g in run for *_, r, _ in g.cells})
                (sheet, folio, train), cols = key
                where = Where(sheet, folio, run[0].where.shape, train,
                              f"rows {rows[0]}–{rows[-1]}",
                              [(r, c) for r in rows for c in sorted(cols)])
                merged = Finding(
                    0, 12.0 + len(run), 0, where,
                    f"{len(run)} findings on consecutive rows of one column — "
                    "read as a column misaligned by a row, not as bad digits",
                    {"first": run[0].message})
                merged.rules = set().union(*(g.rules for g in run))
                out.append(merged)
                absorbed.update(id(g) for g in run)
            run = [f] if f is not None else []
    out.extend(f for f in clusters if id(f) not in absorbed)
    return sorted(out, key=lambda f: f.rank)


# -------------------------------------------------------------------- driver

def validate(src):
    findings = []
    columns, mileposts = read_book(src, findings)
    legs, dwells, speeds = defaultdict(list), defaultdict(list), []
    for col in columns:
        rule0_bad_cells(col, findings)
        fit_direction(col, findings)
        rule1_monotone(col, findings)
        rule1_blanks(col, findings)
        rule2_dwells(col, dwells)
        rule4_legs(col, legs)
        if col.shape in SPEED_SHAPES:
            rule3_speeds(col, speeds, findings)
    for samples in legs.values():
        score_group(samples, findings, 4, "deviation_threshold", "ratio_threshold",
                    "leg_min_diff_sec", "running time")
    for samples in dwells.values():
        score_group(samples, findings, 2, "dwell_deviation_threshold",
                    "dwell_ratio_threshold", "dwell_min_diff_sec", "dwell")
    score_speeds(speeds, findings)
    rule5_mileposts(mileposts, findings)
    return columns, collapse(findings)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--book", type=Path, default=BOOK, help="directory to read")
    ap.add_argument("--limit", type=int, default=40, help="findings to print (0 = all)")
    ap.add_argument("--rule", type=int, action="append", help="only these rules")
    ap.add_argument("--impossible", action="store_true", help="only the impossible ones")
    ap.add_argument("--json", action="store_true", help="findings as JSON")
    a = ap.parse_args()

    columns, findings = validate(a.book)
    if a.rule:
        findings = [f for f in findings if f.rules & set(a.rule)]
    if a.impossible:
        findings = [f for f in findings if f.severity == 0]

    if a.json:
        json.dump([f.as_dict() for f in findings], sys.stdout,
                  ensure_ascii=False, indent=2)
        print()
    else:
        shown = findings if not a.limit else findings[:a.limit]
        for f in shown:
            print(f.render())
            print()
        hard = sum(1 for f in findings if f.severity == 0)
        print(f"{len(columns)} train columns checked; {len(findings)} findings "
              f"({hard} impossible, {len(findings) - hard} deviations), "
              f"{len(shown)} shown.")
        print("Triage, not a verdict — check each against the scan. "
              "Nothing here has been repaired.")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
