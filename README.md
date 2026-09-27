# 1988/1989 приг. раб.

Working timetable of suburban trains, Riga division of the Baltic Railway
(Riga, «Транспорт», 1988). 103 scans: OCR'd, corrected by hand,
rendered back to a PDF.

## Pipeline

    attempts/ocr-NN/              Mistral OCR of the scans
      -> scripts/extract.py
    attempts/extracted-NN/        one file per scan, as extracted; problems.txt
                                  lists the spots extract.py flagged
      -> scripts/validate.py      findings-<time>.txt, saved in extracted-NN
      -> copy
    attempts/final-NN/scan-NN.md  one file per scan, corrected by hand
      -> scripts/validate.py
    findings-<time>.txt           ranked "look here", saved in final-NN

Correcting `attempts/final-NN` and running the validator again is the loop.
Rendering sits outside it, a final production step once the scan files are good:

    attempts/final-NN -> scripts/build_book_pdf.py -> build/   PDF

## Use

Every script takes its dirs as arguments; none are built in.

    python3 scripts/extract.py --src attempts/ocr-00 --dest attempts/extracted-NN
                                           # OCR -> scan files, recorded in attempts/index.md
    python3 scripts/validate.py --src attempts/extracted-NN --dest attempts/extracted-NN
                                           # findings of the new extract, saved next to it
    cp -r attempts/extracted-NN attempts/final-NN && rm attempts/final-NN/manifest.json
                                           # a copy to correct by hand; problems.txt and
                                           # findings-<time>.txt say where to start
    python3 scripts/extract.py --src attempts/ocr-00 --dest attempts/final-NN 93 --force
                                           # redo one scan in final-NN
    python3 scripts/validate.py --src attempts/final-NN --dest attempts/final-NN
                                           # check the scan files against themselves (any
                                           # scan dir works); findings-<time>.txt, or no
                                           # --dest to print
    python3 scripts/build_book_pdf.py --src attempts/final-NN --dest build/1988-1989-prigorodnye-rabochie.pdf
                                           # final render; needs weasyprint

extract.py prints every repair it made and exits nonzero if there were any.
validate.py repairs nothing: it writes a ranked list of places to look (to
`--dest`, or the terminal without it) and exits nonzero if it found any. See `validator.md`.

The builder reads `attempts/final-NN` only. Nothing renders the OCR export directly.

## Rule for all scripts

Repairs are reported, never guessed. If a script can't work out a value, it
doesn't make one up: it adds a line to its report and goes on. Any line in the
report makes the script exit nonzero. New code must keep to this.

## OCR pipeline

    sources/*.djvu -> scripts/render.py --src … [--mode bw|color] -> attempts/scans-NN
                   -> scripts/ocr.py --src … --model … -> attempts/ocr-NN
                   -> scripts/extract.py --src … --dest … -> attempts/extracted-NN

Run each step by hand. Each refuses an unfinished input. render.py and ocr.py
take the next free NN; for extract.py, name the extracted-NN dir in `--dest`. `ocr.py`
needs `MISTRAL_API_KEY`: set it in the shell, or copy `.env.example` to `.env`
and fill it in. See `attempts/index.md`.

## attempts/final-NN

Medium for the book — converted from OCR output, one file per scan, split into
the book's pages, human-readable and editable, machine-readable, diffable.

Frontmatter, then one table per page. The tables are markdown-*like*: `=` rules
the head (which may be more than one row), `-` rules the interior, a one-cell
row is a band across the table. Not GFM — don't normalise it.
