# Test plan: one dir per book

Goal: the tip of `books-layout` works and reads right. The branch is squashed
after, so only that state counts.

The reference is the commit before the move, `009d4ff`, checked out on its own
in a scratch dir. Every comparison is old against new, both run from scratch.
Nothing is compared against hand-made notes.

## 1. Tests

The whole suite, tool tests too, passes. The count only grows: the old tests
plus the new ones.

## 2. Same results as before

Every script and tool runs on the real data in both trees, with the same
inputs. Outputs must match except for paths. Covered:

- **render:** every mode. The PNGs are identical.
- **extract:** all scans, and one scan with `--force` into a copy of `final-NN`.
- **merge:** the vote, and `--prune` on a copy.
- **validate:** each kind of dir, printed and with `--dest`.
- **PDF:** from `final-NN` and from `normalized-NN`. Byte-identical.
- **stop-times:** the default station, another station, the extra columns.
- **stop-names:** the plain run, `--dump`, `--no-ignore`, another `--ignore`.
- **golden check:** today's `final-01`, and the old copy as the README says.

The outputs written into the repo (`books/*/tools/*/output/`, `findings.txt`
and the like) come out the same when run again.

## 3. Every doc command works

Every command shown in a README, SPEC, CLAUDE.md or docstring is run as
written, from the repo root, with `B` set as the docs say. Commands that write
are pointed at scratch copies. Each one works, or the doc is fixed.

## 4. Nothing lost, nothing left behind

- **Files:** the old and new trees hold the same files, apart from the new
  prefix and the new docs. Git records the moves as renames. The PNGs that git
  ignores are still on disk.
- **Manifests:** every `manifest.json` and `run.json` is valid. Every path in
  them exists.
- **Old paths:** a search over the whole repo for the old places (`attempts/`,
  `sources/`, `build/` and tool data at the root). Each hit is fixed, or is a
  name for a kind of dir that is still right inside a book.
- **Book name:** `1988-1989-workdays` appears only where one book is meant:
  examples, the test data, that book's own files.

## 5. Read-through

Every doc and CLAUDE.md is read in full, as a newcomer would read it, against
the new layout. Checked:

- paths and names
- one word for one thing ("book dir", `$B`)
- no leftover "the book" where any book is meant
- tables aligned
- short, simple English

## 6. After the squash

Run 1 again and repeat a sample of 2. The commit message is a title only.

## Notes

- **PDF:** WeasyPrint writes the build time into the PDF. Old and new are
  byte-identical only when built in the same second: run them in parallel.
- **PNGs:** none are in git, `scan-93.png` included. Check them with
  `python3 scripts/render.py --check $B/attempts/scans-NN`.
- **Old tree:** `009d4ff` has no PNGs for `scans-01` to `scans-03`. Copy them
  from the repo.
- **The move commit alone fails the tests:** it only moves files; the paths
  are fixed in the next commit.
- **Not run here:** `pdfinfo` is not installed; `ocr.py --src` calls the paid
  API (`--resume` of a finished copy, its manifest removed, runs offline).
- **Known, left as is:** `build_book_pdf.py` builds a dir with merge marks,
  though `merge.py`'s docstring says the build rejects them. The old
  `extracted-NN` dirs differ from a fresh extract: they record older extractor
  versions.

## Done when

Every point passes. Every difference found is either fixed or listed with its
reason.
