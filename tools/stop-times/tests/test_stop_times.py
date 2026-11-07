"""stop_times.py on small hand-made scan files.

The files are written here, in the final-NN format, so the tool's tests need
nothing from the pipeline's tests/ or scripts/ beyond what the tool imports.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import stop_times as st  # noqa: E402

RIGA = "Рига-пасс."


# ------------------------------------------------------------------ builders
def book_table(rows, header_count=1):
    """A table in the final-NN format: aligned cells, "=" under the head."""
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    w = [max(len(r[i]) for r in rows) for i in range(width)]

    def line(r):
        return "| " + " | ".join(c.ljust(x) for c, x in zip(r, w)) + " |"

    rule = "|" + "|".join("=" * (x + 2) for x in w) + "|"
    return "\n".join([line(r) for r in rows[:header_count]] + [rule]
                     + [line(r) for r in rows[header_count:]])


def suburban_table(stations, *trains):
    """trains: per train, (arr, dep) per station. Numbered 6001, 6003, ..."""
    rows = [["№ поездов"], ["Разд. пункты"]]
    for k in range(len(trains)):
        rows[0] += [str(6001 + 2 * k), ""]
        rows[1] += ["приб.", "отпр."]
    for i, station in enumerate(stations):
        rows.append([station] + [c for t in trains for c in t[i]])
    return book_table(rows, header_count=2)


def scan_file(scan, halves, folios):
    """Text of scan-NN.md. halves: [(shape, [paragraph or table])]."""
    out = ["---", f"scan: {scan}", f"kind: {'spread' if len(halves) == 2 else 'cover'}",
           f"folios: [{', '.join(map(str, folios))}]",
           f"shapes: [{', '.join(s for s, _ in halves)}]", "---", ""]
    for (_, parts), folio in zip(halves, folios):
        out += [f"## page {folio}", ""]
        for p in parts:
            out += [p, ""]
    return "\n".join(out)


@pytest.fixture
def write_book(tmp_path):
    """Write one scan file into tmp_path/book; return the dir."""
    d = tmp_path / "book"
    d.mkdir()

    def write(scan, halves, folios=None):
        folios = folios or [2 * scan - 4, 2 * scan - 3][:len(halves)]
        (d / f"scan-{scan:02d}.md").write_text(scan_file(scan, halves, folios))
        return d
    return write


# ------------------------------------------------------------------ helpers
def rows_of(d, station=RIGA):
    rows, errors = st.stop_times(d, station)
    assert errors == []
    return rows


def errors_of(d, station=RIGA):
    rows, errors = st.stop_times(d, station)
    assert errors
    return errors


def two_way(caption, rows):
    head = ["Прибытие", "Отправление", "Раздельные пункты", "Прибытие", "Отправление"]
    return ("two-way", [caption, book_table([head] + rows)])


def distance(caption, rows):
    head = ["Раздельные пункты", "Расстояние км", "приб.", "отпр.", "приб.", "отпр."]
    return ("distance", [caption, book_table([head] + rows)])


# ------------------------------------------------------------------ cells
@pytest.mark.parametrize("text,kind", [
    ("07.44,5", "time"), ("24.00", "time"), ("24.01", "bad"), ("71.54", "bad"),
    ("0,52", "bad"), ("06.31,2", "bad"), ("—", "pass"), ("", "blank"),
    ("Вецаки", "note"), ("До Саласпилс", "note"),
])
def test_cell_kind(text, kind):
    assert st.cell_kind(text) == kind


@pytest.mark.parametrize("arr,dep,status", [
    ("10.00", "10.05", "stops"), ("—", "10.05", "stops"), ("10.00", "", "stops"),
    ("—", "—", "passes"), ("Вецаки", "", "note"), ("", "", None),
])
def test_status(arr, dep, status):
    assert st.status_of(arr, dep) == status


@pytest.mark.parametrize("arr,dep", [("—", ""), ("Вецаки", "10.00"), ("Вецаки", "—")])
def test_status_without_a_rule(arr, dep):
    with pytest.raises(st.Reject):
        st.status_of(arr, dep)


# ------------------------------------------------------------------ trains
@pytest.mark.parametrize("text,caption,want", [
    ("6501", False, ("6501", "", set())),
    ("6501 Д", False, ("6501", "", {"Д"})),
    ("6481 ДР", False, ("6481", "", {"ДР"})),
    ("6317* Д", False, ("6317", "", {"*", "Д"})),
    ("6431**", False, ("6431", "", {"**"})),
    ("6633/6644", False, ("6633", "6644", set())),
    ("По выходным дням 6848 ДР", False, ("6848", "", {"weekends", "ДР"})),
    ("п. № 606", True, ("606", "", set())),
    ("Пригородный п. № 6805* ДР", True, ("6805", "", {"Пригородный", "*", "ДР"})),
    ("п. № 698/6314", True, ("698", "6314", set())),
    ("п. № 898 ДР «СНЕЖОК»", True, ("898", "", {"ДР"})),
    ("Пригородный п. № 6805* ДР (По особому назначению)", True,
     ("6805", "", {"Пригородный", "**", "ДР"})),
])
def test_parse_train(text, caption, want):
    assert st.parse_train(text, caption) == want


@pytest.mark.parametrize("text,caption", [
    ("", False), ("Д", False), ("6501 Д x", False), ("6501Д", False),
    ("п. № 898 ДР (По заявкам)", True), ("п. № 898 «СНЕЖОК» ДР", True),
    ("Пригодный п. №", True), ("606", True),
])
def test_parse_train_rejects(text, caption):
    with pytest.raises(st.Reject):
        st.parse_train(text, caption)


# ------------------------------------------------------------------ suburban
def test_suburban_rows_in_book_order(write_book):
    stations = ["Огре", RIGA, "Засулаукс"]
    t = suburban_table(stations,
                       [("—", "10.00"), ("10.30", "10.35"), ("10.45", "—")],
                       [("—", "10.10"), ("—", "—"), ("10.25", "—")],
                       [("", ""), ("", ""), ("", "")],
                       [("—", "11.00"), ("Вецаки", ""), ("", "")])
    d = write_book(3, [("suburban", [t]), ("suburban", [t])])
    rows = rows_of(d)
    assert [(r["page"], r["column"], r["number"], r["status"]) for r in rows] == [
        ("2", "1", "6001", "stops"), ("2", "2", "6003", "passes"),
        ("3", "1", "6001", "stops"), ("3", "2", "6003", "passes")]
    first = rows[0]
    assert (first["arrival"], first["departure"]) == ("10.30", "10.35")
    assert (first["first on page"], first["last on page"]) == ("Огре", "Засулаукс")


@pytest.mark.parametrize("note", ["Вецаки", "До Саласпилс"])
def test_note_at_the_station_gives_no_row(write_book, note):
    # A route note in the station's time cell: the train goes round the
    # station, it neither stops nor passes through.
    t = suburban_table(["Огре", RIGA, "Ошкалны"],
                       [("—", "11.00"), (note, ""), ("11.30", "—")],
                       [("—", "12.00"), ("12.30", "—"), ("", "")])
    d = write_book(3, [("suburban", [t])], folios=[2])
    assert [r["number"] for r in rows_of(d)] == ["6003"]


def test_dashes_outside_the_timed_run_give_no_row(write_book):
    # Riga printed first, the train timed only below it: it starts beyond
    # Riga (Ошкалны) or comes in on a link that skips it.
    t = suburban_table([RIGA, "Ошкалны", "Браса"],
                       [("—", "—"), ("—", "09.10"), ("09.14", "—")],
                       [("—", "—"), ("—", "—"), ("—", "—")],
                       [("—", "10.00"), ("10.05", "10.06"), ("10.10", "—")])
    d = write_book(3, [("suburban", [t])], folios=[2])
    assert [r["number"] for r in rows_of(d)] == ["6005"]


def test_dashes_between_bypass_ends_give_no_row(write_book):
    # Яняварты is printed above Riga, Ошкалны below; the link between them
    # skips Riga. Another pair of ends is a real run through Riga.
    t = suburban_table(["Яняварты", RIGA, "Ошкалны"],
                       [("—", "04.20"), ("—", "—"), ("04.28", "—")])
    u = suburban_table(["Засулаукс", RIGA, "Ошкалны"],
                       [("—", "04.20"), ("—", "—"), ("04.28", "—")])
    d = write_book(3, [("suburban", [t]), ("suburban", [u])])
    assert [(r["page"], r["status"]) for r in rows_of(d)] == [("3", "passes")]


def test_station_never_matches_a_substring(write_book):
    t = suburban_table(["Рига Пречу", "Рига-пасс. 2"], [("10.00", "10.01"), ("10.05", "—")])
    d = write_book(3, [("suburban", [t])], folios=[2])
    assert rows_of(d) == []
    assert rows_of(d, "Рига Пречу")[0]["arrival"] == "10.00"


def test_marks_and_renumbering_from_the_header(write_book):
    rows = [["№ поездов", "6633/6644", "", "По выходным дням 6848 ДР", ""],
            ["Разд. пункты", "приб.", "отпр.", "приб.", "отпр."],
            [RIGA, "—", "10.00", "—", "11.00"]]
    d = write_book(3, [("suburban", [book_table(rows, header_count=2)])], folios=[2])
    a, b = rows_of(d)
    assert (a["number"], a["number2"], a["marks"]) == ("6633", "6644", "")
    assert (b["number"], b["number2"], b["marks"]) == ("6848", "", "ДР, вых")
    assert b["train"] == "По выходным дням 6848 ДР"


def test_times_kept_as_printed(write_book):
    # Across midnight; the column is long enough for the direction fit to
    # see one wrap down the page against several up it.
    t = suburban_table(["Икшкиле", "Саулкалне", "Саласпилс", "Доле", RIGA],
                       [("23.55,5", "23.56"), ("23.59,5", "24.00"),
                        ("00.03,5", "00.04,5"), ("00.06", "00.06,5"),
                        ("00.30", "00.40,5")])
    d = write_book(3, [("suburban", [t])], folios=[2])
    r = rows_of(d)[0]
    assert (r["arrival"], r["departure"], r["last on page"]) == ("00.30", "00.40,5", RIGA)


# ------------------------------------------------------------------ captions
def test_two_way_caption_and_bottom_up_train(write_book):
    page = two_way("Пригородный п. № 6802 ДР · п. № 6801 ДР", [
        ["—", "04.30", RIGA, "06.30", "—"],
        ["04.34", "04.35", "Ваг. парк", "06.23,5", "06.25"],
        ["04.41", "—", "Яняварты", "—", "06.16"],
    ])
    d = write_book(3, [page], folios=[2])
    down, up = rows_of(d)
    assert (down["number"], down["marks"]) == ("6802", "ДР, П")
    assert (down["first on page"], down["last on page"]) == (RIGA, "Яняварты")
    assert (up["number"], up["marks"]) == ("6801", "ДР")
    assert (up["first on page"], up["last on page"]) == ("Яняварты", RIGA)
    assert (up["arrival"], up["departure"]) == ("06.30", "—")


def test_distance_caption_marks_every_train_diesel(write_book):
    page = distance("п. № 698/6314 · ДИЗЕЛЬНЫЙ · п. № 6311/697\n\nРига—Бигосово · Бигосово—Рига", [
        [RIGA, "922,8", "—", "16.55", "10.16", "—"],
        ["Огре", "888,5", "17.30", "17.31", "09.40", "09.41"],
    ])
    d = write_book(3, [page], folios=[2])
    a, b = rows_of(d)
    assert (a["number"], a["number2"], a["marks"]) == ("698", "6314", "ДИЗ")
    assert (b["number"], b["number2"], b["marks"]) == ("6311", "697", "ДИЗ")
    assert b["first on page"] == "Огре"


def test_caption_skips_pairs_without_times(write_book):
    head = ["Раздельные пункты", "Расстояние км"] + ["приб.", "отпр."] * 3
    page = ("distance", ["п. № 606 · п. № 605", book_table([head] + [
        [RIGA, "922,8", "—", "15.20", "", "", "09.10", ""],
        ["Огре", "888,5", "15.54", "15.55", "", "", "08.21", "08.23"],
    ])])
    d = write_book(3, [page], folios=[2])
    assert [(r["column"], r["number"]) for r in rows_of(d)] == [("1", "606"), ("3", "605")]


def test_caption_count_mismatch_rejects(write_book):
    page = two_way("п. № 6802", [["—", "04.30", RIGA, "—", "07.10"]])
    d = write_book(3, [page], folios=[2])
    assert "caption names 1 trains" in errors_of(d)[0]


# ------------------------------------------------------------------ rejects
def test_every_bad_cell_is_listed(write_book):
    t = suburban_table(["Огре", RIGA], [("0,52", "10.00"), ("71.54", "—")],
                       [("10.00", "10.01"), ("Вецаки", "11.00")])
    d = write_book(3, [("suburban", [t])], folios=[2])
    errs = errors_of(d)
    assert len(errs) == 3
    assert "Огре (r0c1): «0,52» is not a time" in errs[0]
    assert "«71.54» is not a time" in errs[1]
    assert "no rule for this pair" in errs[2]


def test_leftover_train_text_rejects(write_book):
    page = two_way("п. № 898 ДР (По заявкам) · п. № 6806 ДР",
                   [["—", "07.10", RIGA, "—", "08.25"]])
    d = write_book(3, [page], folios=[2])
    assert errors_of(d) == ['scan 3, page 2, table 1, column 1: left over '
                            '"(По заявкам)" in train cell "п. № 898 ДР (По заявкам)"']


def test_merge_mark_rejects(write_book):
    t = suburban_table([RIGA], [("—", "⟨10.00 ¦ 10.08⟩")])
    d = write_book(3, [("suburban", [t])], folios=[2])
    assert any("merge mark ⟨10.00 ¦ 10.08⟩" in e for e in errors_of(d))


def test_unknown_shape_rejects(write_book):
    t = suburban_table([RIGA], [("—", "10.00")])
    d = write_book(3, [("odd", [t])], folios=[2])
    assert "no rule for it" in errors_of(d)[0]


# ------------------------------------------------------------------ main
def test_main_writes_an_aligned_table(write_book, tmp_path):
    t = suburban_table(["Огре", RIGA], [("—", "10.00"), ("10.30", "—")])
    d = write_book(3, [("suburban", [t])], folios=[2])
    dest = tmp_path / "out.md"
    assert st.main([str(d), "--dest", str(dest)]) == 0
    text = dest.read_text()
    table = [ln for ln in text.split("\n\n")[2].splitlines()]
    assert len({len(ln) for ln in table}) == 1
    assert set(table[1]) <= set("|=")
    assert table[0].split("|")[3].strip() == "no"
    assert table[2].split("|")[3].strip() == "6001"


def test_main_ends_with_the_full_marks_legend(write_book, tmp_path):
    t = suburban_table(["Огре", RIGA], [("—", "10.00"), ("10.30", "—")])
    d = write_book(3, [("suburban", [t])], folios=[2])
    dest = tmp_path / "out.md"
    assert st.main([str(d), "--dest", str(dest)]) == 0
    head, legend = dest.read_text().split("## Marks\n\n")
    lines = legend.splitlines()
    assert len({len(ln) for ln in lines}) == 1
    assert [ln.split("|")[1].strip() for ln in lines[2:]] == \
        ["Д", "ДР", "*", "**", "вых", "ДИЗ", "П"]


@pytest.mark.parametrize("flags, head", [
    (["--train"], ["sc", "pg", "train", "no"]),
    (["--table"], ["sc", "pg", "table", "no"]),
    (["--column", "--table"], ["sc", "pg", "table", "column", "no"]),
])
def test_main_flags_add_columns(write_book, tmp_path, flags, head):
    t = suburban_table(["Огре", RIGA], [("—", "10.00"), ("10.30", "—")])
    d = write_book(3, [("suburban", [t])], folios=[2])
    dest = tmp_path / "out.md"
    assert st.main([str(d), "--dest", str(dest), *flags]) == 0
    table = [ln for ln in dest.read_text().splitlines() if ln.startswith("|")]
    assert [c.strip() for c in table[0].split("|")[1:len(head) + 1]] == head


def test_main_on_reject_writes_nothing(write_book, tmp_path, capsys):
    t = suburban_table([RIGA], [("—", "0,52")])
    d = write_book(3, [("suburban", [t])], folios=[2])
    dest = tmp_path / "out.md"
    dest.write_text("old")
    assert st.main([str(d), "--dest", str(dest)]) == 1
    assert dest.read_text() == "old"
    assert "«0,52» is not a time" in capsys.readouterr().err
