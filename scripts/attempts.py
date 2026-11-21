"""Shared bits of the OCR pipeline: numbered attempt dirs and their manifests.

Each book keeps its attempts in books/<book>/attempts/. A dir is finished once
its manifest.json exists; it is written last. attempts/index.md is kept by
hand; no script writes it.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path


def next_dir(root: Path, kind: str) -> Path:
    """<root>/<kind>-NN with the next free NN; root is a book's attempts/.
    Unfinished dirs keep their NN."""
    taken = [int(p.name.rsplit("-", 1)[1]) for p in root.glob(f"{kind}-[0-9][0-9]")]
    d = root / f"{kind}-{max(taken, default=-1) + 1:02d}"
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
