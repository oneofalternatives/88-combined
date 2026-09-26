"""Shared bits of the OCR pipeline: numbered attempt dirs, manifests, the index.

A dir is finished once its manifest.json exists; it is written last. The index
has one row per attempt: the pieces it combines. See attempts/index.md.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path("attempts")
INDEX = ROOT / "index.md"
NONE = "–"


def next_dir(kind: str) -> Path:
    """attempts/<kind>-NN with the next free NN. Unfinished dirs keep their NN."""
    taken = [int(p.name.rsplit("-", 1)[1]) for p in ROOT.glob(f"{kind}-[0-9][0-9]")]
    d = ROOT / f"{kind}-{max(taken, default=-1) + 1:02d}"
    d.mkdir(parents=True)
    return d


def require_finished(d: Path) -> dict:
    """The manifest of an input dir; exits if the step that made it didn't finish."""
    m = d / "manifest.json"
    if not m.exists():
        sys.exit(f"{d}: no manifest.json -- unfinished or not an attempt dir")
    return json.loads(m.read_text())


def finish(d: Path, manifest: dict) -> None:
    manifest = {"made": datetime.now().isoformat(timespec="seconds"), **manifest}
    (d / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")


def _rows() -> tuple[list[str], list[list[str]]]:
    """Index lines, and the cells of each attempt row (header rows excluded)."""
    lines = INDEX.read_text().splitlines()
    rows = [[c.strip() for c in ln.strip().strip("|").split("|")]
            for ln in lines if ln.startswith("| ") and ln[2:3].isdigit()]
    return lines, rows


def add_attempt(source: str, renders: str, ocr: str, medium: str = NONE, note: str = "") -> None:
    _, rows = _rows()
    n = max((int(r[0]) for r in rows), default=-1) + 1
    with INDEX.open("a") as f:
        f.write(f"| {n:02d} | {source} | {renders} | {ocr} | {medium} | {note} |\n")


def set_medium(ocr: str, medium: str) -> None:
    """Fill the medium of the attempt that has this OCR, or add a new attempt
    reusing its pieces if every such attempt already has one."""
    lines, rows = _rows()
    mine = [r for r in rows if r[3] == ocr]
    if not mine:
        sys.exit(f"{INDEX}: no attempt uses {ocr}")
    free = next((r for r in mine if r[4] == NONE), None)
    if free is None:
        return add_attempt(*mine[-1][1:4], medium)
    free[4] = medium
    # Match the parsed number cell: the index may pad it ('| 01  |').
    i = next(i for i, ln in enumerate(lines)
             if ln.startswith("| ") and ln.strip().strip("|").split("|")[0].strip() == free[0])
    lines[i] = "| " + " | ".join(free) + " |"
    INDEX.write_text("\n".join(lines) + "\n")
