"""attempts.py: numbered attempt dirs and manifests."""
import json

import pytest

import attempts


@pytest.fixture
def root(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "attempts").mkdir()
    return tmp_path / "attempts"


def test_next_dir_counts_unfinished_dirs(root):
    assert attempts.next_dir("ocr").name == "ocr-00"
    assert attempts.next_dir("ocr").name == "ocr-01"     # ocr-00 has no manifest
    assert attempts.next_dir("extracted").name == "extracted-00"


def test_finish_and_require_finished(root):
    d = attempts.next_dir("ocr")
    with pytest.raises(SystemExit, match="no manifest.json"):
        attempts.require_finished(d)
    attempts.finish(d, {"model": "м"})
    m = attempts.require_finished(d)
    assert list(m) == ["made", "model"] and m["model"] == "м"
    assert "м" in (d / "manifest.json").read_text()        # not \u-escaped
