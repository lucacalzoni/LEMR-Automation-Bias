# Export schema

Two exports are produced by the running system, one per-participant JSON and one
aggregate CSV.

## 1. Per-participant JSON

One file per participant at `models/evaluation_study/results/<PARTICIPANT_ID>.json`.
Written incrementally as the participant progresses (started_at on first write,
completed_at when the last case is submitted). Structure:

```json
{
  "user_id": "P05",
  "started_at":   "2026-05-19T15:00:00",
  "completed_at": "2026-05-19T15:47:12",

  "trust_pre":  { "item_1": 4, "item_2": 5, ... },
  "trust_post": { "item_1": 4, "item_2": 5, ... },

  "demographics": {
    "age": 42, "gender": "female", "prof_level": "attending",
    "icu_years": 8
  },

  "cases": [
    {
      "case_id": "demo-case-01",
      "order_index": 2,
      "is_intro": false,

      "condition": {
        "show_highlights": 1,
        "highlights_only": 0,
        "incorrect_highlights": 0
      },

      "items_judges_relevant":         ["K", "CREAT", "BUN"],
      "items_displayed_highlighted":   ["K", "CREAT", "BUN"],
      "items_omitted_from_highlights": [],
      "items_falsely_highlighted":     [],

      "phases": {
        "familiarize_ms": 12345,
        "present_ms":     45678,
        "select_ms":      98765,
        "commission_ms":  0,
        "omission_ms":    0
      },

      "selected_items": ["K", "CREAT", "BUN", "PH"],

      "commission_rationales": [
        { "item": "PH", "rationale": "Wanted to confirm acidosis status" }
      ],

      "omission_rationales": [
        { "item": "GLUC", "reason_code": 2,
          "free_text": "Not clinically relevant to today's plan" }
      ]
    }
  ]
}
```

Reason codes for omission rationales:

| Code | Meaning |
| --- | --- |
| 1 | Not clinically relevant for this case |
| 2 | Missed it during scan |
| 3 | Too many items to consider all |
| 4 | Other (free text required) |

## 2. Aggregate CSV export

Accessed by the coordinator via the admin report page. One row per
participant-case pairing with the following columns:

| Column | Type | Description |
| --- | --- | --- |
| `user_id` | str | Participant ID (P01…P24) |
| `case_id` | str | Case ID |
| `order_index` | int | 0-based position of this case in the participant's sequence |
| `is_intro` | bool | True for the intro/familiarization case only |
| `condition_label` | str | `none` / `correct` / `mixed` |
| `show_highlights` | 0/1 | Column 7 of participant file |
| `highlights_only` | 0/1 | Column 8 |
| `incorrect_highlights` | 0/1 | Column 9 |
| `n_judges_relevant` | int | Count of ground-truth relevant items |
| `n_displayed_highlighted` | int | Count of items shown as highlighted |
| `n_omitted_from_highlights` | int | Judges-relevant items NOT highlighted |
| `n_falsely_highlighted` | int | Non-relevant items highlighted (mixed condition) |
| `n_selected` | int | Items the participant clicked |
| `n_commission_errors` | int | Selected AND not judges-relevant |
| `n_omission_errors` | int | Judges-relevant AND not selected |
| `familiarize_ms`, `present_ms`, `select_ms`, `commission_ms`, `omission_ms` | int | Cumulative time per phase in milliseconds |
| `trust_pre_mean`, `trust_post_mean` | float | Mean McKnight trust across items (1–5) |

The CSV is UTF-8, RFC-4180-quoted where needed. It's designed to feed the
statistical analysis reported in the dissertation directly — one row per
participant × case observation.
