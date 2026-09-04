# Changes from King's original LEMRinterface

This fork descends from Andrew J. King's `LEMRinterface`
(<https://github.com/ajk77/LEMRinterface>, GPL-3.0, University of Pittsburgh,
2018). What follows is a complete inventory of what this fork changes.

## Foundational

- **Python 2 → Python 3 port** of every active module: `views.py` (61 `print`
  statements, `basestring`, `pickle.load(..., encoding='latin-1')`), `utils.py`,
  `loaddata.py`, `WebEmrProject/{settings,urls,wsgi}.py`. Full AST parse-check
  and non-ASCII sweep were run after the port. Django 1.11 is retained
  intentionally — upgrading Django would have required rewriting templating
  and ORM without changing study behaviour.
- **Deployment modernization:** SECRET_KEY moved to env var, ALLOWED_HOSTS
  driven by env var, hardcoded `127.0.0.1` URLs replaced with relative paths so
  reverse-proxy deploys work, reverse-proxy TLS headers configured.
- **Persistence layer:** SQLite for participant state (King's original config
  targeted MySQL via Bitnami stack; SQLite eliminates the credential dance
  for reproducers).

## Study protocol — different experiment than King's

King's evaluation ran three arms: no highlights, in-place highlights,
highlights-only (HID mode). This fork replaces that with three
**reliability-based** conditions:

| Condition | show_highlights | highlights_only | incorrect_highlights |
| --- | --- | --- | --- |
| No highlights | 0 | 0 | 0 |
| Correct-only  | 1 | 0 | 0 |
| Mixed (with planted decoys) | 1 | 0 | 1 |

The reliability manipulation and the `incorrect_highlights` decoy plumbing
(`load_case_highlight_definitions`, `CATALOG_ORD_PATTERNS`, alias-aware
matching) are new. So is the within-participant counterbalanced randomization
across the seven cases per participant (`scripts/generate_participants.py`,
seed 2026), including the 9-column participant file format.

## New instrumentation

- **Five-phase timed workflow:** familiarize → present → select → commission
  rationale → omission rationale. Timing accumulates per phase and handles
  breaks correctly. King's version measured only overall time to task.
- **McKnight multi-item trust instrument** (`trust_instrument.py`) replaces
  King's UTAUT questionnaire and his single-Likert trust item.
- **Pre-trust demographics collection:** age, gender, professional level,
  years of ICU experience.
- **Deterministic error classification:** commission and omission errors
  computed against per-case judges-relevant + planted-decoys ground truth,
  with alias-aware matching to cope with polysemous drug catalogs
  (e.g. "Base solution", "Sodium Chloride 0.9%").
- **Per-error rationale capture:** commission rationales (free text) and
  omission rationales (structured reason codes 1–4 + optional free text)
  collected inline, one prompt per error.
- **Per-participant JSON results store** (`results_io.py`) with per-user
  locks for thread-safe writes.
- **Aggregate CSV export** feeding the statistical analysis; see
  [docs/EXPORT_SCHEMA.md](docs/EXPORT_SCHEMA.md).

## New coordinator-facing tooling

- **Per-participant numeric access codes** with an admin report that lists
  them, exposes demo users with reset buttons, and surfaces per-participant
  progress/error totals.
- **QA reference document generator** that cites items as
  "ABBR (Full Name)" for pre-registration verification.

## User-interface work

- Highlight-panel de-duplication of medication catalogs.
- Mirror between highlight-panel and main-panel yellow tinting.
- Transparent chart title band; non-shifting ✓ selection badge overlay
  (position:absolute so selection doesn't reflow the chart).
- Uniform highlight-panel chart sizing; viewport auto-fit.
- Time-selector that follows the case range; chart reflow after layout
  settles (fixes 0-width SVG).
- Tooltip z-index + positioner fixes.
- Rationale flow with commission/omission Back buttons and gated Submit.
- Study-intro page + access-code gated funnel.

## Bugs fixed vs the original codebase

- `determine_next_url` last-case branch (P02 ended after 4 cases instead of 7).
- Persistence bug where only the first case was being saved for real
  participants (concurrent request race on per-participant JSON write).
- Demo-user end-of-sequence path (`find_first_case` now returns `'end'`).
- Highlight-panel cells wrapped to a new row rendering as 0×80 SVG.

## Removed

- The HID (highlights-only) condition — not part of the reliability study.
- All eye-tracking machinery: `EyeBrowserPy` integration hooks, `runs/` and
  `eye_tracking/` residual paths, `TobiiGazeCore32.dll`, `TobiiGazeCore64.dll`,
  `gazesdk.pyd`.
- King-era ancillary scripts: `audio_recording_scripts.py`,
  `create_feature_vectors.py`, `eye_analysis.py`, `eye_tracking_scripts.py`,
  `eye_video_generator.py`, `retrain_models.py`, `sound_recording_scripts.py`,
  `geocities.py`, `error_determinants_scripts.py`.
- The `auto_training_scripts/` directory (King-era ML training pipeline —
  the `PatientPy` companion package handles this in the modern setup).
- The `.svn/` Subversion residue from King's pre-git history (17 MB).
- Legacy MySQL DSN + Bitnami-era config in `settings.py`.
- King's `Reference files/` directory of pre-git HTML/JS backups.
- The original UTAUT instrument.

## What is not changed

- The temporal EMR display idiom (labs / vitals / meds / vent / IO in one
  window) — inherited unchanged.
- The core selection interaction model (click an item to mark it relevant).
- The pickled `.p` case-data format (schema in
  [docs/CASE_FORMAT.md](docs/CASE_FORMAT.md)) — the pipeline that produces
  the pickles is King's `PatientPy`, unchanged.
- The Highcharts-based chart rendering.
- The overall Django + jQuery + Highcharts architecture.
