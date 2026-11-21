# Instructions for Claude

- Fix stop names in `books/<book>/attempts/normalized-NN`. `final-NN` keeps
  the book's own spellings; an OCR misread is fixed in both.
- When you fix a stop name, change every printing of that stop at once, on
  every scan. In `normalized-NN`, never leave the same stop spelt two ways.
- Keep the number in a name: `856 км` and `867 км` are different stops.
- The golden samples (`golden/`, `check_golden.py`) are for working on the
  tool, not for using it. Leave them out of reports on fixes to the scan dirs.
