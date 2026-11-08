# Plans

Ideas not built yet. Short notes, enough to pick up later.

## Goal

A departure board simulator for Riga, late 80s. `tools/stop-times` gives the
book's trains at the station. The board may show a farther origin or
destination than a train runs, if there is a sensible transfer.

The book is a working timetable, with mistakes. It doesn't print every
transfer, and a note may be missing. We have to work transfers out.

## Transfer detector

A tool that lists possible transfers for a person (or AI) to judge. It
decides nothing. Accepted ones go in a hand-kept list, each with a short
reason. `stop-times` stays as printed.

Printed in the book, out of Riga (`Пересадка на X` past the last stop):

| feeder | note                   | connection | where                           |
| ------ | ---------------------- | ---------- | ------------------------------- |
| 6612   | `Пересадка на Лимбажи` | 6864       | scan 54, p. 105, 3 rows         |
| 6410   | `Пересадка на Алоя`    | 6866 ДР    | scan 56, p. 108; 6866 on p. 109 |

Not printed, the way back (found by the mirror rule below):

| incoming             | Riga train | at         | wait   | where           |
| -------------------- | ---------- | ---------- | ------ | --------------- |
| 6863 ДР from Алоя    | 6417 Д     | Саулкрасты | 16 min | scan 65, p. 126 |
| 6867 ДР from Лимбажи | 6431       | Саулкрасты | 3 min  | scan 66, p. 129 |

Possible rules:

- Same direction: the next train must not go back over stops the first one
  used. Train-number parity also works, but breaks where it flips at a
  junction and on renumbered trains (`6628/6615`).
- A change can be mid-run, not only at the last stop: 6308 goes on to
  Крустпилс but could drop people at Елгава for Riga.
- Skip the far end of a linked train (scans 48, 49 Лиелварде—Айзкраукле):
  it's the same train, not a trip of its own.
- Skip Крустпилс—Елгава: its own line, far from Riga. No transfers to or
  from it at Елгава or Крустпилс.
- Earliest connection wins. Set a sensible wait limit.
- Mirror rule: a train with no Riga row that has a time at a printed note's
  X connects back to the earliest Riga train from a later shared stop.
  Finds exactly the two above.
- Flag possible missing notes: a train that ends just short of where another
  carries on its line.

Open:

- 6627/6638 (scan 69, p. 135) goes round Riga to Лиелварде. A change to
  6463 at Саулкрасты, or later, gets you into Рига-пасс. Count it?
- Departures board only? Then only the way out matters: a transfer extends
  the destination. The way back only changes an origin.
- Output form tried, then dropped: an extra row right after the
  feeder, `->` on the feeder, `<-` on the connection, no time at Riga.

## Possible book errors

| train   | where                      | cells                                         |
| ------- | -------------------------- | --------------------------------------------- |
| 6308 ДР | scan 79, p. 154, t1, col 3 | Виестури dep 18.32, then о.п. 50 км arr 18.30 |
| 6463 Д  | scan 69, p. 135, t1, col 3 | Гауя 15.42 / 16.43, Царникава 15.45           |
