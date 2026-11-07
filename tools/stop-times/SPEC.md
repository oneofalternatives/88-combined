# Stop times tool: spec

Lists every train's arrival and departure at one station, with train number
and route, in book order.

## Usage

```
stop_times.py <final-NN dir> --dest <file.md> [--station "Рига-пасс."]
              [--table] [--column] [--train]
```

- Input: a `attempts/final-NN` dir.
- `--dest`: required. The md file to write.
- `--station` defaults to `Рига-пасс.`.
- `--table`, `--column`, `--train`: add that column. Off by default:
  sc, pg and no find a train, and no, no2 and marks hold
  what `train` does, less a dropped `«…»` name.
- Output: md only, in the repo's own table style.

## Files

- `tools/stop-times/stop_times.py`
- `tools/stop-times/README.md`, short.
- Import only `book_model.parse_scan_file` (`scripts/book_model.py`). Write
  everything else in the tool: cells, column pairs, train names, direction,
  the station row.

## Rows

- One row per train column that has a station row, as printed.
- A train that goes round the station gives no row. The book prints `—`
  both for "runs through without stopping" and for "not on this route", so
  the station cell alone can't tell. It goes round when:
  - the station cell holds a text note (`Вецаки`, `До Саласпилс`): where the
    trip goes on
  - the station cell is `—/—` and the train has no time on one side of it:
    the station is outside its run (it starts or ends at `Ошкалны`)
  - the station cell is `—/—` and the nearest timed stops on each side are
    a bypass pair, a link that skips the station. For `Рига-пасс.`:
    `Яняварты` and `Ошкалны`. Kept in `BYPASSES` in the tool.
- A train printed in two chapters gives two rows. Don't merge, don't link,
  don't report conflicts.
- Order: scan, then page, then table, then column left to right.

## Station row

- Match the station name exactly. Never match a substring
  (`Рига Пречу` must not match `Рига-пасс.`).
- Status:

| status   | printed                                    |
| -------- | ------------------------------------------ |
| `stops`  | one or both times                          |
| `passes` | `—/—`, with times on both sides, no bypass |

- Keep times as printed (`,5`, `24.00`). Don't fix them.

## Columns

| column        | content                                                       |
| ------------- | ------------------------------------------------------------- |
| sc, pg        | scan and page, where the train column is                      |
| table         | table on the page, only with `--table`                        |
| column        | column in the table, only with `--column`                     |
| train         | raw train-number cell, only with `--train`                    |
| no            | first train number                                            |
| no2           | second number of a renumbered train (`6633/6644`), else blank |
| marks         | known marks as short codes, see below                         |
| first on page | first stop with a time in this column                         |
| last on page  | last stop with a time in this column                          |
| arr           | arrival, as printed                                           |
| dep           | departure, as printed                                         |
| status        | `stops` / `passes`                                            |

## Marks

| mark          | code  | form                               |
| ------------- | ----- | ---------------------------------- |
| `Д`           | `Д`   | `… Д`                              |
| `ДР`          | `ДР`  | `… ДР`                             |
| `*`           | `*`   | `…*`                               |
| `**`          | `**`  | `…**`, `… (По особому назначению)` |
| weekends      | `вых` | `По выходным дням …`               |
| `ДИЗЕЛЬНЫЙ`   | `ДИЗ` | caption                            |
| `Пригородный` | `П`   | caption, `Пригородный п. №`        |

- The marks column holds codes, in this order, joined by `, `.
- The output ends with a legend of all seven codes, always the same.
- `(По особому назначению)` replaces a printed `*`: `6805* ДР (По особому
  назначению)` gives `**` only.
- A train name in `«…»` is dropped (`п. № 898 ДР «СНЕЖОК»`). Only one train
  has one.

## Distance and two-way pages

- Train number comes from the caption above the table
  (`п. № 606 · ДИЗЕЛЬНЫЙ · п. № 605`), not from a header cell.
- Match caption trains to column pairs by order.
- Drop column pairs with no times before matching, if that makes the count
  match exactly.
- If the count still doesn't match: reject the book.
- The second train reads bottom-up. Get direction from the times (as
  `fit_direction` in `scripts/validate.py` does), so arrival and departure
  are the right way round.

## Errors

- Reject the whole book on:
  - a `⟨…⟩` mark
  - a caption count mismatch
  - text left in a train cell after number, number2 and marks
  - anything else unparseable that this spec gives no rule for
- Write no output. List every such cell.
