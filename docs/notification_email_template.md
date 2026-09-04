# Courtesy notification email templates

Neither of these emails asks permission — they give notice. The intent is
transparency, not gatekeeping. Send them once the public release is live
so the recipient can inspect the actual repository if they wish.

---

## Template 1 — Data steward / PI

**To:** UPitt DBMI data steward, plus your PI (Dr. Cooper) and dissertation
committee chair
**Subject:** LEMR study code — public release notification

Dear [Data steward / Dr. Cooper],

I'm writing to notify you that the study-specific software from my
dissertation ("Automation Bias in EMR Information Highlighting") has been
released as open source at:

<https://github.com/lucacalzoni/LEMR-Automation-Bias>

The release is a code-only fork of Andrew J. King's original
`LEMRinterface` (GPL-3.0, University of Pittsburgh, 2018) with the
study-specific modifications documented in `CHANGES_FROM_KING.md`. It
inherits King's GPL-3.0-or-later license.

**No protected patient data is included in the release.** The pickled
patient-case files that drove the actual evaluation cannot be
redistributed and are not part of this release. Users who wish to
exercise the interface can either use the three scrambled safe-harbor
demo cases already published in the upstream King repository, or connect
their own data pipeline (see `docs/CASE_FORMAT.md`).

Happy to walk through the contents of the release if useful, or to make
any adjustments you'd recommend.

Best,
Luca

---

## Template 2 — Andrew J. King (courtesy notification, not permission request)

**To:** Andrew J. King
**Subject:** Public release of a LEMR fork citing your original work

Dear Andrew,

Quick note to let you know that I've released the study-specific fork of
your `LEMRinterface` codebase publicly, as part of the software-availability
requirement for my dissertation:

<https://github.com/lucacalzoni/LEMR-Automation-Bias>

The release retains your GPL-3.0 license and attributes you as the
original author throughout — in the README, LICENSE, `CHANGES_FROM_KING.md`,
and the Zenodo metadata. The fork is Python 3 only and adds the
automation-bias study machinery on top of the interface you built.

If you would like anything about the attribution changed, or if you'd
prefer I add a note directing users to your v2.0 upstream for anything
that would be better served by that codebase, just let me know and I'll
make the edits.

Thank you again for the foundational work — it made everything I did
possible.

Best,
Luca

---

## Template 3 — McKnight et al. (only if you ship the exact instrument wording verbatim in templates)

**To:** D. Harrison McKnight (or the corresponding author of McKnight et al.,
2011)
**Subject:** Use of your trust-in-technology instrument in an open-source
research prototype

Dear Dr. McKnight,

I used your trust-in-technology instrument (McKnight, Carter, Thatcher,
Clay 2011) as the pre- and post-use trust measurement in my dissertation
study on automation bias in EMR interfaces at the University of Pittsburgh.
I'm now preparing the study software for open-source release under GPL-3.0.

The exact wording of each of the twelve items appears in the release
templates (`WebEmrGui/trust_instrument.py`). I want to confirm this
usage is permitted under standard academic use, and that a citation to
your 2011 paper in the source file and in the README is sufficient
attribution. If you'd prefer I paraphrase the items or arrange for a
license/permission acknowledgement, I'm happy to accommodate — the
release is not published yet.

The repository will live at
<https://github.com/lucacalzoni/LEMR-Automation-Bias>.

Thank you for your foundational work on trust measurement; it shaped
the trust component of the study.

Best,
Luca Calzoni
University of Pittsburgh
