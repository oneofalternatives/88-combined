"""extract.py: OCR half sheets -> book/ tables, and the repairs on the way."""
import pytest

import book_model as bm
import extract
from conftest import COVER, SUBURBAN_TABLE, block, page, suburban_spread

Divider = extract.Divider


# --------------------------------------------------------------- clean_cell
@pytest.mark.parametrize("raw,pad,out", [
    ("7.10", True, "07.10"),
    ("7.16,5", True, "07.16,5"),        # the half minute rides along
    ("23.32", True, "23.32"),
    ("0.16", True, "00.16"),
    ("12.30", True, "12.30"),           # no boundary inside 12
    ("7.10", False, "7.10"),            # station / distance columns
    ("О/п. 56 км", True, "О/п. 56 км"),
    (" 871,5 ", False, "871,5"),
    ("**Огре**", True, "Огре"),         # OCR emphasis is not data
    ("**7.45**", True, "07.45"),
    ("_Огре_", True, "Огре"),
    ("6305*", True, "6305*"),           # a lone marker is the book's footnote
    ("6301**", True, "6301**"),
    ("6305\\*", True, "6305*"),         # escaped by the OCR
    ("6301* 6303*", True, "6301* 6303*"),
    # Marks on two trains in one cell are not an emphasis pair.
    ("6609*/6620*", True, "6609*/6620*"),
    ("6609*,6620*", True, "6609*,6620*"),
    ("6301** 6303**", True, "6301** 6303**"),
    ("6301**/6303**", True, "6301**/6303**"),
    ("6301**/6303*", True, "6301**/6303*"),   # no mark moves to the other train
    ("6301** 6303*", True, "6301** 6303*"),
    ("6609\\*/6620\\*", True, "6609*/6620*"),  # an escape is never emphasis
    ("\\*\\*Огре\\*\\*", True, "**Огре**"),
    ("**6305\\***", True, "6305*"),            # bold around a marked number
    ("6320** Д", True, "6320** Д"),
    ("6533 Д*", True, "6533 Д*"),
    ("a_b_c", False, "a_b_c"),
    ("**—**", True, "—"),
    ("**О/п. 56 км**", False, "О/п. 56 км"),
    (" **Огре** ", False, "Огре"),
])
def test_clean_cell(raw, pad, out):
    assert extract.clean_cell(raw, pad_time=pad) == out


@pytest.mark.parametrize("cell,flagged", [
    ("6305*", False),
    ("6301** 6303*", False),
    ("6320** Д", False),
    ("6533 Д*", False),
    ("6870 ДР*", False),
    ("**Огре** 56", True),     # emphasis on part of a cell: kept, reported
    ("Огре*", True),
    ("a_b", True),
])
def test_stray_markup_reports_all_but_footnote_marks(cell, flagged):
    report = []
    extract.stray_markup([cell], 7, report)
    assert bool(report) == flagged
    if flagged:
        assert report[0].startswith("sheet 7:") and repr(cell) in report[0]


# ----------------------------------------------------------------- shapes
def _table(md, y=30):
    return block("table", md, 43, y, 483, y + 300)


@pytest.mark.parametrize("header,shape,st,width", [
    ("|  № поездов | 1 |  |", "suburban", 0, 3),
    ("| Раздельные пункты | Расстояние км | приб. | отпр. |", "distance", 0, 4),
    ("| приб. | отпр. | Раздельные пункты | приб. | отпр. |", "two-way", 2, 5),
])
def test_shape_of(header, shape, st, width):
    name, st_col, _, w = extract.shape_of([_table(header + "\n| a |")])
    assert (name, st_col, w) == (shape, st, width)


def test_shape_of_uses_topmost_table_and_rejects_unknown():
    unknown = _table("| Глава | Стр. |", y=10)
    known = _table("|  № поездов | 1 |  |", y=200)
    assert extract.shape_of([known, unknown]) is None
    assert extract.shape_of([block("text", "x", 0, 0, 1, 1)]) is None


def test_caption_by_position_not_type():
    blocks = [block("footer", "ДИЗЕЛЬНЫЙ", 200, 31, 300, 40),
              block("header", "п. № 606", 40, 30, 150, 40),
              block("header", "Рига—Себеж", 40, 50, 150, 60),
              block("header", "низ", 40, 700, 150, 710)]    # too low: not caption
    assert extract.caption(blocks, 821) == ["п. № 606 · ДИЗЕЛЬНЫЙ", "Рига—Себеж"]


# ----------------------------------------------------------------- realign
# Distance sheets: station col 0, milepost col 1, then приб./отпр.
HEAD = ["Раздельные пункты", "Расстояние км", "приб.", "отпр."]


def _realign(*rows):
    report = []
    out = extract.realign([HEAD, *[list(r) for r in rows]], 1, 0, 1, 93, report)
    return out, report


def test_realign_clean_table_is_untouched():
    rows = [["Рига-пасс.", "922,8", "—", "15.20"], ["Яняварты", "917,9", "—", "15.28"]]
    out, report = _realign(*rows)
    assert out == [HEAD, *rows] and report == []


def test_realign_joins_wrapped_name_and_drops_stray_line():
    out, report = _realign(["Блок пост", "866,4", "—", "16.16"],
                           ["867 км", "", "", ""],
                           ["Юмправа", "860,5", "—", "16.26"])
    assert out[1:] == [["Блок пост 867 км", "866,4", "—", "16.16"],
                       ["Юмправа", "860,5", "—", "16.26"]]
    assert report == ["sheet 93: joined wrapped name 'Блок пост 867 км'"]


def test_realign_wrap_recovers_cells_into_blanks_above():
    out, report = _realign(["Блок пост", "866,4", "—", ""],
                           ["867 км", "", "", "16.16"],
                           ["Юмправа", "860,5", "—", "16.26"])
    assert out[1] == ["Блок пост 867 км", "866,4", "—", "16.16"]
    assert "sheet 93: recovered col 3 from cells with no distance of their own" in report


def test_realign_wrap_drops_contradicting_cells_and_reports():
    out, report = _realign(["Блок пост", "866,4", "—", "16.16"],
                           ["867 км", "", "", "16.20,5"],
                           ["Юмправа", "860,5", "—", "16.26"])
    assert out[1] == ["Блок пост 867 км", "866,4", "—", "16.16"]
    assert any("DROPPED cells with no distance" in r and "16.16 vs 16.20,5" in r
               for r in report)


def test_realign_wrap_with_its_own_distance_and_times_keeps_its_row():
    out, report = _realign(["Лиелварде", "871,5", "16.10", "16.11"],
                           ["Блок пост", "866,4", "—", "16.16"],
                           ["856 км", "855,9", "—", "16.31"])
    # a lone "856 км" with a distance and times is a row, but its name still
    # joins the one above -- which is why every join is reported
    assert report[0] == "sheet 93: joined wrapped name 'Блок пост 856 км'"
    assert any("2 station name(s) against 3 row(s)" in r for r in report)
    assert [r[1] for r in out[1:]] == ["871,5", "866,4", "855,9"]


def test_realign_drops_reread_names_and_trailing_name_only_rows():
    out, report = _realign(["Огре", "888,5", "15.54", "15.55"],
                           ["Кегумс", "877,2", "—", "—"],
                           ["Огре", "", "", ""],
                           ["Кегумс", "", "", ""])
    assert out[1:] == [["Огре", "888,5", "15.54", "15.55"],
                       ["Кегумс", "877,2", "—", "—"]]
    assert report == [
        "sheet 93: dropped a second 'Огре' -- the OCR read part of the station column twice",
        "sheet 93: dropped a second 'Кегумс' -- the OCR read part of the station column twice",
    ]


def test_realign_keeps_names_without_times_blank_and_reports():
    out, report = _realign(["Огре", "888,5", "15.54", "15.55"],
                           ["Кегумс", "", "", ""],
                           ["Лиелварде", "", "", ""])
    # the trailing rows had no data, so the names outnumber the rows of times;
    # the names are kept, blank, rather than silently shortening the route
    assert [r[0] for r in out[1:]] == ["Огре", "Кегумс", "Лиелварде"]
    assert out[2] == ["Кегумс", "", "", ""]
    assert any("3 station name(s) against 1 row(s)" in r for r in report)


def test_realign_divider_splits_segments():
    div = Divider(["Латвийская ж. д.", "", "", ""])
    rows = [HEAD, ["Огре", "888,5", "—", "15.55"], div,
            ["Кегумс", "877,2", "—", "16.00"]]
    report = []
    out = extract.realign(rows, 1, 0, 1, 93, report)
    assert out[2] is div
    assert out[3][0] == "Кегумс" and report == []


# ---------------------------------------------------- as_markdown round trip
def test_as_markdown_round_trips_through_parse_book_table():
    rows = [["№ поездов", "6501 Д", "", "6601", ""],
            ["", "приб.", "отпр.", "приб.", "отпр."],
            ["Лиелварде", "—", "23.32", "—", "00.16"],
            Divider(["Латвийская ж. д.", "", "", "", ""]),
            ["Кегумс", "23.37,5", "23.38", "", ""]]
    md = extract.as_markdown(rows, 2, 5)
    lines = md.splitlines()
    assert len({len(ln) for ln in lines}) == 1        # column aligned
    assert lines[2].startswith("|===")
    t = bm.parse_book_table(md)
    assert t["width"] == 5 and t["header_rows"] == 2
    assert [it["kind"] for it in t["items"]] == ["head", "head", "row", "rule",
                                                 "band", "rule", "row"]
    assert t["items"][4]["text"] == "Латвийская ж. д."
    assert t["items"][6]["cells"] == rows[4]


def test_as_markdown_without_header_rules_first_row():
    md = extract.as_markdown([["a", "b"], ["c", "d"]], 0, 2)
    assert md.splitlines()[1].startswith("|===")


# -------------------------------------------------------------- render_page
def test_render_page_spread():
    report = []
    text = extract.render_page(suburban_spread(), 5, report)
    assert report == []
    head, _, body = text.partition("---\n\n")
    assert head == ("---\nsheet: 5\nkind: spread\nfolios: [6, 7]\n"
                    "shapes: [suburban, prose]\n")
    assert "## page 6\n\nп. № 6501\n\n| № поездов" in body
    assert "| Лиелварде    | —       | 23.32 | —       | 00.16   |" in body
    assert body.rstrip().endswith("## page 7\n\nДвижение поездов по графику.")
    # the folio and signature footers are not carried into the text
    assert "1055" not in text


def test_render_page_sheet_2_and_covers_have_no_folios():
    spread = extract.render_page(suburban_spread(), 2, [])
    assert "folios: []" in spread and spread.count("## page\n") == 2
    cover = page([block("text", "СЛУЖЕБНОЕ РАСПИСАНИЕ", 100, 300, 580, 360)], COVER)
    text = extract.render_page(cover, 1, [])
    assert "kind: cover\nfolios: []\nshapes: [prose]" in text


def test_render_page_reports_unknown_shape_and_keeps_text():
    p = page([block("table", "| Глава | Стр. |\n| --- | --- |\n| I | 5 |", 43, 30, 483, 300)])
    report = []
    text = extract.render_page(p, 3, report)
    assert report == ["sheet 3: unrecognized table shape"]
    assert "shapes: [UNKNOWN, prose]" in text
    assert "| I | 5 |" in text


def test_render_page_suburban_with_lost_station_column():
    """The OCR split one timetable into a table and a loose list of names.

    The names become rows of blank times and the narrow table is widened; the
    two are kept in document order, not re-joined (spec/ocr-book-format.md §4).
    Nothing is reported: the hand pass fixes it against the scan.
    """
    head = SUBURBAN_TABLE.split("\n|  Лиелварде")[0] + "\n|  Лиелварде | — | 23.32 | — | 0.16 |"
    p = page([block("table", head, 43, 30, 483, 150),
              block("list", "Кегумс\nОгре", 45, 155, 120, 200),
              block("table", "| 23.37 | 23.38 |\n| 23.49 | 23.50 |", 150, 205, 483, 240)])
    report = []
    text = extract.render_page(p, 5, report)
    t = bm.parse_book_page(text)["halves"][0]["items"][0]["table"]
    rows = [it["cells"] for it in t["items"] if it["kind"] == "row"]
    assert [r[0] for r in rows] == ["Разд. пункты", "Лиелварде", "Кегумс", "Огре", "23.37", "23.49"]
    assert rows[2] == ["Кегумс", "", "", "", ""]
    assert rows[4][:3] == ["23.37", "23.38", ""]
    assert report == []
