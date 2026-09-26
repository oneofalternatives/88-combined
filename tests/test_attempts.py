"""attempts.py: numbered attempt dirs, manifests and the index."""
import json

import pytest

import attempts
from conftest import INDEX_HEAD


@pytest.fixture
def root(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "attempts").mkdir()
    (tmp_path / "attempts" / "index.md").write_text(INDEX_HEAD)
    return tmp_path / "attempts"


def test_next_dir_counts_unfinished_dirs(root):
    assert attempts.next_dir("ocr").name == "ocr-00"
    assert attempts.next_dir("ocr").name == "ocr-01"     # ocr-00 has no manifest
    assert attempts.next_dir("medium").name == "medium-00"


def test_finish_and_require_finished(root):
    d = attempts.next_dir("ocr")
    with pytest.raises(SystemExit, match="no manifest.json"):
        attempts.require_finished(d)
    attempts.finish(d, {"model": "м"})
    m = attempts.require_finished(d)
    assert list(m) == ["made", "model"] and m["model"] == "м"
    assert "м" in (d / "manifest.json").read_text()        # not \u-escaped


def test_add_attempt_numbers_rows(root):
    attempts.add_attempt("a.djvu", "page-renders-00", "ocr-00", note="API")
    attempts.add_attempt("a.djvu", "page-renders-00", "ocr-01")
    rows = attempts._rows()[1]
    assert rows == [["00", "a.djvu", "page-renders-00", "ocr-00", "–", "API"],
                    ["01", "a.djvu", "page-renders-00", "ocr-01", "–", ""]]


def test_set_medium_fills_the_free_row(root):
    attempts.add_attempt("a.djvu", "r-00", "ocr-00")
    attempts.add_attempt("a.djvu", "r-00", "ocr-01")
    attempts.set_medium("ocr-01", "medium-00")
    rows = attempts._rows()[1]
    assert [r[4] for r in rows] == ["–", "medium-00"]


def test_set_medium_adds_a_row_when_every_one_is_taken(root):
    attempts.add_attempt("a.djvu", "r-00", "ocr-00", medium="medium-00")
    attempts.set_medium("ocr-00", "medium-01")
    rows = attempts._rows()[1]
    assert rows[1][:5] == ["01", "a.djvu", "r-00", "ocr-00", "medium-01"]


def test_set_medium_unknown_ocr(root):
    with pytest.raises(SystemExit, match="no attempt uses ocr-07"):
        attempts.set_medium("ocr-07", "medium-00")


@pytest.mark.xfail(strict=True, raises=StopIteration,
                   reason="known bug: rows are found by startswith('| 01 |'), but "
                   "attempts/index.md pads the number column ('| 01  |')")
def test_set_medium_on_a_column_aligned_index(root):
    (root / "index.md").write_text(
        INDEX_HEAD + "| 01  | a.djvu | r-00 | ocr-01 | –      | note |\n")
    attempts.set_medium("ocr-01", "medium-01")
    assert attempts._rows()[1][0][4] == "medium-01"

