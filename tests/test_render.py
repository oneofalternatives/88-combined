"""render.py with djvused and ddjvu faked: each --mode gives PNGs of the right depth."""
import io
import json
import subprocess
import sys

import pytest
from PIL import Image

import render

PAGES = 2
SIZE = (40, 30)


def fake_run(calls):
    """djvused answers the page count; ddjvu a PNM in the asked -format."""
    def run(cmd, capture_output=True, text=False, check=True):
        calls.append(cmd)
        if cmd[0] == "djvused":
            return subprocess.CompletedProcess(cmd, 0, stdout=f"{PAGES}\n")
        fmt = next(a for a in cmd if a.startswith("-format=")).split("=")[1]
        mode = {"pbm": "1", "pgm": "L", "ppm": "RGB"}[fmt]
        img = Image.linear_gradient("L").resize(SIZE).convert(mode)
        buf = io.BytesIO()
        img.save(buf, format="PPM")
        return subprocess.CompletedProcess(cmd, 0, stdout=buf.getvalue())
    return run


@pytest.mark.parametrize("mode, ddjvu_args, pil_mode, depth", [
    ("bw", ["-format=pbm", "-mode=black"], "1", "1-bit"),
    ("gray", ["-format=pgm", "-mode=color"], "L", "8-bit gray"),
    ("color", ["-format=ppm", "-mode=color"], "RGB", "RGB"),
])
def test_modes(tmp_path, monkeypatch, mode, ddjvu_args, pil_mode, depth):
    monkeypatch.chdir(tmp_path)
    src = tmp_path / "book.djvu"
    src.write_bytes(b"djvu")
    calls = []
    monkeypatch.setattr(render.subprocess, "run", fake_run(calls))
    monkeypatch.setattr(sys, "argv", ["render.py", "--src", str(src), "--mode", mode])
    render.main()

    out = tmp_path / "attempts" / "scans-00"
    for p in range(1, PAGES + 1):
        img = Image.open(out / f"scan-{p:02d}.png")
        assert img.mode == pil_mode and img.size == SIZE
    assert all(a in calls[1] for a in ddjvu_args)
    m = json.loads((out / "manifest.json").read_text())
    assert m["scans"] == PAGES and m["sizes"] == {"40x30": PAGES}
    assert depth in m["command"]


def test_default_mode_is_bw(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    src = tmp_path / "book.djvu"
    src.write_bytes(b"djvu")
    calls = []
    monkeypatch.setattr(render.subprocess, "run", fake_run(calls))
    monkeypatch.setattr(sys, "argv", ["render.py", "--src", str(src)])
    render.main()
    assert "-mode=black" in calls[1]
