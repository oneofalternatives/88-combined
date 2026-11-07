"""Find stop names spelt more than one way in a scan dir.

    python3 tools/stop-name-normalizer/stop_names.py attempts/final-01 [--max-dist 2] [--ratio 0.5]
    python3 tools/stop-name-normalizer/stop_names.py attempts/final-01 --dump

Reads the stop-name column of every table (the «пункты» column on two-way pages,
column 0 elsewhere), the route titles (Рига—Елгава · Елгава—Рига), routes in
table cells (the contents) and notes in time cells («На Царникаву»). A merge
mark ⟨a ¦ b⟩ gives one spelling per reading.

Pairs every two spellings by edit distance, raising the distance one step at a
time, and prints only the pairs new at each step. A pair is kept when
distance / length of the shorter name <= --ratio. It also prints names with a
non-Cyrillic letter (Roman numerals aside), names with a «- » left by a line
break, and words with a «-» that join into a known name (Царни-каву).

Then notations, the parts around the stop's own name (О/п., Б/п., -пасс., -II,
Пост … км): a part printed more than one way (О. п. / о. п. / О/п.), and names
that differ only by an abbreviation (Б/п. / Блок пост), an Arabic or Roman
number (-1 / -I) or a word before the same milepost (78 км / Пост 78 км). Each
finding lists every name of either shape (a number as #).
Pairs in ignore.txt (checked: different stops) are left out; --no-ignore keeps them.
Nothing is repaired: which spelling is right is for a person to say.
"""
import argparse
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
IGNORE = Path(__file__).resolve().parent / "ignore.txt"
SKIP = re.compile(r"^[\d.,\s—\-]*$|^№|^Разд|^Прибытие$|^∅$")
MARK = re.compile(r"⟨(.*)⟩")
ROMAN = re.compile(r"(?<![A-Za-z])[IVX]+(?![A-Za-z])")


def readings(cell):
    """One cell -> its spellings; a merge mark gives one per reading."""
    m = MARK.fullmatch(cell)
    parts = m.group(1).split("¦") if m else [cell]
    return [p.strip() for p in parts if p.strip() and not SKIP.match(p.strip())]


NOTE = re.compile(r"^На [А-ЯЁ]")


def route_names(text):
    """Рига—Себеж, Даугавпилс · Елгава—Рига. -> the names in it."""
    out = []
    for part in re.split(r"[·¦,]", text):
        for n in part.strip().strip("⟨⟩#").split("—"):
            n = n.strip().strip("⟨⟩#").strip()
            if re.search(r"(^|[\s-])[А-ЯЁ][^\s-]*\.$", n):
                n = n[:-1]  # a full stop, not an abbreviation like -пасс.
            if 2 < len(n) < 30 and not re.search(r"[\d№]", n):
                out.append(n.capitalize() if n.isupper() else n)
    return out


def collect(src):
    """name -> [(scan, line)] over every scan file in src."""
    occ = defaultdict(list)
    for f in sorted(Path(src).glob("scan-*.md")):
        col = 0
        for ln, line in enumerate(f.read_text().splitlines(), 1):
            if line.startswith("|"):
                if line.startswith("|="):
                    continue
                cells = [c.strip() for c in line.strip().strip("|").split("|")]
                hdr = [i for i, c in enumerate(cells) if "пункт" in c.lower()]
                if hdr:
                    col = hdr[0]
                    continue
                for i, c in enumerate(cells):
                    if i == col:
                        names = readings(c)
                    elif NOTE.match(c):
                        names = [c]
                    elif "—" in c and re.search(r"[А-яЁё]", c):
                        names = route_names(c)
                    else:
                        continue
                    for n in names:
                        occ[n].append((f.stem, ln))
                continue
            if line.strip():
                col = 0
            if "—" in line and not line.startswith(("#", "Не ", "Поезд")):
                for n in route_names(line):
                    occ[n].append((f.stem, ln))
    return occ


def lev(x, y):
    p = list(range(len(y) + 1))
    for i, cx in enumerate(x, 1):
        c = [i]
        for j, cy in enumerate(y, 1):
            c.append(min(p[j] + 1, c[j - 1] + 1, p[j - 1] + (cx != cy)))
        p = c
    return p[-1]


def key(s):
    return unicodedata.normalize("NFC", s).lower()


def pair_levels(names, max_dist, ratio):
    """{distance: [(a, b)]}, each pair at the lowest distance it shows up."""
    out = defaultdict(list)
    names = sorted(names)
    for i, x in enumerate(names):
        for y in names[i + 1:]:
            kx, ky = key(x), key(y)
            if abs(len(kx) - len(ky)) > max_dist:
                continue
            d = lev(kx, ky)
            if 0 < d <= max_dist and d / min(len(kx), len(ky)) <= ratio:
                out[d].append((x, y))
    return out


def read_ignore(path):
    """ignore.txt -> {frozenset((a, b))}: one pair per line, «a ~ b», # for notes."""
    out = set()
    for ln, line in enumerate(path.read_text().splitlines(), 1):
        line = line.split("#")[0].strip()
        if not line:
            continue
        a, sep, b = (p.strip() for p in line.partition("~"))
        if not (sep and a and b):
            sys.exit(f"{path}:{ln}: not «a ~ b»: {line}")
        out.add(frozenset((a, b)))
    return out


def odd_letters(name):
    rest = ROMAN.sub("", name)
    return [ch for ch in rest if ch.isalpha() and not ("А" <= ch <= "я" or ch in "ёЁ")]


def joined(occ):
    """Царни-каву -> Царникава: a word whose «-» joins into a known name, give or
    take its ending. The book's own hyphens (Рига-пасс., Килинги-Нымме) join
    into nothing."""
    words = {w for n in occ for w in re.findall(r"[А-яЁё]{4,}", n)}
    out = {}
    for n in occ:
        for a, b in re.findall(r"([А-яЁё]{2,})-([а-яё]{2,})", n):
            j = key(a + b)
            near = sorted(w for w in words
                          if abs(len(w) - len(j)) <= 1 and lev(key(w), j) <= 1)
            if near:
                out[n] = (f"{a}-{b}", near[0])
    return out


def checks(occ):
    """Names with a non-Cyrillic letter, a «- » from a line break, or a «-» that
    splits a known name."""
    out = []
    join = joined(occ)
    for n in sorted(occ):
        odd = odd_letters(n)
        if odd:
            out.append((n, "letter " + ", ".join(f"{c} ({unicodedata.name(c)})" for c in odd)))
        if re.search(r"\S- ", n):
            out.append((n, "«- » from a line break"))
        if n in join:
            out.append((n, "«-» from a line break: {} joins into {}".format(*join[n])))
    return out


# Notations: the parts of a name around the stop's own name.

TOKEN = re.compile(r"[^\s/-]+")
ROMAN_VAL = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5}


def tokens(name):
    """Блок- пост 856 км -> [('', 'Блок'), ('- ', 'пост'), (' ', '856'), (' ', 'км')]:
    each word with the separator printed before it."""
    out, end = [], 0
    for m in TOKEN.finditer(name):
        out.append((name[end:m.start()], m.group()))
        end = m.end()
    return out


def is_num(t):
    return bool(re.fullmatch(r"[\d,]+", t))


def is_roman(t):
    return t in ROMAN_VAL


def is_abbr(toks, i):
    """Ваг., п., or the Б of Б/п."""
    t = toks[i][1]
    nxt = toks[i + 1][0] if i + 1 < len(toks) else ""
    return t.endswith(".") or (len(t) == 1 and t.isalpha() and nxt == "/")


def shape(name):
    """The name with each Arabic number as #."""
    return re.sub(r"\d+(,\d+)?", "#", name)


def letters(t):
    return re.sub(r"[^\w]", "", t).lower()


def same(x, y):
    return x == y or (is_num(x) and is_num(y))


def abbreviates(x, y):
    """x is a short form of the full word y: Ваг. / Вагонный, Б / Блок."""
    return (not y.endswith(".") and y.isalpha() and len(letters(x)) < len(y)
            and key(y).startswith(letters(x)) and letters(x) != "")


def notation_diff(a, b):
    """How two names differ in notation only, or None: 'abbreviation' (Б/п. 856 км
    / Блок пост 856 км), 'number' (Вентспилс-1 / Вентспилс-I), 'word before a
    milepost' (78 км / Пост 78 км). Punctuation alone is left to the edit
    distance and the parts."""
    ta, tb = tokens(a), tokens(b)
    wa, wb = [t for _, t in ta], [t for _, t in tb]
    i = 0
    while i < min(len(wa), len(wb)) and same(wa[i], wb[i]):
        i += 1
    j = 0
    while j < min(len(wa), len(wb)) - i and same(wa[-1 - j], wb[-1 - j]):
        j += 1
    if i + j == 0:
        return None
    da, db = wa[i:len(wa) - j], wb[i:len(wb) - j]
    if not da and not db:
        return None
    if len(da) == len(db) == 1:
        x, y = da[0], db[0]
        for p, q in ((x, y), (y, x)):
            if is_num(p) and is_roman(q) and int(p) == ROMAN_VAL[q]:
                return "number"
    if len(da) == len(db):
        ok, short = True, False
        for k, (x, y) in enumerate(zip(da, db)):
            if x == y:
                continue
            if is_abbr(ta, i + k) and abbreviates(x, y):
                short = True
            elif is_abbr(tb, i + k) and abbreviates(y, x):
                short = True
            else:
                ok = False
        if ok and short:
            return "abbreviation"
    for short, full, q in ((a, b, db), (b, a, da)):
        # a word before the same bare milepost: 78 км / Пост 78 км
        if len(q) == 1 and re.fullmatch(r"[\d,]+ км", short) \
                and re.fullmatch(r"[А-ЯЁ][а-яё]{2,}", q[0]) and full == f"{q[0]} {short}":
            return "word before a milepost"
    return None


def parts(name):
    """The notation parts of a name: a run of abbreviations in front (О. п., Б/п.)
    and an abbreviation or Roman number at the end (-пасс., -II). Each part as
    (place, key, printed): the key ignores case and punctuation."""
    toks = tokens(name)
    out = []
    i = 0
    while i < len(toks) - 1 and is_abbr(toks, i):
        i += 1
    if i:
        head = "".join(s + t for s, t in toks[:i]) + toks[i][0]
        out.append(("front", "".join(letters(t) for _, t in toks[:i]), head + "…"))
    if len(toks) > 1 and i < len(toks) - 1:
        sep, t = toks[-1]
        if is_roman(t):
            out.append(("end", "Roman number", "…" + sep + "I…"))
        elif t.endswith(".") and t[0].islower() and len(t) > 2:
            out.append(("end", letters(t), "…" + sep + t))
    return out


def notations(occ):
    """[(why, {printed form: [names]})]: each part printed more than one way, and
    each pair of name shapes that differ only in notation, with every name of
    either shape."""
    found = []
    byp = defaultdict(lambda: defaultdict(list))
    for n in sorted(occ):
        for place, k, printed in parts(n):
            byp[(place, k)][printed].append(n)
    for (place, k), forms in sorted(byp.items()):
        if len(forms) > 1:
            found.append((f"{place} part printed {len(forms)} ways", dict(forms)))
    shapes = defaultdict(list)
    for n in sorted(occ):
        shapes[shape(n)].append(n)
    # shapes linked by one kind of difference, joined into groups
    group = {}
    names = sorted(occ)
    for x_i, x in enumerate(names):
        for y in names[x_i + 1:]:
            why = notation_diff(x, y)
            sx, sy = shape(x), shape(y)
            if not why or sx == sy:
                continue
            gx, gy = group.get((why, sx), {sx}), group.get((why, sy), {sy})
            if gx is not gy:
                gx |= gy
            for m in gx:
                group[(why, m)] = gx
    done = []
    for (why, _), g in sorted(group.items(), key=lambda kv: (kv[0][0], sorted(kv[1]))):
        if any(g is d for d in done):
            continue
        done.append(g)
        found.append((why, {m: shapes[m] for m in sorted(g)}))
    return found


def notation_pairs(found):
    """Every two names a notation finding sets against each other."""
    out = set()
    for _, forms in found:
        groups = list(forms.values())
        for gi, g in enumerate(groups):
            for h in groups[gi + 1:]:
                out |= {frozenset((x, y)) for x in g for y in h}
    return out


def shown(path):
    """A dir as the README writes it: from the repo root if it is inside."""
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def where(occ, n):
    return " ".join(sorted({s.replace("scan-", "") for s, _ in occ[n]}))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("src", type=Path, nargs="?", default=ROOT / "attempts" / "final-01",
                    help="scan dir (default attempts/final-01)")
    ap.add_argument("--max-dist", type=int, default=2)
    ap.add_argument("--ratio", type=float, default=0.5)
    ap.add_argument("--dump", action="store_true", help="list every name with its count")
    ap.add_argument("--dest", type=Path, help="write here instead of the terminal")
    ap.add_argument("--ignore", type=Path, default=IGNORE, help="pairs to leave out (default ignore.txt)")
    ap.add_argument("--no-ignore", action="store_true", help="keep the pairs in the ignore list")
    a = ap.parse_args()

    occ = collect(a.src)
    lines = []
    if a.dump:
        lines = [f"{len(occ[n])}\t{n}" for n in sorted(occ)]
    else:
        ignore = set() if a.no_ignore else read_ignore(a.ignore)
        head = f"# {shown(a.src)}: {len(occ)} names, max distance {a.max_dist}, ratio {a.ratio}"
        if not a.no_ignore:
            head += f", {len(ignore)} pairs in {shown(a.ignore)}"
        lines.append(head)
        lines.append("")
        lines.append("## checks")
        for n, why in checks(occ):
            lines.append(f"  {n} ({len(occ[n])})  {why}  [{where(occ, n)}]")
        lines.append("")
        found = notations(occ)
        lines.append(f"## notations: {len(found)}")
        for why, forms in found:
            lines.append(f"  {why}")
            for printed, ns in forms.items():
                lines.append(f"    {printed}: " + ", ".join(
                    f"{n} ({len(occ[n])}) [{where(occ, n)}]" for n in ns))
        levels = pair_levels(occ, a.max_dist, a.ratio)
        for d in range(1, a.max_dist + 1):
            lines.append("")
            kept = [p for p in levels[d] if frozenset(p) not in ignore]
            left_out = len(levels[d]) - len(kept)
            lines.append(f"## distance {d}: {len(kept)} new pairs"
                         + (f", {left_out} ignored" if left_out else ""))
            for x, y in kept:
                if len(occ[x]) < len(occ[y]):
                    x, y = y, x
                lines.append(f"  {x} ({len(occ[x])}) [{where(occ, x)}]  ~  "
                             f"{y} ({len(occ[y])}) [{where(occ, y)}]")
    text = "\n".join(lines) + "\n"
    if a.dest:
        a.dest.parent.mkdir(parents=True, exist_ok=True)
        a.dest.write_text(text)
        print(f"{len(occ)} names -> {a.dest}")
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
