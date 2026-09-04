# -*- coding: utf-8 -*-
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.template import RequestContext, loader
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_exempt
from django.conf import settings
from django import forms
# Python 3: implicit relative imports were removed. The package-relative
# form below works under both Py2 (legacy Django 1.11 / Bitnami stack on
# Windows) and Py3 (any modern install).
from .loaddata import *
from .utils import load_med_maps, load_med_full_map, load_access_code, load_all_access_codes
from . import results_io
from . import trust_instrument
import operator
import time
import random
import pickle
import os.path
import os
import json


# --------------------------------------------------------------------------
# Polysemous-catalog alias-pattern whitelist.
#
# A few catalogs in the study data cover multiple distinct drugs — most
# notably "Sodium Chloride 0.9%", which in some cases is the carrier fluid
# for antibiotics (Unasyn, Zosyn, cefepime, ...). If catalog-based
# expansion blindly added every alias, an antibiotic infusion would light
# up in the highlight panel whenever the judges wrote "Sodium Chloride
# 0.9%". Conversely, if we skip catalog expansion entirely for polysemous
# catalogs, the actual saline rows (which ARE what the judges mean) never
# appear at all.
#
# The compromise: for each polysemous catalog, list the ordered_as
# prefixes / substrings that identify the alias(es) that are clinically
# the same substance. Only aliases whose ordered_as matches one of these
# patterns are added when the catalog is polysemous. Add an entry
# whenever a new polysemous catalog is spotted in the data — leave the
# non-matching aliases (antibiotics diluted in the carrier) to be
# addressed by their own catalog name if the judges list them.
CATALOG_ORD_PATTERNS = {
    'Sodium Chloride 0.9%': ['NS', 'Sodium Chloride', 'Saline', 'Normal Saline'],
    # "Base solution" is the ICU term for the premix carrier bag hanging on
    # a continuous drip. In some cases the catalog aggregates several
    # premix products (Propofol Premix, Fentanyl Premix, Midazolam Premix,
    # Milrinone Premix), so the polysemous guard would otherwise drop all
    # of them from the highlight panel. Every legitimate Base-solution
    # alias has "Premix" in its ordered_as label, so that's a safe
    # discriminator: it lights up the true premix bags without touching
    # anything else that might one day slip under the same catalog.
    'Base solution': ['Premix'],
}


def _trust_answers_map(participant, when):
    """Return {qid: value} for the participant's saved responses to the
    `when` ('pre'|'post') battery. Empty dict if nothing saved yet."""
    out = {}
    responses = (participant.get('trust_responses') or {}).get(when) or []
    for r in responses:
        qid = r.get('question_id')
        v = r.get('value')
        if qid and v is not None:
            out[qid] = int(v)
    return out


def _trust_battery_complete(participant, when):
    """True iff every question in the `when` battery has been answered."""
    answers = _trust_answers_map(participant, when)
    for q in trust_instrument.questions_for(when):
        if q['id'] not in answers:
            return False
    return True


# --------------------------------------------------------------------------
# Demographics battery (administered once, before the pre-trust battery).
#
# Three mandatory items, one screen each: participant's age, gender, and
# years of professional experience in ICUs. The schema is shipped to the
# template as a JSON list so the same template can drive any future
# extension; per-question persistence lives under
# data['demographics'][question_id] in the participant's JSON.
# --------------------------------------------------------------------------

DEMOGRAPHIC_QUESTIONS = [
    {
        'id':   'age',
        'kind': 'number',
        'text': 'What is your age (in years)?',
        'unit': 'years',
        'min':  18,
        'max':  100,
        'placeholder': 'e.g. 42',
    },
    {
        'id':   'gender',
        'kind': 'choice',
        'text': 'What is your gender?',
        'options': [
            {'value': 'female',         'label': 'Female'},
            {'value': 'male',           'label': 'Male'},
            {'value': 'non_binary',     'label': 'Non-binary'},
            {'value': 'self_describe',  'label': 'Self-describe:',
             'kind': 'self_describe', 'placeholder': 'please specify'},
            {'value': 'prefer_not',     'label': 'Prefer not to say'},
        ],
    },
    {
        'id':   'icu_years',
        'kind': 'number',
        'text': 'How many years of professional experience in ICUs do you have?',
        'unit': 'years',
        'min':  0,
        'max':  60,
        'placeholder': 'e.g. 12',
    },
    {
        'id':   'professional_level',
        'kind': 'choice',
        'text': 'What is your current professional level?',
        'options': [
            {'value': 'attending', 'label': 'Attending physician'},
            {'value': 'fellow',    'label': 'Fellow physician'},
            {'value': 'resident',  'label': 'Resident physician'},
        ],
    },
]


def _demographics_answers(participant):
    """Return {qid: value} for the participant's saved demographic answers."""
    return dict((k, v) for k, v in (participant.get('demographics') or {}).items()
                if v is not None and v != '')


def _demographics_complete(participant):
    """True iff every demographic question has an answer."""
    answers = _demographics_answers(participant)
    for q in DEMOGRAPHIC_QUESTIONS:
        if q['id'] not in answers:
            return False
    return True


def _valid_demographic_value(qid, value):
    """Server-side validation matching the JS validator in
    demographics.html. Returns (ok, coerced_value_or_None, err_or_None)."""
    q = next((q for q in DEMOGRAPHIC_QUESTIONS if q['id'] == qid), None)
    if q is None:
        return False, None, 'unknown demographic question'
    if q['kind'] == 'number':
        try:
            n = int(value)
        except (TypeError, ValueError):
            return False, None, 'must be a whole number'
        if 'min' in q and n < q['min']: return False, None, 'below allowed minimum'
        if 'max' in q and n > q['max']: return False, None, 'above allowed maximum'
        return True, n, None
    if q['kind'] == 'choice':
        # Py3 removed `basestring`; use `str` which is the unicode-string
        # type in Py3 (and the byte-string type in Py2 — fine here because
        # the value comes off request.POST which is already a str in both).
        if not isinstance(value, str) or not value:
            return False, None, 'must be a non-empty string'
        valid_values = set(o['value'] for o in q['options'])
        if value.startswith('self:'):
            # self-describe path: the value carries the participant's
            # typed text after the prefix; require that text to be
            # non-empty after stripping whitespace.
            if not value[5:].strip():
                return False, None, 'self-describe text cannot be empty'
            return True, value, None
        if value not in valid_values:
            return False, None, 'value not in option list'
        return True, value, None
    return False, None, 'unknown question kind'
cwd = os.getcwd()
print('Current working directory is:')
print(cwd)


# Global variables
run_model_inference = False  # Set this variable to true when inference based lab promotions are desired
show_probabilities = False  # set show_probabilities to True when print out of probabilities is desired
use_logistic_regression = True  # is the boolean selector between whether logistic regression or lasso...
# regression is used. (Models must be retrained when value is changed)
one_less_day = False  # when true, the most recent 24 hours of patient data is removed from the display
if os.path.isdir("../../models/"):
    local_dir = os.getcwd() + "/../../models/"
use_patient_order = False  # When true the next and previous buttons use the patient_order ordering.


# Identifiers that are NOT real study participants. Their flows still render
# but their data is intentionally not persisted into models/results/.
_DEMO_USER_IDS = (
    'first_four', 'interface_demo', 'Data_Selection',
    'Interface_demo_with_highlights', 'Interface_demo_without_highlights',
)


def _study_user(user_id):
    """Return True iff `user_id` is a real study participant whose results
    we want to persist."""
    return user_id not in _DEMO_USER_IDS


def index(request, user_id=False):
    print(request.path_info)
    if user_id:
        last_interaction_dir = reset_directories(local_dir, user_id)
    else:
        last_interaction_dir = reset_directories(local_dir)

    print('________________________________________________________________________')
    print('LOADING USERS...')
    users = []
    usernames = []
    with open(local_dir + '/evaluation_study/participant_info/participant_info.txt', 'r') as in_file:
        for line in in_file:
            if line[0] == '#':
                continue
            else:
                split_line = line.split(',')
                users.append({'name': split_line[0], 'access': split_line[1], 'count': split_line[2]})
                usernames.append({split_line[0]})
    print('The following users were loaded:')
    listofusers = list(usernames)
    print(listofusers)
    print('________________________________________________________________________')

    print('________________________________________________________________________')
    print('LOADING HOME SCREEN TEMPLATE...')
    print('Rendering home screen template...')
    template = loader.get_template('WebEmrGui/home_screen.html')
#    context = RequestContext(request, {
#        'full': users
#    })
# changed code here to make it compatible with Django v1.11
    context = {
        'full': users
    }

    print('Home screen rendered.')
    print('________________________________________________________________________')
    return HttpResponse(template.render(context, request))




@ensure_csrf_cookie
def end_of_study(request, user_id):
    """
    End-of-study endpoint with two roles:
      * `?completed=1` on the URL -> trust_post battery is done; mark
        the participant complete and render the thank-you screen.
      * Otherwise -> if the post battery is still incomplete, render the
        multi-question trust_post.html (which saves each answer via
        /save_trust/ and then redirects back here with ?completed=1).
        If it's already complete (e.g. the participant refreshed),
        finalise the session immediately.

    Sandbox/demo users skip the post battery entirely.
    """
    print(request.path_info)
    is_study = _study_user(user_id)
    completed = request.GET.get('completed') == '1'

    if not is_study:
        if user_id != 'interface_demo':
            update_participant_info(user_id, local_dir + 'evaluation_study/participant_info/')
        template = loader.get_template('WebEmrGui/end_done.html')
        return HttpResponse(template.render({'user_id': user_id}, request))

    participant = results_io.load(local_dir, user_id)

    # If the post battery has been fully answered, OR the participant
    # arrived back here via the trust_post completion redirect, finalise.
    if completed or _trust_battery_complete(participant, 'post'):
        results_io.mark_complete(local_dir, user_id)
        update_participant_info(user_id, local_dir + 'evaluation_study/participant_info/')
        template = loader.get_template('WebEmrGui/end_done.html')
        return HttpResponse(template.render({'user_id': user_id}, request))

    # Render the multi-question post battery.
    template = loader.get_template('WebEmrGui/trust_post.html')
    return HttpResponse(template.render({
        'user_id':        user_id,
        'when':           'post',
        'questions_json': json.dumps(trust_instrument.POST_QUESTIONS),
        'answers_json':   json.dumps(_trust_answers_map(participant, 'post')),
        'anchors_json':   json.dumps(trust_instrument.LIKERT_ANCHORS),
    }, request))


def train(request):
    # features(local_dir, use_logistic_regression)
    return HttpResponse("The models have been retrained")


def loadcasedata(request):
    #create_feature_vectors()
    #create_output_discrete_data_counts()
    update_cases()
    return HttpResponse("<h2>Cases have been updated!</h2><br>"
                        "<a href=/WebEmrGui/><button>Home</button></a>")


@ensure_csrf_cookie
def eye_test(request, user_id):
    """
    Entry point for a participant session. Funnel order:
      1. Demographics battery (age, gender, ICU years) — once per
         participant; if any answer is missing the demographics form
         is shown and resume-by-first-unanswered behaviour applies.
      2. Pre-study multi-question trust battery — same resume rules.
      3. Direct redirect to the next unfinished case.
      4. Completion screen if no cases remain.
    Demo / sandbox users bypass demographics + trust and jump
    straight to case 1.
    """
    # Compute the authoritative cases-completed count from the per-
    # participant results JSON for study users. This is the count that
    # find_first_case uses to decide whether the participant is done
    # (>= 7) or which case to send them to next. Deriving from the JSON
    # makes the funnel robust to page refreshes, back/forward navigation,
    # and direct-URL visits — none of those mutate the JSON's case
    # list, whereas the old participant_info.txt counter was bumped on
    # every detail() page load and double-counted refreshes.
    num_cases_done = None
    code_ok_set_cookie = False  # if true, we'll attach a cookie to the response
    if _study_user(user_id):
        try:
            existing_for_count = results_io.load(local_dir, user_id)
            num_cases_done = len(existing_for_count.get('cases', []))
        except Exception:
            num_cases_done = None

        # Per-participant access code gate. Each P## (and the pilots) has
        # a 4-digit code listed in models/evaluation_study/access_codes.txt
        # and surfaced to the coordinator on the admin-report page.
        #
        # Authentication flow:
        #   1. First entry: home-screen modal POSTs the code via ?code=NNNN.
        #      eye_test validates it, and if it matches, we set a browser
        #      cookie `lemr_auth_<user_id>=<code>` so subsequent eye_test
        #      visits (e.g. after demographics completes and the
        #      demographics.html template navigates back to /eye_test/) can
        #      pass through without re-prompting.
        #   2. Subsequent entries: if the cookie value matches the current
        #      expected_code, we accept without requiring ?code= in the
        #      URL. If the code is rotated in access_codes.txt the stale
        #      cookie no longer matches and re-auth is required.
        #   3. Neither valid code nor valid cookie → 403.
        expected_code = load_access_code(local_dir, user_id)
        if expected_code:
            cookie_name = 'lemr_auth_' + user_id
            provided_code = (request.GET.get('code') or '').strip()
            cookie_code   = (request.COOKIES.get(cookie_name) or '').strip()
            if provided_code == expected_code:
                # First-entry path; set the cookie below before returning.
                code_ok_set_cookie = True
            elif cookie_code == expected_code:
                # Re-entry path (post-demographics, post-trust). Cookie still
                # valid — fall through without prompting again.
                pass
            else:
                # No valid code and no valid cookie: reject. The home-screen
                # XHR probe interprets the 403 to surface an inline error.
                return JsonResponse(
                    {'ok': False, 'error': 'invalid access code'},
                    status=403,
                )

    next_case_url = find_first_case(
        local_dir + 'evaluation_study/participant_info/',
        user_id,
        num_cases_override=num_cases_done,
    )

    # Helper to attach the auth cookie on the way out (used for every
    # exit path below — demographics, trust battery, redirect to case,
    # end-of-study). The cookie's value is the code itself, so rotating
    # the code in access_codes.txt invalidates the cookie automatically.
    def _attach_cookie(resp):
        if code_ok_set_cookie:
            # 12-hour session is plenty for a 1.5–2 hour study + breaks.
            # Django 1.11's set_cookie() doesn't accept `samesite`
            # (added in 2.1); that's OK for this study because the cookie
            # only protects an internal study tool, not anything CSRF-sensitive.
            resp.set_cookie('lemr_auth_' + user_id, expected_code, max_age=12*3600)
        return resp
    if next_case_url == 'end':
        template = loader.get_template('WebEmrGui/end_done.html')
        return _attach_cookie(HttpResponse(template.render({'user_id': user_id}, request)))

    first_case_path = '/WebEmrGui/' + str(next_case_url) + '/' + user_id + '/'

    if _study_user(user_id):
        existing = results_io.load(local_dir, user_id)

        # Step 0: study-introduction screen. Plain-text walkthrough of
        # what the participant is about to do — shown once, before
        # demographics. A boolean flag `intro_seen` in the participant
        # JSON keeps it from re-appearing on later eye_test re-entries
        # (e.g. after demographics or a mid-study refresh). The intro
        # template POSTs to /save_intro_seen/ on click and then
        # navigates to next_path (eye_test again), which falls through
        # to demographics.
        #
        # Mid-study participants who pre-date this change don't have
        # the `intro_seen` flag in their JSON. They shouldn't suddenly
        # be re-shown the intro — anyone who's already entered ANY
        # demographic answer or completed ANY case is considered to
        # have effectively seen the intro for funnel purposes.
        _has_prior_progress = bool(
            existing.get('demographics')
            or existing.get('cases')
            or existing.get('trust_responses')
        )
        if not existing.get('intro_seen') and not _has_prior_progress:
            template = loader.get_template('WebEmrGui/study_intro.html')
            return _attach_cookie(HttpResponse(template.render({
                'user_id':   user_id,
                'next_path': '/WebEmrGui/eye_test/' + user_id + '/',
            }, request)))

        # Step 1: demographics. The form posts each answer individually
        # to /save_demographic/, then navigates to next_path
        # (eye_test again) — so when demographics complete, the next
        # eye_test call falls through to the trust battery. The auth
        # cookie set on first entry keeps that re-entry from being
        # blocked by the access-code check above.
        if not _demographics_complete(existing):
            template = loader.get_template('WebEmrGui/demographics.html')
            return _attach_cookie(HttpResponse(template.render({
                'user_id':        user_id,
                'next_path':      '/WebEmrGui/eye_test/' + user_id + '/',
                'questions_json': json.dumps(DEMOGRAPHIC_QUESTIONS),
                'answers_json':   json.dumps(_demographics_answers(existing)),
            }, request)))

        # Step 2: pre-trust battery.
        if not _trust_battery_complete(existing, 'pre'):
            template = loader.get_template('WebEmrGui/trust_pre.html')
            return _attach_cookie(HttpResponse(template.render({
                'user_id':        user_id,
                'when':           'pre',
                'next_case_path': first_case_path,
                'questions_json': json.dumps(trust_instrument.PRE_QUESTIONS),
                'answers_json':   json.dumps(_trust_answers_map(existing, 'pre')),
                'anchors_json':   json.dumps(trust_instrument.LIKERT_ANCHORS),
            }, request)))

    return _attach_cookie(HttpResponseRedirect(first_case_path))


@csrf_exempt
def save_intro_seen(request):
    """Mark that the participant has read the study-introduction page.

    Posted by the Continue button in study_intro.html with only a
    user_id; we set data['intro_seen']=True so the eye_test funnel
    skips the intro on subsequent visits. Demo / sandbox users
    aren't gated on this either way, so they can safely POST and the
    server will simply no-op.
    """
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST required'}, status=405)
    user_id = request.POST.get('user_id')
    _p6_log('save_intro_seen', user_id=user_id)
    if not user_id:
        return JsonResponse({'ok': False, 'error': 'missing user_id'}, status=400)
    if _study_user(user_id):
        try:
            results_io.record_intro_seen(local_dir, user_id)
        except Exception as e:
            _p6_log('save_intro_seen.ERROR', err=str(e))
            return JsonResponse({'ok': False, 'error': str(e)}, status=500)
    return JsonResponse({'ok': True})


@csrf_exempt
def save_demographic(request):
    """
    Persist a single demographic answer.

    Required POST fields:
        user_id      — participant id
        question_id  — must be one of DEMOGRAPHIC_QUESTIONS' ids
        value        — string; coerced server-side per the question's kind
    """
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST required'}, status=405)
    user_id = request.POST.get('user_id')
    qid = request.POST.get('question_id')
    raw = request.POST.get('value')
    _p6_log('save_demographic', user_id=user_id, q=qid, raw=raw)
    if not (user_id and qid and raw is not None):
        return JsonResponse({'ok': False, 'error': 'missing field'}, status=400)
    ok, coerced, err = _valid_demographic_value(qid, raw)
    if not ok:
        return JsonResponse({'ok': False, 'error': err or 'invalid value'}, status=400)
    if _study_user(user_id):
        try:
            results_io.record_demographic(local_dir, user_id, qid, coerced)
        except Exception as e:
            _p6_log('save_demographic.ERROR', err=str(e))
            return JsonResponse({'ok': False, 'error': str(e)}, status=500)
    return JsonResponse({'ok': True})




def recording(request):
    message = '```recording functionalites have been removed```'
    return HttpResponse(message)



# NOTE: `save_input` (and its URL route) removed in the Phase-6 cleanup —
# its only persistence path was print_to_manual_input_file(), which wrote
# legacy `manual_input/pat_<id>.txt` files that the simplified study no
# longer reads. All per-case data now goes through the dedicated
# save_phase_time / save_selection / save_commission / save_omission /
# save_trust endpoints into the per-participant JSON results store.


# ----------------------------------------------------------------------
# Phase 6 — persistence endpoints. Each accepts a POST with the
# participant identifier + payload, appends to the participant's JSON
# results file via results_io, and returns {"ok": true}.
#
# Every endpoint prints a one-line trace to the runserver console so the
# coordinator can confirm in real time that each click actually reached
# the server and wrote to disk. If a save is silently dropping (CSRF
# rejection, stale .pyc, or anything else), the absence of the [save_X]
# line in the console will make it obvious which endpoint isn't firing.
# ----------------------------------------------------------------------

def _p6_log(tag, **fields):
    parts = ['[' + tag + ']']
    for k, v in fields.items():
        try:
            parts.append(k + '=' + repr(v))
        except Exception:
            parts.append(k + '=<unprintable>')
    print((' '.join(parts)))


@csrf_exempt
def save_phase_time(request):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST required'}, status=405)
    user_id = request.POST.get('user_id')
    patient_id = request.POST.get('patient_id')
    phase = request.POST.get('phase')
    elapsed_ms = request.POST.get('elapsed_ms')
    _p6_log('save_phase_time', user_id=user_id, patient_id=patient_id, phase=phase, elapsed_ms=elapsed_ms)
    if not (user_id and patient_id and phase and elapsed_ms is not None):
        return JsonResponse({'ok': False, 'error': 'missing field'}, status=400)
    if _study_user(user_id):
        try:
            results_io.record_phase_time(local_dir, user_id, patient_id, phase, int(elapsed_ms))
        except Exception as e:
            _p6_log('save_phase_time.ERROR', err=str(e))
            return JsonResponse({'ok': False, 'error': str(e)}, status=500)
    return JsonResponse({'ok': True})


@csrf_exempt
def save_selection(request):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST required'}, status=405)
    user_id = request.POST.get('user_id')
    patient_id = request.POST.get('patient_id')
    items_raw = request.POST.get('items', '')
    items = [x.strip() for x in items_raw.split(',') if x.strip()]
    _p6_log('save_selection', user_id=user_id, patient_id=patient_id, n_items=len(items), items=items)
    if not (user_id and patient_id):
        return JsonResponse({'ok': False, 'error': 'missing field'}, status=400)
    if _study_user(user_id):
        try:
            results_io.record_selected_items(local_dir, user_id, patient_id, items)
        except Exception as e:
            _p6_log('save_selection.ERROR', err=str(e))
            return JsonResponse({'ok': False, 'error': str(e)}, status=500)
    return JsonResponse({'ok': True})


@csrf_exempt
def save_commission(request):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST required'}, status=405)
    user_id = request.POST.get('user_id')
    patient_id = request.POST.get('patient_id')
    item = request.POST.get('item')
    rationale = request.POST.get('rationale', '')
    _p6_log('save_commission', user_id=user_id, patient_id=patient_id, item=item, rationale_len=len(rationale))
    if not (user_id and patient_id and item):
        return JsonResponse({'ok': False, 'error': 'missing field'}, status=400)
    if _study_user(user_id):
        try:
            results_io.record_commission_rationale(local_dir, user_id, patient_id, item, rationale)
        except Exception as e:
            _p6_log('save_commission.ERROR', err=str(e))
            return JsonResponse({'ok': False, 'error': str(e)}, status=500)
    return JsonResponse({'ok': True})


@csrf_exempt
def save_omission(request):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST required'}, status=405)
    user_id = request.POST.get('user_id')
    patient_id = request.POST.get('patient_id')
    item = request.POST.get('item')
    reason_code = request.POST.get('reason_code')
    free_text = request.POST.get('free_text') or None
    _p6_log('save_omission', user_id=user_id, patient_id=patient_id, item=item, reason_code=reason_code, free_text=free_text)
    if not (user_id and patient_id and item and reason_code is not None):
        return JsonResponse({'ok': False, 'error': 'missing field'}, status=400)
    if _study_user(user_id):
        try:
            results_io.record_omission_rationale(
                local_dir, user_id, patient_id, item, reason_code, free_text)
        except Exception as e:
            _p6_log('save_omission.ERROR', err=str(e))
            return JsonResponse({'ok': False, 'error': str(e)}, status=500)
    return JsonResponse({'ok': True})


@csrf_exempt
def save_trust(request):
    """
    Persist a single trust-instrument Likert response.

    Required POST fields:
        user_id      — participant id (e.g. "P05")
        when         — 'pre' or 'post'
        value        — integer 1..5
    Optional:
        question_id  — the question id from trust_instrument.PRE/POST_QUESTIONS
                       (e.g. "pre_07"). When omitted the legacy single-Likert
                       slot (data['trust_pre']/['trust_post']) is set instead;
                       this keeps the endpoint working for any clients still
                       sending only the legacy payload.
        category     — internal category code (validated against the
                       instrument; if it doesn't match, we resolve it from
                       question_id so callers can't smuggle in a wrong label).
    """
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST required'}, status=405)
    user_id = request.POST.get('user_id')
    when = request.POST.get('when')
    value = request.POST.get('value')
    question_id = request.POST.get('question_id') or None
    category = request.POST.get('category') or None
    _p6_log('save_trust', user_id=user_id, when=when, q=question_id, cat=category, value=value)
    if not (user_id and when in ('pre', 'post') and value):
        return JsonResponse({'ok': False, 'error': 'missing field'}, status=400)
    # Validate question_id against the canonical instrument and resolve the
    # category server-side so the persisted category is always correct.
    if question_id is not None:
        if not trust_instrument.valid_question_id(when, question_id):
            return JsonResponse({'ok': False, 'error': 'unknown question_id'}, status=400)
        category = trust_instrument.category_for(when, question_id)
    if _study_user(user_id):
        try:
            results_io.record_trust(
                local_dir, user_id, when, int(value),
                question_id=question_id, category=category,
            )
        except Exception as e:
            _p6_log('save_trust.ERROR', err=str(e))
            return JsonResponse({'ok': False, 'error': str(e)}, status=500)
    return JsonResponse({'ok': True})


# ----------------------------------------------------------------------
# Phase 6 — admin report + reset
# ----------------------------------------------------------------------

def _admin_password_ok(provided):
    expected = getattr(settings, 'LEMR_ADMIN_PASSWORD', None)
    return bool(expected) and provided == expected


def reset_participant(request):
    """
    Coordinator-triggered reset of a single participant.

    Required POST fields:
        user_id  — the participant id (e.g. "P05")
        password — the admin password (must match settings.LEMR_ADMIN_PASSWORD)

    Side effects:
        - Deletes models/results/{user_id}.json (if present).
        - Resets cases_completed to 0 for this user in participant_info.txt.

    Redirects back to the admin report on success; returns a 401/403 on
    bad credentials.
    """
    if request.method != 'POST':
        return HttpResponse('POST required', status=405)
    user_id = request.POST.get('user_id', '')
    password = request.POST.get('password', '')
    if not _admin_password_ok(password):
        return HttpResponse('Incorrect password.', status=401)
    # Accept study users AND the interface-demo accounts (which have
    # a single-case ordering file and get their counter bumped through
    # normal flow, so they also need a reset path for repeated
    # coordinator-side testing). All-caps sanity check: any known id.
    if not user_id:
        return HttpResponse('Refusing to reset that user.', status=400)
    if not _study_user(user_id) and user_id not in _DEMO_USER_IDS:
        return HttpResponse('Refusing to reset that user.', status=400)

    # 1) Delete the participant's results JSON.
    results_path = os.path.join(local_dir, 'results', user_id + '.json')
    if os.path.isfile(results_path):
        try:
            os.remove(results_path)
        except OSError as e:
            return HttpResponse('Could not delete results file: %s' % e, status=500)

    # 2) Reset cases_completed in participant_info.txt.
    pinfo_path = os.path.join(local_dir, 'evaluation_study',
                              'participant_info', 'participant_info.txt')
    if os.path.isfile(pinfo_path):
        with open(pinfo_path, 'r') as fh:
            lines = fh.readlines()
        new_lines = []
        for line in lines:
            split = line.rstrip('\n').rstrip('\r').split(',')
            if split and split[0] == user_id and len(split) >= 4:
                split[2] = '0'
                new_lines.append(','.join(split) + '\n')
            else:
                new_lines.append(line if line.endswith('\n') else line + '\n')
        with open(pinfo_path, 'w') as fh:
            fh.writelines(new_lines)

    return HttpResponseRedirect('/WebEmrGui/admin_report/?password=' + password)


def admin_report(request):
    """
    Password-protected aggregated report of all participants.
    GET without ?password=… (or with wrong password) -> show login form.
    GET with correct password -> render the full report.
    GET ?password=…&format=csv -> CSV download.
    """
    provided = request.GET.get('password', '')
    template_loader = loader.get_template

    if not getattr(settings, 'LEMR_ADMIN_PASSWORD', None):
        return HttpResponse(
            'Admin report is disabled: LEMR_ADMIN_PASSWORD is not configured '
            'in WebEmrProject/settings.py.', status=503)

    if not _admin_password_ok(provided):
        template = template_loader('WebEmrGui/admin_login.html')
        return HttpResponse(template.render({
            'error': bool(provided),  # truthy only after a failed attempt
        }, request))

    all_data = results_io.load_all(local_dir)

    # Pull in the lab/vital short -> display-name map so item lists in the
    # report can render as "ABBR (Full Name)" (e.g. "K (Potassium)"). Meds
    # aren't in display_names and stay as their catalog name. We load this
    # once at the top of the report so every per-case decoration below
    # shares a single dict.
    try:
        admin_display_names = pickle.load(
            open(local_dir + 'evaluation_study/tests/display_names.p', 'rb'),
            encoding='latin-1',
        )
    except Exception:
        admin_display_names = {}

    def _admin_fmt_item(code):
        """Render an item code as 'CODE (Full Name)' when display_names has
        a different display label; otherwise just the code itself. Strips
        embedded quote characters that some display_names entries carry
        (e.g. '"Bili, Total"')."""
        if not code:
            return code
        disp = admin_display_names.get(code)
        if isinstance(disp, str):
            disp = disp.strip('"').strip("'")
        if disp and disp != code:
            return '%s (%s)' % (code, disp)
        return code

    def _admin_fmt_list(codes):
        return [_admin_fmt_item(c) for c in (codes or [])]

    def _admin_fmt_rationales(rationales):
        """Return a shallow-copied list of rationale dicts where the `item`
        field is rendered as 'CODE (Full Name)' for the template. Other
        fields (free_text, reason_code, …) pass through unchanged."""
        out = []
        for r in (rationales or []):
            rr = dict(r)
            rr['item'] = _admin_fmt_item(rr.get('item'))
            out.append(rr)
        return out

    if request.GET.get('format') == 'csv':
        import csv, io
        # Python 3: csv.writer writes strings, so the underlying buffer
        # must be a StringIO. (io.BytesIO worked under the Py2 stack
        # because str == bytes; under Py3 it raises
        # "TypeError: a bytes-like object is required, not 'str'".)
        buf = io.StringIO()
        writer = csv.writer(buf)
        # n_commission_errors / n_omission_errors are the spec definitions
        # (selected ∖ judges, judges ∖ selected). trust_pre_avg /
        # trust_post_avg are the McKnight battery overall means; the legacy
        # single-Likert columns are kept for backwards compatibility with
        # any earlier participant JSONs.
        writer.writerow([
            'user_id',
            'demo_age', 'demo_gender', 'demo_icu_years', 'demo_professional_level',
            'case_order', 'case_id', 'is_intro',
            'show_highlights', 'highlights_only', 'incorrect_highlights',
            'familiarize_ms', 'present_ms', 'select_ms',
            'commission_ms', 'omission_ms',
            'n_judges_relevant', 'n_displayed', 'n_omitted_cfg', 'n_falsified_cfg',
            'n_selected', 'n_commission_errors', 'n_omission_errors',
            'n_commission_rationales', 'n_omission_rationales',
            'trust_pre_avg', 'trust_post_avg',
            'trust_pre_legacy', 'trust_post_legacy',
            'started_at', 'completed_at',
        ])
        for uid, p in all_data:
            # Compute the McKnight overall averages once per participant.
            def _avg_responses(when):
                vals = [int(r.get('value')) for r in (p.get('trust_responses') or {}).get(when, [])
                        if r.get('value') is not None]
                return ('%.2f' % (sum(vals) / float(len(vals)))) if vals else ''
            avg_pre, avg_post = _avg_responses('pre'), _avg_responses('post')
            demo = p.get('demographics') or {}
            demo_age                = demo.get('age', '')
            demo_gender             = demo.get('gender', '')
            demo_icu_years          = demo.get('icu_years', '')
            demo_professional_level = demo.get('professional_level', '')
            for case in p.get('cases', []):
                judges    = set(case.get('items_judges_relevant', []))
                selected  = set(case.get('selected_items', []))
                phases    = case.get('phases', {})
                writer.writerow([
                    uid,
                    demo_age, demo_gender, demo_icu_years, demo_professional_level,
                    case.get('order_index'), case.get('case_id'), case.get('is_intro'),
                    case.get('condition', {}).get('show_highlights'),
                    case.get('condition', {}).get('highlights_only'),
                    case.get('condition', {}).get('incorrect_highlights'),
                    phases.get('familiarize_ms', 0), phases.get('present_ms', 0),
                    phases.get('select_ms', 0), phases.get('commission_ms', 0),
                    phases.get('omission_ms', 0),
                    len(judges),
                    len(case.get('items_displayed_highlighted', [])),
                    len(case.get('items_omitted_from_highlights', [])),
                    len(case.get('items_falsely_highlighted', [])),
                    len(selected),
                    len(selected - judges),       # commission errors
                    len(judges - selected),       # omission errors
                    len(case.get('commission_rationales', [])),
                    len(case.get('omission_rationales', [])),
                    avg_pre, avg_post,
                    p.get('trust_pre'), p.get('trust_post'),
                    p.get('started_at'), p.get('completed_at'),
                ])
        resp = HttpResponse(buf.getvalue(), content_type='text/csv')
        resp['Content-Disposition'] = 'attachment; filename="lemr_results.csv"'
        return resp

    # Per-participant view model. The error definitions here are the
    # research-meaningful ones per Luca's spec:
    #
    #   commission_errors = items the participant selected that are NOT in
    #                       List #1 (the judges' relevant set). Rationale
    #                       is collected for each.
    #   omission_errors   = items in List #1 that the participant did NOT
    #                       select. Rationale is collected for each.
    #
    # The earlier "intentional_misses / spurious_selections" partitioning
    # (which split commission errors into "selected a planted false
    # highlight" vs "selected a non-highlighted irrelevancy", and split
    # omissions into "missed a planted omission" vs "missed any relevant
    # item") is dropped from the headline metrics. The raw lists are
    # still in the JSON, so post-hoc analyses can reconstruct it; the
    # admin report stays focused on what the participant did vs what
    # the judges said was relevant.
    def _format_ms(v):
        """ms -> 'M:SS' for display in the per-case time tiles."""
        try:
            ms = int(v or 0)
        except (TypeError, ValueError):
            ms = 0
        secs = ms // 1000
        return '%d:%02d' % (secs // 60, secs % 60)

    # Per-participant access codes — surfaced in the admin report so the
    # coordinator can give each participant their own code before they
    # log in via the home-screen modal.
    all_access_codes = load_all_access_codes(local_dir)

    participants = []
    for uid, p in all_data:
        view_cases = []
        for case in p.get('cases', []):
            judges = set(case.get('items_judges_relevant', []))
            selected = set(case.get('selected_items', []))
            falsified = set(case.get('items_falsely_highlighted', []))
            omitted_cfg = set(case.get('items_omitted_from_highlights', []))
            displayed = sorted(case.get('items_displayed_highlighted', []))

            commission_errors = sorted(selected - judges)         # selected but not relevant
            omission_errors   = sorted(judges  - selected)        # relevant but not selected
            correct_selections = sorted(selected & judges)        # selected AND relevant

            phases = case.get('phases', {})
            view_cases.append({
                'order_index':         case.get('order_index'),
                'case_id':             case.get('case_id'),
                'is_intro':            case.get('is_intro'),
                'condition':           case.get('condition', {}),
                'phases':              phases,
                # Pre-formatted time strings for the per-case header tiles.
                'familiarize_time':    _format_ms(phases.get('familiarize_ms')),
                'present_time':        _format_ms(phases.get('present_ms')),
                'select_time':         _format_ms(phases.get('select_ms')),
                # Headline error counts (plain integers — per Luca's spec
                # these are NOT ms, just count of items).
                'commission_count':    len(commission_errors),
                'omission_count':      len(omission_errors),
                # Case Setup section lists. Items decorated as
                # "ABBR (Full Name)" via _admin_fmt_item so the admin
                # report reads consistently with the QA reference doc
                # (e.g. "K (Potassium)" instead of just "K"). Meds and
                # items whose display equals the code pass through
                # unchanged.
                'items_judges_relevant':         _admin_fmt_list(sorted(judges)),
                'items_omitted_from_highlights': _admin_fmt_list(sorted(omitted_cfg)),
                'items_falsely_highlighted':     _admin_fmt_list(sorted(falsified)),
                'items_displayed_highlighted':   _admin_fmt_list(displayed),
                # User Selections section lists.
                'selected_items':       _admin_fmt_list(sorted(selected)),
                'correct_selections':   _admin_fmt_list(correct_selections),
                'commission_errors':    _admin_fmt_list(commission_errors),
                'omission_errors':      _admin_fmt_list(omission_errors),
                # Rationales — `r.item` field decorated to match.
                'commission_rationales': _admin_fmt_rationales(case.get('commission_rationales', [])),
                'omission_rationales':   _admin_fmt_rationales(case.get('omission_rationales', [])),
            })

        # Aggregate trust responses (McKnight battery) per category, and
        # pair pre + post side by side in a single row list so the report
        # template can render one row per category with both columns
        # populated where available. The 3 LEMR-specific Trusting-Belief
        # sub-scales (Reliability / Functionality / Helpfulness) appear in
        # both batteries; the 3 general-technology sub-scales appear only
        # pre-use. Iteration order follows trust_instrument.CATEGORY_LABELS
        # so the rendered table is stable across participants.
        by_when_cat = {'pre': {}, 'post': {}}
        for when in ('pre', 'post'):
            for r in (p.get('trust_responses') or {}).get(when, []) or []:
                cat = r.get('category')
                v   = r.get('value')
                if cat is None or v is None:
                    continue
                by_when_cat[when].setdefault(cat, []).append(int(v))

        def _avg_str(vals):
            return ('%.2f' % (sum(vals) / float(len(vals)))) if vals else None

        trust_rows = []
        for cat_code, label in trust_instrument.CATEGORY_LABELS.items():
            pre_vals  = by_when_cat['pre'].get(cat_code,  [])
            post_vals = by_when_cat['post'].get(cat_code, [])
            if not pre_vals and not post_vals:
                continue
            trust_rows.append({
                'code':     cat_code,
                'label':    label,
                'pre_avg':  _avg_str(pre_vals),
                'post_avg': _avg_str(post_vals),
                'pre_n':    len(pre_vals),
                'post_n':   len(post_vals),
            })

        # Overall (headline) averages — collapse across all the
        # participant's pre/post responses respectively.
        all_pre_vals  = [v for vals in by_when_cat['pre'].values()  for v in vals]
        all_post_vals = [v for vals in by_when_cat['post'].values() for v in vals]
        trust_pre_avg_one  = _avg_str(all_pre_vals)
        trust_post_avg_one = _avg_str(all_post_vals)

        # Legacy single-Likert fallback so participants whose JSON predates
        # the McKnight battery still display a trust value.
        legacy_pre  = p.get('trust_pre')
        legacy_post = p.get('trust_post')
        trust_pre_overall  = trust_pre_avg_one  or (str(legacy_pre)  if legacy_pre  else None)
        trust_post_overall = trust_post_avg_one or (str(legacy_post) if legacy_post else None)

        # Demographics: present a stable list of (label, value) tuples so
        # the template can render them in question order without having
        # to import trust_instrument or DEMOGRAPHIC_QUESTIONS itself.
        demo_dict = p.get('demographics') or {}
        demo_label = {
            'age':                'Age',
            'gender':             'Gender',
            'icu_years':          'Years of ICU experience',
            'professional_level': 'Professional level',
        }
        demo_rows = []
        for q in DEMOGRAPHIC_QUESTIONS:
            raw = demo_dict.get(q['id'])
            # Em-dash placeholder marked as a unicode literal so it
            # round-trips cleanly through Django's template renderer
            # regardless of any future json.dumps() call site.
            display = u'—'
            if raw is not None and raw != '':
                if q['kind'] == 'choice' and isinstance(raw, str) and raw.startswith('self:'):
                    display = raw[5:] or u'—'
                elif q['kind'] == 'choice':
                    # Map option value to display label.
                    label = raw
                    for opt in q.get('options', []):
                        if opt['value'] == raw:
                            # Strip trailing colon from labels like "Self-describe:"
                            label = opt['label'].rstrip(':').strip()
                            break
                    display = label
                else:
                    suffix = (' ' + q['unit']) if q.get('unit') else ''
                    display = '%s%s' % (raw, suffix)
            demo_rows.append({'id': q['id'], 'label': demo_label.get(q['id'], q['id']), 'value': display})

        participants.append({
            'user_id':           uid,
            'access_code':       all_access_codes.get(uid),
            'started_at':        p.get('started_at'),
            'completed_at':      p.get('completed_at'),
            'demographics':      demo_rows,
            'trust_rows':        trust_rows,
            'trust_pre_overall': trust_pre_overall,
            'trust_post_overall':trust_post_overall,
            'cases':             view_cases,
        })

    # Cross-participant trust averages for the summary tiles at the top.
    # Em-dash is a unicode literal so it round-trips cleanly through both
    # Django's template renderer and any future json.dumps() call site.
    def _avg(values):
        try:
            nums = [float(v) for v in values if v is not None]
            return '%.2f' % (sum(nums) / len(nums)) if nums else u'—'
        except (TypeError, ValueError):
            return u'—'

    trust_pre_avg  = _avg([p['trust_pre_overall']  for p in participants])
    trust_post_avg = _avg([p['trust_post_overall'] for p in participants])

    # Per-participant error averages, then meaned across participants.
    #
    #   for each participant:
    #       total_commission_p = Σ commission_count over their non-intro cases
    #       total_omission_p   = Σ omission_count   over their non-intro cases
    #   commission_avg = mean(total_commission_p across participants)
    #   omission_avg   = mean(total_omission_p   across participants)
    #
    # i.e. "the average participant makes X commission errors across all
    # their test cases" — the unit of the headline tile is per participant,
    # not per case, since each participant runs the full 6-case sequence.
    # Participants with zero test cases recorded are excluded from the
    # denominator so a half-started session doesn't drag the mean down.
    per_participant_commission = []
    per_participant_omission   = []
    for p in participants:
        tcomm = 0
        tomis = 0
        had_test_case = False
        for c in p['cases']:
            if c.get('is_intro'):
                continue
            had_test_case = True
            tcomm += int(c.get('commission_count') or 0)
            tomis += int(c.get('omission_count')   or 0)
        if had_test_case:
            per_participant_commission.append(tcomm)
            per_participant_omission.append(tomis)
    if per_participant_commission:
        commission_avg = '%.2f' % (sum(per_participant_commission) /
                                   float(len(per_participant_commission)))
        omission_avg   = '%.2f' % (sum(per_participant_omission)   /
                                   float(len(per_participant_omission)))
    else:
        commission_avg = u'—'
        omission_avg   = u'—'

    # Full list of access codes — used to render a dedicated card on
    # the admin report so the coordinator can hand them to participants
    # before / regardless of whether the participant has started yet.
    # Sorted with P##s in numeric order, pilots last.
    access_code_rows = []
    def _sort_key(item):
        uid, _code = item
        if uid.startswith('Pilot_'):
            return (1, uid)
        if uid.startswith('P'):
            try:
                return (0, int(uid[1:]))
            except ValueError:
                return (2, uid)
        return (3, uid)
    for uid, code in sorted(all_access_codes.items(), key=_sort_key):
        access_code_rows.append({'user_id': uid, 'code': code})

    # Demo-user reset panel. Interface_demo_* accounts have a single-
    # case ordering file; their cases_completed counter in
    # participant_info.txt bumps to 1 after they finish, and the demo
    # then routes to end-of-study on subsequent visits until reset.
    # Surface each demo user + its counter here so the coordinator
    # can reset them from the admin report instead of editing
    # participant_info.txt by hand.
    demo_rows = []
    pinfo_path = os.path.join(local_dir, 'evaluation_study',
                              'participant_info', 'participant_info.txt')
    pinfo_counters = {}
    if os.path.isfile(pinfo_path):
        try:
            with open(pinfo_path, 'r') as fh:
                for line in fh:
                    parts = line.rstrip('\r\n').split(',')
                    if len(parts) >= 3 and parts[0]:
                        pinfo_counters[parts[0]] = parts[2]
        except Exception:
            pass
    # Only surface the two Interface_demo_* users in the report. The
    # other legacy demo ids (first_four / interface_demo /
    # Data_Selection) exist for historical reasons but aren't part of
    # the participant flow the coordinator uses. Order matches the
    # home page: without-highlights first, with-highlights second.
    _demo_display_order = (
        'Interface_demo_without_highlights',
        'Interface_demo_with_highlights',
    )
    for uid in _demo_display_order:
        if uid not in _DEMO_USER_IDS:
            continue
        demo_rows.append({
            'user_id':          uid,
            'cases_completed':  pinfo_counters.get(uid, '—'),
        })

    template = template_loader('WebEmrGui/admin_report.html')
    return HttpResponse(template.render({
        'participants':     participants,
        'access_code_rows': access_code_rows,
        'demo_rows':        demo_rows,
        'password':         provided,
        'trust_pre_avg':    trust_pre_avg,
        'trust_post_avg':   trust_post_avg,
        'commission_avg':   commission_avg,
        'omission_avg':     omission_avg,
    }, request))


@ensure_csrf_cookie
def detail(request, patient_id, user_id):
    print('________________________________________________________________________')
    print('DETERMINING THE DETAILS OF THE CASE TO BE DISPLAYED...')
    print ('Function detail in views.py called.')

    template = loader.get_template('WebEmrGui/index_3.html')
    print("New request to render template index_3.html: " + request.path_info)

    p_info_location = local_dir + 'evaluation_study/participant_info/'

    print('p_info_location', p_info_location)
    print('user_id', user_id)
    print('patient_id', patient_id)




    # determine_next_url returns:
    #   • 5-tuple [patient_id, view, show_highlights, highlights_only, incorrect_highlights]
    #     for normal / end-of-study cases,
    #   • 2-tuple ['error', 'here'] when the current patient_id is not
    #     in the participant's ordering file (or on demo users past
    #     the end of their single-case sequence).
    # Unpacking the 2-tuple into 5 slots raises ValueError. Detect
    # the short return and route the demo user back to the home page
    # rather than crashing.
    _next = determine_next_url(p_info_location, user_id, patient_id)
    if len(_next) < 5:
        print('[detail] determine_next_url returned short tuple ' + repr(_next) +
              ' — redirecting to home. Likely a demo user past the end of their sequence.')
        return HttpResponseRedirect('/WebEmrGui/')
    next_patient, next_view, show_highlights, highlights_only, incorrect_highlights = _next


    print('________________________________________________________________________')
    print('VALUES 2')
    print('Checking current values of the following variables:')
    print('next_patient')
    print(next_patient)
    print('next_view')
    print(next_view)
    print('show_highlights')
    print(show_highlights)
    print('highlights_only')
    print(highlights_only)
    print('incorrect_highlights')
    print(incorrect_highlights)

    # Highlight condition comes straight from the participant's ordering
    # file (show_highlights / highlights_only / incorrect_highlights).
    current_arm = 'C'
    show_highlights = int(show_highlights)
    if show_highlights:
        current_arm = '1'
    if highlights_only == '1':
        current_arm = '2'
        only_show_highlights = 'true'
    else:
        only_show_highlights = 'false'

    print('current_arm')
    print(current_arm)
    print('next_view')
    print(next_view)
    print('only_show_highlights')
    print(only_show_highlights)
    print('show_highlights')
    print(show_highlights)
    print('________________________________________________________________________')

    record_report = 'true'

    # Phase 6: compute case meta + ground-truth lists. Used both to persist
    # to the participant's results JSON AND to feed the JS phase-6 payload
    # so the front-end can drive the commission/omission rationale flow.
    order_index, is_intro_p6, condition_for_results = read_current_case_meta(
        p_info_location, user_id, patient_id)
    ground_relevant, configured_omits, configured_fakes = \
        load_case_highlight_definitions(local_dir, patient_id)

    if condition_for_results['show_highlights'] == 0:
        displayed = []
        omitted_now = list(ground_relevant)   # everything is "omitted"
        falsified_now = []
    elif condition_for_results['incorrect_highlights'] == 1:
        displayed_set = set(ground_relevant) - set(configured_omits)
        displayed = sorted(displayed_set | set(configured_fakes))
        omitted_now = list(configured_omits)
        falsified_now = list(configured_fakes)
    else:  # correct highlights only
        displayed = list(ground_relevant)
        omitted_now = []
        falsified_now = []

    if _study_user(user_id):
        results_io.ensure_case(
            local_dir, user_id, patient_id, order_index, is_intro_p6,
            condition_for_results,
            items_judges_relevant=ground_relevant,
            items_displayed_highlighted=displayed,
            items_omitted_from_highlights=omitted_now,
            items_falsely_highlighted=falsified_now,
        )

    # Single-visit study: pickle data is always under cases_t2/{patient_id}/.
    load_dir = local_dir + 'evaluation_study/cases_t2/' + str(patient_id) + '/'

#Defining what to highlight



    data_fields_to_highlight = []
    items_relevant_according_to_judges = []
    relevant_items_not_to_be_highlighted = []
    non_relevant_items_to_be_highlighted = []
    data_fields_to_highlight_TRIAL = []
    data_fields_to_highlight_FINAL = []

# load med mappings. catalog_display is used as machine learning names, ordered as is the longer display name
    catalog_display_dic, ordered_as_dic = load_med_maps(load_dir + 'med-display-id_to_name.txt')
    # Phase 6: full (one-to-many) maps for highlight alias expansion. The
    # single-valued catalog_display_dic loses information when several med
    # rows share the same short name; this map preserves every alias.
    med_cat_to_ids, med_ord_to_ids, med_id_to_ordered = \
        load_med_full_map(load_dir + 'med-display-id_to_name.txt')


    if show_highlights:


        print('______________________________________________________________________________')
        print('HIGHLIGHTS ACTIVE. Determining what data items to highlight on the screen...')
        print('***')

        # Code added to gather items relevant according to judges
        with open(local_dir + 'evaluation_study/items_relevant_judges.txt', 'r') as j:
            for line in j:
                s_line = line.rstrip().split(': ')
                if s_line[0] == str(patient_id):
                    items_relevant_according_to_judges = s_line[1].split(',')
                    break
        print('Items selected by the judges as relevant:')
        print(items_relevant_according_to_judges)
        #print 'Associating drug names to data items...'
        #for idx, data_field in enumerate(items_relevant_according_to_judges):
        #    if data_field in catalog_display_dic.keys():
        #        items_relevant_according_to_judges[idx] = catalog_display_dic[data_field]
        #print 'Items selected by the judges as relevant (definitive list):'
        #print items_relevant_according_to_judges
        print('***')

        # Code added to gather relevant items not to be highlighted, only if incorrect_highlights is active (=1):
        if incorrect_highlights == '1':
            with open(local_dir + 'evaluation_study/relevant_data_items_not_to_be_highlighted.txt', 'r') as j:
                for line in j:
                    s_line = line.rstrip().split(': ')
                    if s_line[0] == str(patient_id):
                        relevant_items_not_to_be_highlighted = s_line[1].split(',')
                        break
            print('INCORRECT HIGHLIGHTS ACTIVE. Relevant items not to be highlighted:')
            print(relevant_items_not_to_be_highlighted)
        #print 'Associating drug names to data items...'
        #for idx, data_field in enumerate(items_relevant_according_to_judges):
        #    if data_field in catalog_display_dic.keys():
        #        relevant_items_not_to_be_highlighted[idx] = catalog_display_dic[data_field]
        #print 'Relevant items not to be highlighted (definitive list):'
        #print relevant_items_not_to_be_highlighted
            print('***')

        # Code added to gather non relevant items to be highlighted, only if incorrect_highlights is active (=1):
            with open(local_dir + 'evaluation_study/non_relevant_data_items_to_be_highlighted.txt', 'r') as j:
                for line in j:
                    s_line = line.rstrip().split(': ')
                    if s_line[0] == str(patient_id):
                        non_relevant_items_to_be_highlighted = s_line[1].split(',')
                        break
            print('INCORRECT HIGHLIGHTS ACTIVE. Non relevant items to be highlighted:')
            print(non_relevant_items_to_be_highlighted)
        #print 'Associating drug names to data items...'
        #for idx, data_field in enumerate(items_relevant_according_to_judges):
        #    if data_field in catalog_display_dic.keys():
        #        non_relevant_items_to_be_highlighted[idx] = catalog_display_dic[data_field]
        #print 'Non relevant items to be highlighted (definitive list):'
        #print non_relevant_items_to_be_highlighted
            print('***')

        # Code added to gather the final selection of items that will be highlighted on screen [TRIAL]
        print('Items that will be highlighted on screen:')
        data_fields_to_highlight_TRIAL1 = list (set(items_relevant_according_to_judges)-set(relevant_items_not_to_be_highlighted))
        set_data_fields_to_highlight_TRIAL1 = set(data_fields_to_highlight_TRIAL1)
        set_non_relevant_items_to_be_highlighted=set(non_relevant_items_to_be_highlighted)
        data_fields_to_highlight_TRIAL2 = set_data_fields_to_highlight_TRIAL1.union(set_non_relevant_items_to_be_highlighted)
        data_fields_to_highlight = list(data_fields_to_highlight_TRIAL2)
        print(data_fields_to_highlight)
        #for x in range(len(data_fields_to_highlight)):
        #    print data_fields_to_highlight[x],
        print('***')

        # Phase 6: expand med names to ALL their alias ids, not just the
        # last one written by catalog_display_dic. Previously a name like
        # "Sodium Chloride 0.9%" (which appears as multiple med_info rows
        # via IVPB / I/O / fluid orders) was being translated to just one
        # integer id, so only that single row got highlighted on screen.
        # Now we keep the short name AND every matching med-row id in the
        # final list so the template highlights every administration of
        # that med.
        # Expand each judges-named drug into every med_info row id that
        # corresponds to it, so the main All-patient-data panel
        # highlights every administration of that drug (e.g. multiple
        # bags of vancomycin, or IV + PO furosemide). Two lookup keys:
        #   • med_cat_to_ids  — catalog name (e.g. "vancomycin")
        #   • med_ord_to_ids  — ordered_as label (e.g. "Vanco 1g IV")
        #
        # Caveat that motivates the extra filter below: some cases carry
        # a POLYSEMOUS catalog — e.g. case <example-id-A> has four separate
        # med rows whose catalog is "Sodium Chloride 0.9%" but whose
        # ordered_as labels are vancomycin, cefepime, NS for bolus, and
        # Sodium Chloride 0.9%. If the judges list literally names
        # "Sodium Chloride 0.9%" and we blindly add every id sharing
        # that catalog, cefepime + vancomycin + NS-bolus all get
        # painted yellow in the main panel even though they aren't in
        # the judges' relevance set. To avoid that, for catalog-based
        # expansion we require ALL sibling ids under the catalog to
        # share the same ordered_as (the pure "vancomycin all rows are
        # ordered_as vancomycin" case). If ordered_as varies across
        # aliases, we skip catalog expansion and rely on the exact
        # ordered_as match below — which for "Sodium Chloride 0.9%"
        # correctly picks only the single id whose ordered_as is
        # literally "Sodium Chloride 0.9%".
        print('Expanding drug names to all alias ids...')
        expanded = set()
        for data_field in data_fields_to_highlight:
            expanded.add(data_field)                # short name (lab/vital code or original)
            # Ordered_as match first — exact-name binding.
            for mid in med_ord_to_ids.get(data_field, []):
                expanded.add(mid)
            # Catalog match ONLY when the catalog is unambiguous (all
            # aliases share one ordered_as). Prevents cross-drug
            # false-positives from polysemous carrier catalogs.
            cat_ids = med_cat_to_ids.get(data_field, [])
            if cat_ids:
                distinct_ord = set(med_id_to_ordered.get(mid) for mid in cat_ids)
                if len(distinct_ord) == 1:
                    # Fully unambiguous catalog (e.g. vancomycin, all aliases
                    # share one ordered_as): expand all aliases.
                    for mid in cat_ids:
                        expanded.add(mid)
                else:
                    # Polysemous catalog (e.g. "Sodium Chloride 0.9%" whose
                    # aliases include NS bags AND antibiotics diluted in NS
                    # like Unasyn / Zosyn / cefepime). We can't blindly
                    # expand — that would falsely highlight the antibiotics.
                    # But we ALSO shouldn't drop every alias, or the actual
                    # saline rows (which the judges DO mean by "Sodium
                    # Chloride 0.9%") never appear in the highlight panel.
                    #
                    # Rule: keep aliases whose ordered_as string matches a
                    # known pattern for the catalog. `CATALOG_ORD_PATTERNS`
                    # is the extensible whitelist — add an entry whenever
                    # a new polysemous catalog shows up in the study data.
                    patterns = CATALOG_ORD_PATTERNS.get(data_field, [])
                    for mid in cat_ids:
                        ordered_as = (med_id_to_ordered.get(mid) or '').strip()
                        if not ordered_as:
                            continue
                        lower = ordered_as.lower()
                        for pat in patterns:
                            if lower.startswith(pat.lower()) or pat.lower() in lower:
                                expanded.add(mid)
                                break
        data_fields_to_highlight = sorted(expanded)
        print('***')

        print('Items that will be highlighted on screen (with drug names adjusted):')
        print (data_fields_to_highlight)
        #for x in range(len(data_fields_to_highlight)):
        #    print data_fields_to_highlight[x]

        # Code added to gather the final selection of items that will be highlighted on screen
        #with open(local_dir + 'evaluation_study/case_highlights.txt', 'r') as f:
        #    for line in f:
        #        s_line = line.rstrip().split(': ')
        #        if s_line[0] == str(patient_id):
        #            data_fields_to_highlight = s_line[1].split(',')
        #            break
        #print 'Items that will be highlighted on screen: '
        #print data_fields_to_highlight

        #print 'Associating drug names to data items...'
        #for idx, data_field in enumerate(data_fields_to_highlight):
        #    if data_field in catalog_display_dic.keys():
        #        data_fields_to_highlight[idx] = catalog_display_dic[data_field]
        #
        #print 'Items that will be highlighted on screen (with drug names adjusted):'
        #print data_fields_to_highlight

        print('______________________________________________________________________________')
# Gathering data items that were annotated as relevant:
#
#
# data_items_relevant = []
#    with open(local_dir + 'evaluation_study/data_items_relevant.txt', 'r') as g:
#        for line in g:
#            p_line = line.rstrip().split(': ')
#            if p_line[0] == str(patient_id):
#                data_items_relevant = p_line[1].split(',')
#                break



    demographics_dict = pickle.load(open(load_dir + 'demographics.p', 'rb'), encoding='latin-1')
    global_time = pickle.load(open(load_dir + 'global_time.p', 'rb'), encoding='latin-1')
    lab_info = pickle.load(open(load_dir + 'labs.p', 'rb'), encoding='latin-1')
    vital_info = pickle.load(open(load_dir + 'vitals.p', 'rb'), encoding='latin-1')
    group_order_labs = pickle.load(open(local_dir + 'evaluation_study/tests/group_order_labs.p', 'rb'), encoding='latin-1')
    group_info = pickle.load(open(local_dir + 'evaluation_study/tests/group_membership.p', 'rb'), encoding='latin-1')
    global_params = pickle.load(open(local_dir + 'evaluation_study/tests/global_params.p', 'rb'), encoding='latin-1')
    display_names = pickle.load(open(local_dir + 'evaluation_study/tests/display_names.p', 'rb'), encoding='latin-1')
    recent_results = pickle.load(open(load_dir + 'recent_results.p', 'rb'), encoding='latin-1')
    med_info = pickle.load(open(load_dir + 'case_test_meds.p', 'rb'), encoding='latin-1')
    display_med_names = pickle.load(open(load_dir + 'display_med_names.p', 'rb'), encoding='latin-1')
    med_routes = pickle.load(open(load_dir + 'med_routes.p', 'rb'), encoding='latin-1')
    routes_mapping = pickle.load(open(load_dir + 'routes_mapping.p', 'rb'), encoding='latin-1')
    procedure_dict = pickle.load(open(load_dir + 'procedures.p', 'rb'), encoding='latin-1')
    micro_report_dict = pickle.load(open(load_dir + 'micro_report.p', 'rb'), encoding='latin-1')
    op_note = pickle.load(open(load_dir + 'OP.p', 'rb'), encoding='latin-1')
    rad_note = pickle.load(open(load_dir + 'RAD.p', 'rb'), encoding='latin-1')
    ekg_note = pickle.load(open(load_dir + 'EKG.p', 'rb'), encoding='latin-1')
    other_note = pickle.load(open(load_dir + 'other_notes.p', 'rb'), encoding='latin-1')
    pgn_note = pickle.load(open(load_dir + 'PGN.p', 'rb'), encoding='latin-1')
    hp_note = pickle.load(open(load_dir + 'HP.p', 'rb'), encoding='latin-1')

    # Phase 6 — JSON payload injected into the page so the front-end can run
    # the time tracker + commission/omission rationale flow against the real
    # case-specific data, and POST results back keyed by participant.
    #
    # For each judges-relevant item we ship:
    #   code   — the canonical short id used in models/results/*.json
    #   display — the friendly label shown to participants in rationale prompts
    #   aliases — every string the user's selected_items array might contain
    #             when they click the item on screen (lab/vital code, or the
    #             integer med-id strings that correspond to the same
    #             catalog-display name in med-display-id_to_name.txt)
    #
    # We also ship a name_for_id map so phase6_flow.js can pretty-print
    # whatever item the participant actually clicked during selection.

    # Build catalog_display -> [med_id_strs] from med-display-id_to_name.txt.
    # We already loaded the full map above as med_cat_to_ids (one-to-many);
    # reuse it instead of re-parsing the file.
    med_catalog_to_ids = med_cat_to_ids

    def _friendly(item):
        # Friendly label for a judges-relevant item. We strip embedded
        # quote characters that some `display_names` entries carry as
        # part of the raw label (e.g. '"Bili, Total"' or '"PCO2,
        # Arterial"') so the participant prompt reads cleanly.
        if item in display_names:
            disp = display_names[item]
            if isinstance(disp, str):
                disp = disp.strip('"').strip("'")
            return disp or item
        return item  # med catalog names are already human-readable

    def _aliases(item):
        # Strings the user's selected_items array might contain for this item.
        aliases = [item]
        for mid in med_catalog_to_ids.get(item, []):
            aliases.append(str(mid))
        return aliases

    # ------------------------------------------------------------------
    # Rationale-prompt display disambiguation.
    #
    # Some codes in different sections share the same _friendly() label —
    # e.g. CREAT ("Creatinine", Basic Chemistry) and UCREAT ("Creatinine",
    # Urinalysis); or K / UK ("Potassium"); or CL / UCL ("Chloride"); or
    # NA / UNA ("Sodium"). Without disambiguation the omission prompt
    # "You did not include Creatinine among the most relevant items"
    # is confusing when the participant DID select the other Creatinine
    # (the urine one, which is a different code but same display label).
    #
    # Rule: append " (Section)" ONLY for codes whose friendly label is
    # not unique among the codes actually present in this case. Unique
    # labels (Temperature, PT, ...) stay clean.
    # ------------------------------------------------------------------
    code_to_section = {}
    if isinstance(group_info, dict):
        for _section_name, _codes in group_info.items():
            for _c in (_codes or []):
                code_to_section[str(_c)] = _section_name

    _case_codes = set(str(c) for c in list(lab_info.keys()) + list(vital_info.keys()))
    _label_counts = {}
    for _c in _case_codes:
        _lbl = _friendly(_c)
        _label_counts[_lbl] = _label_counts.get(_lbl, 0) + 1

    def _friendly_disambig(code):
        lbl = _friendly(code)
        if _label_counts.get(lbl, 1) > 1:
            section = code_to_section.get(str(code))
            if section:
                return '%s (%s)' % (lbl, section)
        return lbl

    judges_payload = []
    for it in ground_relevant:
        judges_payload.append({
            'code':    it,
            'display': _friendly_disambig(it),
            'aliases': _aliases(it),
        })

    # name_for_id maps every possible selected_items DOM-id to a friendly
    # label (used in the commission rationale prompts).
    #   Labs/vitals: code -> display_names[code] (e.g. "K" -> "Potassium")
    #   Meds:        integer-id-string -> catalog name (e.g. "9" -> "vancomycin"),
    #                NOT ordered_as, because the catalog name is what a
    #                clinician would actually say in morning rounds.
    name_for_id = {}
    for code in list(lab_info.keys()) + list(vital_info.keys()):
        name_for_id[str(code)] = _friendly(code)
    # Build id -> catalog name from the per-case med map.
    id_to_catalog = {}
    for cat_name, mids in med_catalog_to_ids.items():
        for mid in mids:
            id_to_catalog[mid] = cat_name
    for med_id, ordered_as in display_med_names.items():
        # Prefer the catalog (short, study-friendly) name; fall back to
        # ordered_as if no mapping exists.
        name_for_id[str(med_id)] = id_to_catalog.get(str(med_id), ordered_as)

    # canonical_for_id: DOM-id -> canonical short name.
    #   For labs/vitals, the canonical IS the code itself.
    #   For meds, the canonical is the catalog name (short).
    # Used in JS to normalize selected_items BEFORE POSTing so that the
    # report can do plain set intersection against items_judges_relevant /
    # items_falsely_highlighted / items_omitted_from_highlights (which are
    # all short names too).
    canonical_for_id = {}
    for code in list(lab_info.keys()) + list(vital_info.keys()):
        canonical_for_id[str(code)] = str(code)
    for mid, cat in id_to_catalog.items():
        canonical_for_id[mid] = cat

    # display_for_canonical: canonical-name -> friendly display label.
    # Used in JS to render commission rationale prompts after de-duplicating
    # selections through canonical_for_id. Uses _friendly_disambig so a
    # commission prompt about "Creatinine" also reads "(Basic Chemistry)"
    # or "(Urinalysis)" when the same friendly label is used by more than
    # one code in this case — same disambiguation the omission side gets.
    display_for_canonical = {}
    for code in list(lab_info.keys()) + list(vital_info.keys()):
        display_for_canonical[str(code)] = _friendly_disambig(code)
    for cat_name in med_catalog_to_ids.keys():
        display_for_canonical[cat_name] = cat_name

    phase6_payload = json.dumps({
        'user_id':                user_id,
        'patient_id':             str(patient_id),
        'is_intro':               is_intro_p6,
        'is_study_user':          _study_user(user_id),
        'order_index':            order_index,
        'items_judges_relevant':  judges_payload,
        'name_for_id':            name_for_id,
        'canonical_for_id':       canonical_for_id,
        'display_for_canonical':  display_for_canonical,
    })

    # Phase 6 fix: build a "short med name" map keyed by med id so the
    # Highlighted-data panel can render each med row with its short catalog
    # name (e.g. "Sodium Chloride 0.9%") instead of the very long
    # ordered_as label (e.g. "Sodium Chloride 0.9% Premix 1^000 mL [60
    # mL/hr]"). The chart cells in the highlight panel are only ~180 px
    # wide, so ordered_as labels overflow and look like garbled text. The
    # main All-patient-data panel keeps using the full ordered_as label.
    #
    # IMPORTANT: keep the dict keyed on the SAME type as display_med_names
    # (integer med ids loaded from the pickle). The template iterates
    # `for med in med_info` which yields the integer keys, and the
    # `get_json_arr` filter does a plain `dict[key]` lookup — string keys
    # would raise KeyError.
    short_med_name = {}
    for med_id, ordered_as in display_med_names.items():
        short_med_name[med_id] = id_to_catalog.get(str(med_id), ordered_as)

    # Phase 6 fix: deduplicate meds for the Highlighted-data panel.
    #
    # The alias expansion above adds every med_info row id that shares
    # a catalog name (so the main All-patient-data panel highlights all
    # administrations of e.g. "Sodium Chloride 0.9%" across IVPB / IV /
    # fluid orders). In the highlight panel that would produce visually
    # duplicated chart cells, so `highlight_panel_meds` keeps only one
    # representative med_info id per catalog name.
    #
    # Pick rule: prefer the alias with the most non-zero data points
    # (a real value curve like vancomycin dose over time), then tie-
    # break on total points, then on lowest med_id for determinism.
    # We DO keep catalogs whose only data is event-style (all y == 0,
    # e.g. "Base solution" with its "Begin Bag / mL / mcg" annotations);
    # the chart-render function get_med_chart_highlight_area now nudges
    # the y-axis when it detects all-zero data so the markers and the
    # latest-value label render visibly inside the cell.
    def _useful_med_score(rows):
        """Return (points_count, nonzero_count) for the first series."""
        try:
            data = rows[0][0].get('data', []) if rows and rows[0] else []
        except Exception:
            return (0, 0)
        nz = sum(1 for p in data
                 if p and len(p) >= 2 and p[1] not in (0, 0.0, None))
        return (len(data), nz)

    highlight_panel_meds = []
    _picked_for_cat = {}
    for med_id in med_info.keys():
        if str(med_id) not in data_fields_to_highlight:
            continue
        cat = id_to_catalog.get(str(med_id))
        rows = med_info.get(med_id) or []
        n_points, n_nonzero = _useful_med_score(rows)
        if not cat:
            # No catalog mapping — take it as-is if it has any data.
            if n_points > 0:
                highlight_panel_meds.append(med_id)
            continue
        current = _picked_for_cat.get(cat)
        score = (n_nonzero, n_points, -med_id)
        if current is None or score > current['score']:
            _picked_for_cat[cat] = {
                'med_id':    med_id,
                'score':     score,
                'n_points':  n_points,
            }
    # Keep every catalog whose representative alias has at least one
    # data point recorded for this case. Empty-data aliases still drop.
    for cat, info in _picked_for_cat.items():
        if info['n_points'] > 0:
            highlight_panel_meds.append(info['med_id'])
    highlight_panel_meds.sort()

    # ------------------------------------------------------------------
    # Mirror the highlight-panel med picks into `data_fields_to_highlight`
    # so the AI-highlight tint paints both panels.
    #
    # Case in point: fentanyl catalog has multiple ordered_as forms
    # ("Fentanyl 2500 mcg/50 mL", "Fentanyl 100 mcg IV push", ...),
    # so the polysemous-catalog guard above (which prevents cefepime /
    # vancomycin / NS-bolus from all lighting up when the judges list
    # "Sodium Chloride 0.9%") skips catalog expansion for fentanyl too.
    # Without that expansion, `data_fields_to_highlight` still contains
    # only the string "fentanyl" — no integer med_id — so the JS
    # highlight() loop can't match .medrow[id='42'] in the main panel.
    # highlight_panel_meds already picked a representative med_id per
    # catalog (the alias with the most non-zero data points); adding
    # those med_ids here lets highlight() find the corresponding row in
    # the All-patient-data panel and paint it yellow, keeping the two
    # panels visually consistent.
    for _mid in highlight_panel_meds:
        _mid_str = str(_mid)
        if _mid_str not in data_fields_to_highlight:
            data_fields_to_highlight.append(_mid_str)

    # ------------------------------------------------------------------
    # Dedupe: keep exactly one main-panel yellow-tinted med row per
    # catalog, matching the highlight-panel count.
    #
    # Before this step data_fields_to_highlight can contain MANY med_ids
    # for the same catalog — for instance the Base solution catalog in
    # case <example-id-B> has four premix aliases (Propofol, Fentanyl,
    # Midazolam, Milrinone) that CATALOG_ORD_PATTERNS added because
    # each ordered_as contains "Premix". The highlight panel dedupes to
    # one representative per catalog (highlight_panel_meds), so the
    # participant sees 13 items up top but ~15 highlighted below —
    # confusing. This loop drops every med_id that shares a catalog
    # with a highlight_panel_meds representative but IS NOT that
    # representative.
    _kept_reps = set(str(m) for m in highlight_panel_meds)
    _all_med_ids_in_dfth = [
        _v for _v in data_fields_to_highlight
        if _v.isdigit() and int(_v) in med_info
    ]
    for _mid_str in _all_med_ids_in_dfth:
        cat = id_to_catalog.get(_mid_str)
        if not cat:
            continue
        # Is there a representative for this catalog?
        _rep_for_cat = _picked_for_cat.get(cat, {}).get('med_id')
        if _rep_for_cat is None:
            continue
        _rep_str = str(_rep_for_cat)
        # Drop any sibling that isn't the picked representative.
        if _mid_str != _rep_str and _mid_str in data_fields_to_highlight:
            data_fields_to_highlight.remove(_mid_str)

#    context = RequestContext(request, {
    # changed code here to make it compatible with Django v1.11
    context = {
        'global_time': global_time,
        'next_patient': next_patient,
        'next_view': next_view,
        'incorrect_highlights': incorrect_highlights,
        'user_id': str(user_id),
        'phase6_json': phase6_payload,
        'demographics_dict': demographics_dict,
        'OP_note': op_note,
        'RAD_note': rad_note,
        'EKG_note': ekg_note,
        'other_note': other_note,
        'PGN_note': pgn_note,
        'HP_note': hp_note,
        'micro_report_dict': micro_report_dict,
        'lab_info': lab_info,
        'vital_info': vital_info,
        'group_info': group_info,
        'global_display_info': global_params,
        'labs_to_highlight': data_fields_to_highlight,
        'only_show_highlights': only_show_highlights,
        'show_highlights': show_highlights,
        'arm': current_arm,
        'display_names': display_names,
        'group_order': group_order_labs,
        'procedures': procedure_dict,
        'recent': recent_results,
        'med_info': med_info,
        'med_routes': med_routes,
        'routes_mapping': routes_mapping,
        'display_med_names': display_med_names,
        'short_med_name': short_med_name,
        'highlight_panel_meds': highlight_panel_meds,
        'record_report': record_report
    }
#    })
    return HttpResponse(template.render(context, request))



# used when finding which models to highlight
def model_inference(patient_id):
    del patient_id
    return ['CC_BUN', 'BH_INR', 'heparin', 'IV_heparin', 'fio2', 'CC_AST_B_SGOT']
