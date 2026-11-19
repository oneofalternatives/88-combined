# Instructions for Claude

- When writing docs, keep them short and concise, lean towards simpler English.
- In md docs (README, SPEC and the like, not generated output such as
  `tools/*/output/`), align table columns: pad every cell to the column's
  width, and make the `---` separator span it too.
- `attempts/final-NN/` and `attempts/normalized-NN/` may hold hand corrections. Never
  `--force` over them without checking first.
- `final-NN` is the book as printed: fix only OCR misreads there. Misprinted
  times and stops spelt two ways are fixed in `normalized-NN`. Fix an OCR
  misread in both.
- Changing extract.py: regenerate every scan to a scratch dir, diff against the
  previous run, confirm only the pages you meant to touch moved.

## Working with the codebase

- Commit to the currently active branch unless asked otherwise.
- Never commit to `master` unless the user gave you an explicit permission.
- Commit message must only contain title, no description or "co-authored by Claude".
