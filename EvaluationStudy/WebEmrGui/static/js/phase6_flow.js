/*  Phase 6 — study-flow controller.
 *
 *  Drives the per-case participant journey for the simplified 2026 study:
 *
 *      familiarize  →  present  →  select  →  commission rationales
 *                                              →  omission rationales
 *                                              →  next case
 *
 *  Time spent in each phase is recorded by POSTing to /save_phase_time/.
 *  The participant's selected items are POSTed to /save_selection/ when
 *  the selection phase ends. Each commission and omission rationale is
 *  POSTed individually so a participant can quit mid-flow and still have
 *  every answered question persisted.
 *
 *  Expects:
 *      window.PHASE6 = {
 *          user_id, patient_id, is_intro, is_study_user, order_index,
 *          items_judges_relevant: [...]
 *      };
 *      window.selected_items = [...]    // populated by emr_3.js
 *      window.next_patient_link         // URL of the next case (or /end/.../)
 *
 *  Drives the task-box content via #task by hijacking the screen-transition
 *  functions originally defined in emr_3.js:
 *      create_rounding_report_screen  → starts "present" phase
 *      create_selection_screen        → starts "select" phase
 *      create_error_check_screen      → starts commission phase
 *      next_case_link_press           → submits final results + advances
 */

(function () {
    "use strict";

    // ------------------------------------------------------------------
    // State
    // ------------------------------------------------------------------

    var PHASES = ['familiarize', 'present', 'select', 'commission', 'omission'];
    var current_phase = null;
    var phase_started_at_ms = null;

    // Commission stage iterator state
    var commission_queue = [];
    var commission_idx = 0;

    // Omission stage iterator state
    var omission_queue = [];
    var omission_idx = 0;

    // ------------------------------------------------------------------
    // Networking
    // ------------------------------------------------------------------

    function getCsrfToken() {
        var name = 'csrftoken=';
        var parts = document.cookie.split(';');
        for (var i = 0; i < parts.length; i++) {
            var c = parts[i].replace(/^\s+/, '');
            if (c.indexOf(name) === 0) return c.substring(name.length);
        }
        return '';
    }

    function post(path, params, onDone) {
        var body = [];
        for (var k in params) {
            if (params.hasOwnProperty(k)) {
                body.push(encodeURIComponent(k) + '=' + encodeURIComponent(params[k]));
            }
        }
        var xhr = new XMLHttpRequest();
        xhr.open('POST', path, true);
        xhr.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded');
        xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
        var tok = getCsrfToken();
        if (tok) xhr.setRequestHeader('X-CSRFToken', tok);
        xhr.onreadystatechange = function () {
            if (xhr.readyState === 4) {
                var ok = xhr.status >= 200 && xhr.status < 300;
                if (!ok) {
                    // Surface every failed save in DevTools so the
                    // coordinator can spot persistence problems early.
                    console.error('[phase6 POST ' + path + ' FAILED] status=' +
                                  xhr.status + ' body=' + xhr.responseText.substring(0, 240));
                } else {
                    console.log('[phase6 POST ' + path + ' OK]');
                }
                if (onDone) onDone(ok);
            }
        };
        xhr.send(body.join('&'));
    }

    function isStudyParticipant() {
        return !!(window.PHASE6 && window.PHASE6.is_study_user);
    }

    // ------------------------------------------------------------------
    // Phase tracking
    //
    // Wall-clock time per phase, with Page Visibility-based pause: when
    // the participant minimizes the window or switches tabs, the timer
    // pauses and resumes on return. This catches the common "break" case
    // (closed laptop lid, alt-tabbed away) without needing user-visible
    // pause buttons. Limitation: time still accumulates if the tab is
    // visible but the participant has stepped away.
    // ------------------------------------------------------------------

    var phase_paused_total_ms = 0;
    var phase_pause_start_ms  = null;

    function startPhase(name) {
        if (PHASES.indexOf(name) < 0) return;
        if (current_phase) finishPhase();   // close out any open phase
        current_phase = name;
        phase_started_at_ms = Date.now();
        phase_paused_total_ms = 0;
        phase_pause_start_ms = null;
        console.log('[phase6] started phase: ' + name);
    }

    // sendBeacon is a "deliver this even if I'm navigating away" hammer.
    // Browsers guarantee it won't be cancelled by an in-flight unload.
    // We use it for finishPhase() because the last phase of a case (and
    // its save_phase_time POST) often fires right before the participant
    // is navigated to the next case.
    function postBeacon(path, params) {
        if (!navigator.sendBeacon) return false;
        var body = [];
        for (var k in params) {
            if (params.hasOwnProperty(k)) {
                body.push(encodeURIComponent(k) + '=' + encodeURIComponent(params[k]));
            }
        }
        var blob = new Blob([body.join('&')],
            { type: 'application/x-www-form-urlencoded' });
        var ok = navigator.sendBeacon(path, blob);
        console.log('[phase6 BEACON ' + path + (ok ? ' queued' : ' FAILED to queue') + ']');
        return ok;
    }

    function finishPhase() {
        if (!current_phase || phase_started_at_ms === null) return;
        // If we ended the phase while still paused (e.g. tab hidden when
        // the participant clicked "continue" with the keyboard), close
        // out the pause first.
        if (phase_pause_start_ms !== null) {
            phase_paused_total_ms += Date.now() - phase_pause_start_ms;
            phase_pause_start_ms = null;
        }
        var elapsed = (Date.now() - phase_started_at_ms) - phase_paused_total_ms;
        if (elapsed < 0) elapsed = 0;
        console.log('[phase6] finished phase ' + current_phase +
                    ' (' + elapsed + ' ms, paused ' + phase_paused_total_ms + ' ms)');
        if (isStudyParticipant()) {
            var payload = {
                user_id:    window.PHASE6.user_id,
                patient_id: window.PHASE6.patient_id,
                phase:      current_phase,
                elapsed_ms: elapsed
            };
            // Try sendBeacon first (survives navigation); fall back to XHR
            // if the browser doesn't support it.
            if (!postBeacon('/WebEmrGui/save_phase_time/', payload)) {
                post('/WebEmrGui/save_phase_time/', payload);
            }
        }
        current_phase = null;
        phase_started_at_ms = null;
        phase_paused_total_ms = 0;
        phase_pause_start_ms = null;
    }

    document.addEventListener('visibilitychange', function () {
        if (!current_phase) return;
        if (document.hidden) {
            if (phase_pause_start_ms === null) {
                phase_pause_start_ms = Date.now();
                console.log('[phase6] paused (tab hidden)');
            }
        } else {
            if (phase_pause_start_ms !== null) {
                var paused_for = Date.now() - phase_pause_start_ms;
                phase_paused_total_ms += paused_for;
                phase_pause_start_ms = null;
                console.log('[phase6] resumed (was paused ' + paused_for + ' ms)');
            }
        }
    });

    // ------------------------------------------------------------------
    // Hijack the screen-transition functions so we can hook timing.
    // emr_3.js defines them; we wrap them.
    // ------------------------------------------------------------------

    var _orig_create_rounding_report_screen = window.create_rounding_report_screen;
    var _orig_create_selection_screen       = window.create_selection_screen;
    var _orig_create_error_check_screen     = window.create_error_check_screen;
    var _orig_next_case_link_press          = window.next_case_link_press;

    window.create_rounding_report_screen = function (next_link) {
        startPhase('present');
        return _orig_create_rounding_report_screen.call(this, next_link);
    };

    window.create_selection_screen = function () {
        startPhase('select');
        return _orig_create_selection_screen.call(this);
    };

    /*  emr_3.js's create_error_check_screen was hard-coded to a single
     *  example data item. We replace it with a real implementation that
     *  computes commission / omission lists and iterates through them. */
    window.create_error_check_screen = function () {
        // Selection phase ends here.
        finishPhase();

        // selected_items comes from emr_3.js and contains raw DOM ids
        // (lab/vital codes like "CREAT", or integer-stringified med-row ids
        // like "9"). We normalize those to canonical short names BEFORE
        // POSTing so the saved selected_items list matches what's in the
        // judges / falsified / omitted lists (all short names) — that lets
        // the admin report do plain set intersection for the metric counts.
        var sel_raw     = window.selected_items || [];
        var canon_map   = (window.PHASE6 && window.PHASE6.canonical_for_id) || {};
        var display_map = (window.PHASE6 && window.PHASE6.display_for_canonical) || {};

        function _canonicalize(id) { return canon_map[id] || id; }
        function _displayOf(canon) { return display_map[canon] || canon; }

        var seen = {};
        var sel_canonical = [];
        for (var ci = 0; ci < sel_raw.length; ci++) {
            var c = _canonicalize(sel_raw[ci]);
            if (!seen[c]) { seen[c] = true; sel_canonical.push(c); }
        }

        // Persist the participant's selected items (canonical form).
        // Beacon so it survives an immediate navigation in the intro-case
        // skip branch below.
        if (isStudyParticipant()) {
            var selPayload = {
                user_id:    window.PHASE6.user_id,
                patient_id: window.PHASE6.patient_id,
                items:      sel_canonical.join(',')
            };
            if (!postBeacon('/WebEmrGui/save_selection/', selPayload)) {
                post('/WebEmrGui/save_selection/', selPayload);
            }
        }

        // The intro case: skip rationale stages entirely.
        if (window.PHASE6 && window.PHASE6.is_intro) {
            console.log('[phase6] intro case — skipping commission/omission stages.');
            advanceToNextCase();
            return;
        }

        // ----------------------------------------------------------------
        // Build error queues — ONLY actual errors, not every selection / every
        // judges-relevant item.
        //
        //   commission_queue = items the participant selected that are NOT in
        //                      the judges-relevant set (commission errors only).
        //                      Rationale is asked only for those — items the
        //                      participant correctly identified as relevant
        //                      get no follow-up prompt.
        //
        //   omission_queue   = items in the judges-relevant set that the
        //                      participant did NOT select (omission errors).
        //                      Match against every alias the server ships
        //                      (lab/vital codes AND every med id mapping to
        //                      the same catalog-display name) so meds with
        //                      multiple alias ids aren't falsely reported as
        //                      missed.
        // ----------------------------------------------------------------
        var judges = (window.PHASE6 && window.PHASE6.items_judges_relevant) || [];

        // Set of canonical short names the judges considered relevant — used
        // for the commission filter below. Each jrow's `code` IS the
        // canonical short name (lab/vital code, or med catalog name).
        var judges_canon_set = {};
        for (var jc = 0; jc < judges.length; jc++) {
            var jcode = (judges[jc] && (judges[jc].code || judges[jc]));
            if (jcode) judges_canon_set[jcode] = true;
        }

        commission_queue = [];
        for (var i = 0; i < sel_canonical.length; i++) {
            if (judges_canon_set[sel_canonical[i]]) continue;  // correct pick — no rationale
            commission_queue.push({
                code:    sel_canonical[i],
                display: _displayOf(sel_canonical[i])
            });
        }
        commission_idx = 0;

        // Selected-id set used to test whether ANY alias of a judges-relevant
        // item matches the participant's raw selections.
        var selected_set = {};
        for (var k = 0; k < sel_raw.length; k++) {
            selected_set[sel_raw[k]] = true;
        }
        omission_queue = [];
        for (var j = 0; j < judges.length; j++) {
            var jrow = judges[j];
            var aliases = jrow.aliases || [jrow.code || jrow];
            var hit = false;
            for (var a = 0; a < aliases.length; a++) {
                if (selected_set[aliases[a]]) { hit = true; break; }
            }
            if (!hit) {
                omission_queue.push({
                    code:    jrow.code    || jrow,
                    display: jrow.display || jrow.code || jrow
                });
            }
        }
        omission_idx = 0;
        console.log('[phase6] commission errors: ' + commission_queue.length +
                    ', omission errors: ' + omission_queue.length);

        if (commission_queue.length > 0) {
            startPhase('commission');
            renderCommissionItem();
        } else if (omission_queue.length > 0) {
            startPhase('omission');
            renderOmissionItem();
        } else {
            advanceToNextCase();
        }
    };

    window.next_case_link_press = function () {
        // If a phase is still open at this point (shouldn't normally
        // happen) close it.
        finishPhase();
        return _orig_next_case_link_press.call(this);
    };

    // ------------------------------------------------------------------
    // Rationale stages — Back-button support
    //
    // commission_answers / omission_answers cache the participant's
    // most recent submission per index, so a Back click can re-render
    // the previous prompt with their original answer pre-filled. We
    // also support cross-stage Back from omission #1 back to the last
    // commission item (so the participant can revise either way).
    //
    // Back is hidden on the very first prompt of the first non-empty
    // stage (no earlier prompt to return to). The submit endpoints
    // already de-dupe by item code, so re-submitting a revised answer
    // overwrites the prior server-side record cleanly.
    // ------------------------------------------------------------------
    var commission_answers = [];   // commission_answers[i] = "rationale text"
    var omission_answers   = [];   // omission_answers[i]   = {reason, free_text}

    function _isFirstPrompt(stage) {
        if (stage === 'commission') return commission_idx === 0;
        if (stage === 'omission')   return omission_idx === 0 && commission_queue.length === 0;
        return true;
    }

    // ------------------------------------------------------------------
    // Commission stage
    // ------------------------------------------------------------------

    function renderCommissionItem() {
        if (commission_idx >= commission_queue.length) {
            // Move to omission stage (or skip to next case if none).
            if (omission_queue.length > 0) {
                startPhase('omission');
                renderOmissionItem();
            } else {
                advanceToNextCase();
            }
            return;
        }
        var item = commission_queue[commission_idx];
        var progress = (commission_idx + 1) + ' of ' + commission_queue.length;
        var canGoBack = !_isFirstPrompt('commission');
        var prior = commission_answers[commission_idx] || '';

        // v2 task-box layout: step pill + lead + textarea + divider +
        // right-aligned primary submit, with an optional Back button on
        // the left. Styles live in bs_3.css under .task-step-tag /
        // .task-lead / .task-textarea / .task-divider / .task-action-row
        // + .lemr-btn.
        var backBtn = canGoBack
            ? "<input id='p6_commission_back' type='button' value='Back' "
            + "class='lemr-btn secondary' onclick='__phase6_back_commission()'>"
            : "<span></span>";   // placeholder so flex justify-content stays sane

        var html =
              "<span class='task-step-tag'>Selected · " + progress + "</span>"
            + "<p class='task-lead'>You marked <b>" + escapeHtml(item.display) + "</b> as relevant. Why?</p>"
            + "<textarea id='p6_commission_text' rows='3' class='task-textarea' "
            +           "placeholder='In a few words…'></textarea>"
            + "<hr class='task-divider'>"
            + "<div class='task-action-row' style='justify-content:space-between;'>"
            +   backBtn
            +   "<input id='p6_commission_next' type='button' value='Submit and continue' "
            +          "class='lemr-btn primary' disabled "
            +          "onclick='__phase6_submit_commission()'>"
            + "</div>";
        $("#task").html(html);
        $('.shower').hide();

        var ta = document.getElementById('p6_commission_text');
        var btn = document.getElementById('p6_commission_next');
        if (ta) ta.value = prior;
        function _refresh() {
            btn.disabled = ta.value.replace(/\s+/g, '').length === 0;
        }
        if (ta && btn) {
            ta.addEventListener('input', _refresh);
            _refresh();
            ta.focus();
        }
    }

    window.__phase6_submit_commission = function () {
        var item = commission_queue[commission_idx];
        var rationale = (document.getElementById('p6_commission_text') || {value: ''}).value;
        // Defensive — the button should be disabled until non-empty, but
        // guard against any code path that bypasses the UI.
        if (rationale.replace(/\s+/g, '').length === 0) {
            return;
        }
        commission_answers[commission_idx] = rationale;
        if (isStudyParticipant()) {
            post('/WebEmrGui/save_commission/', {
                user_id:    window.PHASE6.user_id,
                patient_id: window.PHASE6.patient_id,
                item:       item.code,
                rationale:  rationale
            });
        }
        commission_idx++;
        renderCommissionItem();
    };

    window.__phase6_back_commission = function () {
        // Capture the current (possibly-unsubmitted) text so it isn't
        // lost if the participant Back-then-Forwards.
        var ta = document.getElementById('p6_commission_text');
        if (ta) commission_answers[commission_idx] = ta.value;
        if (commission_idx > 0) {
            commission_idx--;
            renderCommissionItem();
        }
    };

    // ------------------------------------------------------------------
    // Omission stage
    // ------------------------------------------------------------------

    function renderOmissionItem() {
        if (omission_idx >= omission_queue.length) {
            advanceToNextCase();
            return;
        }
        var item = omission_queue[omission_idx];
        var progress = (omission_idx + 1) + ' of ' + omission_queue.length;
        var canGoBack = !_isFirstPrompt('omission');
        var prior = omission_answers[omission_idx] || {reason: '', free_text: ''};

        // v2 task-box layout: step pill + lead + four card-style radio
        // options (Other carries an inline text input) + right-aligned
        // primary submit, with an optional Back button on the left.
        var backBtn = canGoBack
            ? "<input id='p6_omission_back' type='button' value='Back' "
            + "class='lemr-btn secondary' onclick='__phase6_back_omission()'>"
            : "<span></span>";

        function _checked(v) { return prior.reason === v ? " checked" : ""; }

        var html =
              "<span class='task-step-tag'>Rationale · " + progress + "</span>"
            + "<p class='task-lead'>You did not include <b>" + escapeHtml(item.display) +
              "</b> among the most relevant items for this case. Why?</p>"
            + "<div class='task-opt-grid'>"
            +   "<label class='task-opt'><input type='radio' name='p6_om_reason' value='1'" + _checked('1') + ">"
            +     "<span>Considered, but deemed not relevant</span></label>"
            +   "<label class='task-opt'><input type='radio' name='p6_om_reason' value='2'" + _checked('2') + ">"
            +     "<span>Did not notice on screen</span></label>"
            +   "<label class='task-opt'><input type='radio' name='p6_om_reason' value='3'" + _checked('3') + ">"
            +     "<span>Noticed, but didn't carefully consider</span></label>"
            +   "<label class='task-opt'><input type='radio' name='p6_om_reason' value='4'" + _checked('4') + ">"
            +     "<span>Other:</span>"
            +     "<input id='p6_omission_text' type='text' placeholder='please explain' "
            +           "value='" + escapeHtml(prior.free_text || '') + "'>"
            +   "</label>"
            + "</div>"
            + "<div class='task-action-row' style='justify-content:space-between;'>"
            +   backBtn
            +   "<input id='p6_omission_next' type='button' value='Submit and continue' "
            +          "class='lemr-btn primary' disabled "
            +          "onclick='__phase6_submit_omission()'>"
            + "</div>";
        $("#task").html(html);
        $('.shower').hide();

        // Live-validate: enable Submit only when (a) a reason radio is
        // picked AND (b) if the choice is "Other (4)", the free-text field
        // is non-empty.
        var radios = document.querySelectorAll('input[name="p6_om_reason"]');
        var freeTxt = document.getElementById('p6_omission_text');
        var btn     = document.getElementById('p6_omission_next');
        function _omRefresh() {
            var picked = null;
            for (var i = 0; i < radios.length; i++) {
                if (radios[i].checked) { picked = radios[i].value; break; }
            }
            if (!picked) { btn.disabled = true; return; }
            if (picked === '4' && freeTxt && freeTxt.value.replace(/\s+/g, '').length === 0) {
                btn.disabled = true;
                return;
            }
            btn.disabled = false;
        }
        for (var ri = 0; ri < radios.length; ri++) {
            radios[ri].addEventListener('change', _omRefresh);
        }
        if (freeTxt) {
            freeTxt.addEventListener('input', function () {
                if (freeTxt.value.length > 0) {
                    for (var i = 0; i < radios.length; i++) {
                        if (radios[i].value === '4') radios[i].checked = true;
                    }
                }
                _omRefresh();
            });
        }
        _omRefresh();
    }

    window.__phase6_back_omission = function () {
        // Capture the current (possibly-unsubmitted) values so they
        // survive a Back-then-Forwards round trip.
        var radios = document.querySelectorAll('input[name="p6_om_reason"]');
        var freeTxt = document.getElementById('p6_omission_text');
        var picked = '';
        for (var i = 0; i < radios.length; i++) {
            if (radios[i].checked) { picked = radios[i].value; break; }
        }
        omission_answers[omission_idx] = {
            reason:    picked,
            free_text: freeTxt ? freeTxt.value : ''
        };
        if (omission_idx > 0) {
            omission_idx--;
            renderOmissionItem();
        } else if (commission_queue.length > 0) {
            // Cross-stage back: hop from omission #1 back to the LAST
            // commission item so the participant can revise either
            // side of the rationale flow without escaping the case.
            startPhase('commission');
            commission_idx = commission_queue.length - 1;
            renderCommissionItem();
        }
    };

    window.__phase6_submit_omission = function () {
        var item = omission_queue[omission_idx];
        var radios = document.querySelectorAll('input[name="p6_om_reason"]');
        var reason = null;
        for (var i = 0; i < radios.length; i++) {
            if (radios[i].checked) { reason = radios[i].value; break; }
        }
        if (!reason) return;   // defensive — button should be disabled
        var free_text = (document.getElementById('p6_omission_text') || {value: ''}).value;
        if (reason === '4' && free_text.replace(/\s+/g, '').length === 0) return;
        if (isStudyParticipant()) {
            post('/WebEmrGui/save_omission/', {
                user_id:     window.PHASE6.user_id,
                patient_id:  window.PHASE6.patient_id,
                item:        item.code,
                reason_code: reason,
                free_text:   free_text
            });
        }
        omission_idx++;
        renderOmissionItem();
    };

    // ------------------------------------------------------------------
    // Done — advance to next case
    // ------------------------------------------------------------------

    function advanceToNextCase() {
        finishPhase();
        if (typeof _orig_next_case_link_press === 'function') {
            _orig_next_case_link_press();
        } else if (window.next_patient_link) {
            window.location.href = window.next_patient_link;
        }
    }

    // ------------------------------------------------------------------
    // Helpers
    // ------------------------------------------------------------------

    function escapeHtml(s) {
        return String(s).replace(/[&<>"']/g, function (c) {
            return ({
                '&': '&amp;', '<': '&lt;', '>': '&gt;',
                '"': '&quot;', "'": '&#39;'
            })[c];
        });
    }

    // ------------------------------------------------------------------
    // Boot — do NOT start the familiarize phase on page load. Timing is
    // gated on the participant clicking "Start reviewing" on the intro
    // modal (see remove_directions() in emr_3.js, which now triggers
    // startFamiliarizePhase() below). This means time-on-case doesn't
    // start ticking while the participant is still reading the intro
    // card or was called away before actually engaging with the
    // interface — matching Luca's requirement that only true review
    // time is counted.
    // ------------------------------------------------------------------

    function boot() {
        if (!window.PHASE6) {
            console.warn('[phase6] PHASE6 payload missing; flow controller idle.');
            return;
        }
        console.log('[phase6] booting for ' + window.PHASE6.user_id +
                    ' / case ' + window.PHASE6.patient_id +
                    (window.PHASE6.is_intro ? ' (intro)' : '') +
                    ' — waiting for participant to click Start reviewing.');
    }

    // Exposed globally so remove_directions() in emr_3.js can call it.
    window.startFamiliarizePhase = function () {
        // Idempotent — repeated calls (e.g. from double-click on Start
        // reviewing) don't restart the clock.
        if (current_phase === 'familiarize') return;
        startPhase('familiarize');
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', boot);
    } else {
        boot();
    }

})();
