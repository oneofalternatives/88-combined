#!/usr/bin/env python3
"""OCR pipeline, step 1: DjVu -> one PNG per scan in attempts/scans-NN.

--mode bw (default) renders the bilevel text layer (ddjvu -mode=black) as
1-bit PNGs; --mode gray and --mode color render the full page (ddjvu
-mode=color) as 8-bit grayscale or RGB PNGs. All at the DjVu's own pixel
size. Lossless: every PNG is checked pixel for pixel against ddjvu's output.
"""
from __future__ import annotations

import argparse
import hashlib
import io
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", type=Path, required=True, help="DjVu scan")
    ap.add_argument("--mode", choices=MODES, default="bw",
                    help="bw: 1-bit text layer (default); gray: full page, 8-bit gray; "
                         "color: full page, RGB")
    args = ap.parse_args()
    src = args.src
    fmt, ddjvu_mode, pil_mode = MODES[args.mode]

    n = int(subprocess.run(["djvused", str(src), "-e", "n"],
                           capture_output=True, text=True, check=True).stdout)
    out = next_dir("scans")
    sizes: dict[str, int] = {}
    for p in range(1, n + 1):
        raw = subprocess.run(["ddjvu", f"-page={p}", f"-format={fmt}", f"-mode={ddjvu_mode}", str(src), "-"],
                             capture_output=True, check=True).stdout
        img = Image.open(io.BytesIO(raw))
        dest = out / f"scan-{p:02d}.png"
        img.save(dest, optimize=True)
        if ImageChops.difference(Image.open(dest).convert(pil_mode), img.convert(pil_mode)).getbbox():
            sys.exit(f"{dest}: PNG differs from ddjvu output")
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
    })
    print(f"{out}: {n} scans")


if __name__ == "__main__":
    main()
