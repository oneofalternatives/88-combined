"""validate.py: each rule on small synthetic book pages, plus the helpers.

Pages are written with the extractor's own as_markdown, so these tests also
hold the validator to the format extract.py actually produces.
"""
import json
import sys

import pytest

import validate as v
from conftest import book_table, suburban_table

STATIONS = ["Рига-пасс.", "Засулаукс", "Золитуде", "Иманта"]


def run(book_dir):
    columns, findings = v.validate(book_dir)
    return columns, findings


def messages(findings):
    return [f.message for f in findings]


def train(*times):
    """(arr, dep) pairs from a flat list: train("—", "10.00", "10.05", ...)."""
    return list(zip(times[::2], times[1::2]))


# ------------------------------------------------------------------ parsing
@pytest.mark.parametrize("text,kind,sec", [
    ("07.44,5", "time", 7 * 3600 + 44 * 60 + 30),
    ("7.44", "time", 7 * 3600 + 44 * 60),
    ("24.00", "time", 24 * 3600),
    ("24.01", "bad", None),
    ("25.13", "bad", None),
    ("07.71", "bad", None),
    ("1O.05", "bad", None),           # letter O for a zero: damage, not prose
    ("—", "pass", None), ("-", "pass", None), ("–", "pass", None),
    ("", "blank", None), ("  ", "blank", None),
    ("Следует до", "note", None),
])
def test_cell(text, kind, sec):
    c = v.Cell(text)
    assert (c.kind, c.sec) == (kind, sec)


@pytest.mark.parametrize("text,km", [
    ("922,8", 922.8), ("0,0", 0.0), ("56.4", 56.4), ("56", None), ("", None), ("км", None)])
def test_parse_km(text, km):
    assert v.parse_km(text) == (pytest.approx(km) if km is not None else None)


def test_hhmm_and_mmss():
    assert v.hhmm(24 * 3600 + 5 * 60 + 30) == "00.05,5"
    assert v.mmss(330) == "5:30"
    assert v.mmss(-90) == "-1:30"


def test_median_and_modified_z():
    assert v.median([]) == 0.0
    assert v.median([3, 1, 2]) == 2
    assert v.median([4, 1, 3, 2]) == 2.5
    # a spread sample scores by modified z
    dev, med, mad, how = v.modified_z(20, [10, 11, 12, 13, 20])
    assert (how, med, mad) == ("z", 12, 1)
    assert dev == pytest.approx(0.6745 * 8)
    # every train printed the same minute: fall back to a ratio
    assert v.modified_z(900, [300] * 5 + [900])[::3] == (3.0, "ratio")
    assert v.modified_z(100, [300] * 5 + [100])[0] == 3.0
    assert v.modified_z(0, [300] * 6 + [0])[0] == float("inf")


@pytest.mark.parametrize("width,protected,pairs", [
    (7, {0}, [(1, 2), (3, 4), (5, 6)]),                  # suburban
    (6, {0, 1}, [(2, 3), (4, 5)]),                       # distance
    (5, {2}, [(0, 1), (3, 4)]),                          # two-way
    (4, {0}, [(1, 2), (3, None)]),                       # a lone last column
])
def test_pair_columns(width, protected, pairs):
    assert v.pair_columns(width, protected) == pairs


def test_shape_rules_come_from_extract():
    import extract
    assert set(v.SHAPE_RULES) == set(extract.SHAPES)
    assert v.SHAPE_RULES["two-way"][0] == 2


def test_km_zones():
    # a reset: Рига—Пыталово counts down to Плявиняс, then up again from 0
    assert v.km_zones([922.8, 917.9, 904.7, 0.0, 12.0]) == [0, 0, 0, 1, 1]
    # the kilometres turn round without a big step
    assert v.km_zones([10.0, 20.0, 15.0, 5.0]) == [0, 0, 1, 1]
    # a row without a milepost neither opens nor breaks a zone
    assert v.km_zones([10.0, None, 20.0]) == [0, 0, 0]


@pytest.mark.parametrize("kms,name", [
    ([922.8, 616.3], "moscow"), ([472.8, 300.0], "daugavpils"), ([0.0, 141.1], "riga"),
    ([100.0, 700.0], None), ([], None), ([None], None)])
def test_reckoning_of(kms, name):
    assert v.reckoning_of(kms) == name


@pytest.mark.parametrize("caption,dest", [
    ("п. № 606 · ДИЗЕЛЬНЫЙ\nРига—Себеж · Себеж—Рига", "Себеж"),
    ("Рига-пасс.—Лиепая", "Лиепая"),
    ("п. № 692", None),
])
def test_route_destination(caption, dest):
    assert v.route_destination([{"kind": "caption", "text": caption}]) == dest


# -------------------------------------------------------- suburban sheets
def test_clean_page_has_no_findings(write_book):
    d = write_book(5, [("suburban", [suburban_table(
        STATIONS,
        train("—", "10.00", "10.05", "10.05,5", "10.10", "10.11", "10.15", "—"),
        # the other way up the same column: direction is per column pair
        train("11.20", "—", "11.14", "11.15", "11.09", "11.10", "—", "11.05"),
    )])])
    columns, findings = run(d)
    assert findings == []
    assert [(c.train, c.direction) for c in columns] == [("6001", 1), ("6003", -1)]


def test_midnight_wrap_is_not_a_finding(write_book):
    d = write_book(5, [("suburban", [suburban_table(
        STATIONS, train("—", "23.50", "23.57", "23.58", "00.03,5", "00.04,5", "00.10", "—"))])])
    assert run(d)[1] == []


def test_wrap_after_24_00_is_not_a_finding(write_book):
    # sheet 5, train 6501 Д: out at 24.00, in at the next stop after midnight
    d = write_book(5, [("suburban", [suburban_table(
        STATIONS, train("—", "23.50", "23.59,5", "24.00", "00.03,5", "00.04,5", "00.10", "—"))])])
    assert run(d)[1] == []


def test_arrival_at_24_00_then_departure_after_is_not_a_finding(write_book):
    # sheet 96, train 662 at Вецуми: in at 24.00, out at 00.01
    d = write_book(5, [("suburban", [suburban_table(
        STATIONS, train("—", "23.50", "24.00", "00.01", "00.05", "00.06", "00.10", "—"))])])
    assert run(d)[1] == []


def test_dwell_across_midnight_is_not_a_finding(write_book):
    # sheet 51, train 6826 at Кегумс: in at 23.59, out at 00.01
    d = write_book(5, [("suburban", [suburban_table(
        STATIONS, train("—", "23.50", "23.55", "23.56", "23.59", "00.01", "00.05", "—"))])])
    assert run(d)[1] == []


def test_long_dwell_across_midnight_is_impossible(write_book):
    # sheet 44, train 6176 Д at Асари: 02.06,5 is a misread 20.06,5
    d = write_book(5, [("suburban", [suburban_table(
        STATIONS, train("—", "20.00", "20.06", "02.06,5", "20.08", "20.08,5", "20.10", "—"))])])
    f = [f for f in run(d)[1] if f.severity == 0]
    assert [x.message for x in f] == ["departure before its arrival: 20.06 then 02.06,5"]


def test_wrap_after_24_00_is_the_second_one(write_book):
    # long enough that down the page is the better fit
    d = write_book(5, [("suburban", [suburban_table(
        STATIONS + ["Дзинтари", "Майори"],
        train("23.58", "23.59", "24.00", "00.01", "00.05", "00.06",
              "21.00", "21.01", "21.05", "21.06", "01.00", "—"))])])
    assert any(m.endswith("a second wrap in this column") for m in messages(run(d)[1]))


def test_morning_time_after_a_daytime_one_is_not_a_wrap(write_book):
    d = write_book(5, [("suburban", [suburban_table(
        STATIONS, train("—", "15.50", "15.55", "15.56", "06.00", "06.01", "06.05", "—"))])])
    assert "time steps backwards along the run: 15.56 then 06.00" in messages(run(d)[1])


def test_backwards_step_is_impossible(write_book):
    d = write_book(5, [("suburban", [suburban_table(
        STATIONS, train("—", "10.00", "10.10", "10.11", "10.05", "10.06", "10.20", "—"))])])
    (f,) = run(d)[1]
    assert f.severity == 0 and f.rules == {1}
    assert f.message == "time steps backwards along the run: 10.11 then 10.05"
    assert str(f.where) == "page-05.md folio 6 [suburban] п.№ 6001 — Золитуде  r2c1"


def test_departure_before_arrival(write_book):
    d = write_book(5, [("suburban", [suburban_table(
        STATIONS, train("—", "10.00", "10.10", "10.05", "10.15", "10.16", "10.20", "—"))])])
    (f,) = run(d)[1]
    assert f.rules == {2} and f.severity == 0
    assert f.message == "departure before its arrival: 10.10 then 10.05"


def test_non_time_in_time_cell(write_book):
    d = write_book(5, [("suburban", [suburban_table(
        STATIONS, train("—", "10.00", "1O.05", "10.06", "10.10", "10.11", "10.15", "—"))])])
    (f,) = run(d)[1]
    assert f.rules == {0} and f.message == "'1O.05' is not a time"


def test_blank_between_served_stations(write_book):
    d = write_book(5, [("suburban", [suburban_table(
        STATIONS, train("—", "10.00", "", "", "10.10", "10.11", "10.15", "—"))])])
    (f,) = run(d)[1]
    assert f.rules == {1} and "blank between two served stations" in f.message


def test_blanks_at_the_ends_are_fine(write_book):
    d = write_book(5, [("suburban", [suburban_table(
        STATIONS, train("", "", "—", "10.00", "10.05", "10.06", "10.10", ""))])])
    assert run(d)[1] == []


def test_column_that_fits_neither_direction(write_book):
    d = write_book(5, [("suburban", [suburban_table(
        STATIONS[:3], train("—", "10.10", "—", "10.00", "10.20", "—"))])])
    columns, findings = run(d)
    assert columns[0].direction is None
    assert any("fit neither direction" in m for m in messages(findings))


def test_repeated_header_restarts_the_station_list(write_book):
    """A header repeated inside the body (sheet 32) splits the column: the
    runs either side are separate, named from the header over them."""
    rows = [["№ поездов", "6001", ""], ["", "приб.", "отпр."],
            ["Рига-пасс.", "—", "12.00"], ["Засулаукс", "12.10", "—"],
            ["№ поездов", "6007", ""], ["Разд. пункты", "приб.", "отпр."],
            ["Рига-пасс.", "—", "10.00"], ["Засулаукс", "10.10", "—"]]
    d = write_book(5, [("suburban", [book_table(rows, header_count=2)])])
    columns, findings = run(d)
    assert findings == []
    assert [c.train for c in columns] == ["6001 (part 1)", "6007 (part 2)"]


# ----------------------------------------------------- rule 4: same leg
def _leg_trains(n, outlier_minutes=None):
    out = []
    for k in range(n):
        leg = outlier_minutes if (outlier_minutes and k == n - 1) else 5
        t0 = 10 * 60 + 20 * k
        hm = lambda m: f"{m // 60:02d}.{m % 60:02d}"   # noqa: E731
        out.append(train("—", hm(t0), hm(t0 + leg), hm(t0 + leg + 1),
                          hm(t0 + leg + 5), "—"))
    return out


def test_slow_leg_against_other_trains(write_book):
    d = write_book(5, [("suburban", [suburban_table(STATIONS[:3], *_leg_trains(6, 15))])])
    (f,) = run(d)[1]
    assert f.severity == 1 and f.rules == {4}
    assert f.message == "running time 15:00 against 5:00 elsewhere (ratio 3.0)"
    assert f.evidence == {"n": 6, "median": "5:00", "MAD": "0:00"}
    assert f.where.station == "Рига-пасс. → Засулаукс"
    assert f.where.train == "6011"


def test_leg_under_min_samples_gets_no_opinion(write_book):
    d = write_book(5, [("suburban", [suburban_table(STATIONS[:3], *_leg_trains(4, 15))])])
    assert run(d)[1] == []


def test_leg_within_a_printed_tick_is_not_a_finding(write_book):
    d = write_book(5, [("suburban", [suburban_table(STATIONS[:3], *_leg_trains(6, 5))])])
    assert run(d)[1] == []


# --------------------------------------------------------- distance sheets
DIST_HEAD = ["Раздельные пункты", "Расстояние км", "приб.", "отпр."]


def distance_page(route, rows):
    return ("distance", [route, book_table([DIST_HEAD, *rows])])


def test_speed_over_limit_is_impossible(write_book):
    d = write_book(90, [distance_page("Рига—Лиепая", [
        ["Рига-пасс.", "0,0", "—", "10.00"],
        ["Засулаукс", "5,0", "10.05", "10.06"],
        ["Тукумс", "35,0", "10.11", "—"],    # 30 km in 5 minutes
    ])])
    (f,) = run(d)[1]
    assert f.rules == {3} and f.severity == 0
    assert f.message == "implied 360 km/h over 120 — 30.0 km in 5:00 (10.06 → 10.11)"


def test_speed_is_not_measured_across_a_mileposting_reset(write_book):
    d = write_book(90, [distance_page("Рига—Пыталово", [
        ["Рига-пасс.", "922,8", "—", "10.00"],
        ["Яняварты", "917,9", "10.06", "10.07"],
        ["Плявиняс", "904,7", "10.20", "10.21"],
        ["Плявиняс II", "0,0", "10.25", "10.26"],   # reset: new reckoning
        ["Мадона", "12,0", "10.36", "—"],
    ])])
    assert run(d)[1] == []


def test_zone_outside_declared_reckoning_is_reported(write_book):
    d = write_book(90, [distance_page("Рига—Лиепая", [
        ["Рига-пасс.", "922,8", "", ""], ["Яняварты", "917,9", "", ""]])])
    (f,) = run(d)[1]
    assert f.rules == {5}
    assert f.message == ("mileposts 917.9–922.8 км fall in 'moscow', which route "
                         "«Лиепая» does not use — this zone is left out of rule 5")


def test_milepost_names_agree_across_sheets(write_book):
    for sheet in (90, 91, 92):
        write_book(sheet, [distance_page("Рига—Себеж", [
            ["Рига-пасс.", "922,8", "", ""], ["Яняварты", "917,9", "", ""]])])
    # a misspelling at the same milepost; and the same name at another one
    d = write_book(93, [distance_page("Рига—Себеж", [
        ["Рига-пасс.", "922,8", "", ""], ["Янявврты", "917,9", "", ""],
        ["Яняварты", "916,0", "", ""]])])
    found = sorted(messages(run(d)[1]))
    assert found == [
        "milepost 917.9 км is Янявврты here but Яняварты on 3 other moscow sheet(s)",
        "station Яняварты is 916.0 here but 917.9 on 3 other moscow sheet(s)",
    ]


def test_shared_milepost_on_different_lines_is_fine(write_book):
    write_book(90, [distance_page("Рига—Валга", [["Стренчи", "141,1", "", ""]])])
    d = write_book(91, [distance_page("Рига—Пярну", [["Пярну-пасс.", "141,1", "", ""]])])
    assert run(d)[1] == []


# ------------------------------------------------------ shapes and ranking
def test_unknown_shape_is_skipped_and_reported(write_book):
    d = write_book(3, [("UNKNOWN", ["| Глава | Стр. |"]), ("prose", ["Текст."])])
    (f,) = run(d)[1]
    assert f.message == "shape 'UNKNOWN' — not checked, no rules apply to it"


def _finding(rule, rows, col=1, severity=0, score=5.0):
    where = v.Where(5, 6, "suburban", "6001", "X", [(r, col) for r in rows])
    return v.Finding(severity, score, rule, where, f"rule {rule} at {rows}")


def test_collapse_merges_findings_on_one_cell():
    (f,) = v.collapse([_finding(1, [3]), _finding(4, [3], severity=1, score=9.0)])
    assert f.rules == {1, 4} and f.severity == 0 and f.score == 9.0
    assert "(2 rules agree)" in f.render()


def test_collapse_turns_a_run_into_one_misaligned_column():
    fs = v.collapse([_finding(1, [r]) for r in (4, 5, 6)] + [_finding(1, [9])])
    assert len(fs) == 2
    top = fs[0]
    assert top.where.station == "rows 4–6" and top.score == 15.0
    assert top.message.startswith("3 findings on consecutive rows of one column")


def test_ranking_puts_impossible_first():
    fs = v.collapse([_finding(4, [1], severity=1, score=50.0), _finding(1, [8], score=1.0)])
    assert [f.severity for f in fs] == [0, 1]


# ------------------------------------------------------------------- main
def test_main_exit_codes_and_json(write_book, monkeypatch, capsys):
    d = write_book(5, [("suburban", [suburban_table(
        STATIONS, train("—", "10.00", "10.10", "10.05", "10.15", "10.16", "10.20", "—"))])])
    monkeypatch.setattr(sys, "argv", ["validate.py", "--book", str(d), "--json"])
    assert v.main() == 1
    (f,) = json.loads(capsys.readouterr().out)
    assert f["rules"] == [2] and f["sheet"] == 5 and f["cells"] == [[1, 2]]

    (d / "page-05.md").write_text((d / "page-05.md").read_text().replace("10.05", "10.12"))
    monkeypatch.setattr(sys, "argv", ["validate.py", "--book", str(d)])
    assert v.main() == 0
    assert "1 train columns checked; 0 findings" in capsys.readouterr().out
