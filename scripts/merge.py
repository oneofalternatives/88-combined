#!/usr/bin/env python3
"""Merge several extractions of the same book into one, by vote.

Every --src run gets an equal vote. A cell they all agree on is written as is.
A cell they disagree on keeps every reading, most votes first:

    ⟨06.52,5 ¦ 06.52.5⟩        ∅ stands for an empty cell

--extra runs never vote. Their reading is added only where the --src runs
already disagree, and breaks a tie in the order. Use it for a weaker run that
still reads some cells right (e.g. a low-resolution OCR).

Cells can only be voted when the runs lay the page out the same way: the same
blocks, and tables of the same size. The layout most --src runs share wins and
the others sit that page out. With no such majority, or when the majority is a
table extract.py could not recognise (UNKNOWN), each layout is written one
after the other, marked ⟨alternative …⟩, for a person to choose.

Every ⟨…⟩ is listed in disputes.txt. The output is not a valid scan file until
they are resolved, on purpose: the validator and the PDF build reject it.
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path
from typing import NamedTuple

sys.path.insert(0, str(Path(__file__).parent))

import attempts
from book_model import parse_book_table
from extract import Divider, as_markdown

SEP = " ¦ "
EMPTY = "∅"


def variants(values) -> str:
    return "⟨" + SEP.join(v or EMPTY for v in values) + "⟩"


# ------------------------------------------------------------------ reading
class Table(NamedTuple):
    rows: list          # lists of cells, and Dividers
    header_count: int   # as extract.as_markdown counts it: rows up to the head rule
    width: int


def as_table(text: str):
    """The table in `text`, or None when it is not in extract.py's own format
    (raw OCR kept on an UNKNOWN page) -- that is merged as text."""
    t = parse_book_table(text)
    rows, hc = [], 0
    for it in t["items"]:
        if it["kind"] == "rule":
            continue
        if it["kind"] == "band":
            rows.append(Divider([it["text"]]))
            continue
        rows.append(list(it["cells"]))
        if it["kind"] == "head":
            hc = len(rows)
    try:
        if rows and as_markdown(rows, hc, t["width"]) == text:
            return Table(rows, hc, t["width"])
    except (ValueError, IndexError):
        pass
    return None


def blocks(lines):
    """A page's text as blocks: Tables and strings.

    extract.py writes the heading, a blank line, then each block followed by one
    blank line. An empty block (a page with no text) is thus an extra blank line,
    and is kept as "" so the file reads back exactly.
    """
    out, i = [], 1
    while i < len(lines):
        j = i
        while j < len(lines) and lines[j].strip():
            j += 1
        text = "\n".join(lines[i:j])
        out.append((text.startswith("|") and as_table(text)) or text)
        i = max(j, i + 1) + 1  # the block, then its blank line
    return out


def read_scan(path: Path):
    """(frontmatter lines, {key: value}, [(heading, blocks)]) for one scan file."""
    lines = path.read_text().splitlines()
    end = lines.index("---", 1)
    head = lines[:end + 1]
    meta = dict(ln.split(": ", 1) for ln in head[1:-1])
    pages = []
    for ln in lines[end + 1:]:
        if ln.startswith("## page"):
            pages.append((ln, []))
        elif pages:
            pages[-1][1].append(ln)
    return head, meta, [(h, blocks(b)) for h, b in pages]


def shapes(meta) -> list[str]:
    return [s.strip() for s in meta["shapes"].strip("[]").split(",")]


def layout(page_blocks):
    """What must match for two runs' pages to be voted cell by cell."""
    return tuple(("table", b.width, b.header_count,
                  tuple("band" if isinstance(r, Divider) else "row" for r in b.rows))
                 if isinstance(b, Table) else "text" for b in page_blocks)


# ------------------------------------------------------------------ voting
class Dispute(NamedTuple):
    scan: int
    page: str
    where: str
    readings: str   # value (runs), most votes first


def vote(values: dict, voters: list, extras: list):
    """(merged value, dispute or None) for one cell. values: run -> reading."""
    counts = Counter(values[r] for r in voters)
    if len(counts) == 1:
        return values[voters[0]], None
    first = {}
    for i, r in enumerate(voters):
        first.setdefault(values[r], i)
    backed = {values[r] for r in extras}
    order = sorted(counts, key=lambda v: (-counts[v], v not in backed, first[v]))
    order += [v for v in dict.fromkeys(values[r] for r in extras) if v not in counts]
    who = {v: [r for r in voters + extras if values[r] == v] for v in order}
    detail = "; ".join(f"{v or EMPTY} ({', '.join(who[v])})" for v in order)
    return variants(order), detail


def train_of(table: Table, c: int) -> str:
    """The train a column belongs to: the nearest train number at or left of it."""
    head = [r for r in table.rows[:table.header_count] if not isinstance(r, Divider)]
    if not head:
        return ""
    return next((head[0][j] for j in range(c, 0, -1) if head[0][j]), "")


def merge_table(tables: dict, voters, extras, note):
    """One table from runs that share its layout; note(where, detail) logs disputes."""
    base = tables[voters[0]]
    rows = []
    for i, row in enumerate(base.rows):
        if isinstance(row, Divider):
            text, d = vote({r: tables[r].rows[i][0] for r in tables}, voters, extras)
            if d:
                note(f"band, row {i + 1}", d)
            rows.append(Divider([text]))
            continue
        out = []
        for c in range(base.width):
            cell, d = vote({r: tables[r].rows[i][c] for r in tables}, voters, extras)
            if d:
                where = f"row {i + 1} col {c + 1}"
                if i >= base.header_count:
                    where += f" · {row[0]} · {train_of(base, c)}".rstrip(" ·")
                note(where, d)
            out.append(cell)
        rows.append(out)
    return as_markdown(rows, base.header_count, base.width)


def merge_text(texts: dict, voters, extras, note, n):
    """Text line by line; when the runs split it into different lines, each
    reading whole, marked with the runs that gave it."""
    split = {r: t.split("\n") for r, t in texts.items()}
    if len({len(s) for s in split.values()}) == 1:
        out = []
        for j in range(len(split[voters[0]])):
            line, d = vote({r: s[j] for r, s in split.items()}, voters, extras)
            if d:
                note(f"text block {n}, line {j + 1}", d)
            out.append(line)
        return "\n".join(out)
    groups = {}
    for r in voters + extras:
        groups.setdefault(texts[r], []).append(r)
    note(f"text block {n}", "; ".join(f"{len(t.splitlines())} lines ({', '.join(rs)})"
                                      for t, rs in groups.items()))
    return "\n\n".join(f"⟨text from {', '.join(rs)}⟩\n{t}" for t, rs in groups.items())


def merge_page(pages: dict, voters, extras, note):
    """One page's blocks from runs that share its layout."""
    out = []
    for n, b in enumerate(pages[voters[0]], 1):
        got = {r: pages[r][n - 1] for r in pages}
        if isinstance(b, Table):
            out.append(merge_table(got, voters, extras, lambda w, d: note(f"table {n}, {w}", d)))
        else:
            out.append(merge_text(got, voters, extras, note, n))
    return out


def merge_scan(files: dict, voters: list, extras: list):
    """(text of the merged scan file, disputes, pages given as alternatives).
    files: run -> path of its scan file; voters and extras name the runs."""
    read = {r: read_scan(p) for r, p in files.items()}
    head, meta, _ = read[voters[0]]
    n = int(meta["scan"])
    disputes, alternatives = [], 0
    # Runs that split the scan into a different number of pages sit it out.
    count = Counter(len(read[r][2]) for r in voters).most_common(1)[0][0]
    voters = [r for r in voters if len(read[r][2]) == count]
    extras = [r for r in extras if len(read[r][2]) == count]
    body, page_shapes = [], []
    for k in range(count):
        heading = read[voters[0]][2][k][0]
        page = heading[len("## page"):].strip()

        def note(where, detail):
            disputes.append(Dispute(n, page, where, detail))

        groups = {}
        for r in voters + extras:
            groups.setdefault(layout(read[r][2][k][1]), []).append(r)
        ranked = sorted(groups.values(), key=lambda g: -sum(r in voters for r in g))
        top = [r for r in ranked[0] if r in voters]
        shape = shapes(read[top[0]][1])[k]
        tied = len(ranked) > 1 and sum(r in voters for r in ranked[1]) == len(top)
        body += [heading, ""]
        if len(top) >= 2 and not tied and (shape != "UNKNOWN" or len(ranked) == 1):
            group = ranked[0]
            left = [r for g in ranked[1:] for r in g]
            if left:
                note("layout", f"outvoted, not merged: {', '.join(left)}")
            parts = merge_page({r: read[r][2][k][1] for r in group},
                               top, [r for r in group if r in extras], note)
            page_shapes.append(shape)
        else:
            alternatives += 1
            note("layout", f"{len(ranked)} alternatives: "
                 + " / ".join(", ".join(g) for g in ranked))
            parts = []
            for g in ranked:
                g_voters = [r for r in g if r in voters] or g
                sh = shapes(read[g[0]][1])[k]
                parts.append(f"⟨alternative from {', '.join(g)} ({sh})⟩")
                parts += merge_page({r: read[r][2][k][1] for r in g},
                                    g_voters, [r for r in g if r not in g_voters], note)
            page_shapes.append("UNKNOWN")
        for p in parts:
            body += [p, ""]
    head = [f"shapes: [{', '.join(page_shapes)}]" if ln.startswith("shapes:") else ln
            for ln in head]
    return "\n".join(head + [""] + body), disputes, alternatives


def dispute_table(disputes) -> str:
    rows = [["scan", "page", "where", "readings"]]
    rows += [[str(d.scan), d.page, d.where, d.readings] for d in disputes]
    return as_markdown(rows, 1, 4) + "\n" if disputes else ""


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", type=Path, nargs="+", required=True,
                    help="scan file dirs that vote, equally; on a tie the earlier one leads")
    ap.add_argument("--extra", type=Path, nargs="*", default=[],
                    help="scan file dirs shown only where the --src dirs disagree")
    ap.add_argument("--dest", type=Path, required=True, help="dir to write the merge to")
    a = ap.parse_args()
    if len(a.src) < 2:
        sys.exit("--src: give at least two dirs")
    if a.dest.exists() and any(a.dest.iterdir()):
        sys.exit(f"{a.dest}: not empty")
    # Output into attempts/merged-NN makes an attempt: finished inputs, a
    # manifest and an index row once done.
    made = a.dest.parent == attempts.ROOT and a.dest.name.startswith("merged-")
    if made:
        for d in a.src + a.extra:
            attempts.require_finished(d)
    name = {d: d.name.rsplit("-", 1)[-1] for d in a.src + a.extra}
    if len(set(name.values())) != len(name):
        name = {d: str(d) for d in name}
    voters = [name[d] for d in a.src]
    extras = [name[d] for d in a.extra]
    wanted = sorted({p.name for d in a.src for p in d.glob("scan-*.md")})

    a.dest.mkdir(parents=True, exist_ok=True)
    disputes, alternatives = [], 0
    for f in wanted:
        have = {name[d]: d / f for d in a.src + a.extra if (d / f).exists()}
        v = [r for r in voters if r in have]
        if len(v) < 2:
            sys.exit(f"{f}: in fewer than two --src dirs")
        text, found, alt = merge_scan(have, v, [r for r in extras if r in have])
        (a.dest / f).write_text(text)
        disputes += found
        alternatives += alt

    (a.dest / "disputes.txt").write_text(dispute_table(disputes))
    cells = sum(1 for d in disputes if d.where != "layout")
    print(f"{len(wanted)} scans; {cells} disputed cells or lines, "
          f"{alternatives} pages given as alternatives -> {a.dest / 'disputes.txt'}")
    if made:
        # The index row lists the pieces of every merged run, from their own rows.
        _, rows = attempts._rows()
        pieces = [next((r[1:4] for r in rows if r[4] == d.name), [attempts.NONE] * 3)
                  for d in a.src + a.extra]
        cols = [", ".join(dict.fromkeys(p[i] for p in pieces)) for i in range(3)]
        note = "merge of " + " ".join(voters) + (f", extra {' '.join(extras)}" if extras else "")
        # Index first: if it fails, the dir stays unfinished and can be rerun.
        attempts.add_attempt(*cols, a.dest.name, note)
        attempts.finish(a.dest, {"src": [str(d) for d in a.src], "extra": [str(d) for d in a.extra],
                                 "scans": len(wanted), "disputes": cells,
                                 "alternatives": alternatives})
    return 0


if __name__ == "__main__":
    sys.exit(main())
