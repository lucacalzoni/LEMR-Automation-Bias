# Release checklist

Reference checklist for publishing a new version of this fork to GitHub +
Zenodo. Follow top-to-bottom.

## 0. Before you start

- [ ] All changes committed on `main`.
- [ ] `python manage.py check` passes locally.
- [ ] Update the version number in `CHANGES_FROM_KING.md` and in
      `.zenodo.json` (`version`, if you add it) and in any prose that
      mentions "v1.0.0".
- [ ] Confirm `docs/CASE_FORMAT.md`, `docs/SETUP.md`, and
      `docs/EXPORT_SCHEMA.md` still reflect the current behaviour.

## 1. LICENSE — one-time step before first release

The `LICENSE` file in the repo is a stub that carries the fork's
copyright header and refers to the canonical GPL-3.0 body. Before the
first public release, append the canonical text:

```bash
curl -sSL https://www.gnu.org/licenses/gpl-3.0.txt > /tmp/gpl3.txt
# sanity-check: file should be ~35 KB and end with "please read
# <https://www.gnu.org/licenses/why-not-lgpl.html>."
wc -c /tmp/gpl3.txt   # expect ~35 000
tail -1 /tmp/gpl3.txt
# append body (skip the top preamble already in LICENSE)
cat /tmp/gpl3.txt >> LICENSE
git add LICENSE
git commit -m "LICENSE: append canonical GPL-3.0 body"
```

## 2. Sanity sweep for sensitive content

Run these from the repo root before every release; they should all print
"(clean)" or return no matches:

```bash
grep -RIn -E '\b3[0-9]{7}\b' --include='*.py' --include='*.html' --include='*.js' . \
  | grep -v 'demo-' || echo "(clean: no numeric case IDs)"

grep -RIn -E 'ajk77|luc30|hauskrecht|calzoni|clermont|deepphe|dbmi\.pitt|andrewjk|crisma1|pitt\.edu' \
  --include='*.py' --include='*.html' --include='*.js' . || echo "(clean: no name/host leaks)"

grep -RIn -E "SECRET_KEY\s*=\s*['\"][A-Za-z0-9]" --include='*.py' . \
  | grep -v 'os.environ' || echo "(clean: no hardcoded SECRET_KEY)"

# Case data, DBs, exports should not be tracked
git ls-files | grep -E '\.(p|pkl|pickle|sqlite3|csv|xlsx?)$' \
  || echo "(clean: no data files tracked)"
```

## 3. Tag and push

```bash
# Set the version
VERSION=v1.0.0

# Tag the current HEAD with a signed, annotated tag
git tag -a "$VERSION" -m "Release $VERSION"
git push origin main
git push origin "$VERSION"
```

## 4. GitHub release

- [ ] Open <https://github.com/lucacalzoni/LEMR-Automation-Bias/releases/new>
- [ ] Choose tag: `v1.0.0`
- [ ] Release title: `v1.0.0 — Initial public release`
- [ ] Release notes: paste the "What's new" section from
      `CHANGES_FROM_KING.md` for this version.
- [ ] Do **not** attach any archive files — GitHub auto-generates the
      source ZIP/tarball, and Zenodo picks up from there.
- [ ] Publish release.

## 5. Zenodo DOI mint (one-time setup + automatic per-release)

**One-time setup** (do this once, before the first release):

1. Go to <https://zenodo.org/> and sign in with GitHub.
2. Go to <https://zenodo.org/account/settings/github/> to see your
   GitHub repos.
3. Find `lucacalzoni/LEMR-Automation-Bias` in the list and toggle it
   **ON**. This installs a webhook so Zenodo will mint a DOI for every
   future GitHub release automatically.

**Per-release** (happens automatically after step 4 above):

- Zenodo receives the GitHub release webhook.
- Zenodo reads `.zenodo.json` from the release tag and populates the
  metadata record.
- Zenodo issues a new DOI (both a version-specific DOI and a
  "concept" DOI that always resolves to the latest version).
- Both DOIs appear at
  <https://zenodo.org/account/settings/github/repository/lucacalzoni/LEMR-Automation-Bias>
  usually within 2–5 minutes.

## 6. Post-release housekeeping

- [ ] Paste the new DOI into README.md's citation section (replace
      `XXXXXXX` in `10.5281/zenodo.XXXXXXX`) and push to `main`.
- [ ] Update the dissertation's software-availability sentence with the
      DOI, if the DOI wasn't available at dissertation submission.
- [ ] Optional: send the courtesy notification email to your UPMC/UPitt
      data steward. See `docs/notification_email_template.md` for a
      one-paragraph template.
