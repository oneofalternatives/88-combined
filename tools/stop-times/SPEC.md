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
  the station row, links to tables without the station.

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
| from          | first stop with a time in this column, see below              |
| to            | last stop with a time in this column, see below               |
| arr           | arrival, as printed; `—` if blank                             |
| dep           | departure, as printed; `—` if blank                           |
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
| weekdays      | `w…`  | caption, `(по вторникам, …)`       |

- The marks column holds codes, in this order, joined by `, `.
- The output ends with a legend of all eight codes, always the same.
- Weekdays: `w` and the days of a `(по …)` caption note as digits, 1 = Mon …
  7 = Sun. Page 192, `(по вторникам, четвергам, субботам, воскресеньям)`,
  gives `w2467`. It marks every train on the page, on any page shape.
- `(По особому назначению)` replaces a printed `*`: `6805* ДР (По особому
  назначению)` gives `**` only.
- A train name in `«…»` is dropped (`п. № 898 ДР «СНЕЖОК»`). Only one train
  has one.

## Tables without the station

- A train's run can go on in a table without the station, which the output
  would never show: scans 48, 49 print Лиелварде—Айзкраукле apart from the
  Riga tables. from and to then take the far end (`Айзкраукле`, not
  `Лиелварде`).
- Read every table in the book for this, not only the station's. Each train
  column runs from its first to its last stop with a time, in the train's
  direction.
- Column A goes on in column B when:
  - they share a train number (first or second)
  - A's last stop is B's first stop
  - that stop's arrival or departure is printed the same in both
  - A or B is in a table without the station
- Column A also goes on in column B when the table is split over two
  pages (scans 95, 96, 99: to Бигосово, Пыталово, Пярну-груз.):
  - they share a train number (first or second)
  - both pages print the same caption
  - B is on the next page, or the page before for a bottom-up train
  - both run the same way
  - A or B is in a table without the station
- Follow these links both ways, through any number of such tables.
- Two tables with the station are never linked (a train through Riga in two
  chapters): each row is as printed, the run can be pieced together from
  the output by train number.
- A shared number alone doesn't link: 6322 is also Елгава—Крустпилс.

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
  - a `(по …)` caption note that is not all day names, or two of them
  - text left in a train cell after number, number2 and marks
  - a column that goes on in two columns, or two that go on in one
  - links that run in a loop
  - anything else unparseable that this spec gives no rule for
- Write no output. List every such cell.
