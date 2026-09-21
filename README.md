# 1988/1989 приг. раб.

Working timetable of suburban trains, Riga division of the Baltic Railway
(Riga, «Транспорт», 1988). 103 scanned sheets: OCR'd, corrected by hand,
rendered back to HTML and PDF.

## Pipeline

    sources/<ocr-export>/    Mistral OCR of the scans
      -> scripts/extract.py
    book/page-NN.md          one file per sheet, corrected by hand
      -> scripts/build_book_html.py / build_book_pdf.py
    build/                   HTML, PDF

## Use

    python3 scripts/extract.py             # OCR -> book/, skips existing files
    python3 scripts/extract.py 93 --force  # redo one sheet
    python3 scripts/build_book_html.py
    python3 scripts/build_book_pdf.py      # needs weasyprint

extract.py prints every repair it made and exits nonzero if there were any.

Both builders take `--from-ocr` to render the raw export instead of `book/`.
Build both to see what a correction changed.

## book/

Frontmatter, then one table per page. The tables are markdown-*like*: `=` rules
the head (which may be more than one row), `-` rules the interior, a one-cell
row is a band across the table. Not GFM — don't normalise it.
