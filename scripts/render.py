#!/usr/bin/env python3
"""OCR pipeline, step 1: books/<book>/sources/*.djvu -> one PNG per scan in
books/<book>/attempts/scans-NN.

--mode bw (default) renders the bilevel text layer (ddjvu -mode=black) as
1-bit PNGs; --mode gray and --mode color render the full page (ddjvu
-mode=color) as 8-bit grayscale or RGB PNGs. All at the DjVu's own pixel
size. Lossless: every PNG is checked pixel for pixel against ddjvu's output.

The PNGs are not in git. The manifest keeps a hash of each one's pixels
(pixel_sha256, see pixel_hash); --check DIR tells whether the PNGs on disk
still match.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageChops

sys.path.insert(0, str(Path(__file__).parent))

from attempts import finish, next_dir  # noqa: E402

# --mode -> (ddjvu -format, ddjvu -mode, PIL mode for the lossless check)
MODES = {"bw": ("pbm", "black", "1"), "gray": ("pgm", "color", "L"),
         "color": ("ppm", "color", "RGB")}
DEPTH = {"bw": "1-bit", "gray": "8-bit gray", "color": "RGB"}


def pixel_hash(img: Image.Image) -> str:
    """sha256 of "<mode> <w>x<h>\\n" and then the raw pixels (Image.tobytes).
    The pixels, not the PNG file: its bytes change with the encoder."""
    h = hashlib.sha256(f"{img.mode} {img.width}x{img.height}\n".encode())
    h.update(img.tobytes())
    return h.hexdigest()


def check(d: Path) -> int:
    """Compare the PNGs in a scans dir with the hashes in its manifest."""
    want = json.loads((d / "manifest.json").read_text()).get("pixel_sha256")
    if want is None:
        sys.exit(f"{d}/manifest.json: no pixel_sha256")
    bad = []
    for name, h in want.items():
        png = d / name
        if not png.exists():
            bad.append(f"{png}: missing")
        elif pixel_hash(Image.open(png)) != h:
            bad.append(f"{png}: pixels differ from the manifest")
    extra = [f"{p}: not in the manifest" for p in sorted(d.glob("*.png")) if p.name not in want]
    for line in bad + extra:
        print(line)
    print(f"{d}: {len(want) - len(bad)} of {len(want)} PNGs match")
    return 1 if bad or extra else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", type=Path, help="DjVu scan")
    ap.add_argument("--mode", choices=MODES, default="bw",
                    help="bw: 1-bit text layer (default); gray: full page, 8-bit gray; "
                         "color: full page, RGB")
    ap.add_argument("--check", type=Path, metavar="DIR",
                    help="instead of rendering: check a scans-NN dir's PNGs against its manifest")
    args = ap.parse_args()
    if args.check:
        return check(args.check)
    if not args.src:
        ap.error("give --src, or --check")
    src = args.src
    if src.parent.name != "sources":
        sys.exit(f"{src}: not in a book's sources/ dir (books/<book>/sources/)")
    fmt, ddjvu_mode, pil_mode = MODES[args.mode]

    n = int(subprocess.run(["djvused", str(src), "-e", "n"],
                           capture_output=True, text=True, check=True).stdout)
    out = next_dir(src.parent.parent / "attempts", "scans")
    sizes: dict[str, int] = {}
    hashes: dict[str, str] = {}
    for p in range(1, n + 1):
        raw = subprocess.run(["ddjvu", f"-page={p}", f"-format={fmt}", f"-mode={ddjvu_mode}", str(src), "-"],
                             capture_output=True, check=True).stdout
        img = Image.open(io.BytesIO(raw))
        dest = out / f"scan-{p:02d}.png"
        img.save(dest, optimize=True)
        saved = Image.open(dest)
        if ImageChops.difference(saved.convert(pil_mode), img.convert(pil_mode)).getbbox():
            sys.exit(f"{dest}: PNG differs from ddjvu output")
        hashes[dest.name] = pixel_hash(saved)
        size = "x".join(map(str, img.size))
        sizes[size] = sizes.get(size, 0) + 1
        print(f"{dest} {size}")

    md5 = hashlib.md5(src.read_bytes()).hexdigest()
    finish(out, {
        "source": str(src),
        "source_md5": md5,
        "scans": n,
        "command": f"ddjvu -page=N -format={fmt} -mode={ddjvu_mode} -> PNG, {DEPTH[args.mode]}, no scaling",
        "sizes": sizes,
        "pixel_sha256": hashes,
    })
    print(f"{out}: {n} scans")
    return 0


if __name__ == "__main__":
    sys.exit(main())
