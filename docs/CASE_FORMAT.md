# Data formats

Two kinds of files feed the interface at runtime: **case data** (pickled `.p` files
that hold the temporal patient data for each case) and **participant files**
(text files that define the case sequence and condition assignment for each
participant). This document describes both.

---

## 1. Pickled case files

The Django app expects one directory per case, under
`models/evaluation_study/data/<CASE_ID>/`, containing the following pickled
files:

| File | Type | Contents |
| --- | --- | --- |
| `demographics.p` | `dict` | Patient demographics (age, sex, height, weight, admit diagnosis, etc.) |
| `global_time.p`  | `dict` | Case time range (`start`, `end`, `cut1`, `cut2` epoch seconds) |
| `labs.p`         | `dict` | Time-series lab values keyed by lab abbreviation |
| `vitals.p`       | `dict` | Time-series vital signs and ventilator settings |
| `display_names.p`| `dict` | Full clinical name for every item abbreviation (`"K" → "Potassium"`) |
| `group_order_labs.p` | `list` | Grouping/ordering hints for how labs are laid out in the UI |
| `group_membership.p` | `dict` | Assignment of each item to a display group (labs, vitals, meds, IO) |
| `global_params.p` | `dict` | Per-case display parameters (chart Y-axis ranges, normal ranges) |

Every pickle was originally produced by the `PatientPy` pipeline
(<https://github.com/ajk77/PatientPy>) from de-identified HIDENIC extracts and can
be regenerated with that pipeline against any compatible clinical data source.

The included synthetic demo cases in `resources/demo_study/` (mirrored from the
upstream King repository) illustrate the exact on-disk shape and are safe to use
for local development. **The pickle files that drove the actual study cannot be
redistributed** and are not included in this release.

### Per-case highlight definitions

For each case, the reliability manipulation needs two additional per-case files:

| File | Contents |
| --- | --- |
| `judges_relevant.txt` | Items an independent judge panel labelled as clinically relevant for this case. Ground truth for omission-error scoring. |
| `planted_decoys.txt`  | Items that are **not** clinically relevant but are shown as highlighted in the `mixed` (incorrect-highlights) condition. Ground truth for commission-error scoring in mixed. |

Both files are one item abbreviation per line. See
`EvaluationStudy/WebEmrGui/views.py::load_case_highlight_definitions` for the loader.

---

## 2. Participant file

Each participant has one text file at
`models/evaluation_study/participant_info/<PARTICIPANT_ID>.txt` listing the case
sequence, per-case cut times, and per-case condition assignment.

### Format

Nine columns, comma-separated, one row per case, with a header line beginning
with `#`.

```
#visitID,cuttime1,cuttime2,t1,t2,condition,show_highlights,highlights_only,incorrect_highlights
demo-intro,0.0,0.0,0,0,ARF,0,0,0
demo-case-01,0.0,0.0,0,0,ARF,0,0,0
demo-case-02,0.0,0.0,0,0,AKF,1,0,0
demo-case-03,0.0,0.0,0,0,ARF,1,0,0
demo-case-04,0.0,0.0,0,0,AKF,1,0,1
demo-case-05,0.0,0.0,0,0,ARF,1,0,1
demo-case-06,0.0,0.0,0,0,ARF,1,0,0
```

| Column | Purpose |
| --- | --- |
| 1  `visitID` | Case ID — matches a directory under `models/evaluation_study/data/` |
| 2  `cuttime1`, 3 `cuttime2` | Cut-time boundaries (epoch seconds); legacy fields, unused by the simplified runtime |
| 4  `t1`, 5 `t2` | Day indices; legacy fields, unused by the simplified runtime |
| 6  `condition` | Admission-diagnosis label for reporting (e.g. `ARF`, `AKF`) |
| 7  `show_highlights` | `1` → highlight panel visible; `0` → hidden |
| 8  `highlights_only` | `1` → all-patient-data panel hidden (King's HID condition); `0` → both panels shown. **Should be 0 in this study.** |
| 9  `incorrect_highlights` | `1` → include planted decoys (mixed condition); `0` → correct highlights only |

Columns 7–9 together encode the three highlighting conditions:

| Condition | `show_highlights` | `highlights_only` | `incorrect_highlights` |
| --- | --- | --- | --- |
| No highlights   | 0 | 0 | 0 |
| Correct-only    | 1 | 0 | 0 |
| Mixed (with decoys) | 1 | 0 | 1 |

### Regenerating participant files

Run:

```bash
cd EvaluationStudy
python scripts/generate_participants.py
```

`SEED` at the top of the script (default `2026`) drives the randomization. Bump it
to draw a fresh case-to-condition assignment; keep it constant to reproduce the
study's assignment.

---

## 3. Master registry

A single `participant_info.txt` at
`models/evaluation_study/participant_info/participant_info.txt` lists every
participant currently in the study, one per line, followed by their current status
flag. The generator writes this alongside the per-participant files; the runtime
reads it to decide which access code corresponds to which participant.
