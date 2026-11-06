"""Score stop_names.py against the golden sample.

    python3 tools/stop-name-normalizer/check_golden.py [attempts/final-01] [--max-dist 8] [--ratio 0.6]

For each golden line (form -> target) says at which distance the script pairs
them, that its checks flag the form, that a notation finding sets the two
against each other, or why none: the form or the target is not in the dir, or
the two are too far apart. A notation line (… for any text, # for a number) is
found when every name printed as the form is set against a name printed as the
target. Then lists the pairs the script found that no golden line explains
(different stops, or forms the golden sample misses).
"""
import argparse
import re
from pathlib import Path

from stop_names import ROOT, checks, shown, collect, key, lev, notation_pairs, notations, pair_levels, where

HERE = Path(__file__).parent
TAGS = ("mistake", "artifact", "scatter", "form")


def read_golden(path):
    rows = []
    for line in path.read_text().splitlines():
        parts = [p.strip() for p in line.split("|")]
        if parts and parts[0] in TAGS:
            tag, form, target, count = parts[:4]
            rows.append((tag, form, target, count))
    return rows


def pattern(p):
    """Notation side -> regex: … is any text, # a number."""
    rx = re.escape(p).replace("…", ".*").replace("\\#", r"[\d,]+").replace("\\ ", " ")
    return re.compile("^" + rx + "$")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("src", type=Path, nargs="?", default=ROOT / "attempts" / "final-01",
                    help="scan dir (default attempts/final-01)")
    ap.add_argument("--golden", type=Path, default=HERE / "golden" / "stop-name-findings.txt")
    ap.add_argument("--max-dist", type=int, default=8)
    ap.add_argument("--ratio", type=float, default=0.6)
    a = ap.parse_args()

    occ = collect(a.src)
    levels = pair_levels(occ, a.max_dist, a.ratio)
    found = {frozenset(p): d for d, ps in levels.items() for p in ps}
    flagged = {n for n, _ in checks(occ)}
    noted = notation_pairs(notations(occ))
    golden = read_golden(a.golden)

    print(f"# {shown(a.src)} against {a.golden.name}: max distance {a.max_dist}, ratio {a.ratio}\n")
    print(f"{'tag':8} | {'form':22} | {'target':20} | {'count':9} | result")
    tally = {}
    for tag, form, target, count in golden:
        if "…" in form or "#" in form:
            fs = [n for n in occ if pattern(form).match(n)]
            ts = [n for n in occ if pattern(target).match(n)]
            got = sum(len(occ[n]) for n in fs)
            cnt = f"{got}/{count}"
            left = [f for f in fs if not any(frozenset((f, t)) in noted for t in ts if t != f)]
            if not fs:
                res = "MISS form not in dir"
            elif not ts:
                res = "MISS target not printed"
            elif left:
                res = f"MISS notation, {len(left)} of {len(fs)} names not set against the target: " \
                      + ", ".join(left)
            else:
                res = f"found by notations ({len(fs)} names ~ {len(ts)} names)"
            tally[res.split()[0]] = tally.get(res.split()[0], 0) + 1
            print(f"{tag:8} | {form:22} | {target:20} | {cnt:9} | {res}")
            continue
        got = len(occ.get(form, []))
        cnt = f"{got}/{count}"
        d = lev(key(form), key(target))
        r = d / min(len(form), len(target))
        if not got:
            res = "MISS form not in dir"
        elif frozenset((form, target)) in found:
            res = f"found at d{found[frozenset((form, target))]}"
            if form in flagged:
                res += "; flagged by checks"
        elif form in flagged:
            res = "found by checks"
        elif frozenset((form, target)) in noted:
            res = "found by notations"
        elif target not in occ:
            res = "MISS target not printed"
        else:
            res = f"MISS d{d}, ratio {r:.2f}"
        tally[res.split()[0]] = tally.get(res.split()[0], 0) + 1
        print(f"{tag:8} | {form:22} | {target:20} | {cnt:9} | {res}")
    print("\n" + ", ".join(f"{k} {v}" for k, v in sorted(tally.items())))

    forms = {f for _, f, _, _ in golden} | {t for _, _, t, _ in golden}
    print("\n## pairs no golden line explains")
    for d in sorted(levels):
        extra = [(x, y) for x, y in levels[d] if not ({x, y} & forms)]
        print(f"\n### distance {d}: {len(extra)} of {len(levels[d])}")
        if d <= 2:
            for x, y in extra:
                print(f"  {x} ({len(occ[x])}) ~ {y} ({len(occ[y])})  [{where(occ, x)} | {where(occ, y)}]")


if __name__ == "__main__":
    main()
