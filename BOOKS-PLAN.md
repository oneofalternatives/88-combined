# Plan: one dir per book

Each book gets `books/<book>/`, scripts stay shared. First book:
`books/1988-1989-workdays/`. One commit per step; tests pass after each.

Done: steps 1–4. Step 5 waits for the second book.

## Before

Run every script and tool on today's data into a scratch dir; save the output
and the `pytest` result. After each step, run again and diff: only paths may
change.

## 1. Move the data

`git mv` only, so `git log --follow` keeps history:

    sources/   -> books/1988-1989-workdays/sources/
    attempts/  -> books/1988-1989-workdays/attempts/
    build/     -> books/1988-1989-workdays/build/

Then fix every path pointing at the old places:

- `tests/conftest.py`: `OCR_00`, `EXTRACTED`.
- `.gitignore`: `books/*/attempts/scans-*/*.png` and `books/*/build/`. No
  PNG stays in git; `render.py --check` checks them.
- Paths in `manifest.json` / `run.json` (`"renders": "attempts/scans-01"`):
  fixed with `sed`, so `ocr.py --resume` keeps working.
- README, `validator.md`, tool READMEs, CLAUDE.md: examples and rule paths.

## 2. Scripts find the book's dirs from their arguments

No new flag, nothing hardcoded:

- `ocr.py --src books/X/attempts/scans-01` makes `ocr-NN` next to its input.
- `render.py --src books/X/sources/….djvu` writes to `books/X/attempts/`.
- `extract.py`: checks `dest.parent.name == "attempts"`, not `ROOT`.
- `attempts.ROOT` goes away (kept through step 1: moving it broke the tests
  that build `attempts/` in a tmp dir).

## 3. Book data of the tools moves to the book

    books/1988-1989-workdays/tools/stop-name-normalizer/  ignore.txt, output/
    books/1988-1989-workdays/tools/stop-times/            output/

The golden sample is test data for the tool, not the book's: it stays in the
tool, `tools/stop-name-normalizer/golden/1988-1989-workdays.txt`.

Tools find this dir from the scan dir given. Defaults like `attempts/final-01`
go; the scan dir is required. `tools/` keeps code, READMEs and tests only.

## 4. Docs

- Root README: the pipeline and how to use it, for any book.
- `books/1988-1989-workdays/README.md`: what this book is (Riga 1988, 103
  scans, page size, notes).
- `PLANS.md`, `validator.md` stay at the root.

## 5. `book.toml` (when the second book comes)

Page size and title (`build_book_pdf.py`), mileposts and stations
(`validate.py`) move to `books/<book>/book.toml`, found by walking up from
`--src`. Wait for the second book's real values: if its layout differs, this
grows into splitting the extractor's rules.
