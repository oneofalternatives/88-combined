# Instructions for Claude

- When writing docs, keep them short and concise, lean towards simpler English.
- `book/` may hold hand corrections. Never `--force` over it without checking first.
- Changing extract.py: regenerate every sheet to a scratch dir, diff against the
  previous run, confirm only the pages you meant to touch moved.
- Repairs are reported, never guessed. If it can't be derived, append to the
  report and let the exit code carry it.

## Working with the codebase

- Commit to `develop` branch unless specifically asked otherwise.
- Commit message must only contain title, no description or "co-authored by Claude".
