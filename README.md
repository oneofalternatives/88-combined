# 1988/1989 приг. раб.

Working timetable of suburban trains, Riga division of the Baltic Railway
(Riga, «Транспорт», 1988). 103 scanned sheets: OCR'd, corrected by hand,
rendered back to a PDF.

## Pipeline

    attempts/ocr-NN/         Mistral OCR of the scans
      -> scripts/extract.py
    book/page-NN.md          one file per sheet, corrected by hand
      -> scripts/validate.py
    findings                 ranked "look here", judged against the scans

Correcting `book/` and running the validator again is the loop. Rendering sits
outside it, a final production step once the sheets are good:

    book/ -> scripts/build_book_pdf.py -> build/   PDF

## Use

    python3 scripts/extract.py             # OCR -> book/, skips existing files
    python3 scripts/extract.py 93 --force  # redo one sheet
    python3 scripts/validate.py            # check book/ against itself
    python3 scripts/build_book_pdf.py      # final render; needs weasyprint

extract.py prints every repair it made and exits nonzero if there were any.
validate.py repairs nothing: it prints a ranked list of places to look and
exits nonzero if it found any. See `validator.md`.

The builder reads `book/` only. Nothing renders the OCR export directly.

## Rule for all scripts

Repairs are reported, never guessed. If a script can't work out a value, it
doesn't make one up: it adds a line to its report and goes on. Any line in the
report makes the script exit nonzero. New code must keep to this.

## OCR pipeline

    sources/*.djvu -> scripts/render.py -> attempts/page-renders-NN
                   -> scripts/ocr.py    -> attempts/ocr-NN
                   -> scripts/extract.py --src … --out … -> attempts/medium-NN

Run each step by hand. Each refuses an unfinished input. render.py and ocr.py
take the next free NN; for extract.py, name the medium in `--out`. `ocr.py`
needs `MISTRAL_API_KEY`. See `attempts/index.md`.

## book/

Medium for the book — converted from OCR output, split into pages matching the
book, human-readable and editable, machine-readable, diffable.

Frontmatter, then one table per page. The tables are markdown-*like*: `=` rules
the head (which may be more than one row), `-` rules the interior, a one-cell
row is a band across the table. Not GFM — don't normalise it.
