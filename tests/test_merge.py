"""merge.py: several extractions of one book -> one, by vote."""
import shutil
import subprocess
import sys

import pytest

import merge
from conftest import EXTRACTED, REPO, book_table, scan_file, suburban_table

STATIONS = ["Лиелварде", "Кегумс", "Огре"]
TRAIN = [("—", "23.32"), ("23.37,5", "23.38"), ("23.49", "—")]


def page(*trains, stations=STATIONS, caption="п. № 6001"):
    return [caption, suburban_table(stations, *trains)]


def write(tmp_path, halves_by_run):
    """One scan file per run; returns {run: path}."""
    files = {}
    for run, halves in halves_by_run.items():
        d = tmp_path / run
        d.mkdir(exist_ok=True)
        files[run] = d / "scan-05.md"
        files[run].write_text(scan_file(5, halves))
    return files


def run(tmp_path, halves_by_run, voters, extras=()):
    files = write(tmp_path, halves_by_run)
    return merge.merge_scan(files, list(voters), list(extras))


def with_cell(train, i, j, value):
    t = [list(x) for x in train]
    t[i][j] = value
    return [tuple(x) for x in t]


def test_unanimous_runs_give_the_file_back(tmp_path):
    halves = [("suburban", page(TRAIN)), ("prose", ["Движение поездов по графику."])]
    text, disputes, alt = run(tmp_path, {"a": halves, "b": halves, "c": halves}, "abc")
    assert text == scan_file(5, halves)
    assert (disputes, alt) == ([], 0)


def test_empty_page_reads_back_exactly(tmp_path):
    halves = [("prose", [""]), ("prose", ["Текст", ""])]
    text, _, _ = run(tmp_path, {"a": halves, "b": halves}, "ab")
    assert text == scan_file(5, halves)


def test_a_disputed_cell_keeps_every_reading_most_votes_first(tmp_path):
    odd = with_cell(TRAIN, 1, 0, "23.37.5")
    text, disputes, _ = run(tmp_path, {
        "a": [("suburban", page(odd))],
        "b": [("suburban", page(TRAIN))],
        "c": [("suburban", page(TRAIN))]}, "abc")
    assert "⟨23.37,5 ¦ 23.37.5⟩" in text
    [d] = disputes
    assert d.where == "table 2, row 4 col 2 · Кегумс · 6001"
    assert d.readings == "23.37,5 (b, c); 23.37.5 (a)"


def test_an_empty_reading_is_shown(tmp_path):
    odd = with_cell(TRAIN, 2, 0, "")
    text, _, _ = run(tmp_path, {
        "a": [("suburban", page(odd))], "b": [("suburban", page(TRAIN))]}, "ab")
    assert "⟨∅ ¦ 23.49⟩" in text          # a 1-1 tie: the earlier run leads


def test_extra_shows_only_where_the_voters_disagree(tmp_path):
    extra = with_cell(with_cell(TRAIN, 0, 1, "23.82"), 1, 0, "23.37 5")
    text, disputes, _ = run(tmp_path, {
        "a": [("suburban", page(with_cell(TRAIN, 1, 0, "23.37.5")))],
        "b": [("suburban", page(TRAIN))],
        "x": [("suburban", page(extra))]}, "ab", "x")
    assert "23.82" not in text               # a and b agree there: x is not asked
    assert "⟨23.37.5 ¦ 23.37,5 ¦ 23.37 5⟩" in text
    assert [d.readings for d in disputes] == ["23.37.5 (a); 23.37,5 (b); 23.37 5 (x)"]


def test_extra_breaks_a_tie_in_the_order(tmp_path):
    text, _, _ = run(tmp_path, {
        "a": [("suburban", page(with_cell(TRAIN, 1, 0, "23.37.5")))],
        "b": [("suburban", page(TRAIN))],
        "x": [("suburban", page(TRAIN))]}, "ab", "x")
    assert "⟨23.37,5 ¦ 23.37.5⟩" in text


def test_text_is_voted_line_by_line(tmp_path):
    text, disputes, _ = run(tmp_path, {
        "a": [("suburban", page(TRAIN, caption="п. № 6001\nРига—Огре"))],
        "b": [("suburban", page(TRAIN, caption="п. № 6001\nРига-Огре"))],
        "c": [("suburban", page(TRAIN, caption="п. № 6001\nРига—Огре"))]}, "abc")
    assert "п. № 6001\n⟨Рига—Огре ¦ Рига-Огре⟩\n" in text
    assert disputes[0].where == "text block 1, line 2"


def test_text_split_differently_is_given_whole(tmp_path):
    text, disputes, _ = run(tmp_path, {
        "a": [("suburban", page(TRAIN, caption="п. № 6001 Рига"))],
        "b": [("suburban", page(TRAIN, caption="п. № 6001\nРига"))]}, "ab")
    assert "⟨text from a⟩\nп. № 6001 Рига\n\n⟨text from b⟩\nп. № 6001\nРига" in text
    assert disputes[0].readings == "1 lines (a); 2 lines (b)"


def test_a_run_laid_out_differently_sits_the_page_out(tmp_path):
    shifted = page(TRAIN + [("23.55", "—")], stations=STATIONS + ["Икшкиле"])
    text, disputes, alt = run(tmp_path, {
        "a": [("suburban", page(TRAIN))],
        "b": [("suburban", shifted)],
        "c": [("suburban", page(TRAIN))]}, "abc")
    assert "Икшкиле" not in text and "⟨" not in text
    assert alt == 0
    assert [(d.where, d.readings) for d in disputes] == [("layout", "outvoted, not merged: b")]


def test_no_majority_layout_gives_each_one(tmp_path):
    two = page(TRAIN, TRAIN)
    text, disputes, alt = run(tmp_path, {
        "a": [("suburban", page(TRAIN))], "b": [("suburban", two)]}, "ab")
    assert alt == 1
    assert "⟨alternative from a (suburban)⟩" in text
    assert "⟨alternative from b (suburban)⟩" in text
    assert "shapes: [UNKNOWN]" in text       # keeps the validator off it
    assert disputes[0].readings == "2 alternatives: a / b"


def test_an_unknown_majority_is_given_with_the_extras_table(tmp_path):
    raw = "|  № поездов | 6001 |\n| --- | --- |\n|  Огре | 23.49 |"
    unknown = [("UNKNOWN", ["п. № 6001", raw])]
    text, _, alt = run(tmp_path, {"a": unknown, "b": unknown,
                                  "x": [("suburban", page(TRAIN))]}, "ab", "x")
    assert alt == 1
    assert text.index("⟨alternative from a, b (UNKNOWN)⟩") < text.index(raw) \
        < text.index("⟨alternative from x (suburban)⟩")


def test_an_unknown_page_all_agree_on_is_kept(tmp_path):
    raw = "|  № поездов | 6001 |\n| --- | --- |\n|  Огре | 23.49 |"
    unknown = [("UNKNOWN", [raw])]
    text, disputes, alt = run(tmp_path, {"a": unknown, "b": unknown}, "ab")
    assert (text, disputes, alt) == (scan_file(5, unknown), [], 0)


def test_bands_are_voted(tmp_path):
    import extract

    def banded(name):
        rows = [extract.Divider([name]), ["№ поездов", "6001"], ["Огре", "23.49"]]
        return [("suburban", [extract.as_markdown(rows, 2, 2)])]
    text, disputes, _ = run(tmp_path, {"a": banded("Рига—Огре"), "b": banded("Рига-Огре")}, "ab")
    assert "| ⟨Рига—Огре ¦ Рига-Огре⟩" in text
    assert disputes[0].where == "table 1, band, row 1"


# ------------------------------------------------------------------ the CLI
def _merge(*args, cwd=REPO):
    return subprocess.run([sys.executable, str(REPO / "scripts" / "merge.py"), *map(str, args)],
                          cwd=cwd, capture_output=True, text=True)


def test_real_run_merged_with_itself_is_unchanged(tmp_path):
    for d in "ab":
        shutil.copytree(EXTRACTED, tmp_path / d / "run")
    r = _merge("--src", tmp_path / "a" / "run", tmp_path / "b" / "run", "--dest", tmp_path / "out")
    assert r.returncode == 0, r.stderr
    for f in sorted(EXTRACTED.glob("scan-*.md")):
        assert (tmp_path / "out" / f.name).read_text() == f.read_text(), f.name
    assert (tmp_path / "out" / "disputes.txt").read_text() == ""


def test_cli_writes_disputes_and_refuses_a_full_dest(tmp_path):
    files = write(tmp_path, {"r-01": [("suburban", page(TRAIN))],
                             "r-02": [("suburban", page(with_cell(TRAIN, 0, 1, "23.33")))]})
    out = tmp_path / "out"
    r = _merge("--src", files["r-01"].parent, files["r-02"].parent, "--dest", out)
    assert r.returncode == 0, r.stderr
    assert "1 disputed cells or lines" in r.stdout
    assert "23.32 (01); 23.33 (02)" in (out / "disputes.txt").read_text()
    r = _merge("--src", files["r-01"].parent, files["r-02"].parent, "--dest", out)
    assert r.returncode != 0 and "not empty" in r.stderr


def test_cli_wants_two_voters(tmp_path):
    r = _merge("--src", EXTRACTED, "--dest", tmp_path / "out")
    assert r.returncode != 0 and "at least two" in r.stderr


def test_cli_into_attempts_adds_an_index_row(tmp_path):
    import json
    from conftest import INDEX_HEAD
    root = tmp_path / "attempts"
    root.mkdir()
    (root / "index.md").write_text(INDEX_HEAD + "| 00 | a.djvu | scans-01 | ocr-01 | extracted-01 |  |\n"
                                   "| 01 | a.djvu | scans-02 | ocr-02 | extracted-02 |  |\n")
    for n, train in [("01", TRAIN), ("02", with_cell(TRAIN, 0, 1, "23.33"))]:
        d = root / f"extracted-{n}"
        d.mkdir()
        (d / "scan-05.md").write_text(scan_file(5, [("suburban", page(train))]))
        (d / "manifest.json").write_text("{}")
    r = _merge("--src", "attempts/extracted-01", "attempts/extracted-02",
               "--dest", "attempts/extracted-03", cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    assert (root / "index.md").read_text().endswith(
        "| 02 | a.djvu | scans-01, scans-02 | ocr-01, ocr-02 | extracted-03 | merge of 01 02 |\n")
    m = json.loads((root / "extracted-03" / "manifest.json").read_text())
    assert (m["disputes"], m["alternatives"]) == (1, 0)
