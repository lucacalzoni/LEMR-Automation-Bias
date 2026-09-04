# -*- coding: utf-8 -*-
"""
Per-participant results store for the 2026 LEMR simplified study (Phase 6).

One JSON file per participant lives at:
    {local_dir}/results/{user_id}.json

Schema (current as of Phase 6-A):

{
  "user_id":      "P05",                       # str, matches participant_info.txt
  "started_at":   "2026-05-19T15:00:00",       # ISO 8601, set on first write
  "completed_at": null,                        # set when end_of_study fires
  "trust_pre":    null,                        # int 1-5 once recorded
  "trust_post":   null,
  "cases": [
    {
      "case_id":        "demo-case-01",            # str
      "order_index":    0,                     # 0-based position in participant file
      "is_intro":       true,                  # only the first row of the file
      "condition": {                           # mirrors columns 6,7,8 of the
                                               # participant's ordering file
        "show_highlights":      0,
        "highlights_only":      0,
        "incorrect_highlights": 0
      },
      "items_judges_relevant":          [],    # ground-truth relevant items
      "items_displayed_highlighted":    [],    # actually shown to participant
      "items_omitted_from_highlights":  [],    # relevant items NOT highlighted
      "items_falsely_highlighted":      [],    # non-relevant items highlighted
      "phases": {                              # cumulative ms per phase
        "familiarize_ms": 0,
        "present_ms":     0,
        "select_ms":      0,
        "commission_ms":  0,
        "omission_ms":    0
      },
      "selected_items":         [],            # what the participant chose
      "commission_rationales":  [],            # [{"item": "...", "rationale": "..."}, ...]
      "omission_rationales":    []             # [{"item": "...", "reason_code": 1-4,
                                               #   "free_text": null|"..."}, ...]
    },
    ...
  ]
}

Concurrency: Django dev server is single-threaded so naive read-modify-write
is fine. For production deploy (Phase 7) we should add a file lock; for now
we keep it simple.

Py2.7 compatible.
"""

from __future__ import print_function

import datetime
import json
import os
import sys
import threading


PHASE_KEYS = ('familiarize', 'present', 'select', 'commission', 'omission')


# --------------------------------------------------------------------------
# Per-participant write serialization
#
# The Django dev server runs threaded by default (one thread per request),
# so two requests for the same participant can race their load-modify-save
# sequence on the per-participant JSON results file. Symptom in the field:
# only the first case ends up persisted, because save_phase_time / save_*
# requests fire concurrently with the next case's detail-view ensure_case
# call, and the loser of the race overwrites the winner's changes.
#
# A module-level dict of per-participant threading.Lock() instances forces
# all writes for one participant to execute strictly in order. The lookup
# dict itself is guarded by a single global Lock so two requests for a
# brand-new participant id don't race to create the per-user lock.
# --------------------------------------------------------------------------

_user_locks_guard = threading.Lock()
_user_locks = {}


def _lock_for(user_id):
    """Return the threading.Lock() owning writes for `user_id`, creating
    it on first use. Cheap; the per-user lock lives for the life of the
    process, which is fine for a 24-participant single-server study."""
    key = str(user_id)
    with _user_locks_guard:
        lock = _user_locks.get(key)
        if lock is None:
            lock = threading.Lock()
            _user_locks[key] = lock
        return lock


# --------------------------------------------------------------------------
# Path helpers
# --------------------------------------------------------------------------

def _results_dir(local_dir):
    """Return absolute path to the results folder; create it if missing."""
    path = os.path.join(local_dir, 'results')
    if not os.path.isdir(path):
        os.makedirs(path)
    return path


def _results_path(local_dir, user_id):
    return os.path.join(_results_dir(local_dir), str(user_id) + '.json')


def _now_iso():
    return datetime.datetime.now().replace(microsecond=0).isoformat()


# --------------------------------------------------------------------------
# Empty-state constructors
# --------------------------------------------------------------------------

def _new_case_entry(case_id, order_index, is_intro, condition):
    return {
        'case_id':        str(case_id),
        'order_index':    int(order_index),
        'is_intro':       bool(is_intro),
        'condition':      dict(condition),
        'items_judges_relevant':         [],
        'items_displayed_highlighted':   [],
        'items_omitted_from_highlights': [],
        'items_falsely_highlighted':     [],
        'phases': {(k + '_ms'): 0 for k in PHASE_KEYS},
        'selected_items':         [],
        'commission_rationales':  [],
        'omission_rationales':    [],
    }


def _new_participant(user_id):
    return {
        'user_id':      str(user_id),
        'started_at':   _now_iso(),
        'completed_at': None,
        'trust_pre':    None,
        'trust_post':   None,
        'cases':        [],
    }


# --------------------------------------------------------------------------
# Load / save
# --------------------------------------------------------------------------

def load(local_dir, user_id):
    """Return participant dict, creating an empty one if no file exists yet."""
    path = _results_path(local_dir, user_id)
    if not os.path.isfile(path):
        return _new_participant(user_id)
    with open(path, 'r') as fh:
        try:
            return json.load(fh)
        except ValueError as e:
            sys.stderr.write('WARN: corrupt results file %s (%s); rebuilding.\n'
                             % (path, e))
            return _new_participant(user_id)


def save(local_dir, user_id, data):
    """Write the full participant dict atomically (write+rename)."""
    path = _results_path(local_dir, user_id)
    tmp = path + '.tmp'
    with open(tmp, 'w') as fh:
        json.dump(data, fh, indent=2, sort_keys=False)
        fh.write('\n')
    if os.path.exists(path):
        os.remove(path)
    os.rename(tmp, path)


# --------------------------------------------------------------------------
# High-level recorders
# --------------------------------------------------------------------------

def _find_or_create_case(participant, case_id, defaults):
    """Locate a case dict by case_id, or append a fresh one using `defaults`
    (an _new_case_entry result) at the end."""
    for case in participant['cases']:
        if case['case_id'] == str(case_id):
            return case
    participant['cases'].append(defaults)
    return defaults


def ensure_case(local_dir, user_id, case_id, order_index, is_intro, condition,
                items_judges_relevant=None,
                items_displayed_highlighted=None,
                items_omitted_from_highlights=None,
                items_falsely_highlighted=None):
    """
    Make sure the participant + case entry exist in the JSON, populated with
    the case's condition and the server-side ground-truth lists. Called once
    on each case page-load (detail view).
    """
    with _lock_for(user_id):
        data = load(local_dir, user_id)
        defaults = _new_case_entry(case_id, order_index, is_intro, condition)
        case = _find_or_create_case(data, case_id, defaults)
        # If the case had been created earlier by a record_* call (when the
        # detail view hadn't fired ensure_case yet), the placeholder will
        # have order_index=-1, is_intro=False, condition={}. Patch those in
        # now so the report has correct metadata.
        if case.get('order_index', -1) < 0 and order_index >= 0:
            case['order_index'] = int(order_index)
            case['is_intro']    = bool(is_intro)
            case['condition']   = dict(condition)
        # Overwrite the ground-truth lists every time so that if Luca edits the
        # source files mid-study they propagate to subsequent visits.
        if items_judges_relevant is not None:
            case['items_judges_relevant'] = list(items_judges_relevant)
        if items_displayed_highlighted is not None:
            case['items_displayed_highlighted'] = list(items_displayed_highlighted)
        if items_omitted_from_highlights is not None:
            case['items_omitted_from_highlights'] = list(items_omitted_from_highlights)
        if items_falsely_highlighted is not None:
            case['items_falsely_highlighted'] = list(items_falsely_highlighted)
        save(local_dir, user_id, data)


def record_phase_time(local_dir, user_id, case_id, phase, elapsed_ms):
    """Add `elapsed_ms` to the participant's case_id.phases[phase + '_ms']."""
    if phase not in PHASE_KEYS:
        sys.stderr.write('WARN: unknown phase %r ignored\n' % phase)
        return
    with _lock_for(user_id):
        data = load(local_dir, user_id)
        case = _find_or_create_case(data, case_id,
                                    _new_case_entry(case_id, -1, False, {}))
        key = phase + '_ms'
        case['phases'][key] = case['phases'].get(key, 0) + int(elapsed_ms)
        save(local_dir, user_id, data)


def record_selected_items(local_dir, user_id, case_id, items):
    with _lock_for(user_id):
        data = load(local_dir, user_id)
        case = _find_or_create_case(data, case_id,
                                    _new_case_entry(case_id, -1, False, {}))
        case['selected_items'] = list(items)
        save(local_dir, user_id, data)


def record_commission_rationale(local_dir, user_id, case_id, item, rationale):
    with _lock_for(user_id):
        data = load(local_dir, user_id)
        case = _find_or_create_case(data, case_id,
                                    _new_case_entry(case_id, -1, False, {}))
        # Replace existing entry for this item if any (so a participant can
        # change their answer if they go back).
        case['commission_rationales'] = [
            r for r in case['commission_rationales'] if r.get('item') != item
        ]
        case['commission_rationales'].append({
            'item':      item,
            'rationale': rationale,
        })
        save(local_dir, user_id, data)


def record_omission_rationale(local_dir, user_id, case_id, item, reason_code,
                              free_text):
    with _lock_for(user_id):
        data = load(local_dir, user_id)
        case = _find_or_create_case(data, case_id,
                                    _new_case_entry(case_id, -1, False, {}))
        case['omission_rationales'] = [
            r for r in case['omission_rationales'] if r.get('item') != item
        ]
        case['omission_rationales'].append({
            'item':        item,
            'reason_code': int(reason_code),
            'free_text':   free_text,
        })
        save(local_dir, user_id, data)


def record_trust(local_dir, user_id, when, value, question_id=None,
                 category=None):
    """Persist a trust-instrument response.

    Modes:
      * Legacy single-Likert (question_id is None):
          - data['trust_' + when] is set to the integer value.
            Kept for backwards compatibility with old participant JSONs.

      * McKnight multi-item (question_id is provided):
          - data['trust_responses'][when] is a list of
            {question_id, category, value} dicts. Duplicate question_ids
            are deduplicated (the latest answer wins) so a participant
            who scrolls back and changes a response doesn't accumulate
            both answers.

    when = 'pre' or 'post'. value is the integer Likert (1-5).
    """
    if when not in ('pre', 'post'):
        return
    with _lock_for(user_id):
        data = load(local_dir, user_id)

        if question_id is None:
            # Legacy single-Likert path.
            data['trust_' + when] = int(value)
        else:
            responses = data.setdefault('trust_responses', {}).setdefault(when, [])
            # Drop any previous answer for the same question so the latest
            # wins (participants can revise within the same session).
            data['trust_responses'][when] = [
                r for r in responses if r.get('question_id') != question_id
            ]
            data['trust_responses'][when].append({
                'question_id': str(question_id),
                'category':    str(category) if category is not None else None,
                'value':       int(value),
            })

        if when == 'pre' and not data.get('started_at'):
            data['started_at'] = _now_iso()
        save(local_dir, user_id, data)


def record_demographic(local_dir, user_id, question_id, value):
    """Persist a single demographic answer under data['demographics'][qid].

    value is whatever the caller passed (int for age / icu_years,
    string for gender — including the "self:<text>" sentinel for the
    self-describe option). The shape is intentionally permissive
    because the validation lives in views._valid_demographic_value;
    this layer just writes whatever it receives.
    """
    with _lock_for(user_id):
        data = load(local_dir, user_id)
        demo = data.setdefault('demographics', {})
        demo[str(question_id)] = value
        save(local_dir, user_id, data)


def record_intro_seen(local_dir, user_id):
    """Persist that the participant has read the study-introduction page.
    A boolean sentinel under data['intro_seen']; truthy means we won't
    re-show the intro on subsequent /eye_test/ visits."""
    with _lock_for(user_id):
        data = load(local_dir, user_id)
        data['intro_seen'] = True
        save(local_dir, user_id, data)


def mark_complete(local_dir, user_id):
    with _lock_for(user_id):
        data = load(local_dir, user_id)
        data['completed_at'] = _now_iso()
        save(local_dir, user_id, data)


# --------------------------------------------------------------------------
# Read helpers used by the admin report
# --------------------------------------------------------------------------

def list_participants(local_dir):
    """Return participant ids that have a results file, sorted lexicographically."""
    rdir = _results_dir(local_dir)
    ids = []
    for fname in os.listdir(rdir):
        if fname.endswith('.json') and not fname.endswith('.tmp'):
            ids.append(fname[:-5])
    return sorted(ids)


def load_all(local_dir):
    """Return [(user_id, participant_dict), ...] for the report view."""
    return [(uid, load(local_dir, uid)) for uid in list_participants(local_dir)]
