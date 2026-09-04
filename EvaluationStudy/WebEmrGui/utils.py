# -*- coding: utf-8 -*-
# Py3 requires explicit relative imports for intra-package modules.
# The four model classes below come from WebEmrGui/models.py.
from .models import marstorootcodes
from .models import rootgroupmember
from .models import displayparams
from .models import a_groupmember
import os
import time


def load_med_maps(med_map_filename):
    """
    Loads the per-case med-display-id_to_name file. The file is
        id<TAB>catalog_display_name<TAB>ordered_as_name
    Returns two dicts (legacy callers use these):
        med_cd_id[catalog_name] = id        (LAST-write wins — only one id)
        med_or_id[ordered_name] = id        (LAST-write wins — only one id)
    Both maps are one-to-one; for the one-to-many cases (e.g. several rows
    all named "Sodium Chloride 0.9%") see load_med_full_map below.
    """
    med_cd_id = {}
    med_or_id = {}
    with open(med_map_filename, 'r') as f:
        for line in f:
            s_line = line.rstrip().split('\t')
            if s_line:
                med_cd_id[s_line[1]] = s_line[0]
                med_or_id[s_line[2]] = s_line[0]
    return [med_cd_id, med_or_id]


def load_med_full_map(med_map_filename):
    """
    Phase 6 helper for highlight aliasing.

    Returns three structures:
      cat_to_ids:    {catalog_display_name: [id, id, ...]}   one-to-many
      ord_to_ids:    {ordered_as_name:      [id, id, ...]}   one-to-many
      id_to_ordered: {id: ordered_as_name}                   id -> friendly label

    Used by views.py to (a) expand items_relevant_judges that name a
    medication into all matching med_info row ids so every administration
    of that drug is highlighted, and (b) resolve a clicked med-row id back
    to a friendly display label for the rationale screens.
    """
    cat_to_ids = {}
    ord_to_ids = {}
    id_to_ordered = {}
    if not os.path.isfile(med_map_filename):
        return cat_to_ids, ord_to_ids, id_to_ordered
    with open(med_map_filename, 'r') as f:
        for line in f:
            parts = line.rstrip().split('\t')
            if len(parts) < 3:
                continue
            mid, cat, ordered = parts[0], parts[1], parts[2]
            cat_to_ids.setdefault(cat, []).append(mid)
            ord_to_ids.setdefault(ordered, []).append(mid)
            id_to_ordered[mid] = ordered
    return cat_to_ids, ord_to_ids, id_to_ordered


def print_to_manual_input_file(local_dir, patient_id, timestamp, selections, rating, reason):
    print('\t___printing to input file ' + str(patient_id))
    out_file = open(local_dir + "manual_input/pat_" + str(patient_id) + '.txt', 'w+')
    out_file.write('>>>' + str(float(timestamp) / 1000) + '\n')
    out_file.write(selections + '\n')
    out_file.write('### difficulty rating ###\n')
    out_file.write(rating + '\n')
    out_file.write('--- has audio recording ---\n')
    out_file.write(reason + '\n')
    out_file.close()
    return





def find_first_case(location, user_id, num_cases_override=None):
    """
    Find the next case for this participant.

    `num_cases_override` (added 2026-05) lets the caller pass an
    authoritative cases-completed count derived from the per-participant
    JSON results file. The old behaviour (read the counter from
    participant_info.txt) double-counted page refreshes and direct-URL
    visits because determine_next_url used to bump the counter on every
    detail() page load, so a participant who refreshed their browser a
    few times could hit the 7-case cap after only 3 or 4 real cases and
    get booted to the end-of-study screen prematurely. The JSON results
    file's `cases` list is idempotent (ensure_case only appends new
    case_ids) so its length is the safe authoritative count.

    When `num_cases_override` is None we fall back to the legacy .txt
    counter — kept so non-study users (interface_demo etc.) without a
    results file still work.
    """
    print('Function find_first_case in utils.py called to determine next case.')
    next_patient_id = 0

    if num_cases_override is not None:
        num_cases = int(num_cases_override)
    else:
        in_file = open(location + 'participant_info.txt', 'r')
        lines = in_file.readlines()
        in_file.close()
        num_cases = 0
        for line in lines:
            line_split = line.split(',')
            if line_split[0] == user_id:
                num_cases = int(line_split[2])

    # 2026 simplified design: 1 introductory case + 6 test cases = 7 total per participant.
    if num_cases >= 7:
        print('All 7 cases completed.')
        return 'end'

    in_file = open(location + user_id + '.txt', 'r')
    lines = in_file.readlines()
    in_file.close()
    for line in lines:
        if line[0] == '#':
            continue
        if num_cases == 0:
            next_patient_id = line.split(',')[0]
            break
        num_cases -= 1
    # Demo users (Interface_demo_*) have a single-case ordering file
    # rather than the 7-case study sequence. Once they've completed
    # their single case, the loop above walks past every row without
    # ever seeing num_cases == 0, leaving next_patient_id at its
    # initial 0. Returning 0 causes the caller to redirect to
    # /WebEmrGui/0/<user_id>/ which then crashes in
    # determine_next_url (patient_id=0 is not in the file). Treat
    # that as the demo-equivalent of 'end' — the eye_test view
    # renders end_done.html and study users past their cap take
    # the same path.
    if not next_patient_id:
        print('No further case found for user_id=' + str(user_id) +
              ' (num_cases_used=' + str(num_cases_override) +
              ', file length=' + str(len(lines)) + '). Returning "end".')
        return 'end'
    return next_patient_id


def update_participant_info(user_id, location):
    print('[Updating participant info in participant_info.txt file...]')
    import datetime
    in_file = open(location + 'participant_info.txt', 'r+')
    out_lines = []
    for line in in_file:
        line_split = line.split(',')
        if line_split[0] == user_id:
            now = datetime.datetime.now()
            out_lines.append(user_id+','+now.strftime("%Y-%m-%d")+','+str(int(line_split[2])+1)+','+line_split[3])
            print('[participant_info.txt file updated.]')
        else:
            out_lines.append(line)
    in_file.close()
    with open(location + 'participant_info.txt', 'w') as out_file:
        out_file.write(''.join(out_lines))

    return
    #missing something here


def read_current_case_meta(location, user_id, curr_patient_id):
    """
    Look up the current case in the participant's ordering file and return
    (order_index, is_intro, condition_dict).

    order_index is 0-based across NON-comment rows; the first row is the
    introductory case (order_index = 0, is_intro = True).
    """
    in_file = open(location + user_id + '.txt', 'r')
    lines = in_file.readlines()
    in_file.close()
    data_idx = -1
    for line in lines:
        if line[0] == '#':
            continue
        data_idx += 1
        split = line.rstrip().split(',')
        if split and split[0] == str(curr_patient_id):
            store = split[6:9]
            while len(store) < 3:
                store.append('0')
            return (
                data_idx,
                data_idx == 0,
                {
                    'show_highlights':      int(store[0]),
                    'highlights_only':      int(store[1]),
                    'incorrect_highlights': int(store[2]),
                },
            )
    return (-1, False, {'show_highlights': 0, 'highlights_only': 0, 'incorrect_highlights': 0})


def _read_highlight_file_entry(path, key):
    """Read a 'key: a,b,c' style file and return the items list for `key`,
    or [] if the key is missing or the line is empty after the colon."""
    if not os.path.isfile(path):
        return []
    with open(path, 'r') as fh:
        for line in fh:
            s_line = line.rstrip().split(': ')
            if s_line and s_line[0] == str(key):
                if len(s_line) > 1 and s_line[1]:
                    return [x for x in s_line[1].split(',') if x.strip()]
                return []
    return []


def load_case_highlight_definitions(local_dir, patient_id):
    """
    Return the case's configured highlight definitions as a 3-tuple:
        (items_relevant_judges,
         items_relevant_but_omitted_when_incorrect,
         items_non_relevant_but_added_when_incorrect)

    These are the *static* definitions from the three text files in
    models/evaluation_study/, NOT the per-condition displayed set.
    """
    base = local_dir + 'evaluation_study/'
    relevant   = _read_highlight_file_entry(base + 'items_relevant_judges.txt',                       patient_id)
    omitted    = _read_highlight_file_entry(base + 'relevant_data_items_not_to_be_highlighted.txt',   patient_id)
    falsified  = _read_highlight_file_entry(base + 'non_relevant_data_items_to_be_highlighted.txt',   patient_id)
    return relevant, omitted, falsified


def determine_next_url(location, user_id, curr_patient_id):
    """
    Look up the current case in the participant's ordering file and return:
        [next_patient_id, next_view, show_highlights, highlights_only, incorrect_highlights]

    Returns ['end', '', ...] when curr_patient_id is the last case.
    Returns ['error', 'here'] if curr_patient_id is not found.

    Side-effect-free. The legacy version of this function used to
    call update_participant_info(...) on every invocation as a way of
    advancing the cases_completed counter — but determine_next_url
    runs on every detail() page load (including refreshes and
    back/forward navigation), so that side-effect double-counted page
    revisits and could push the counter past 7 after only 3-4 actual
    cases, prematurely triggering the end-of-study screen. The
    cases-completed signal is now derived from the per-participant
    JSON results store via results_io (see find_first_case for the
    new authoritative count) so this function is read-only.
    """
    in_file = open(location + user_id + '.txt', 'r')
    lines = in_file.readlines()
    in_file.close()
    for i in range(len(lines)):
        if lines[i][0] == '#':
            continue
        split_line = lines[i].rstrip().split(',')
        if len(split_line) and split_line[0] == curr_patient_id:
            store = split_line[6:9]
            # Pad to 3 elements in case a participant file is still in the
            # legacy 8-column format (no incorrect_highlights). Defaults the
            # missing flag to '0' (= no incorrect highlights).
            while len(store) < 3:
                store.append('0')
            if i >= len(lines) - 1:  # last case in file
                # NB: propagate store[2] (incorrect_highlights) here — the
                # previous code hard-coded '0' in this branch, which meant
                # the last case in any participant's ordering file always
                # rendered as if incorrect_highlights=0, silently skipping
                # the planted-commission / relevant-not-highlighted logic.
                # For P01 that was case <example-id-B> (HCT/PHOS never planted,
                # vancomycin never omitted). Fix: use the same store[2]
                # the non-last branch below already returns.
                return ['end', '', store[0], store[1], store[2]]
            next_split = lines[i + 1].split(',')
            return [next_split[0], 1, store[0], store[1], store[2]]
    print('Matching Case ID was not found in ' + user_id + '.txt')
    return ['error', 'here']


def load_marstoroot():
    mtr = {}  # mars to root
    rtm = {}  # root to mars
    results = marstorootcodes.objects.all()
    for result in results:
        mtr[result.marscode] = result.rootcode
        if result.rootcode in rtm.keys():
            rtm[result.rootcode].append(result.marscode)
        else:
            rtm[result.rootcode] = [result.marscode]
    return [mtr, rtm]


def load_rootgroupmember():
    groups = {}  # [groupname] = [root1, root2, ...]
    lab_group_order = [0] * 19
    rtn = {}  # root to name
    rtt = {}  # root to table
    results = rootgroupmember.objects.all()
    for result in results:
        if result.groupname in groups.keys():
            groups[result.groupname].append(result.root)
        else:
            groups[result.groupname] = [result.root]
            if result.grouprank < 20:
                lab_group_order[result.grouprank-1] = result.groupname
        rtn[result.root] = result.labname
        rtt[result.root] = result.datatable
    return [groups, lab_group_order, rtn, rtt]


def find_discrete_roots():
    discrete_roots = []
    results = rootgroupmember.objects.all()
    for result in results:
        if result.datatype == 'd':
            discrete_roots.append(result.root)
    return discrete_roots


def load_displayparams():
    rtdt = {}   # root to display type
    default_ranges = {}  # [root] -> [display min, normal range min, normal range max, display max]
    default_units = {}  # [root] -> units
    results = displayparams.objects.all()
    for result in results:
        rtdt[result.root] = result.displaytype
        default_ranges[result.root] = [None, None, None, None]
        if result.mindd is not None:
            default_ranges[result.root][0] = result.mindd
        if result.maxdd is not None:
            default_ranges[result.root][3] = result.maxdd
        default_units[result.root] = result.unitsdefault
    return [rtdt, default_ranges, default_units]


def load_a_groupmember():
    clinical_event_ranges = {'M': {}, 'F': {}}  # normal ranges for learningemr.clinicalEvent items
    results = a_groupmember.objects.all()
    for result in results:
        clinical_event_ranges['M'][result.name] = [result.lowernormal, result.uppernormal]
        clinical_event_ranges['F'][result.name] = [result.femalelowernormal, result.femaleuppernormal]
    return clinical_event_ranges


def load_access_code(local_dir, user_id):
    """Return the per-participant numeric access code from
    `models/evaluation_study/access_codes.txt`, or None if not configured.

    File format is one line per participant: `P05: 4729`. Read on every
    call so the coordinator can edit / rotate codes without restarting
    the server. None return means "no code-gating for this participant"
    (used for the Interface_demo_* accounts, which are unauthenticated
    by design).
    """
    path = os.path.join(local_dir, 'evaluation_study', 'access_codes.txt')
    if not os.path.isfile(path):
        return None
    try:
        with open(path, 'r') as fh:
            for line in fh:
                s = line.rstrip().split(':')
                if len(s) >= 2 and s[0].strip() == user_id:
                    return s[1].strip()
    except Exception:
        pass
    return None


def load_all_access_codes(local_dir):
    """Return {user_id: code} for the admin report. Same source file as
    load_access_code()."""
    out = {}
    path = os.path.join(local_dir, 'evaluation_study', 'access_codes.txt')
    if not os.path.isfile(path):
        return out
    try:
        with open(path, 'r') as fh:
            for line in fh:
                s = line.rstrip().split(':')
                if len(s) >= 2 and s[0].strip():
                    out[s[0].strip()] = s[1].strip()
    except Exception:
        pass
    return out


def reset_directories(local_dir, user_id=False):
    """
    No-op since the Phase 6 simplified study.

    The original implementation created a timestamped `run-<epoch>/` folder
    on every home-page load and shuffled the contents of `interaction_stream/`,
    `pixelmaps/`, `eye_stream/`, `manual_input/`, `errors/`, `notemaps/`,
    and `audio_recordings/` into it. Those folders existed to collect the
    eye-tracking and pixelmap telemetry used by the earlier version of the
    study; the Phase 6 design (24 participants, 6 cases each, JSON results
    file per participant) replaced all of that with `results_io.py`, so
    the folder-shuffle is now pure noise — it created empty directories
    on every visit and accumulated `run-*` archives indefinitely.

    Kept as a function (rather than removed at every call site) so the
    `views.index` signature doesn't have to change, and so existing
    `run-*` archives on disk are left untouched. Returns False to match
    the legacy "no pat_calibration.txt found" return value, which is what
    `views.index` already handles.
    """
    return False
