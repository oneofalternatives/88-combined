# stop-name-normalizer

Finds stop names spelt more than one way: OCR misreads (`Торнякалис`), line-break
leftovers (`Блок- пост`), odd letters (`Қандава`), and the book's own
inconsistencies. It repairs nothing. How to pick and apply the right spelling
is not decided yet.

## Use

    python3 tools/stop-name-normalizer/stop_names.py attempts/final-01 --dest tools/stop-name-normalizer/output/final-01.txt
    python3 tools/stop-name-normalizer/stop_names.py attempts/final-01 --max-dist 4 --ratio 0.6
    python3 tools/stop-name-normalizer/stop_names.py attempts/final-01 --dump
    python3 tools/stop-name-normalizer/stop_names.py attempts/final-01 --no-ignore
    python3 tools/stop-name-normalizer/check_golden.py /tmp/golden/attempts/final-01

Both scripts read `attempts/final-01` when no dir is given. For `check_golden.py`,
give it `final-01` as of `2d2a3f4` (see Golden check).

`stop_names.py` reads the stop-name column of every table, the route titles,
the routes in the contents (scan 03) and notes in time cells (`На Царни-каву`).
It splits merge marks `⟨a ¦ b⟩` into readings. Then it runs three checks:

- **checks**: a non-Cyrillic letter (`Қандава`), a `- ` inside (`Блок- пост`),
  or a `-` that joins into a known name (`Царни-каву` → `Царникава`).
- **notations**: the parts around the stop's own name. A front or end part
  printed more than one way (`О. п.` / `о. п.` / `О/п.`, `-пасс.` / ` пасс.`,
  `-II` / ` II`). Names that differ only by an abbreviation (`Б/п.` /
  `Блок пост`, `Ваг.` / `Вагонный`), an Arabic or Roman number (`-1` / `-I`),
  or a word before the same milepost (`78 км` / `Пост 78 км`). A finding lists
  every name of that shape (a number as `#`), so `210 км` comes with `78 км`.
- **pairs**: edit distance, raised one step at a time; only the new pairs per
  step. A pair is kept when distance / length of the shorter name ≤ `--ratio`.

## Ignore list

`ignore.txt` holds pairs checked against the scan that are not one stop spelt
two ways: different stops (`Ликсна ~ Виксна`), or a town and its station
(`Тукумс-I ~ Тукумс`). One pair per line, `a ~ b`, in either order; `#`
starts a note. The finder leaves these pairs out and counts them
(`2 ignored`). It covers the distance pairs only, not notations. `--ignore`
reads another list, `--no-ignore` keeps every pair. The golden check does not
use it.

## Files

| file                            | what                                        |
|---------------------------------|---------------------------------------------|
| `stop_names.py`                 | the finder                                  |
| `check_golden.py`               | scores the finder against the golden sample |
| `ignore.txt`                    | pairs that are different stops              |
| `golden/stop-name-findings.txt` | golden sample, built on `final-01`          |
| `output/`                       | generated: run again, don't edit            |

## Golden check (`final-01` as of `2d2a3f4`)

For work on `stop_names.py` only. The golden sample describes `final-01` as of
commit `2d2a3f4`, before its stop names were fixed. Run it on that copy, not on
the current `final-01`:

    mkdir -p /tmp/golden && git archive 2d2a3f4 attempts/final-01 | tar -x -C /tmp/golden
    python3 tools/stop-name-normalizer/check_golden.py /tmp/golden/attempts/final-01

All 57 lines found, at distance ≤ 8, ratio 0.6 and at the defaults (2, 0.5).
A notation line is found when every name printed as the form is set against a
name printed as the target.

## Known limits

- The most common spelling is not always the right one: `Калигале` 35 vs `Калнгале` 2.
- Different stops can differ by one letter: `Ладе`/`Лоде`, `Лачи`/`Личи`, `Пуре`/`Пузе`.
- Past distance 2 most pairs are noise (122 at d2, 304 at d3 on `final-01`, ratio 0.6).
- Prose (the safety texts on scan 03) is not read; only the contents table is.

## Next

1. Tests in `tests/`, the golden check as one of them.
