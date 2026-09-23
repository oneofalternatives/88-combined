#!/usr/bin/env python3
"""OCR pipeline, step 2: page PNGs -> Mistral OCR -> attempts/ocr-NN.

One API call per page; each raw response is saved as page-NN.json. A page that
fails is reported and the dir stays unfinished (no manifest.json) -- run again
with --resume to fetch only the missing pages. Needs MISTRAL_API_KEY.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from attempts import add_attempt, finish, next_dir, require_finished  # noqa: E402

URL = "https://api.mistral.ai/v1/ocr"
# Every optional request field, spelled out. The required two -- model
# (--model) and document (the page PNG) -- are added in call().
SETTINGS = {
    "include_blocks": True,                   # block boxes and types; split_halves needs them
    "confidence_scores_granularity": "word",  # "page" | "block" | "word"
    "table_format": None,                     # None: tables inline in markdown; "markdown"/"html": separate
    "extract_header": False,                  # True: running heads go to page["header"] instead
    "extract_footer": False,                  # True: footers go to page["footer"] instead
    "pages": None,                            # all; each call is one image anyway
    "include_image_base64": False,
    "image_limit": None,
    "image_min_size": None,
    "document_annotation_format": None,
    "document_annotation_prompt": None,
    "bbox_annotation_format": None,
}


def call(key: str, model: str, png: Path) -> dict:
    body = json.dumps({
        "model": model,
        "document": {"type": "image_url",
                     "image_url": "data:image/png;base64," + base64.b64encode(png.read_bytes()).decode()},
        **SETTINGS,
    }).encode()
    req = urllib.request.Request(URL, body, {"Authorization": f"Bearer {key}",
                                             "Content-Type": "application/json"})
    for wait in (5, 20, 60, None):
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if wait is None or (e.code != 429 and e.code < 500):
                raise RuntimeError(f"HTTP {e.code}: {e.read().decode(errors='replace')[:300]}")
            print(f"  HTTP {e.code}, retrying in {wait}s")
            time.sleep(wait)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("renders", type=Path, nargs="?", help="attempts/page-renders-NN")
    ap.add_argument("--resume", type=Path, help="an unfinished attempts/ocr-NN")
    ap.add_argument("--model", default="mistral-ocr-latest")
    args = ap.parse_args()
    key = os.environ.get("MISTRAL_API_KEY") or sys.exit("MISTRAL_API_KEY is not set")

    if args.resume:
        out = args.resume
        if (out / "manifest.json").exists():
            sys.exit(f"{out}: already finished")
        run = json.loads((out / "run.json").read_text())
    elif args.renders:
        out = None
        run = {"renders": str(args.renders), "model": args.model, "settings": SETTINGS}
    else:
        ap.error("give a renders dir or --resume")
    renders = Path(run["renders"])
    require_finished(renders)
    if out is None:
        out = next_dir("ocr")
        (out / "run.json").write_text(json.dumps(run, indent=2) + "\n")

    failed, models = [], set()
    for png in sorted(renders.glob("page-*.png")):
        dest = out / png.with_suffix(".json").name
        if not dest.exists():
            print(f"{png} ...", flush=True)
            try:
                resp = call(key, run["model"], png)
            except Exception as e:  # noqa: BLE001 -- any failure is reported, not fatal
                print(f"  FAILED: {e}")
                failed.append(png.name)
                continue
            dest.write_text(json.dumps(resp, ensure_ascii=False, indent=1) + "\n")
        models.add(json.loads(dest.read_text()).get("model"))

    if failed:
        print(f"\n{len(failed)} page(s) failed: {', '.join(failed)}")
        print(f"not finished; run: python3 scripts/ocr.py --resume {out}")
        return 1
    models = sorted(m for m in models if m)
    finish(out, {**run, "models_reported": models})
    add_attempt(Path(require_finished(renders)["source"]).name, renders.name, out.name,
                note=f"API, {', '.join(models)}")
    print(f"{out}: done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
