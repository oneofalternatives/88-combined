"""render.py with djvused and ddjvu faked: each --mode gives PNGs of the right depth;
the manifest hashes their pixels and --check compares them."""
import hashlib
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
    src = tmp_path / "sources" / "book.djvu"
    src.parent.mkdir()
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
    src = tmp_path / "sources" / "book.djvu"
    src.parent.mkdir()
    src.write_bytes(b"djvu")
    calls = []
    monkeypatch.setattr(render.subprocess, "run", fake_run(calls))
    monkeypatch.setattr(sys, "argv", ["render.py", "--src", str(src)])
    render.main()
    assert "-mode=black" in calls[1]


def test_src_outside_sources_is_refused(tmp_path, monkeypatch):
    src = tmp_path / "book.djvu"
    src.write_bytes(b"djvu")
    monkeypatch.setattr(render.subprocess, "run", fake_run([]))
    monkeypatch.setattr(sys, "argv", ["render.py", "--src", str(src)])
    with pytest.raises(SystemExit, match="not in a book's sources/ dir"):
        render.main()
    assert not (tmp_path / "attempts").exists()


def render_one(tmp_path, monkeypatch, mode="gray"):
    monkeypatch.chdir(tmp_path)
    src = tmp_path / "sources" / "book.djvu"
    src.parent.mkdir()
    src.write_bytes(b"djvu")
    monkeypatch.setattr(render.subprocess, "run", fake_run([]))
    monkeypatch.setattr(sys, "argv", ["render.py", "--src", str(src), "--mode", mode])
    assert render.main() == 0
    return tmp_path / "attempts" / "scans-00"


def test_pixel_hash_is_of_mode_size_and_pixels():
    img = Image.new("L", (3, 2), 7)
    want = hashlib.sha256(b"L 3x2\n" + bytes([7] * 6)).hexdigest()
    assert render.pixel_hash(img) == want
    assert render.pixel_hash(img.convert("RGB")) != want


@pytest.mark.parametrize("mode", ["bw", "gray", "color"])
def test_manifest_has_pixel_hashes(tmp_path, monkeypatch, mode):
    out = render_one(tmp_path, monkeypatch, mode)
    m = json.loads((out / "manifest.json").read_text())
    assert sorted(m["pixel_sha256"]) == [f"scan-{p:02d}.png" for p in range(1, PAGES + 1)]
    for name, h in m["pixel_sha256"].items():
        assert render.pixel_hash(Image.open(out / name)) == h


def check(monkeypatch, d):
    monkeypatch.setattr(sys, "argv", ["render.py", "--check", str(d)])
    return render.main()


def test_check_passes_on_a_fresh_render(tmp_path, monkeypatch, capsys):
    out = render_one(tmp_path, monkeypatch)
    assert check(monkeypatch, out) == 0
    assert f"{PAGES} of {PAGES} PNGs match" in capsys.readouterr().out


def test_check_ignores_png_encoding(tmp_path, monkeypatch):
    out = render_one(tmp_path, monkeypatch)
    png = out / "scan-01.png"
    Image.open(png).save(png, compress_level=0)
    assert check(monkeypatch, out) == 0


def test_check_reports_changed_missing_and_extra(tmp_path, monkeypatch, capsys):
    out = render_one(tmp_path, monkeypatch)
    img = Image.open(out / "scan-01.png")
    img.putpixel((0, 0), 255 - img.getpixel((0, 0)))
    img.save(out / "scan-01.png")
    (out / "scan-02.png").rename(out / "scan-99.png")
    assert check(monkeypatch, out) == 1
    printed = capsys.readouterr().out
    assert "scan-01.png: pixels differ" in printed
    assert "scan-02.png: missing" in printed
    assert "scan-99.png: not in the manifest" in printed
    assert f"0 of {PAGES} PNGs match" in printed


def test_check_needs_hashes_in_the_manifest(tmp_path, monkeypatch):
    (tmp_path / "manifest.json").write_text("{}")
    with pytest.raises(SystemExit, match="no pixel_sha256"):
        check(monkeypatch, tmp_path)
