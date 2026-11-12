# Split final-01 into final-01 and normalized-01

Working notes for one job. Not committed; delete when done.

## Goal

Two versions of the book, side by side on one branch:

| dir                      | what                                     |
| ------------------------ | ---------------------------------------- |
| `attempts/final-01`      | 100% as printed. Only OCR misreads fixed |
| `attempts/normalized-01` | fixed by hand: spellings, misprints      |

`book-normalized` and `stop-times` did their work in `final-01`, which is
really `normalized-01`. We redo them on a new branch so each commit says what
it changed. The old branches stay as they are until the end.

## Plan

1. Tag the old tips: `old/book-normalized` (`fa207df`), `old/stop-times` (`42fd24b`).
2. New branch `split-versions` from `develop` (`9224e4d`).
3. Commit 0: copy `attempts/final-01` to `attempts/normalized-01`, with its
   `findings.txt`, `ignore.txt` and `disputes.txt`.
4. Replay each commit in the table, in order. For each one:
   - **data**: changes to `attempts/final-01/` go to `attempts/normalized-01/`.
     `final-01` stays as on `develop`.
   - **output**: `tools/*/output/final-01.*` becomes `normalized-01.*`, and the
     source dir in its header too.
   - **text**: `attempts/final-01` in docs and defaults becomes
     `attempts/normalized-01`. Not the golden sample: that one is `final-01` as
     of `2d2a3f4`, and stays.
   - **title**: `final-01` in the commit title becomes `normalized-01`.
   - Keep author, date and order. Change nothing else.
5. Fill in **new** with the new hash. Fill in **checked** once the step below
   is done for it.
6. After row 28: one new commit for the stop-name-normalizer rule "fix every
   printing of a stop at once". It holds for `normalized-NN` only.
7. You review. Then point `book-normalized` at row 11's new commit and
   `stop-times` at the last one, and force-push both. Merging into `develop`
   is a separate decision.

Done with a script that builds each new commit from the old one's files, not
by hand, so it gives the same result if run again.

## Checks

Per commit (**checked**):

- files outside `attempts/final-01`, `attempts/normalized-01` and the renamed
  outputs are the same as in the old commit, apart from the **text** changes
- `normalized-01` equals the old commit's `final-01`
- `final-01` equals `develop`'s

At the end:

- both test suites pass on row 11's commit and on the last one
- `stop_names.py` and `stop_times.py` on `normalized-01` give the committed
  outputs
- `validate.py` on each dir gives that dir's `findings.txt`
- `git grep final-01`: every remaining mention looked at
- the diff between the old and new tips is only the planned changes, small
  enough to read

## Commits

`x` = this kind of change is needed. Rows 1-11 are `book-normalized`, 12-28
are `stop-times`.

| #  | old     | new     | branch          | data | output | text | title | checked | subject                                                                                                                                                                                      |
| -- | ------- | ------- | --------------- | ---- | ------ | ---- | ----- | ------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 0  | –       |         | –               | copy |        |      |       |         | copy attempts/final-01 to attempts/normalized-01                                                                                                                                             |
| 1  | 7d1c6f6 |         | book-normalized | x    |        |      | x     |         | final-01: fix misprinted times on scans 5, 27, 74, 76 and 88, new validator findings                                                                                                         |
| 2  | fc97c77 |         | book-normalized | x    | x      | x    | x     |         | final-01: fix 31 misspelt stop names on 53 scans, ignore.txt to match, new validator findings; stop-name-normalizer output                                                                   |
| 3  | 0079288 |         | book-normalized |      |        |      |       |         | stop-name-normalizer: CLAUDE.md, fix every printing of a stop at once, keep numbers, golden sample is for development                                                                        |
| 4  | 6a74411 |         | book-normalized | x    | x      | x    | x     |         | final-01: fix line-break leftovers in stop names on scans 21, 95 and 99, one spelling for Блок-пост and Даугавпилс-пасс. on scans 93-96, new validator findings; stop-name-normalizer output |
| 5  | e57e238 |         | book-normalized | x    | x      | x    | x     |         | final-01: Тукумс-1/-2 and Вентспилс-1/-2 in Arabic, Вагонный парк on scans 83-86, Рига Пречу 2 on scan 85, ignore.txt to match, new validator findings; stop-name-normalizer output          |
| 6  | d56f68f |         | book-normalized | x    | x      |      | x     |         | final-01: Тукумс-I/-II and Вентспилс-I/-II back to Roman, as the book prints them but on page 192 (scan 98), new validator findings; stop-name-normalizer output                             |
| 7  | 86c0941 |         | book-normalized | x    | x      | x    | x     |         | final-01: Вайнёде on scan 81 and Мызакюла on scan 99, as printed elsewhere, new validator findings; stop-name-normalizer output                                                              |
| 8  | 9a44813 |         | book-normalized |      | x      | x    | x     |         | stop-name-normalizer: ignore list for different stops, 105 pairs from final-01, README; output regenerated                                                                                   |
| 9  | cefa278 |         | book-normalized |      | x      | x    |       |         | stop-name-normalizer: ignore list cut to the approved pairs, Ликсна/Виксна and two town/station pairs, README; output regenerated                                                            |
| 10 | 5397cba |         | book-normalized | x    | x      | x    | x     |         | final-01: one spelling for б.п. and о.п., Разъезд 98 км and Пост 78 км on scans 87-91, new validator findings; stop-name-normalizer output                                                   |
| 11 | fa207df |         | book-normalized |      | x      | x    |       |         | stop-name-normalizer: ignore list adds 14 pairs checked on the scans, 11 number pairs and Ладе/Лоде, Лачи/Личи, Пуре/Пузе; output regenerated                                                |
| 12 | cee8e3d |         | stop-times      |      |        |      |       |         | stop-times: stop_times.py lists every train's arrival and departure at one station; SPEC.md, README and tests                                                                                |
| 13 | 7b089df |         | stop-times      |      | x      | x    | x     |         | stop-times: output/final-01.md, Riga stop times of final-01; README, output dir                                                                                                              |
| 14 | 1b449c0 |         | stop-times      |      | x      |      | x     |         | stop-times: table, column and train columns only with --table, --column, --train; SPEC, README, tests, output/final-01.md                                                                    |
| 15 | 19ee6e2 |         | stop-times      |      |        |      |       |         | CLAUDE.md: table alignment rule is for docs, not generated output                                                                                                                            |
| 16 | a2f3581 |         | stop-times      |      | x      |      | x     |         | stop-times: short column titles sc, pg, no, no2, arr, dep; SPEC, tests, output/final-01.md                                                                                                   |
| 17 | 4c2769a |         | stop-times      |      | x      |      | x     |         | stop-times: marks as short codes П, ДИЗ, вых, full marks legend at the end of the output; SPEC, README, tests, output/final-01.md                                                            |
| 18 | 5748cc4 |         | stop-times      |      | x      |      | x     |         | stop-times: no row for trains with a route note at the station, they go round it; SPEC, README, tests, output/final-01.md                                                                    |
| 19 | f016c82 |         | stop-times      |      | x      |      | x     |         | stop-times: output/final-01.md regenerated on the fixed stop names                                                                                                                           |
| 20 | 08e1d78 |         | stop-times      |      | x      |      | x     |         | stop-times: no row for trains that go round the station, outside their timed run or between bypass ends Яняварты/Ошкалны; SPEC, README, tests, output/final-01.md                            |
| 21 | 4dbb656 |         | stop-times      |      | x      |      | x     |         | stop-times: output/final-01.md regenerated on scan 41 restored                                                                                                                               |
| 22 | a0e3aab |         | stop-times      |      | x      |      | x     |         | stop-times: — for a blank arrival or departure; SPEC, tests, output/final-01.md                                                                                                              |
| 23 | b63fc73 |         | stop-times      |      | x      |      | x     |         | stop-times: from/to follow the run into tables without the station, Айзкраукле for scans 48, 49 trains; SPEC, README, tests, output/final-01.md                                              |
| 24 | 7ae2630 |         | stop-times      |      |        |      |       |         | PLANS.md: board goal, transfer detector rules, possible book errors                                                                                                                          |
| 25 | 5e3fd44 |         | stop-times      |      | x      |      | x     |         | stop-times: output/final-01.md regenerated on 6635 and 6481 Д at scan 71                                                                                                                     |
| 26 | 4890c8b |         | stop-times      |      | x      |      | x     |         | stop-times: from/to follow a table split over two pages, Бигосово, Пыталово, Пярну-груз. for scans 95, 96, 99; SPEC, README, tests, output/final-01.md                                       |
| 27 | 43fdd6d |         | stop-times      |      | x      |      | x     |         | stop-times: weekday mark w and the days as digits from a caption note, w2467 for 611, 612 on page 192; SPEC, README, tests, output/final-01.md                                               |
| 28 | 42fd24b |         | stop-times      |      | x      |      | x     |         | stop-times: of a 3+4-digit pair only the local 3-digit number is kept, no2 hidden unless --no2; SPEC, README, tests, output/final-01.md                                                      |
