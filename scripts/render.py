#!/usr/bin/env python3
"""OCR pipeline, step 1: DjVu -> one PNG per page in attempts/page-renders-NN.

Renders the bilevel text layer (ddjvu -mode=black) at the DjVu's own pixel
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("djvu", type=Path, nargs="?", help="default: the one in sources/")
    args = ap.parse_args()
    src = args.djvu or next(Path("sources").glob("*.djvu"))

    n = int(subprocess.run(["djvused", str(src), "-e", "n"],
                           capture_output=True, text=True, check=True).stdout)
    out = next_dir("page-renders")
    sizes: dict[str, int] = {}
    for p in range(1, n + 1):
        pbm = subprocess.run(["ddjvu", f"-page={p}", "-format=pbm", "-mode=black", str(src), "-"],
                             capture_output=True, check=True).stdout
        img = Image.open(io.BytesIO(pbm))
        dest = out / f"page-{p:02d}.png"
        img.save(dest, optimize=True)
        if ImageChops.difference(Image.open(dest).convert("1"), img.convert("1")).getbbox():
            sys.exit(f"{dest}: PNG differs from ddjvu output")
        size = "x".join(map(str, img.size))
        sizes[size] = sizes.get(size, 0) + 1
        print(f"{dest} {size}")

    md5 = hashlib.md5(src.read_bytes()).hexdigest()
    finish(out, {
        "source": str(src),
        "source_md5": md5,
        "pages": n,
        "command": "ddjvu -page=N -format=pbm -mode=black -> PNG, 1-bit, no scaling",
        "sizes": sizes,
    })
    print(f"{out}: {n} pages")


if __name__ == "__main__":
    main()
