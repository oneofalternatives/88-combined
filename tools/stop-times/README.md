# stop-times

Lists every train's arrival and departure at one station, in book order. One
md table, one row per printed train column. See `SPEC.md`.

    python3 tools/stop-times/stop_times.py attempts/final-NN --dest riga.md
    python3 tools/stop-times/stop_times.py attempts/final-NN --dest x.md --station "Огре"

The station name must match the cell exactly. `--station` defaults to `Рига-пасс.`.

## Reject

If any cell can't be read, the tool writes nothing. It lists every such cell
and exits 1. A cell is named the way `validate.py` names it: `Огре (r4c6)` is
body row 4, cell 6, both counted from 0.

The tool reads only the tables that have the station row. A merge mark `⟨…⟩`
anywhere in the book rejects it.

## Notes

- Suburban pages: the train number comes from the header cell. Two-way and
  distance pages: from the caption.
- Caption parts without `№` (routes, `ЕЖЕДНЕВНО`) are skipped. `ДИЗЕЛЬНЫЙ`
  marks every train on the page.
- A train name in `«…»` is dropped. `(По особому назначению)` gives `**`,
  in place of a printed `*`.
- A column whose station cells are both blank gives no row.
- `first on page` and `last on page` follow the train's direction, taken from
  its times. The printed `приб.`/`отпр.` order holds for bottom-up trains too.

Tests: `pytest tools/stop-times`.
