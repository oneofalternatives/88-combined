# stop-times

Lists every train's arrival and departure at one station, in book order. One
md table, one row per printed train column. See `SPEC.md`.

    python3 tools/stop-times/stop_times.py attempts/final-NN --dest tools/stop-times/output/final-NN.md
    python3 tools/stop-times/stop_times.py attempts/final-NN --dest tools/stop-times/output/final-NN-ogre.md --station "Огре"

The station name must match the cell exactly. `--station` defaults to `Рига-пасс.`.
Add `--table`, `--column` or `--train` to get the table number, the column
number or the raw train-number cell as a column.

Output goes in `output/`, one file per input dir, named after it. For another
station, add its name. Files there are generated: run the tool again after
correcting the book, don't edit them by hand.

## Reject

If any cell can't be read, the tool writes nothing. It lists every such cell
and exits 1. A cell is named the way `validate.py` names it: `Огре (r4c6)` is
body row 4, cell 6, both counted from 0.

The tool reads every table in the book, to find runs that go on in a table
without the station. A merge mark `⟨…⟩` anywhere in the book rejects it.

## Notes

- Suburban pages: the train number comes from the header cell. Two-way and
  distance pages: from the caption.
- Caption parts without `№` (routes, `ЕЖЕДНЕВНО`) are skipped. `ДИЗЕЛЬНЫЙ`
  marks every train on the page.
- Marks are short codes (`П`, `ДИЗ`, `вых`). The legend is at the end of
  the output.
- A train name in `«…»` is dropped. `(По особому назначению)` gives `**`,
  in place of a printed `*`.
- A column whose station cells are both blank gives no row.
- A train that goes round the station gives no row: a text note at the
  station (`До Саласпилс`), no time on one side of it, or `—/—` between the
  two ends of a bypass link (`BYPASSES`, for Riga `Яняварты` and `Ошкалны`).
- `from` and `to` are the first and last stop with a time in the column.
  If the run goes on in a table without the station (same number, starts
  where the column ends, same time there), they take its far end: 6413 is
  `Айзкраукле`—`Слока`, not `Лиелварде`—`Слока` (scans 48, 49). A table
  split over two pages, with the caption on both, is followed the same way:
  698 is `Рига-пасс.`—`Бигосово` (scan 95). Two tables with the station are
  never linked.
- Direction comes from the times. The printed `приб.`/`отпр.` order holds
  for bottom-up trains too.

Tests: `pytest tools/stop-times`.
