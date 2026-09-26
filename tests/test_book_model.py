"""book_model: reading the OCR export, repairing it, and reading book pages back."""
import json

import pytest

import book_model as bm
from conftest import COVER, SUBURBAN_TABLE, block, page, suburban_spread


# ------------------------------------------------------------- parse_table
def test_parse_table_gfm_with_stacked_header():
    body, head, width = bm.parse_table(SUBURBAN_TABLE)
    assert width == 5
    # the приб./отпр. row the OCR left in the body is promoted to head
    assert head == 2
    assert body[0] == ["№ поездов", "6501 Д", "", "6601", ""]
    assert body[1] == ["", "приб.", "отпр.", "приб.", "отпр."]
    assert body[3] == ["Лиелварде", "—", "23.32", "—", "0.16"]


def test_parse_table_pads_ragged_rows():
    body, head, width = bm.parse_table("| a | b | c |\n| --- | --- | --- |\n| x |")
    assert width == 3
    assert head == 1
    assert body[1] == ["x", "", ""]


def test_parse_table_without_separator_has_no_head():
    body, head, width = bm.parse_table("| a | b |\n| c | d |")
    assert head == 0
    assert body == [["a", "b"], ["c", "d"]]


def test_parse_table_ignores_non_table_text():
    assert bm.parse_table("just a paragraph") is None


def test_parse_table_only_promotes_pure_arr_dep_rows():
    md = "| № поездов | 1 | |\n| --- | --- | --- |\n| Разд. | приб. | 7.10 |"
    _, head, _ = bm.parse_table(md)
    assert head == 1


def test_pad_table_widens_rows_and_separator():
    out = bm.pad_table("| a | b |\n| --- | --- |\n| c | d |", 4)
    body, head, width = bm.parse_table(out)
    assert width == 4 and head == 1
    assert body == [["a", "b", "", ""], ["c", "d", "", ""]]
    assert out.splitlines()[1].count("---") == 4


# -------------------------------------------------------- split and repair
def test_split_halves_by_centre_and_drops_noise():
    left, right = bm.split_halves(suburban_spread())
    assert [b["content"] for b in left] == ["п. № 6501", SUBURBAN_TABLE]
    assert [b["content"] for b in right] == ["Движение поездов по графику."]


def test_split_halves_portrait_is_one_half():
    p = page([block("text", "ГЛАВА I", 100, 100, 500, 140),
              block("text", "Рига", 600, 100, 660, 140)], COVER)
    halves = bm.split_halves(p)
    assert len(halves) == 1 and len(halves[0]) == 2


@pytest.mark.parametrize("content,noise", [
    ("6", True), ("123", True), ("5 — 1055", True), ("9*", True), ("13\\*", True),
    ("", True), ("  ", True),
    ("6501", False), ("Рига", False), ("п. № 606", False),
])
def test_is_noise(content, noise):
    assert bm.is_noise({"content": content}) is noise


def test_repair_fuses_station_blocks_and_pads_narrow_tables():
    header = ("|  № поездов | 1 |  | 2 |  |\n| --- | --- | --- | --- | --- |\n"
              "|  Рига | 7.00 | 7.01 | 8.00 | 8.01 |")
    blocks = [
        block("table", header, 40, 30, 480, 100),
        # the OCR lost the station column: names arrive as a list block ...
        block("list", "Засулаукс\nЗолитуде", 42, 105, 120, 140),
        # ... and the times beside them as a table that is too narrow
        block("table", "| 7.05 | 7.06 |\n| 7.09 | 7.10 |", 150, 105, 480, 140),
        # a caption to the right is not a station block
        block("text", "Рига—Тукумс", 300, 150, 470, 160),
    ]
    out = bm.repair(blocks)
    assert [b["type"] for b in out] == ["table", "table", "table", "text"]
    fused = bm.parse_table(out[1]["content"])
    assert fused[2] == 5
    assert [r[0] for r in fused[0]] == ["Засулаукс", "Золитуде"]
    assert all(c == "" for r in fused[0] for c in r[1:])
    assert bm.parse_table(out[2]["content"])[2] == 5


def test_station_block_rejects_times_and_wide_text():
    left, span = 40, 440
    assert bm.is_station_block(block("text", "Огре", 45, 0, 100, 10), left, span)
    assert not bm.is_station_block(block("text", "7.10 7.12", 45, 0, 100, 10), left, span)
    assert not bm.is_station_block(block("text", "Огре", 45, 0, 400, 10), left, span)
    assert not bm.is_station_block(block("text", "Огре", 200, 0, 250, 10), left, span)
    assert not bm.is_station_block(block("table", "| Огре |", 45, 0, 100, 10), left, span)


def test_repair_leaves_halves_without_timetable_alone():
    blocks = [block("text", "Примечание", 40, 30, 480, 100)]
    assert bm.repair(blocks) is blocks


# -------------------------------------------------------------- load_pages
def test_load_pages_playground_export(tmp_path):
    for n in (1, 2):
        d = tmp_path / "pages" / f"page-{n}"
        d.mkdir(parents=True)
        (d / "page-metadata.json").write_text(json.dumps({"index": n - 1, "blocks": []}))
    assert [p["index"] for p in bm.load_pages(tmp_path)] == [0, 1]


def test_load_pages_api_responses_are_camel_cased(tmp_path):
    resp = {"model": "m", "pages": [{"index": 0,
            "dimensions": {"width": 10, "height": 20},
            "blocks": [{"top_left_x": 1, "top_left_y": 2, "bottom_right_x": 3,
                        "bottom_right_y": 4, "type": "text", "content": "x"}]}]}
    (tmp_path / "page-01.json").write_text(json.dumps(resp))
    (tmp_path / "page-02.json").write_text(json.dumps(resp))
    pages = bm.load_pages(tmp_path)
    assert len(pages) == 2
    assert pages[0]["blocks"][0] == {"topLeftX": 1, "topLeftY": 2, "bottomRightX": 3,
                                     "bottomRightY": 4, "type": "text", "content": "x"}


def test_load_pages_stops_at_first_gap(tmp_path):
    for n in (1, 3):
        (tmp_path / f"page-{n:02d}.json").write_text(json.dumps({"pages": [{}]}))
    assert len(bm.load_pages(tmp_path)) == 1


# ------------------------------------------------- book pages as input
BOOK_TABLE = """\
| № поездов | 6501 Д |       | 6601  |       |
|           | приб.  | отпр. | приб. | отпр. |
|===========|========|=======|=======|=======|
| Лиелварде | —      | 23.32 | —     | 00.16 |
|-----------|--------|-------|-------|-------|
| Латвийская ж. д.                          |
|-----------|--------|-------|-------|-------|
| Кегумс    | 23.37  | 23.38 |       |       |"""


def test_parse_book_table():
    t = bm.parse_book_table(BOOK_TABLE)
    assert t["width"] == 5 and t["header_rows"] == 2
    kinds = [it["kind"] for it in t["items"]]
    assert kinds == ["head", "head", "row", "rule", "band", "rule", "row"]
    assert t["items"][4]["text"] == "Латвийская ж. д."
    assert t["items"][6]["cells"] == ["Кегумс", "23.37", "23.38", "", ""]


def test_parse_book_page_and_captions():
    text = ("---\nsheet: 93\nkind: spread\nfolios: [182, 183]\n"
            "shapes: [distance, prose]\n---\n\n## page 182\n\n"
            "п. № 606 · ДИЗЕЛЬНЫЙ\n\nРига—Себеж\n\n" + BOOK_TABLE +
            "\n\nПримечание внизу.\n\n## page 183\n\n# ГЛАВА XII\n\nТекст.\n")
    p = bm.parse_book_page(text)
    assert p["sheet"] == 93 and p["kind"] == "spread"
    assert p["shapes"] == ["distance", "prose"]
    assert [h["folio"] for h in p["halves"]] == [182, 183]
    left = [it["kind"] for it in p["halves"][0]["items"]]
    # paragraphs above the table are its caption; below it, ordinary prose
    assert left == ["caption", "caption", "table", "para"]
    right = p["halves"][1]["items"]
    assert [it["kind"] for it in right] == ["heading", "para"]
    assert right[0]["text"] == "ГЛАВА XII"


def test_parse_book_page_unnumbered_folio():
    p = bm.parse_book_page("---\nsheet: 2\nkind: spread\nfolios: []\n"
                           "shapes: [prose, prose]\n---\n\n## page\n\nа\n\n## page\n\nб\n")
    assert [h["folio"] for h in p["halves"]] == [None, None]


def test_render_book_table_head_spans_and_bands():
    html = bm.render_book_table(bm.parse_book_table(BOOK_TABLE))
    assert html.startswith("<table class='tt'><thead>")
    # an empty header cell continues the train number beside it
    assert "<th colspan='2'>6501 Д</th>" in html
    assert "</thead><tbody>" in html
    assert "<tr class='band ruled'><td colspan='5'>Латвийская ж. д.</td></tr>" in html
    assert "<tr class='ruled'><td class='st'>Кегумс</td>" in html
    assert html.endswith("</tbody></table>")


def test_render_book_table_narrow_is_prose_and_escaped():
    t = bm.parse_book_table("| Глава | <стр> |\n|===|===|\n| I | 5 |")
    html = bm.render_book_table(t)
    assert "class='tt prose'" in html and "&lt;стр&gt;" in html


def test_book_fit_scale():
    small = [{"kind": "table", "table": {"items": [{"kind": "row"}] * 10}}]
    big = [{"kind": "table", "table": {"items": [{"kind": "row"}] * 94}}]
    assert bm.book_fit_scale(small) == 1.0
    assert bm.book_fit_scale(big) == pytest.approx(0.5)


def test_book_sheets_cover_and_spread(tmp_path):
    (tmp_path / "page-01.md").write_text(
        "---\nsheet: 1\nkind: cover\nfolios: []\nshapes: [prose]\n---\n\n## page\n\nx\n")
    (tmp_path / "page-02.md").write_text(
        "---\nsheet: 2\nkind: spread\nfolios: [0, 1]\nshapes: [prose, prose]\n---\n\n"
        "## page 0\n\nа\n\n## page 1\n\nб\n")
    sheets = list(bm.book_sheets(tmp_path))
    assert [s["kind"] for s in sheets] == ["cover", "spread"]
    assert [side for *_, side in sheets[1]["halves"]] == ["left", "right"]
