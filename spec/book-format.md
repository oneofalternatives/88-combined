# Spec: `book/` page files

One file per scanned sheet, `book/page-NN.md`. Frontmatter, then one `## page N`
section per half sheet. Written by `scripts/extract.py`, read by
`scripts/build_book_pdf.py` and the validator. See the README for the table
syntax.

## Frontmatter

| key      | meaning                                                 |
| -------- | ------------------------------------------------------- |
| `sheet`  | scan page number, 1..103                                |
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
| `distance` | `Раздельные пункты` + `Расстояние` | 0           | chapter XII; col 1 is the milepost in km        |
| `two-way`  | `Раздельные пункты` in col 2       | 2           | station column in the middle, a train each side |
| `prose`    | —                                  | —           | no table: notices, chapter lists                |
| `UNKNOWN`  | —                                  | —           | a table no predicate matched                    |

Direction of travel is **per column pair**, not per shape: on a `distance` sheet
the two trains of a spread run opposite ways down one station column
(`п. № 606 Рига—Себеж` and `п. № 605 Себеж—Рига` on folio 182). Infer it from
the times, never from the shape or the neighbouring pair.

`UNKNOWN` is reported by extract.py and carried into the frontmatter rather
than guessed at — a quiet fallback is what let a whole chapter sit
unnormalized. Today the only one is the contents table on folio 2.

## Shapes and mileposts

Only the six `distance` sheets (folios 182..195) carry a `Расстояние км`
column. The values are **mileposts, not distance from the origin**: they
decrease away from Riga (922,8 at Рига-пасс. down to 616,3 at Себеж), so a leg
is `abs(km[i] - km[i+1])`.
