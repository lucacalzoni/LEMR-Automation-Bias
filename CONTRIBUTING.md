# Contributing

Contributions are welcome. Because this fork is tied to a specific published
study, some ground rules apply:

## Scope of contributions

**Welcome:**
- Bug fixes.
- Modernization work (e.g. Django 1.11 → 4.x/5.x, dependency updates).
- New Docker/deployment recipes.
- Additional documentation.
- Portable test coverage.
- Adaptation to different data pipelines (non-`PatientPy` inputs).

**Requires discussion first (open an issue before opening a PR):**
- Changes to the reliability-based highlighting conditions or the participant
  file format — these are tied to the published study design.
- Changes to the error-classification logic — same reason.
- Changes to the McKnight trust instrument wording.

## Ground rules

1. **License.** All contributions are accepted under GPL-3.0-or-later,
   matching the fork's license. By opening a PR you confirm you have the
   right to license your contribution under those terms.
2. **No patient data, ever.** Please do not include any real patient data,
   even de-identified, in a PR or issue. Use synthetic data only.
3. **No credentials.** Do not commit secrets, API keys, or hostnames of
   private servers.
4. **Attribution.** Preserve the header attributions to Andrew J. King's
   original codebase and to Luca Calzoni's study fork.

## Development

```bash
# clone + set up (see docs/SETUP.md)
python3.9 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cd EvaluationStudy && python manage.py check
```

## PR checklist

- [ ] `python manage.py check` passes
- [ ] No new secrets, credentials, or patient data introduced
- [ ] Docstrings updated where behaviour changed
- [ ] CHANGES_FROM_KING.md updated if the change is study-relevant
