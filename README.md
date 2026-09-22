# 1988/1989 приг. раб.

Working timetable of suburban trains, Riga division of the Baltic Railway
(Riga, «Транспорт», 1988). 103 scanned sheets: OCR'd, corrected by hand,
rendered back to a PDF.

## Pipeline

    sources/<ocr-export>/    Mistral OCR of the scans
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

## book/

Medium for the book — converted from OCR output, split into pages matching the
book, human-readable and editable, machine-readable, diffable.

Frontmatter, then one table per page. The tables are markdown-*like*: `=` rules
the head (which may be more than one row), `-` rules the interior, a one-cell
row is a band across the table. Not GFM — don't normalise it.
