# Instructions for Claude

- `book/` may hold hand corrections. Never `--force` over it without checking first.
- Changing extract.py: regenerate every sheet to a scratch dir, diff against the
  previous run, confirm only the pages you meant to touch moved.
- Repairs are reported, never guessed. If it can't be derived, append to the
  report and let the exit code carry it.
- Don't use font emphasis marks (e.g. `*`) A trailing `*` on a train number is the book's footnote marker, not emphasis.
