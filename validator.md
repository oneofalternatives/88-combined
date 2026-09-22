# validator — notes

Not written. Idea: the book over-determines itself, so check it against itself.
Reads `book/` only, like the builder. Shapes and station columns come from the
frontmatter and from `SHAPES` in extract.py — see `spec/book-format.md`.

Output is triage — ranked "look here", not a verdict. The data is unchecked OCR.
Repairs are reported, never guessed.

## Rules

1. **Monotone times.** Times increase along the direction of travel. Direction
   is fitted per column pair, both ways, better fit wins; no fit is itself a
   finding. `24.00` is midnight and night trains wrap, so compare on a
   cumulative clock — a second wrap in one column is a finding. `—` (passes
   without stopping) is skipped; blanks should run contiguously to the ends of
   the column.
2. **отпр. >= приб.** at a stop. A departure before its arrival is impossible.
   A long dwell is only suspicious — junctions really do hold ten minutes — so
   rank it against that station's other dwells. `,5` is half a minute and
   counts; parse to seconds.
3. **Implied speed**, Δkm/Δt, on the `distance` sheets. Over `max_speed_kmh`
   the data is impossible. Below that, flag by deviation from the same leg
   elsewhere (rule 4). Ties the times to the mileposts — the only rule that
   crosses the two number systems on the page.
4. **Same leg across many trains.** Group adjacent (station A, station B) pairs
   by name and score each running time by modified z, `0.6745*(x-med)/MAD`.
   Median and MAD, not mean and σ: the outliers are in the sample. MAD is often
   0 here — every train printed the same minute — so fall back to `x/median`
   over `ratio_threshold`. Under `min_samples` a leg gets no opinion.
   Report n, median and MAD with every finding: real legs vary, and the spread
   is how you judge the finding by eye.
5. **Distance -> station name** agrees book-wide. Each milepost has one name and
   each name one milepost. Cheapest rule, almost no false positives, and it
   doubles as a spell-check on the station column (`Январь` for `Яняварты`,
   `Саурнеши` for `Сауриеши`).

## What each shape gets

| shape      | rules         | notes                         |
| ---------- | ------------- | ----------------------------- |
| `suburban` | 1, 2, 4       | station col 0                 |
| `distance` | 1, 2, 3, 4, 5 | station col 0, milepost col 1 |
| `two-way`  | 1, 2, 4       | station col 2                 |
| `prose`    | none          | skipped                       |
| `UNKNOWN`  | none          | skipped **and reported**      |

## Ranking

Impossible first — non-time text in a time cell, negative dwell, backwards
time, over `max_speed_kmh` — then deviations by size. Several rules on one cell
collapse to one finding, ranked up: independent constraints rarely agree on an
innocent cell. A run of outliers in one column is one finding, not eight — that
is a column misaligned by a row, which is worse than a bad digit. Train numbers
keep their `*`/`**`: those are the book's footnote markers, not damage.

## Config

One dict at the top of the file, tuned by editing and re-running:
`max_speed_kmh` (~120), `speed_deviation_threshold` (3.5), `ratio_threshold`
(~1.5), `min_samples` (~5), and the dwell equivalents.
