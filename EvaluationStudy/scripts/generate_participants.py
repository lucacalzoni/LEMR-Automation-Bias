# -*- coding: utf-8 -*-
"""
Regenerate the 24 participant ordering files and the participant_info.txt
master list for the 2026 simplified study design.

Design:
  - Each participant gets 1 introductory case (no highlights) followed by
    6 test cases.
  - The 6 test cases are the SAME case IDs for every participant, but
    presented in a randomized order with randomized condition assignment.
  - Condition split per participant: 2 cases with no highlights,
    2 cases with correct highlights only, 2 cases with correct + incorrect
    highlights (the automation-bias arm).
  - Randomization uses a fixed seed so the output is reproducible across
    runs and across machines. Bump the seed if you ever need a fresh draw.

File format (9 columns):
  #visitID,cuttime1,cuttime2,t1,t2,condition,show_highlights,highlights_only,incorrect_highlights

Run from the EvaluationStudy directory (so ../../models/ resolves):
    python scripts/generate_participants.py

This overwrites P01.txt..P24.txt and participant_info.txt inside
../../models/evaluation_study/participant_info/. Make a backup first if
you want to keep the previous draw.
"""

from __future__ import print_function

import datetime
import os
import random
import sys


# --------------------------------------------------------------------------
# Config -- change these if the study design changes
# --------------------------------------------------------------------------

SEED = 2026  # bump this to draw a fresh randomization

# ------------------------------------------------------------------
# EXAMPLE CASE IDS
# Replace these placeholders with the case IDs of the pickled `.p` case
# files installed under models/evaluation_study/data/<CASE_ID>/. Case IDs
# in the demo data set that ships in resources/demo_study/ are documented
# in CASE_FORMAT.md. To reuse your own cases, list their IDs here.
# ------------------------------------------------------------------
INTRO_CASE = 'demo-intro'  # first case for every participant (no highlights)

TEST_CASES = [
    'demo-case-01',
    'demo-case-02',
    'demo-case-03',
    'demo-case-04',
    'demo-case-05',
    'demo-case-06',
]

# (show_highlights, highlights_only, incorrect_highlights)
CONDITIONS = {
    'none':     ('0', '0', '0'),  # no highlights
    'correct':  ('1', '0', '0'),  # correct highlights only
    'mixed':    ('1', '0', '1'),  # correct + incorrect highlights
}

# Two cases per condition -> 6 test cases total per participant.
CONDITION_PATTERN = ['none', 'none', 'correct', 'correct', 'mixed', 'mixed']

# Metadata for each case ID. Pulled from the legacy participant files so the
# cuttime/t/condition columns stay plausible-looking. They are not used by
# the simplified runtime flow (determine_next_url only reads columns 6-8),
# but the file still needs a parseable structure.
#   case_id -> (cuttime1, cuttime2, t1, t2, condition)
CASE_METADATA = {
    # Case IDs and metadata for the case set used by this deployment.
    # Cuttime values are epoch seconds; t values are day indices; the
    # last string is the admission diagnosis (e.g. 'ARF', 'AKF').
    # Replace these entries with metadata for your own case data.
    '99999999':  ('0.0', '0.0', '0', '0', 'ARF'),   # synthetic demo case shipped in models/evaluation_study/data/99999999/
    'demo-case-01':('0.0', '0.0', '0', '0', 'ARF'),
    'demo-case-02':('0.0', '0.0', '0', '0', 'AKF'),
    'demo-case-03':('0.0', '0.0', '0', '0', 'ARF'),
    'demo-case-04':('0.0', '0.0', '0', '0', 'AKF'),
    'demo-case-05':('0.0', '0.0', '0', '0', 'ARF'),
    'demo-case-06':('0.0', '0.0', '0', '0', 'ARF'),
}

PARTICIPANT_IDS = ['P%02d' % i for i in range(1, 25)]  # P01..P24

# Users to keep in participant_info.txt alongside the freshly-reset P01..P24.
# Data_Selection is intentionally dropped (Luca confirmed it doesn't work
# and isn't needed).
KEEP_USERS = [
    'Interface_demo_with_highlights',
    'Interface_demo_without_highlights',
    'Pilot_1',
    'Pilot_2',
]


# --------------------------------------------------------------------------
# Path resolution
# --------------------------------------------------------------------------

def resolve_paths():
    # script is at EvaluationStudy/scripts/generate_participants.py
    script_dir = os.path.dirname(os.path.abspath(__file__))
    eval_dir = os.path.dirname(script_dir)
    models_dir = os.path.normpath(os.path.join(eval_dir, '..', '..', 'models'))
    pinfo_dir = os.path.join(models_dir, 'evaluation_study', 'participant_info')
    if not os.path.isdir(pinfo_dir):
        sys.stderr.write('FATAL: participant_info dir not found at %s\n' % pinfo_dir)
        sys.exit(1)
    return pinfo_dir


# --------------------------------------------------------------------------
# Row builder
# --------------------------------------------------------------------------

HEADER = '#visitID,cuttime1,cuttime2,t1,t2,condition,show_highlights,highlights_only,incorrect_highlights'


def format_row(case_id, condition_key):
    meta = CASE_METADATA[case_id]
    sh, ho, ih = CONDITIONS[condition_key]
    return ','.join((case_id,) + meta + (sh, ho, ih))


def draw_participant(pid, rng):
    """Return the 7-row content for a single participant, plus a per-case
    assignment summary used for the audit log."""
    cases = list(TEST_CASES)
    rng.shuffle(cases)
    conditions = list(CONDITION_PATTERN)
    rng.shuffle(conditions)

    rows = [HEADER]
    # Intro case is always first and always no-highlights.
    rows.append(format_row(INTRO_CASE, 'none'))
    summary = [(INTRO_CASE, 'none (intro)')]
    for case_id, cond in zip(cases, conditions):
        rows.append(format_row(case_id, cond))
        summary.append((case_id, cond))
    return rows, summary


def write_participant_info(pinfo_dir, today):
    """Rewrite participant_info.txt with KEEP_USERS + 24 fresh P## entries."""
    path = os.path.join(pinfo_dir, 'participant_info.txt')
    lines = ['#id,last_accessed,cases_completed,name']
    for u in KEEP_USERS:
        # Preserve their existing rows literally if present; otherwise emit
        # a neutral placeholder. The simplified study only relies on the
        # P## rows; KEEP_USERS rows are just so the home page still lists
        # them.
        existing = _find_existing_row(path, u)
        if existing:
            lines.append(existing)
        else:
            lines.append('%s,%s,0,' % (u, today))
    for pid in PARTICIPANT_IDS:
        lines.append('%s,%s,0,' % (pid, today))
    _write_lines(path, lines)


def _find_existing_row(path, user_id):
    if not os.path.isfile(path):
        return None
    with open(path, 'r') as fh:
        for line in fh:
            line = line.rstrip('\n').rstrip('\r')
            if line.split(',')[0:1] == [user_id]:
                return line
    return None


def _write_lines(path, lines):
    with open(path, 'w') as fh:
        fh.write('\n'.join(lines) + '\n')


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main():
    pinfo_dir = resolve_paths()
    rng = random.Random(SEED)

    today = datetime.date.today().isoformat()

    print('Writing fresh P01..P24 ordering files to %s' % pinfo_dir)
    print('Seed: %d   Intro: %s   Tests: %s' % (SEED, INTRO_CASE, ','.join(TEST_CASES)))
    print('---')

    all_summaries = []
    for pid in PARTICIPANT_IDS:
        rows, summary = draw_participant(pid, rng)
        out_path = os.path.join(pinfo_dir, '%s.txt' % pid)
        _write_lines(out_path, rows)
        all_summaries.append((pid, summary))
        print('%s: %s' % (pid, ' '.join('%s=%s' % (cid, c.split()[0]) for cid, c in summary[1:])))

    print('---')
    print('Updating participant_info.txt with %d entries (24 participants + %d demo users)'
          % (len(PARTICIPANT_IDS) + len(KEEP_USERS), len(KEEP_USERS)))
    write_participant_info(pinfo_dir, today)

    # Sanity check: every participant should have exactly 2 of each condition.
    print('---')
    print('Sanity check (each row should be 2/2/2):')
    for pid, summary in all_summaries:
        counts = {'none': 0, 'correct': 0, 'mixed': 0}
        for _cid, cond in summary[1:]:  # skip intro
            counts[cond] += 1
        flag = '  OK' if counts == {'none': 2, 'correct': 2, 'mixed': 2} else '  *** FAIL ***'
        print('  %s: none=%d correct=%d mixed=%d%s'
              % (pid, counts['none'], counts['correct'], counts['mixed'], flag))

    print('---')
    print('Done.')


if __name__ == '__main__':
    main()
