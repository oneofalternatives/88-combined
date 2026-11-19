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
| 3. copy commit on `split-versions`          | normalized-01: copy of final-01, to be normalized by hand                                     | `a0ce763` |
| 4. replay 1 onto 3                          | normalized-01: fix stop names and misprinted times; stop-name-normalizer ignore list, output  | `86dfe4c` |
| 5. docs for the split                       | docs: final-NN as printed, normalized-NN fixed by hand; README, CLAUDE.md, docstrings         | `2bf9061` |
| 6. replay 2 onto 5                          | as 2                                                                                          |           |

## Squash

Tag the old tip as `old/<branch>` and push the tag (`book-normalized` at
`fa207df`, `stop-times` at `42fd24b`). Make one commit with the old tip's
files. Check, then reset the branch to it.

- Same files as `old/<branch>`, byte for byte.
- The scripts the branch changed give the committed outputs.

## Copy

Copies `attempts/final-01` to `attempts/normalized-01`, with its
`findings.txt`, `ignore.txt` and `disputes.txt`.

## Docs

Say what `final-NN` and `normalized-NN` are, and which fixes go where:

- `README.md`: `normalized-NN` in the pipeline and the use; the PDF can be
  built from either dir.
- `tools/stop-name-normalizer/CLAUDE.md`: stop names are fixed in
  `normalized-NN`; `final-NN` keeps the book's own spellings.
- Docstrings that call `final-NN` the only hand-corrected dir.
- Whatever the review of step 4 finds.

Checks: the tests pass; `git grep 'final-NN'`: every mention looked at.

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
