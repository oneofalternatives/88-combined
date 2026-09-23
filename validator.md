# validator — notes

`scripts/validate.py`. The book over-determines itself, so it is checked
against itself. Reads `book/` only, like the builder. Shapes come from the
frontmatter, station columns from `SHAPES` in extract.py, imported rather than
restated — see `spec/book-format.md`. `--limit 0` for all of it, `--rule N` for
one rule, `--json` for a machine.

Output is triage — ranked "look here", not a verdict. The data is unchecked
OCR. Repairs are reported, never guessed, and the exit code carries them.

## Rules

1. **Monotone times.** Times increase along the direction of travel. Direction is
   fitted per column pair, both ways, better fit wins; no fit is itself a
   finding. `24.00` is midnight and night trains wrap, so compare on a
   cumulative clock — one wrap is allowed, and only where it reads like
   midnight: out late, in early, not inside a stop. Any other backwards step is
   damage, so it does not advance the clock and the times around it stop being
   evidence for rules 3 and 4. `—` (passes without stopping) is skipped; blanks
   should run contiguously to the ends of the column.
2. **отпр. >= приб.** at a stop. A departure before its arrival is impossible. A
   long dwell is only suspicious — junctions really do hold ten minutes — so
   rank it against that station's other dwells. `,5` is half a minute and
   counts; parse to seconds.
3. **Implied speed**, Δkm/Δt, on the `distance` sheets. Over `max_speed_kmh` the
   data is impossible; far off the book-wide median speed it is a deviation
   (`speed_deviation_threshold`, quiet on this book). Never measured across a
   mileposting reset. Ties the times to the mileposts — the only rule that
   crosses the two number systems on the page.
4. **Same leg across many trains.** Group adjacent (station A, station B) pairs
   by name, each direction its own sample — a leg can genuinely run slower one
   way, and pooling the two makes every train in the slower direction an
   outlier — and score each running time by modified z, `0.6745*(x-med)/MAD`,
   over `deviation_threshold`. Median and MAD, not
   mean and σ: the outliers are in the sample. MAD is often 0 here — every
   train printed the same minute — so fall back to `x/median` over
   `ratio_threshold`. Under `min_samples` a leg gets no opinion, nor does a
   sample within `leg_min_diff_sec` of the median however tight the spread: the
   book prints to the half minute. Report n, median and MAD with every finding:
   real legs vary, and the spread is how you judge the finding by eye.
5. **Distance -> station name** agrees within a reckoning. Each milepost has one
   name and each name one milepost. Cheapest rule, almost no false positives,
   and it doubles as a spell-check on the station column (`Январь` for
   `Яняварты`) — but only on the six `distance` sheets, the only ones carrying
   mileposts, so the two-way sheets are out of its reach. Lines reuse kilometre
   numbers, so a shared milepost is a finding only where the two names are
   near-duplicates (`name_similarity`).

## Mileposting

Chapter XII prints a through route in several reckonings and the numbering
resets where it changes: Рига—Пыталово counts down from 922,8 at Рига-пасс. to
Плявиняс, then up from 0,0 again, so Рига-пасс. honestly has two mileposts and
neither is damage. Each half is cut into zones at a step over `max_leg_km` or
where the kilometres turn round, and each zone placed in a reckoning by its
band. `MILEPOSTING`, keyed by the destination in the route caption, declares
which reckonings a route may use; a zone outside them is reported, not filed.

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
keep their footnote markers: those are the book's, not damage.

## Config

`CONFIG` at the top of the file, tuned by editing and re-running: the
thresholds named above, their dwell equivalents (`dwell_deviation_threshold`,
`dwell_ratio_threshold`, `dwell_min_diff_sec`), `misalign_run` for the run that
collapses to one finding, and the hours that let a wrap read as midnight.
`MILEPOSTING` and `RECKONINGS` sit beside it.
