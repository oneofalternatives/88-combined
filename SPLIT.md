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

1. Tag the old tips and push the tags, so the old commits stay on origin:
   `old/book-normalized` at `fa207df`, `old/stop-times` at `42fd24b`.
2. Squash each branch into one commit. No file changes.
   - `book-normalized`: one commit on `develop`.
   - `stop-times`: one commit on the squashed `book-normalized`.
3. On `split-versions`, add the copy commit, then replay the two squashed
   commits, changed so they work on `normalized-01`. Then add the rule commit.
4. You review. Then point `book-normalized` and `stop-times` at their
   replayed commits and force-push both. Merging into `develop` is a separate
   decision.

## Commits

| commit            | title                                                                                        | squashed | replayed | checked |
| ----------------- | -------------------------------------------------------------------------------------------- | -------- | -------- | ------- |
| copy              | normalized-01: copy of final-01, to be normalized by hand                                    | –        |          |         |
| `book-normalized` | normalized-01: fix stop names and misprinted times; stop-name-normalizer ignore list, output |          |          |         |
| `stop-times`      | stop-times: stop_times.py lists every train at one station; SPEC, README, tests, output      |          |          |         |
| rule              | stop-name-normalizer: fix every printing of a stop at once, in normalized-NN only            | –        |          |         |

Fill in **squashed** and **replayed** with the new hashes.

## What changes when replaying

- Changes to `attempts/final-01/` go to `attempts/normalized-01/`. `final-01`
  stays as on `develop`.
- `tools/*/output/final-01.*` becomes `normalized-01.*`, and the source dir in
  its header too.
- `attempts/final-01` in docs and defaults becomes `attempts/normalized-01`.
  Not the golden sample: that one is `final-01` as of `2d2a3f4`, and stays.
- `final-01` in the commit title becomes `normalized-01`.
- The copy commit copies `attempts/final-01` to `attempts/normalized-01`, with
  its `findings.txt`, `ignore.txt` and `disputes.txt`.
- The rule commit: the rule in `tools/stop-name-normalizer/CLAUDE.md` holds for
  `normalized-NN` only.

## Checks

- Squashed `book-normalized` has the same files as `fa207df`, and squashed
  `stop-times` the same as `42fd24b`, byte for byte.
- After each replay: `normalized-01` = the squashed commit's `final-01`;
  `final-01` = `develop`'s; every other file = the squashed commit's, apart
  from the changes listed above.
- Both test suites pass.
- `stop_names.py` and `stop_times.py` on `normalized-01` give the committed
  outputs; `validate.py` on each dir gives that dir's `findings.txt`.
- `git grep final-01`: every remaining mention looked at.
