# Split final-01 into final-01 and normalized-01

Working notes for one job.

## Goal

Two versions of the book, side by side on one branch:

| dir                      | what                                     |
| ------------------------ | ---------------------------------------- |
| `attempts/final-01`      | 100% as printed. Only OCR misreads fixed |
| `attempts/normalized-01` | fixed by hand: spellings, misprints      |

`book-normalized` and `stop-times` did their work in `final-01`, which is
really `normalized-01`.

## Steps

A hash in **commit** means the step is done and checked.

| step                                        | title                                                                                         | commit    |
| ------------------------------------------- | --------------------------------------------------------------------------------------------- | --------- |
| 1. squash `book-normalized` onto `develop`  | final-01: fix stop names and misprinted times; stop-name-normalizer ignore list, output       | `e83740a` |
| 2. squash `stop-times` onto 1               | stop-times: stop_times.py lists every train at one station; SPEC, README, tests, output       | `bbd9949` |
| 3. copy commit on `split-versions`          | normalized-01: copy of final-01, to be normalized by hand                                     |           |
| 4. replay 1 onto 3                          | normalized-01: fix stop names and misprinted times; stop-name-normalizer ignore list, output  |           |
| 5. replay 2 onto 4                          | as 2                                                                                          |           |

## Squash

Tag the old tip as `old/<branch>` and push the tag (`book-normalized` at
`fa207df`, `stop-times` at `42fd24b`). Make one commit with the old tip's
files. Check, then reset the branch to it.

- Same files as `old/<branch>`, byte for byte.
- The scripts the branch changed give the committed outputs.

## Copy

Copies `attempts/final-01` to `attempts/normalized-01`, with its
`findings.txt`, `ignore.txt` and `disputes.txt`.

## Replay

The squashed commit, changed to work on `normalized-01`:

- Changes to `attempts/final-01/` go to `attempts/normalized-01/`. `final-01`
  stays as on `develop`.
- `tools/*/output/final-01.*` becomes `normalized-01.*`, and the source dir in
  its header too.
- `attempts/final-01` in docs and defaults becomes `attempts/normalized-01`.
  Not the golden sample: that one is `final-01` as of `2d2a3f4`, and stays.
- `final-01` in the title becomes `normalized-01`.

Checks:

- `normalized-01` = the squashed commit's `final-01`; `final-01` =
  `develop`'s; every other file = the squashed commit's, apart from the
  changes above.
- The tests pass.
- `stop_names.py` and `stop_times.py` on `normalized-01` give the committed
  outputs; `validate.py` on each dir gives that dir's `findings.txt`.
- `git grep final-01`: every remaining mention looked at.
