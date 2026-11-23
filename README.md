# Timetable books

Scanned railway timetable books: OCR'd, corrected by hand, rendered back to a
PDF. The scripts are shared; each book has its own dir in `books/`.

| dir                        | book                                              |
| -------------------------- | ------------------------------------------------- |
| `books/1988-1989-workdays` | 1988/1989 приг. раб., suburban trains, Riga, 1988 |
| `books/1988-1989-weekends` | 1988/1989 приг. вых., days off, summer part       |

## A book dir

    books/<book>/
      README.md        what the book is
      sources/         the scan (djvu)
      attempts/        OCR runs, extracts, final-NN, normalized-NN; index.md lists them
      build/           the PDF; built, not in git
      tools/<tool>/    the book's data for a tool: ignore lists, output

## Pipeline

Paths are inside a book dir.

    attempts/ocr-NN/              Mistral OCR of the scans
      -> scripts/extract.py
    attempts/extracted-NN/        one file per scan, as extracted; problems.txt
                                  lists the spots extract.py flagged
      -> scripts/merge.py         (optional) several extracted-NN by vote
    attempts/merged-NN/           the same, with disputed readings marked;
                                  disputes.txt lists them
      -> scripts/validate.py      findings.txt, saved in extracted-NN or merged-NN
      -> copy
    attempts/final-NN/scan-NN.md  one file per scan, corrected by hand
      -> scripts/validate.py      findings.txt, ranked "look here", saved in final-NN
      -> copy
    attempts/normalized-NN/       the same, with the book's own mistakes fixed
      -> scripts/validate.py      findings.txt, saved in normalized-NN

Two dirs are corrected by hand:

- `final-NN` is the book as printed. Only OCR misreads are fixed in it.
- `normalized-NN` starts as a copy of `final-NN` and also fixes the book:
  misprinted times, a stop spelt two ways. An OCR misread is fixed in both.

Correcting either dir and running the validator again is the loop.
`findings.txt` and `disputes.txt` are generated. After each correction, run
`validate.py` and `merge.py --prune` again; don't edit either file by hand.
Rendering sits outside it, a final production step once the scan files are good:

    attempts/final-NN or normalized-NN -> scripts/build_book_pdf.py -> build/   PDF

## Use

Every script takes its dirs as arguments; none are built in. A book's data
lives in `books/<book>/`; below, `B=books/1988-1989-workdays`.

    python3 scripts/extract.py --src $B/attempts/ocr-00 --dest $B/attempts/extracted-NN
                                           # OCR -> scan files; add its row to $B/attempts/index.md
    python3 scripts/validate.py --src $B/attempts/extracted-NN --dest $B/attempts/extracted-NN
                                           # findings of the new extract, saved in it
    cp -r $B/attempts/extracted-NN $B/attempts/final-NN && rm $B/attempts/final-NN/manifest.json
                                           # a copy to correct by hand; problems.txt and
                                           # findings.txt say where to start
    cp -r $B/attempts/final-NN $B/attempts/normalized-NN
                                           # a copy to fix the book's own mistakes in
    python3 scripts/extract.py --src $B/attempts/ocr-00 --dest $B/attempts/final-NN 93 --force
                                           # redo one scan in final-NN
    python3 scripts/validate.py --src $B/attempts/final-NN --dest $B/attempts/final-NN
                                           # check the scan files against themselves (any
                                           # scan dir works); findings.txt, or no
                                           # --dest to print
                                           # findings checked and true to the book go in
                                           # that dir's ignore.txt (in normalized-NN, fix
                                           # a misprint instead); see validator.md
    python3 scripts/build_book_pdf.py --src $B/attempts/final-NN --dest $B/build/1988-1989-prigorodnye-rabochie.pdf
                                           # final render; needs weasyprint

extract.py prints every repair it made and exits nonzero if there were any.
validate.py repairs nothing: it writes a ranked list of places to look (to
`--dest`, or the terminal without it) and exits nonzero if it found any. See `validator.md`.

The builder reads a hand-corrected dir only, `final-NN` or `normalized-NN`.
Nothing renders the OCR export directly.

## Rule for all scripts

Repairs are reported, never guessed. If a script can't work out a value, it
doesn't make one up: it adds a line to its report and goes on. Any line in the
report makes the script exit nonzero. New code must keep to this.

## OCR pipeline

    sources/*.djvu -> scripts/render.py --src … [--mode bw|gray|color] -> attempts/scans-NN
                   -> scripts/ocr.py --src … --model … -> attempts/ocr-NN
                   -> scripts/extract.py --src … --dest … -> attempts/extracted-NN

Run each step by hand. Each refuses an unfinished input. render.py and ocr.py
take the next free NN; for extract.py, name the extracted-NN dir in `--dest`. `ocr.py`
needs `MISTRAL_API_KEY`: set it in the shell, or copy `.env.example` to `.env`
and fill it in. Each book's `attempts/index.md` lists its attempts.

The scan PNGs are not in git. Each `scans-NN/manifest.json` keeps a hash of
every PNG's pixels (`pixel_sha256`). To check the PNGs on disk:

    python3 scripts/render.py --check $B/attempts/scans-NN

render.py makes a lost set again, pixel for pixel, into a new `scans-NN`.

Several extractions can be merged into one by vote:

    python3 scripts/merge.py --src $B/attempts/extracted-A $B/attempts/extracted-B … [--extra …] --dest $B/attempts/merged-NN

Each `--src` run gets one vote. Where they disagree, the cell keeps every
reading, most votes first: `⟨06.52,5 ¦ 06.52.5⟩` (`∅` is an empty cell).
`--extra` runs don't vote; they're only shown where the votes differ. A page
laid out differently by the runs is given whole, marked `⟨alternative …⟩`.
Every mark is listed in `disputes.txt`, the sources in `manifest.json`. A merged-NN is copied to final-NN
like an extracted-NN. Remove all marks before the build.

As you resolve marks by hand, drop them from the list:

    python3 scripts/merge.py --prune $B/attempts/final-NN

A row stays while its mark is still on its page. Layout notes ("outvoted")
have no mark and always stay.

## attempts/final-NN, attempts/normalized-NN

Medium for a book — converted from OCR output, one file per scan, split into
the book's pages, human-readable and editable, machine-readable, diffable.

Frontmatter, then one table per page. The tables are markdown-*like*: `=` rules
the head (which may be more than one row), `-` rules the interior, a one-cell
row is a band across the table. Not GFM — don't normalise it.
