# Spec: `book/` page files

One file per scanned sheet, `book/page-NN.md`. Frontmatter, then one `## page N`
section per half sheet. Written by `scripts/extract.py`, read by
`scripts/build_book_pdf.py` and the validator. See the README for the table
syntax.

## Frontmatter

| key      | meaning                                                 |
| -------- | ------------------------------------------------------- |
| `sheet`  | scan page number, 1-based                               |
| `kind`   | `cover` or `spread`                                     |
| `folios` | printed page numbers, computed not read: `[2N-4, 2N-3]` |
| `shapes` | one shape per half sheet, left then right               |

## Shapes

A shape is the layout of the half sheet. Each table names itself in its header
row, so the shape is **detected, never configured** — there is no page→shape
map to keep in step with `book/`. `SHAPES` in `scripts/extract.py` holds the
header predicate, the station column and the columns that are never
time-padded.

| shape      | header row                         | station col | notes                                           |
| ---------- | ---------------------------------- | ----------- | ----------------------------------------------- |
| `suburban` | `№ поездов`                        | 0           | the common one; column pairs приб./отпр.        |
| `distance` | `Раздельные пункты` + `Расстояние` | 0           | col 1 is the milepost in km                     |
| `two-way`  | `Раздельные пункты` in col 2       | 2           | station column in the middle, a train each side |
| `prose`    | —                                  | —           | no table: notices, chapter lists                |
| `UNKNOWN`  | —                                  | —           | a table no predicate matched                    |

Direction of travel is **per column pair**, not per shape: the two trains of a
spread may run opposite ways down one station column. Infer it from the times,
never from the shape or the neighbouring pair.

`UNKNOWN` is reported by extract.py and carried into the frontmatter rather
than guessed at — a quiet fallback is what lets a whole chapter sit
unnormalized.

## Shapes and mileposts

Only the `distance` sheets carry a `Расстояние км` column. The values are
**mileposts, not distance from the origin**, and a book may number its lines in
more than one reckoning — counting down toward the origin, or up away from it.
The numbering can also **reset mid-sheet**, where a through route passes from
one reckoning into the next, so one station may honestly carry two mileposts. A
leg is `abs(km[i] - km[i+1])` within a single reckoning only; across a reset the
difference means nothing.

## Emphasis marks

No font emphasis in these files. A trailing `*` or `**` on a train number is
the book's own footnote marker, defined on its contents page, so an asterisk
added for emphasis cannot be told from the data. `book/` only — the repo's
docs use emphasis freely.
