# Spec: OCR output of «Служебное расписание движения пригородных поездов (1988/1989 г.)»

Source: `sources/ocr-playground-download-20260920T112147Z/1988-1989_приг_раб.pdf/`
(Mistral OCR export of a scanned Soviet-era working timetable of suburban trains,
Riga division of the Baltic Railway, published Riga «Транспорт», 1988.)

## 1. Input layout

```
<root>/
  markdown.md                 # concatenation of all per-page markdown, no page separators
  pages/page-<N>/             # N = 1..103, 1-based, NOT zero padded
    markdown.md               # markdown of that scan page
    page-metadata.json        # authoritative structured description of that scan page
```

`markdown.md` at the root is a convenience dump only: it loses the
left/right-half geometry and must NOT be used for reconstruction.
The per-page `page-metadata.json` is the source of truth.

### page-metadata.json

```jsonc
{
  "index": 0,                                  // 0-based scan index = N-1
  "dimensions": { "dpi": 128, "height": 821, "width": 1019 },
  "confidenceScores": { ... },                 // per-word OCR confidence; not needed for rendering
  "blocks": [
    {
      "topLeftX": 32, "topLeftY": 23,
      "bottomRightX": 471, "bottomRightY": 86, // pixel bbox in the page image
      "content": "...",                        // markdown text of the block
      "confidenceScores": null,
      "type": "table"                          // see §3
    }
  ]
}
```

Block bboxes are in image pixels of that page's `dimensions`. Blocks appear in
reading order *per half-page*: all blocks of the left half first, then the right
half (this ordering is not guaranteed and must not be relied on — sort by geometry).

## 2. Physical structure: sheets, spreads and folios

Two page geometries occur:

| scan page N | dimensions (w×h) | meaning                                   |
| ----------- | ---------------- | ----------------------------------------- |
| 1           | 683×1019 portrait| front cover (single page)                 |
| 2 … 102     | 1019×821 landscape | **a spread: two facing book pages**     |
| 103         | 683×1019 portrait| back cover (single page)                  |

So the book renders as: 1 single sheet, 101 two-page spreads, 1 single sheet.

**Half-page split.** No block ever crosses the gutter (verified: 0 blocks with
`topLeftX < 490 and bottomRightX > 530`). A block belongs to the **left** page if
its horizontal centre `(topLeftX+bottomRightX)/2 < width/2`, otherwise to the right.

**Printed folio numbers.** Printed page numbers exist in the scans as `footer`
blocks at the bottom outer corner, but OCR captured them only on ~40% of pages,
so they must be *computed*, not read:

```
spread N (2 ≤ N ≤ 102):  left folio = 2N-4,  right folio = 2N-3
```

Verified against every OCR-captured folio (N=3 → right "3"; N=4 → left "4";
N=34 → "64"/"65"; N=74 → "144"/"145"; N=93 → "182"/"183"; N=99 → right "195").
For N=2 the folios are 0/1 (inside front cover, blank, and the title page) and
must be suppressed. Covers (N=1, 103) carry no folio.

## 3. Block types and their semantics

| `type`  | count | meaning / rendering                                                            |
| ------- | ----: | ------------------------------------------------------------------------------ |
| `title` |    37 | headings. Content carries markdown `#`/`##` prefixes (`# ГЛАВА I`, `## ОГЛАВЛЕНИЕ`). Centred. |
| `header`|    81 | running heads above a timetable (train number `п. № 606`, traction `ДИЗЕЛЬНЫЙ`, direction `Рига—Себеж`), or occasionally a stray folio. |
| `text`  |   512 | paragraphs (safety notices in Russian and Latvian), chapter sub-lists, single station names orphaned from a table. |
| `list`  |     4 | a run of station names that OCR failed to attach to the adjacent table — newline-separated, belongs to the station column of the neighbouring table. |
| `table` |   228 | a markdown pipe table — the timetables themselves. |
| `footer`|   200 | bottom-of-page material: printed folio (digits only), printer signature marks (`5 — 1055`, `9*`, `13\*`, `10 — 1055`), imprint line, and — mis-typed by the OCR — some running heads sitting at `y ≈ 30`. |

`footer` is unreliable as a semantic label: it must be classified by content and
position, not by the type field (see §5).

## 4. Timetable table format

A timetable table is GitHub-flavoured markdown with a leading and trailing pipe
and one padding space inside each cell:

```
|  № поездов | 6501 Д |   | 6601 |   | 6605  |   |
| --- | --- | --- | --- | --- | --- | --- |
|   |  приб. | отпр. | приб. | отпр. | приб. | отпр.  |
|  Разд. пункты |  |  |  |  |  |   |
|  Лиелварде | — | 23.32 | — | 0.16 |  |   |
```

Semantics:

* **Column 0** — `Разд. пункты` (block posts / stations), one row per station, in
  geographic order along the line. The station list repeats identically on every
  table of a chapter; empty time cells mean the train does not run over that part.
* **Remaining columns** come in **pairs per train**: `приб.` (arrival) / `отпр.`
  (departure). The train number (`6501 Д`, `6301*`, `6609/6620`) sits in the
  `№ поездов` row above the pair; OCR emits it in the first cell of the pair and
  leaves the second cell empty — i.e. **an empty header cell continues the
  previous one and must be rendered as a `colspan`**.
* Chapter XII tables add a `Расстояние км` column after the station column.
* **Times** use a dot as the h.m separator and a comma for the half minute:
  `5.44,5` = 05:44:30. `24.00` is midnight at the end of the day. On output the
  hour is zero-padded to `HH.MM`, keeping the optional `,5` (`5.44,5` → `05.44,5`);
  only a bare time is rewritten, so station names and train numbers pass through. `—` means the
  train passes without stopping; a blank cell means it does not serve the station.
* Cell text may also be prose spanning the pair, e.g. `Следует до` / `Вецаки`
  ("runs as far as Vecāki").
* Markers defined on the contents page (folio 3): `Д` = stops at depot Засулаукс;
  `*` = runs, cancelled when demand is low; `**` = not scheduled, run only
  exceptionally (path reserved for engineering work).
* Rows are usually but **not always** of equal width; a renderer must pad ragged
  rows to the widest row of the table.
* **Not every pipe table is a timetable.** A timetable is wide — a station
  column plus `приб.`/`отпр.` pairs, so 6 columns at least. A table of **3
  columns or fewer is prose** (the contents list on folio 3) and must be
  rendered with wrapping cells and automatic column widths; timetable cells
  instead stay on one line, since a wrapped time column would misalign.
* OCR occasionally breaks one printed table into several `table` blocks separated
  by `text`/`list` blocks holding the station names (e.g. scan page 6). These are
  rendered in document order; no attempt is made to re-join them.

## 5. Code map

| file | role |
| ---- | ---- |
| `scripts/book_model.py` | Everything in §§2–5: loading, gutter split, noise filter, row grouping, table parsing, time normalisation, `align_of`, `estimate_rows`/`fit_scale`, and block→HTML rendering. Both builders import it, so the two outputs cannot drift apart. |
| `scripts/build_book_html.py` | Screen stylesheet only (container queries, `cqw` sizing, page shadows) + file assembly. |
| `scripts/build_book_pdf.py` | Print stylesheet only (absolute mm/pt, named `@page` rules) + WeasyPrint call. `--dump-html` writes the print HTML without needing WeasyPrint installed. |

A change to layout *semantics* belongs in `book_model.py` and reaches both
outputs; a change to how a medium *looks* belongs in that medium's builder.

## 6. Reconstruction rules

1. For each scan page, split blocks into halves by bbox centre (§2); portrait
   pages have a single half.
2. Drop noise blocks: content that is only digits (a printed folio), or matches
   the printer signature pattern `^\d+\s*(—\s*\d+|\\?\*)$`.
3. Within a half, group blocks into **rows**: sort by `topLeftY`, then merge
   consecutive blocks whose vertical spans overlap by more than half the shorter
   span *and* which do not overlap horizontally. Each row is laid out
   horizontally, each block aligned left/centre/right by where its centre falls
   **within its own half** — for a right-hand block the gutter offset (half the
   scan width) must be subtracted from the centre first, or everything centred
   on a right-hand page drifts to the outer margin. This reproduces running
   heads such as `п. № 606 | ДИЗЕЛЬНЫЙ | п. № 605`.
4. Render blocks by type: `title` → `<h2>`/`<h3>` (strip `#` prefix), `header` →
   small caps running head, `text` → `<p>` (blank line = paragraph break),
   `list` → station column list, `table` → `<table>` per §4.
5. Emit the computed folio in the bottom outer corner of each book page.

## 7. Output requirements

### Shared

* One self-contained HTML file, no external assets, no network fonts.
* Every book page is a visually distinct sheet with a white ground, border and
  shadow, in a fixed aspect ratio taken from the scans (a half of 1019×821 ⇒
  ~509×821, i.e. `aspect-ratio: 509/821`).
* Scan page 1 and 103 are single sheets, centred. Spreads 2…102 render as a pair
  of facing sheets side by side, glued at the gutter, and must stay side by side
  (they are one flex row that does not wrap on wide screens; below ~900 px the
  two halves stack so the content stays readable on a phone).
### Screen (HTML)

* **All tables use one and the same font** throughout the book — a monospace
  stack for every cell, station names included, so the columns align.
* Inside a table, data cells (station names and times) are left-aligned; the
  header rows (`№ поездов`, train numbers, `приб.`/`отпр.`) stay centred.
* Facing pages sit side by side with a small gap so their drop shadows do not overlap.
* Content is scaled to the sheet with a page-local font size so the densest
  timetable — 46 rows, chapter I — fits one sheet without overflow. A half page
  is measured in
  "table rows" (`estimate_rows`); a half holding more than ~47 rows — which
  happens where the OCR emitted a fragmented table *and* a duplicate station
  list — gets a per-page shrink factor so nothing is clipped. 13 of the 202
  half pages are scaled this way.

## 8. PDF output

`scripts/build_book_pdf.py` renders the same model through WeasyPrint. One PDF
page per physical sheet, sized from the scan geometry: spread
202 × 162.9 mm, cover 109.1 × 162.9 mm, zero margins, via named `@page` rules.
Base text 6.1 pt. It shares every layout decision with the HTML build through
`book_model.py`, so the two cannot drift.

Install (no system package needed beyond pango/cairo, which are present):

```
python3 -m venv --without-pip .venv
# bootstrap pip, then:
.venv/bin/pip install weasyprint
PYTHONPATH=scripts .venv/bin/python scripts/build_book_pdf.py
```

### Verifying the PDF

Unlike the HTML, the PDF can be checked mechanically and visually:

* `pdfinfo -f 1 -l 103` — 103 pages, two distinct page sizes.
* Text-loss sweep: for each sheet compare `pdftotext` output against the text of
  the rendered half pages; any ratio below ~1.0 means content was clipped by an
  overflowing page. Must report zero sheets.
* `pdftoppm -r 110 -png` a sample and look at it — the only way to catch
  alignment and column-width faults.
