"""Whole-book regression: the real OCR export through the real pipeline.

conftest.EXTRACTED is the extractor's untouched output from attempts/ocr-00.
A change to extract.py or book_model.py that moves any scan fails here, scan by
scan -- which is the check CLAUDE.md asks for, done automatically. If a change
is meant to move a scan, regenerate into a new extracted-NN, compare, and point
conftest.EXTRACTED at it; don't edit an extracted-NN.
"""
import json
import os
import subprocess
import sys
from argparse import Namespace
from collections import Counter

import pytest

import book_model as bm
import build_book_pdf
import extract
import validate
from conftest import EXTRACTED, OCR_00, REPO

SCANS = 103

# The repairs extract.py reports for ocr-00, in order. Each is a place the hand
# pass has to look; a new one, or one gone, is a change in behaviour.
P = extract.Problem
JOINED, REREAD = "joined wrapped name", "dropped a re-read name"
EXPECTED_REPORT = [
    P(3, "unrecognized table shape"),
    P(93, JOINED, "⟨Блок пост 867 км⟩"),
    P(93, "DROPPED cells", "no distance, they contradict the row above: "
      "col 3: ⟨16.16⟩ vs ⟨16.20,5⟩"),
    P(93, JOINED, "⟨Блок пост 856 км⟩"),
    P(93, "recovered cells", "col 5 from cells with no distance of their own"),
    P(93, JOINED, "⟨Блок пост 867 км⟩"),
    P(93, JOINED, "⟨Блок пост 856 км⟩"),
    *[P(93, REREAD, f"⟨{n}⟩ -- the OCR read part of the station column twice")
      for n in ["Межаре", "Аташиене", "Стирниене", "Варакляны", "Виляны", "Сакстагалс",
                "Резекне II", "Таудеяни", "Таудеяни", "Цирма"]],
    P(94, JOINED, "⟨Блок пост 867 км⟩"),
    P(94, "DROPPED cells", "no distance, they contradict the row above: "
      "col 1: ⟨871,5⟩ vs ⟨866,4⟩"),
    P(94, JOINED, "⟨Блок пост 856 км⟩"),
    P(94, JOINED, "⟨Блок пост 867 км⟩"),
    P(94, JOINED, "⟨Блок пост 856 км⟩"),
    P(96, JOINED, "⟨Блок пост 867 км⟩"),
    P(96, JOINED, "⟨Блок пост 856 км⟩"),
]


@pytest.fixture(scope="module")
def extracted():
    scans = bm.load_scans(OCR_00)
    assert list(scans) == list(range(1, SCANS + 1))
    report = []
    texts = {n: extract.render_scan(scans[n], n, report) for n in scans}
    return texts, report


@pytest.mark.parametrize("scan", range(1, SCANS + 1))
def test_scan_matches_extracted(extracted, scan):
    texts, _ = extracted
    assert texts[scan] == (EXTRACTED / f"scan-{scan:02d}.md").read_text()


def test_repair_report_matches(extracted):
    _, report = extracted
    assert report == EXPECTED_REPORT
    manifest = json.loads((EXTRACTED / "manifest.json").read_text())
    assert manifest["problems"] == len(EXPECTED_REPORT)


def test_shape_tally(extracted):
    texts, _ = extracted
    tally = Counter(s.strip() for t in texts.values()
                    for s in t.split("shapes: [", 1)[1].split("]", 1)[0].split(","))
    assert tally == {"suburban": 156, "prose": 28, "distance": 12, "two-way": 7, "UNKNOWN": 1}


# -------------------------------------------------------------- the CLI
def _script(name, *args, cwd=REPO):
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    return subprocess.run([sys.executable, str(REPO / "scripts" / name), *map(str, args)],
                          cwd=cwd, env=env, capture_output=True, text=True)


def test_extract_cli_writes_skips_and_forces(tmp_path):
    out = tmp_path / "out"
    r = _script("extract.py", 5, 93, "--src", OCR_00, "--dest", out)
    assert r.returncode == 1                      # scan 93 has repairs to report
    assert "16 PROBLEM(S) -- not guessed at, fix these:" in r.stdout
    assert "halves by shape: distance=2, suburban=2" in r.stdout
    for n in (5, 93):
        assert (out / f"scan-{n:02d}.md").read_text() == \
               (EXTRACTED / f"scan-{n:02d}.md").read_text()
    assert sorted(p.name for p in out.iterdir()) == ["scan-05.md", "scan-93.md"]

    # a one-way door: edited files are not overwritten without --force
    (out / "scan-05.md").write_text("hand corrected")
    r = _script("extract.py", 5, "--src", OCR_00, "--dest", out)
    assert r.returncode == 0 and "skip" in r.stdout
    assert (out / "scan-05.md").read_text() == "hand corrected"

    r = _script("extract.py", 5, "--force", "--src", OCR_00, "--dest", out)
    assert r.returncode == 0
    assert (out / "scan-05.md").read_text() == (EXTRACTED / "scan-05.md").read_text()


# ------------------------------------------------------------ validator
def test_validator_snapshot():
    """Tuning CONFIG moves these on purpose; update them when it does."""
    columns, findings = validate.validate(EXTRACTED)
    assert len(columns) == 521
    assert len(findings) == 269
    assert sum(f.severity == 0 for f in findings) == 78
    by_rules = Counter(tuple(sorted(f.rules)) for f in findings)
    assert by_rules == {(0,): 6, (1,): 32, (2,): 130, (2, 3, 4): 2, (2, 4): 12,
                        (3,): 7, (3, 4): 3, (4,): 71, (5,): 6}
    assert str(findings[0].where) == ("scan-93.md folio 182 [distance] п.№ 606 — "
                                      "Стрелка № 2-а → Айзкраукле  r11c3,r12c2")


def test_validator_output_is_stable_across_runs():
    """Clustering must not depend on set iteration order (hash seed)."""
    outs = []
    for seed in ("1", "2"):
        env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONHASHSEED": seed}
        r = subprocess.run([sys.executable, str(REPO / "scripts" / "validate.py"),
                            "--src", str(EXTRACTED), "--json"],
                           cwd=REPO, env=env, capture_output=True, text=True)
        assert r.returncode == 1
        outs.append(r.stdout)
    assert outs[0] == outs[1]


# ---------------------------------------------------------------- builder
def test_print_html_has_every_scan():
    html = build_book_pdf.build_html(Namespace(src=EXTRACTED))
    assert html.count("<div class='scan single'>") == 2
    assert html.count("<div class='scan'>") == SCANS - 2
    assert html.count("<div class='page left'>") == html.count("<div class='page right'>") == 101
    # the densest book pages are shrunk to fit rather than clipped
    assert "style='--fit:" in html
    assert "Саулкалне" in html and "23.59,5" in html
