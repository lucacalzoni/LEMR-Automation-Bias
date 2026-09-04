# Starter data tree

This directory holds the case data, per-participant files, and results the
Django app reads and writes at runtime.

Contents shipped in the repo:
- `participant_info/participant_info.txt` — master registry of participants
  (one demo user only, so the home screen renders on a fresh clone)
- `participant_info/Interface_demo_without_highlights.txt` — the demo user's
  case ordering (one placeholder row pointing at `demo-intro`)
- `data/.gitkeep` — where pickled `.p` case files go, one directory per case
  (see [../../docs/CASE_FORMAT.md](../../docs/CASE_FORMAT.md))
- `results/.gitkeep` — where per-participant JSON results are written
- `tests/.gitkeep` — where global test/config pickles go (`display_names.p`, etc.)

For a working demo, populate `data/demo-intro/` (and the other case IDs in the
participant file) with pickled case data. Andy King's upstream repository ships
three scrambled safe-harbor cases under `resources/demo_study/` that can be
adapted as a starting point.
