// Global Highcharts defaults. `useHTML: true` on tooltips renders the
// tooltip content as an HTML node (positioned by Highcharts) rather
// than as an SVG element bound to the chart's own SVG root. That lets
// the tooltip escape the chart's bounding box and stack above
// neighbouring cells + main-panel rows — otherwise a tooltip that
// wants to sit above a small chart cell gets clipped or hidden by
// adjacent cells. Combined with the CSS z-index rule for
// .highcharts-tooltip in bs_3.css, tooltips are now always
// legible in the foreground. Safe to call even before any chart is
// constructed.
if (typeof Highcharts !== 'undefined') {
    Highcharts.setOptions({
        tooltip: {
            useHTML: true
        }
    });
}

$(document).ready(function () {

    let navHeight = $('.navbar').outerHeight(true) + 10;
    $(document.body).scrollspy({
        target: '.bs-sidebar',
        offset: navHeight
    });

    $(window).on('load', function () {
        $(document.body).scrollspy('refresh')
    });

    $('a[data-toggle="tab"]').on('shown.bs.tab', function () {
        $(window).trigger('resize')
    });

    $("#progress-notes").addClass('active');

    // bottom labs scroll event
    $(".labbox").bind("scroll", function() {
        send_div_locations();
    });
    $(".half-vitmedbox").bind("scroll", function() {
        send_div_locations();
    });
    $(".medbox").bind("scroll", function() {
        send_div_locations();
    });


    // notes scroll
    $(".report").bind("scroll", function() {
        //note_tracking();
        note_scroll(this.id);
    });
    // note tabs change
    $('.nav-track').on('shown.bs.tab', function () {
        note_tracking();
    });
    // note selection change
    $('.tab-pane').on('shown.bs.tab', function () {
        note_tracking();
    });

    // Update extremes which hides items that do not have data within current time selection
    updateExtremes();

    $('#directions_button').removeAttr("disabled");

    // Force every Highcharts chart to re-measure its container now that
    // DOM ready has fired. Rationale: the highlight-panel chart cells
    // are constructed by inline <script> tags that fire while the HTML
    // parser is still INSIDE the container div — the first cell that
    // wraps to a new row in the floated grid (previously "Base
    // solution" for a specific case × participant combination) hadn't been laid out yet at
    // that moment, so Highcharts measured its parent at 0 px wide and
    // produced a 0×80 SVG. By the time doc-ready fires the layout is
    // stable, so a reflow() gets those charts their real container
    // width. Harmless for charts that were already sized correctly.
    reflowAllCharts();
    // Belt-and-suspenders — some browsers finalize layout on the
    // slightly-later `load` event or after fonts finish loading. A
    // second pass a beat later catches any stragglers.
    setTimeout(reflowAllCharts, 250);
    window.addEventListener('load', reflowAllCharts);

});

function reflowAllCharts() {
    if (!Array.isArray(chartsContainers)) return;
    var fixed = 0;
    var still_zero = [];

    // Two-pass strategy for highlight-panel charts. Pass 1 finds the
    // largest measured cell width across the highlight panel (some
    // Highcharts chart types reserve slightly different amounts of
    // internal space for y-axis labels, credits, etc., which was
    // producing e.g. 217 px med charts next to 227 px lab charts —
    // visually inconsistent). Pass 2 forces every highlight-panel
    // chart to that same target width via setSize, so they all look
    // uniform. Non-highlight-panel charts still take their own
    // measured width — the main-panel layout doesn't have the same
    // visual-uniformity requirement.
    function walk_measure(el) {
        var w = el.clientWidth || el.offsetWidth;
        var probe = el.parentElement;
        var depth = 0;
        while (probe && w <= 1 && depth < 6) {
            w = probe.clientWidth || probe.offsetWidth;
            probe = probe.parentElement;
            depth++;
        }
        return w;
    }
    function is_highlight_chart(c) {
        return c && c.renderTo && c.renderTo.closest &&
               c.renderTo.closest('.highlight_area');
    }

    // Pass 1: find max highlight-panel width.
    var highlight_target = 0;
    for (var i = 0; i < chartsContainers.length; i++) {
        var c = chartsContainers[i];
        if (!c || !c.renderTo || !is_highlight_chart(c)) continue;
        var w = walk_measure(c.renderTo);
        if (w > highlight_target) highlight_target = w;
    }

    // Pass 2: resize.
    for (var i = 0; i < chartsContainers.length; i++) {
        var c = chartsContainers[i];
        if (!c || !c.renderTo) continue;
        try {
            var el = c.renderTo;
            var w = walk_measure(el);
            var h = c.chartHeight || el.clientHeight || 80;
            // For highlight-panel charts, override width to the shared
            // target so all cells match visually.
            if (is_highlight_chart(c) && highlight_target > 1) {
                w = highlight_target;
            }
            if (w > 1) {
                c.setSize(w, h, false);
                fixed++;
            } else {
                still_zero.push(el.id || '(no id)');
                if (typeof c.reflow === 'function') c.reflow();
            }
        } catch (e) {
            /* ignore individual chart failures */
        }
    }
    if (typeof console !== 'undefined' && console.log) {
        console.log('[reflowAllCharts] resized=' + fixed +
                    ' highlight-target=' + highlight_target +
                    ' still-zero-width=' + still_zero.length +
                    (still_zero.length ? '  containers: ' + still_zero.join(', ') : ''));
    }
}

// send timestamp when leaving or refreshing a patient page
window.onbeforeunload = function () {
    if(in_study){
        let curr_timestamp = Date.now();
    }
};


// Listener for whether the mouse is clicked or not.
// Needed so that charts don't update until new time range is selected (prevents lag)
$(document).mousedown(function() {
    down = true;
}).mouseup(function() {
    down = false;
});

// ----------------------------------------------------------------
// Phase-6 cleanup of vestigial eye-tracking / pixelmap plumbing.
//
// `send_div_locations`, `note_tracking`, and `note_scroll` used to
// compute pixel positions of every chart row and notes pane on every
// scroll / tab change so the eye-tracking analysis could correlate
// gaze with what was actually visible on screen. The Phase-4 telemetry
// rip-out removed every server endpoint these functions targeted, so
// they had been silently computing the positions and throwing them
// away. They are kept here as no-op stubs (rather than deleted) only
// because they are referenced from many in-flight call sites and from
// the scroll listeners in $(document).ready; collapsing the bodies
// avoids the per-scroll work without forcing a sweep of every call
// site.
//
// `create_manual_input_post` used to POST a `selections + rating +
// clinical_impact` blob to /WebEmrGui/save_input/ (which wrote
// `manual_input/pat_<id>.txt`). That endpoint has been removed; the
// Phase-6 flow persists everything via the dedicated /save_*/ endpoints
// in phase6_flow.js. The stub here just navigates straight to the next
// case so the next-button flow keeps working.
// ----------------------------------------------------------------
function send_div_locations() { /* phase-6: deprecated eye-tracking helper */ }
function note_tracking()     { /* phase-6: deprecated eye-tracking helper */ }
function note_scroll(curr_id){ /* phase-6: deprecated eye-tracking helper */ }

function create_manual_input_post(new_link) {
    link_press(new_link);
    return false;
}

// Telemetry deactivated (Phase 4): pixelmap and errors-report endpoints
// have been fully removed, including all call sites in this file.










// Gets cookie from webpage
function getCookie(cname) {
    let name = cname + "=";
    let ca = document.cookie.split(';');
    for(let i=0; i<ca.length; i++) {
        let c = ca[i];
        while (c.charAt(0) === ' ') c = c.substring(1);
        if (c.indexOf(name) === 0) return c.substring(name.length,c.length);
    }
    return "";
}

// console log function (not used)
function jsTest(jsTest) {
    console.log(jsTest);
}

// -----------------------------------------------------------------
// Chart-title normalisation helper.
//
// `cleanLabel(s)` strips leading / trailing quote characters that some
// of the pickled display_names entries carry around (e.g.
// '"pH, Arterial"' -> 'pH, Arterial'). It also collapses surrounding
// whitespace.
//
// `chartTitleHtml(s, maxLen)` returns an HTML <span> with the cleaned
// label truncated to `maxLen` characters (default 24) plus a `title`
// attribute holding the full cleaned label so the browser's native
// tooltip surfaces the un-truncated name on hover. Designed for use
// inside Highcharts `title.text` with `title.useHTML: true`.
// -----------------------------------------------------------------
function cleanLabel(s) {
    if (s == null) return '';
    var out = String(s).replace(/^[\s"'“”‘’]+|[\s"'“”‘’]+$/g, '');
    return out;
}

// Draw the "recent value + unit" label in the top-right corner of a lab
// or vital chart using the Highcharts SVG renderer directly. Replaces
// the built-in `credits` we used to rely on for the same purpose —
// credits proved brittle across cells with sparse data, tight y-axis
// ranges, or plot bands, silently dropping the label on some cells even
// though post_data[4] held a valid number (SvO2, Weight, and every
// venous blood-gas cell were reproducible offenders). Manual rendering
// via chart.renderer.text() sidesteps all of Highcharts's credits-path
// heuristics; the label is a plain SVG <text> element under our control.
//
// The chart holds a reference on `chart._recentValueLabel` so we can
// destroy and re-create it on every redraw (extreme change, resize)
// rather than accumulating a stack of stale labels behind the current
// one on the SVG.
function _drawRecentValueLabel(chart, post_data, titleText) {
    // Convenience wrapper for lab / vital charts. Pulls the value from
    // recentValueFromPostData (post_data[4] with a series-last fallback)
    // and the unit from post_data[5], then defers to _setOverlayLabel.
    var val = cleanLabel(recentValueFromPostData(post_data));
    var unit = cleanLabel(String((post_data && post_data[5]) == null ? '' : post_data[5]).replace('null',''));
    _setOverlayLabel(chart, val, unit, titleText);
}

function _drawMedRecentValueLabel(chart, post_data, titleText) {
    // Med charts store dose values and units on post_data[1] — one
    // [value, unit] pair per data point. Grab the last non-null pair
    // so the label reflects the most recent dose or bag-change event.
    if (!chart || !post_data) return;
    var series = post_data[0] && post_data[0][0];
    var data = series && series.data;
    if (!data || !data.length) { _setOverlayLabel(chart, '', '', titleText); return; }
    var ann = post_data[1] || [];
    // Iterate from the end so the newest annotation wins. Skip entries
    // whose value or unit is null / empty so we don't render '[null null]'.
    for (var i = ann.length - 1; i >= 0; i--) {
        var pair = ann[i];
        if (!pair) continue;
        var v = cleanLabel(pair[0]);
        var u = cleanLabel(pair[1]);
        if (v || u) { _setOverlayLabel(chart, v, u, titleText); return; }
    }
    _setOverlayLabel(chart, '', '', titleText);
}

function _setOverlayLabel(chart, val, unit, titleText) {
    if (!chart) return;
    // A single HTML overlay per cell that renders BOTH the chart title
    // (left, flex-grow, truncate with ellipsis when it doesn't fit) and
    // the recent value + unit (right, fixed width). Previously the title
    // was rendered by Highcharts itself and the value+unit was a separate
    // absolute-positioned overlay — the two competed for the same top-row
    // pixels and the title kept getting chopped to "N…" / "Lym…" on
    // narrow cells (CBC / Differential rows fit 4 cells per section, so
    // each cell is only ~150 px wide). Owning both labels in the same
    // flex row means the title never runs into the value column: it
    // takes whatever horizontal space remains after the value+unit block
    // reserves its own width, and text-overflow:ellipsis handles the
    // rest. The Highcharts title config is disabled by the caller.
    var container = chart.container && chart.container.parentNode;
    if (!container) return;
    val  = (val  == null) ? '' : String(val);
    unit = (unit == null) ? '' : String(unit);
    // cleanLabel strips embedded quote wrappers (e.g. '"Bili, Total"',
    // '"PCO2, Arterial"') that some display_names.p entries carry over
    // from the pickle. We used to run this inside chartTitleHtml; when
    // title rendering moved into the overlay the step was dropped and
    // quotes came back. Applying it here restores clean titles like
    // "Bili, Total" instead of "\"Bili, Total\"".
    titleText = cleanLabel(titleText);
    // Find or create the overlay div. Store it on the chart so
    // redraws update the same DOM node instead of stacking.
    var overlay = chart._recentValueOverlay;
    if (!overlay) {
        overlay = document.createElement('div');
        overlay.className = 'lemr-recent-value-overlay';
        // Compact single-line title band anchored to the top of the cell.
        // Chart configs reserve 22 px of spacingTop so the plot area
        // starts just below this overlay and the y-axis top label sits
        // fully within the plot area (no more clipping). `background:#fff`
        // keeps the band visually distinct from the chart. Value and
        // unit are rendered INLINE (e.g. "20 mmHg") to fit on one row
        // and keep the band short.
        overlay.style.cssText = 'position:absolute;top:0;left:0;right:0;' +
            'height:20px;padding:3px 12px 0 12px;box-sizing:border-box;' +
            'display:flex;align-items:center;overflow:hidden;' +
            'background:transparent;pointer-events:none;font-family:inherit;' +
            'z-index:5;color:#000;';
        var cs = window.getComputedStyle(container);
        if (cs && cs.position === 'static') {
            container.style.position = 'relative';
        }
        container.appendChild(overlay);
        chart._recentValueOverlay = overlay;
    }
    var escTitle = _escapeHtmlForOverlay(titleText);
    var escVal   = _escapeHtmlForOverlay(val);
    var escUnit  = _escapeHtmlForOverlay(unit);
    // Title: flex-grow so it takes everything the value column doesn't
    // need. `title=` attribute preserves the full untruncated text so
    // hovering the ellipsised title shows the whole label in a browser
    // tooltip — critical when the label is cropped to "Neutrophils Abs…".
    var titleSpan = titleText
        ? '<span title="' + escTitle + '" ' +
              'style="flex:1 1 auto;min-width:0;white-space:nowrap;overflow:hidden;' +
              'text-overflow:ellipsis;font-size:12px;line-height:14px;">' +
              escTitle + '</span>'
        : '<span style="flex:1 1 auto;min-width:0;"></span>';
    // Value + unit inline (single line, e.g. "20 mmHg"). Slightly
    // smaller unit font gives visual separation without stacking.
    // flex:0 0 auto so the value block never surrenders width to the
    // title's overflow; margin-left keeps a small gap between the
    // truncated title ellipsis and the value.
    var valBlock = '';
    if (val || unit) {
        valBlock =
          '<span style="flex:0 0 auto;margin-left:6px;white-space:nowrap;font-size:12px;">' +
            (val  ? escVal  : '') +
            (val && unit ? ' ' : '') +
            (unit ? '<span style="font-size:10px;">' + escUnit + '</span>' : '') +
          '</span>';
    }
    overlay.innerHTML = titleSpan + valBlock;
}

function _escapeHtmlForOverlay(s) {
    return String(s)
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

// Recent-value fallback for the top-right credits label on lab charts.
// post_data[4] carries the pickled `recent_value` slot for each lab, but
// several labs in some cases ship with that slot empty (Glucose, Calcium,
// Ionized Ca, Lactate, Lipase, Osmolality in the interface demo case are
// the ones we've spotted). When that happens the credits render as an
// empty top-right corner even though the chart clearly has data points.
// Fallback: pluck the y of the last numeric point in the series so the
// participant always sees the latest measurement above each chart.
function recentValueFromPostData(post_data) {
    var v = post_data && post_data[4];
    if (v !== null && v !== undefined && String(v).trim() !== '' && String(v).trim() !== 'null') {
        return v;
    }
    var series = post_data && post_data[0];
    if (!series || !series.length) return '';
    for (var s = 0; s < series.length; s++) {
        var data = series[s] && series[s].data;
        if (!data || !data.length) continue;
        for (var i = data.length - 1; i >= 0; i--) {
            var p = data[i];
            var y = null;
            if (Array.isArray(p) && p.length >= 2) y = p[1];
            else if (p && typeof p === 'object' && 'y' in p) y = p.y;
            if (y !== null && y !== undefined && y !== '' && !isNaN(y)) {
                return y;
            }
        }
    }
    return '';
}

// -----------------------------------------------------------------
// Compute the x-axis {min,max} for a highlight-panel chart. The panel
// is a set of summary sparklines — the participant reads the full-
// scale timeline in the main All-patient-data panel below — so each
// sparkline should auto-fit to its own data rather than sharing a
// global window. That fixes items whose measurements sit in a narrow
// slice of a long case (e.g. "Base solution" infusing over 12h in a
// 7-day case): the shared-window approach compressed those into an
// invisible hairline; auto-fit makes them fill the cell.
//
// Falls back to globalMin/globalMax (case's full range) if the data
// array is empty or degenerate — so an empty chart still renders a
// visible axis rather than collapsing to zero width. Handles the
// single-timestamp case by padding ±1 hour so the marker isn't
// clipped at the axis edge.
// -----------------------------------------------------------------
function highlightXAxisRange(dataArr) {
    var fallback = { min: globalMin, max: globalMax };
    if (!dataArr || dataArr.length === 0) return fallback;
    var xs = [];
    for (var i = 0; i < dataArr.length; i++) {
        var p = dataArr[i];
        if (p && typeof p[0] === 'number' && isFinite(p[0])) xs.push(p[0]);
    }
    if (xs.length === 0) return fallback;
    var lo = Math.min.apply(null, xs);
    var hi = Math.max.apply(null, xs);
    if (lo === hi) {
        // Single unique timestamp — give the axis 2h of visible width.
        return { min: lo - 3600000, max: hi + 3600000 };
    }
    // 5% padding on each side so points at the extremes aren't clipped
    // by the spacingLeft / spacingRight.
    var span = hi - lo;
    return { min: lo - span * 0.05, max: hi + span * 0.05 };
}

function chartTitleHtml(s, maxLen) {
    var clean = cleanLabel(s);
    if (!maxLen || maxLen < 4) maxLen = 24;
    var display = clean;
    if (clean.length > maxLen) {
        display = clean.substring(0, maxLen - 1).replace(/\s+$/, '') + '…';
    }
    // HTML-escape for safety: titles can contain & or quotes once we
    // start stripping. The `title` attribute also needs escaping.
    function esc(v) {
        return String(v)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }
    // white-space:nowrap + text-overflow:ellipsis truncates the title
    // with a "…" when it doesn't fit. The `max-width: calc(100% - 38px)`
    // reserves a 38 px gutter on the right so the truncated title cannot
    // physically overlap the value/unit overlay we render in the top-
    // right of every cell (see _setOverlayLabel). Without the gutter,
    // long med titles like "epinephrine 16" ran directly into "Zero mL"
    // and the two labels overlapped illegibly. 38 px is a compromise:
    // enough room for typical short units ("mg/dL", "bpm", "%") without
    // crushing the title on narrow cells (CBC / Differential rows fit 4
    // cells per section, so each cell is only ~150 px wide, and a 60 px
    // gutter was chopping "Neutrophils" down to "N…"). Cells with wide
    // units like "X10E+09/L" (~55 px) will visually kiss the truncated
    // title's ellipsis but stay legible. The full untruncated label is
    // still exposed via the `title=` attribute for hover.
    return '<span title="' + esc(clean) + '" style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis;display:inline-block;max-width:calc(100% - 38px);">' +
        esc(display) + '</span>';
}

// window alert function (not used)
function sendAlert(myalert){
// disabled alert here
    console.log(myalert);
         //window.alert(myalert);
}

function get2D( num ) {
    return ( num.toString().length < 2 ? "0"+num : num ).toString();
}

// Global Variables
let only_show_highlights = false; // Set true when non highlighted data fields should be hidden
let chartsContainers = []; // Holds all of the promoted charts
// `var` here (not `let`) so that phase6_flow.js can read window.selected_items.
// In modern browsers, top-level `let` creates a script-scoped binding that is
// NOT attached to the global object. `var` keeps the same in-script semantics
// but also makes the array reachable from other scripts loaded on the page.
var selected_items = []; // The names of the labs that are in the promoted region
let chartrowids = []; // The ids of all the chart rows
let selectedMin; // The min time taken from the time chart range selector
let selectedMax; // The max time taken from the time chart range selector
// globalMin / globalMax track the case's FULL time range and are never
// updated after setDefaultTimes() runs. Used by the highlight-panel
// chart functions (get_*_highlight_area) so an AI-suggested med whose
// data happens to fall outside the participant's current time-selector
// window still renders visibly (otherwise meds with only-historical
// data, e.g. "Base solution" infusing days before the selected window,
// produced empty grey cells).
let globalMin;
let globalMax;
let data_max; // the max time loaded to interface
let down = false; // True is the mouse is currently clicked.
let patient_id = 0; // holds current patient id
let short_patient_id = 0; // holds a string of the last three digits of the patient id
let user_id = '';  // holds the current user id
let in_study = false; // false if first_four (interface demo), true otherwise
let selection_screen = false; // true when on selection screen
let case_difficulty = false;
let paused_study = true;
let recording = false;
let issue_box = false;
let clinical_impact = 0;
let next_patient_link = '';
let study_arm = '';
let show_highlights = ''; // added

// sets global patient_id
function set_ids(curr_id, curr_user_id){
    patient_id = curr_id;
    let str_id = String(patient_id);
    short_patient_id = str_id.slice(-3);
    user_id = curr_user_id;
    if (curr_user_id !== 'first_four'){
        in_study = true
    }
}

// sets only_show_highlights variable
function set_only_show_highlights(bool_val){
    only_show_highlights = bool_val;
}

// sets show_highlights variable - added
//function set_show_highlights(show_highl){
//    show_highlights = show_highl;
//}

// sets arm variable [C: SV, 1: AHV, 2: APV]
function set_arm(arm_val){
    study_arm = arm_val;
}

// Assigns the global min and max time to global variables (called once when page is loading)
function setDefaultTimes(global_time){
    selectedMin = global_time.min_t;
    selectedMax = global_time.max_t;
    // Frozen copies for the highlight-panel charts (see globalMin /
    // globalMax declarations near the top of this file).
    globalMin   = global_time.min_t;
    globalMax   = global_time.max_t;
    data_max = global_time.max_t;
}

// Shows loading screen after navigation buttons have been clicked
function show_loading(){
    $('#loading_new_patient').show();
}

// Removes directions div and hides loading text. This is the single
// gate for the case timer: the phase6 flow controller no longer starts
// the "familiarize" phase on page load (see phase6_flow.js boot()), so
// time-on-case only begins counting the moment the participant hits
// Start reviewing here. Participants can pause between cases simply by
// not clicking Start reviewing — no more "Take a break" button, no
// more side-effect that skipped cases on return.
function remove_directions(){
    $('#directions').hide();
    $('#loading_new_patient').hide();
    paused_study = false;
    send_div_locations();
    note_tracking();
    // Kick off the phase6 timer. Guarded by the flow controller itself
    // so it's safe if this is somehow called twice.
    if (typeof window.startFamiliarizePhase === 'function') {
        window.startFamiliarizePhase();
    }
}

// The "Take a break" button has been removed from the New-Patient card
// (see index_3.html). Take-a-break's home-page navigation had a side
// effect that advanced the participant's next-case counter by two on
// return — data-integrity risk during the pilot. Participants now pause
// simply by not clicking "Start reviewing" yet; the phase timer is
// gated on that click (see remove_directions() + phase6_flow.js
// boot()), so waiting on the intro card does not accrue time. The
// take_a_break() function is retained as a no-op only in case any
// stale rendered page still contains the button; the safest thing it
// can do is nothing.
function take_a_break(_user_id){
    console.warn('[phase6] take_a_break() is deprecated and is now a no-op. ' +
                 'Participants pause by not clicking Start reviewing.');
    return false;
}

function get_formatted_date(ms_date){
    let js_date = new Date(ms_date);
    let display_date = 0;
    if (js_date.getHours() < 20) {
        display_date = ' ' + get2D(js_date.getMonth() + 1) + '/' + get2D(js_date.getDate()) + ' ' + get2D(js_date.getHours() + 4) + ':' + get2D(js_date.getMinutes());
    }else{
        display_date = ' ' + get2D(js_date.getMonth() + 1) + '/' + get2D(js_date.getDate() + 1) + ' ' + get2D(js_date.getHours() - 20) + ':' + get2D(js_date.getMinutes());
    }

    return display_date;
}

// Updates the min and max time for each of the promoted labs (called every time the time selector moves and...
// ...every time a lab is promoted)
function updateExtremes(){
    //update time axes
    $("#selectedTimes").text(get_formatted_date(selectedMin) + ' to ' + get_formatted_date(selectedMax));
    try {
        $("#lab-time1").highcharts().xAxis[0].setExtremes(selectedMin, selectedMax);
        $("#lab-time2").highcharts().xAxis[0].setExtremes(selectedMin, selectedMax);
        $("#lab-time3").highcharts().xAxis[0].setExtremes(selectedMin, selectedMax);
        $("#lab-time4").highcharts().xAxis[0].setExtremes(selectedMin, selectedMax);
        $("#lab-time5").highcharts().xAxis[0].setExtremes(selectedMin, selectedMax);
        $("#lab-time6").highcharts().xAxis[0].setExtremes(selectedMin, selectedMax);
        $("#lab-time11").highcharts().xAxis[0].setExtremes(selectedMin, selectedMax);
        $("#lab-time12").highcharts().xAxis[0].setExtremes(selectedMin, selectedMax);
        $("#lab-time13").highcharts().xAxis[0].setExtremes(selectedMin, selectedMax);
        $("#lab-time14").highcharts().xAxis[0].setExtremes(selectedMin, selectedMax);
        $("#lab-time15").highcharts().xAxis[0].setExtremes(selectedMin, selectedMax);
        $("#lab-time16").highcharts().xAxis[0].setExtremes(selectedMin, selectedMax);
    }catch(err){}
    // Time-selector propagation policy (updated per Luca's spec):
    //   • Every chart — highlight-panel AND main-panel — follows the
    //     time selector. Dragging the selector re-scopes what the
    //     participant sees on every card in both panels, in lockstep.
    //   • Items that appear in the highlight panel (i.e. any id in
    //     `window.labs_to_highlight`, whether it was AI-flagged as
    //     legitimately relevant OR planted as an intentional error)
    //     must NEVER be hidden by the "no points in selected window"
    //     rule — the participant needs to see the row wherever it
    //     appears (highlight panel cell AND main-panel row), even when
    //     the current window is empty. An empty chart on a visible row
    //     is fine; a disappeared row is not.
    //   • Every other main-panel row keeps the existing behaviour:
    //     hide when it has no points in the selected window (or when
    //     only_show_highlights is on and the row isn't in
    //     selected_items).
    for (let i = 0; i < chartsContainers.length; i++) {
        var _renderTo = chartsContainers[i].renderTo;
        var _isHighlightPanelChart = !!(_renderTo && _renderTo.closest && _renderTo.closest('.highlight_area'));

        let notPoints = true;
        let currData = [];
        for (let q=0; q < chartsContainers[i].xAxis[0].series.length; q++) {
            currData = currData.concat(chartsContainers[i].xAxis[0].series[q].xData);
        }
        for(q=0;q<currData.length;q++){
            if (currData[q] >= selectedMin && currData[q] <= selectedMax){
                notPoints = false;
                break;
            }
        }

        var _rowid = chartrowids[i];
        var _isAiHighlighted = !!(typeof window !== 'undefined' && window.labs_to_highlight &&
                                  jQuery.inArray(String(_rowid), window.labs_to_highlight) !== -1);
        // A row is "protected from hiding" if:
        //   - the chart itself lives in the highlight panel (every cell
        //     there is highlighted by construction), OR
        //   - the row's id is in the AI-highlighted list — which is the
        //     mirror rule that keeps the main-panel row visible for the
        //     same item.
        var _protectedFromHide = _isHighlightPanelChart || _isAiHighlighted;

        // Selectors are scoped so a hide/show on a shared id doesn't
        // bleed across the two panels (main-panel and highlight-panel
        // rows share id="{{ lab }}" or id="{{ med }}").
        var _selector = _isHighlightPanelChart
            ? ".highlight_area div[id='"+chartrowids[i]+"'], .highlight_area div[id='"+chartrowids[i]+"_highlight']"
            : "#entire_all_patient_data_area div[id='"+chartrowids[i]+"']";

        // Extend the x-axis max by ~3% of the window on both sides so
        // data points at the exact selectedMin / selectedMax boundary
        // are not clipped or unhittable at the edge. Without this the
        // rightmost point renders half-inside / half-outside the plot
        // area, its hover hit-target is missed, and Highcharts keeps
        // showing the tooltip from the second-to-last point instead.
        var _pad = (selectedMax - selectedMin) * 0.03;
        var _xMin = selectedMin - _pad;
        var _xMax = selectedMax + _pad;

        if (_protectedFromHide) {
            // Follow the time selector but never hide.
            chartsContainers[i].xAxis[0].setExtremes(_xMin, _xMax);
            $(_selector).show();
            chartsContainers[i].reflow();
        } else if (notPoints || only_show_highlights && jQuery.inArray( chartrowids[i], selected_items ) === -1 ) {
            $(_selector).hide();
        } else {
            chartsContainers[i].xAxis[0].setExtremes(_xMin, _xMax);
            $(_selector).show();
            chartsContainers[i].reflow();
        }
    }
    send_div_locations();
}

// Shows group when it contains items (prevents empty groups from being displayed, called during page loading)
function showgroup(id) {
    $("div[id='"+id+"']").show();
}


// Visually paints a data-item row as AI-highlighted. Called at page load
// (for every item the AI flagged as relevant for this case). Selection
// state (selected_items) is mutated by activate() ONLY, not by this
// function.
//
// IMPORTANT: the same `id` exists in the DOM twice — once in the
// Highlighted-data panel at the top, once in the All-patient-data panel
// below. Per Luca's QA spec, the yellow AI-highlight should appear ONLY
// in the Highlighted-data panel. If we painted both, participants would
// be able to identify AI-highlighted items in the main panel by their
// background colour — which leaks the AI's suggestion outside the place
// the prototype is supposed to surface it, and (more importantly) lets
// participants tell apart correct vs planted highlights by visual cue.
//
// Paints the yellow AI-highlight tint on every place a given item shows
// up on screen.
//
// `.highlight_area` is the wrapper around the Highlighted-data panel and
// `#entire_all_patient_data_area` is the main All-patient-data panel
// container (see index_3.html). Per Luca's QA spec, an item that the AI
// has surfaced in the Highlighted-data panel — whether truly relevant or
// a planted commission error — must ALSO tint yellow in its native
// location in the All-patient-data panel. That way the participant can
// see, while scanning the main panel, which rows the AI has flagged. The
// tint is purely visual and does NOT mark the row as selected (that's
// .is-user-selected, added by activate() on click).
//
// Notes on selector scope:
//   • Highlight-panel labs/vitals reuse the canonical id ("K", "VTHR");
//     meds and I/O use a derived `<id>_highlight` id. We paint both
//     within the panel so the call is symmetric for every type.
//   • Main-panel rows always use the canonical id (no `_highlight`
//     suffix), so `#entire_all_patient_data_area div[id='X']` is the
//     unambiguous selector.
function highlight(id){
    // Selector strategy:
    //   • Highlight panel: lab/vital rows reuse the canonical id ("K",
    //     "VTHR"); meds and I/O use `<id>_highlight`. We paint both
    //     within `.highlight_area` so every type tints symmetrically.
    //   • All-patient-data panel: rows always use the canonical id (no
    //     `_highlight` suffix). We target the row classes directly
    //     (.chartrow, .vitalrow, .medrow, .iorow) so the selector doesn't
    //     depend on the container id surviving template changes, and we
    //     `:not(.chartcolH)` to avoid double-matching panel cells which
    //     also carry .chartrow.
    let panelSel = ".highlight_area div[id='"+id+"'], "
                 + ".highlight_area div[id='"+id+"_highlight']";
    let mainSel  = ".chartrow[id='"+id+"']:not(.chartcolH), "
                 + ".vitalrow[id='"+id+"'], "
                 + ".medrow[id='"+id+"'], "
                 + ".iorow[id='"+id+"']";

    var $panel = $(panelSel);
    var $main  = $(mainSel);
    // Apply via class for !important specificity (defined in bs_3.css);
    // keep the inline fallback so the tint still appears even if the
    // bundled CSS is overridden by a downstream stylesheet.
    $panel.addClass('lemr-ai-highlighted').css("background-color", "#ffffc1");
    $main.addClass('lemr-ai-highlighted').css("background-color", "#ffffc1");

    // One console line per call so the coordinator can verify in dev
    // tools that the page-load loop is matching the expected DOM rows.
    if (typeof console !== 'undefined' && console.log) {
        console.log('[highlight] id=' + id +
                    '  panel matches=' + $panel.length +
                    '  main matches=' + $main.length);
    }

    if (case_difficulty){
        $('#next_case_button').css("background-color","green");
    }else{
        $('#next_case_button').css("background-color","#82E0AA");
    }
}

// Reverses the visual painting from highlight(). Visual only — selection
// state is mutated by activate(). Mirrors highlight()'s scope so an
// un_highlight() call clears the tint in both the highlight panel and
// the All-patient-data panel.
function un_highlight(id){
    let panelSel = ".highlight_area div[id='"+id+"'], "
                 + ".highlight_area div[id='"+id+"_highlight']";
    let mainSel  = ".chartrow[id='"+id+"']:not(.chartcolH), "
                 + ".vitalrow[id='"+id+"'], "
                 + ".medrow[id='"+id+"'], "
                 + ".iorow[id='"+id+"']";
    $(panelSel).removeClass('lemr-ai-highlighted').css("background-color","");
    $(mainSel) .removeClass('lemr-ai-highlighted').css("background-color","");
}

// "hid" data field — orange tint. Visual only; selection state is the
// caller's responsibility if anyone ends up using this code path.
function hid(id){
    let curr = "div[id='"+id+"']";
    $(curr).css("background-color","#FFC300");
}

//changes note button colors
function setColor(curr){
    $(curr).parent().parent().children().children().removeClass('red-text');
    $(curr).addClass('n-button');
    $(curr).addClass('v-button');
    $(curr).addClass('red-text');
    //remove_vertical_point(false);  // this removes bands and dotted lines
}

//  Add vertical plot line to each graph
//
//  When called from a "Mark date" button (from_note === true), `this` is
//  the button DOM node. We treat the button as a TOGGLE: a second click
//  on the same button clears the band; clicking a different note button
//  swaps the band over to that date instead of stacking marks.
function add_vertical_point(point_time, from_note){
    if (typeof from_note !== 'undefined'){
        // Identify which "Mark date" button is currently active (if any) so
        // we can decide whether this click is a toggle-off or a swap.
        var prev_active_btn = document.querySelector('.m-button.mark-date-active');
        var clicked_btn     = this;  // the <button class="m-button"> we were attached to

        // Always clear any existing mark first so a swap doesn't stack
        // plot bands on top of each other.
        remove_vertical_point(true);
        if (prev_active_btn) {
            prev_active_btn.classList.remove('mark-date-active');
            prev_active_btn.style.background = '';
        }

        // Toggle off: same button clicked again -> done after the clear above.
        if (prev_active_btn === clicked_btn) {
            $("#selectedTime").text('');
            $("#selectedP").css('background', '#222222');
            return;
        }

        setColor(this.previousSibling.previousElementSibling);
        // Visually mark this button as the active one so a second click toggles off.
        if (clicked_btn && clicked_btn.classList) {
            clicked_btn.classList.add('mark-date-active');
            clicked_btn.style.background = '#F5F5DC';
        }
        // floor to start of day
        let coeff = 1000 * 60 * 60 * 24;
        let round_time = point_time - (point_time%coeff) + 3600000;
        let band_start = new Date(round_time);
        let band_end = band_start.getTime() + coeff;
        for (i = 0; i < chartsContainers.length; i++) {
            chartsContainers[i].xAxis[0].addPlotBand({
                from: band_start,
                to: band_end,
                color: '#E0E0E0',
                id: 'plot-line-1'
            });
        }
        if (band_start < selectedMin){
            selectedMin = band_start;
            // select time selector and update
            $("#time_selector").highcharts().xAxis[0].setExtremes(selectedMin, selectedMax);
        }
        if (band_end > selectedMax) {
            selectedMax = band_end;
            // select time selector and update
            $("#time_selector").highcharts().xAxis[0].setExtremes(selectedMin, selectedMax);
        }
        let st_display = ' ' + get2D(band_start.getMonth() + 1) + '/' + get2D(band_start.getDate() + 1);
        $("#selectedTime").text(st_display);
        $("#selectedP").css('background', 'white');
    }else{
        remove_vertical_point(true);
        for (let i = 0; i < chartsContainers.length; i++) {
            chartsContainers[i].xAxis[0].addPlotLine({
                value: point_time,
                color: 'black',
                dashStyle: 'dash',
                width: 1,
                id: 'plot-line-1'
            });
        }
        if (point_time < selectedMin) {
            selectedMin = point_time;
            // select time selector and update
            $("#time_selector").highcharts().xAxis[0].setExtremes(selectedMin, selectedMax);
        }
        if (point_time > selectedMax) {
            selectedMax = point_time;
            // select time selector and update
            $("#time_selector").highcharts().xAxis[0].setExtremes(selectedMin, selectedMax);
        }
        $("#selectedTime").text(get_formatted_date(point_time));
        $("#selectedP").css('background', 'white');
    }
}

//  Remove the user-placed marker (plotLine for a single timestamp, plotBand
//  for a full-day "Mark date" range) from every chart. Highcharts has
//  separate removePlotLine / removePlotBand methods, so we call both —
//  removePlotLine alone leaves the day-shaded band painted on screen,
//  which is what made the Mark-date button look irreversible.
function remove_vertical_point(display_recent_24){
    for (let i = 0; i < chartsContainers.length; i++) {
        try { chartsContainers[i].xAxis[0].removePlotLine('plot-line-1'); } catch (e) {}
        try { chartsContainers[i].xAxis[0].removePlotBand('plot-line-1'); } catch (e) {}
        if (display_recent_24){
            chartsContainers[i].xAxis[0].addPlotBand({
                from: data_max-86400000,
                to: data_max,
                color: '#fce1c9',
                id: 'plot-line-1'
                });
        }
    }
    $("#selectedP").css('background', '#222222');
}

function activate_continue_button(selection, is_case_difficulty){
    if (!(issue_box || recording)){
        $('#next_case_button').removeAttr("disabled");
    }
    if (selected_items.length > 0){
        $('#next_case_button').css("background-color","green");
    }else{
        $('#next_case_button').css("background-color","#ED1D1D");
    }

    if (is_case_difficulty) {
        case_difficulty = selection;
    }
    else{
        clinical_impact = selection;
    }
}

// Creates rounding report screen
/*
function create_rounding_report_screen(next_link) {
    selection_screen = true;
    next_patient_link = next_link;
    let task_text =
        "<p>Please briefly present the patient as if you were presenting during morning rounds, including pertinent positives and negatives, as "
        + "well as your assessment and management plan for the day.</p>"
        + "<p>Use the audio recorder to record your presentation.</p>"
        + "<p>Start the recording with '<b>" + user_id + "</b> rounding for <b>" + short_patient_id + "</b>.'</p>"
        + "<hr>Then click <input id='rate_complexity_continue' type='button' value='continue' "
        + "onclick='create_rate_complexity_screen()'>.";
    $("#task").html(task_text);
    //next is create rate complexity screen
}
*/

function create_rounding_report_screen(next_link) {
    console.log('Function create_rounding_report_screen in emr_3.js called to change instructions in the task box.');
    selection_screen = true;
    next_patient_link = next_link;
    let task_text =
          "<span class='task-step-tag'>Step 2 · Present</span>"
        + "<p class='task-lead'>Present this patient as if rounding.</p>"
        + "<p class='task-body'>Include positives and negatives, plus your assessment and plan for the day. "
        +   "Start with: 'Clinician <b>" + user_id + "</b> rounding for patient <b>" + short_patient_id + "</b>.'</p>"
        + "<hr class='task-divider'>"
        + "<div class='task-action-row'>"
        +   "<input id='create_selection_screen' type='button' value='Continue' class='lemr-btn primary' "
        +         "onclick='create_selection_screen()'>"
        + "</div>";
    $("#task").html(task_text);
    selection_screen = true;
}


// Creates complexity rating screen
function create_rate_complexity_screen(){
    let task_text =
        "Rate the level of effort you exerted when becoming up to date with this patient’s problems and latest data:<br> "
        + '<form><input type="radio" name="diff" value="1" onclick="activate_continue_button(1, true);">  1. low<br>'
        + '<input type="radio" name="diff" value="2" onclick="activate_continue_button(2, true);">  2. below-average<br>'
        + '<input type="radio" name="diff" value="3" onclick="activate_continue_button(3, true);">  3. average<br>'
        + '<input type="radio" name="diff" value="4" onclick="activate_continue_button(4, true);">  4. above-average<br>'
        + '<input type="radio" name="diff" value="5" onclick="activate_continue_button(5, true);">  5. high<br>'
        + '</form>';

    if (study_arm === 'C') { // if control -> next is selection screen
        task_text +=
            "<hr>Then click <input id='selection_screen_continue' type='button' value='continue' "
            + "onclick='create_selection_screen()'>.";
    } else if (study_arm === '1') {// if arm one -> next is next_link press
        task_text +=
            "<hr>Then click <input id='next_case_continue' type='button' value='next case' "
            + "onclick='next_case_link_press()'>";
    } else if (study_arm === '2'){    // if arm two -> next is show additional information
        task_text +=
           "<hr>Then click <input id='show_additional_info_continue' type='button' value='continue' "
           + "onclick='show_additional_information()'>.";
    }
    $("#task").html(task_text);
}

// Creates selection screen (original version)
function create_selection_screen_original(){
    let task_text =
            "Select the information that you found to be the most relevant for this patient, when becoming up to date with this patient’s problems and latest data.\n"
            + "<hr>Then click <input id='rounding_report_continue' type='button' value='next case' "
            + "onclick='next_case_link_press()'>.";
    $('.chartcol1').each(function (i, obj) {
        $(obj).html("<span class='glyphicon glyphicon-unchecked' aria-hidden='true'></span>");
    });
    $('.shower').show();
    $("#task").html(task_text);
    send_div_locations();
}


// Creates selection screen
function create_selection_screen(){

    console.log('Function create_selection_screen in emr_3.js called to change instructions in the task box.');
    let task_text =
          "<span class='task-step-tag'>Step 3 · Select</span>"
        + "<p class='task-lead'>Pick the most relevant items.</p>"
        + "<p class='task-body'>Click on the items in the data and medication panels on the left "
        +   "that you found most relevant to understanding this patient.</p>"
        + "<hr class='task-divider'>"
        + "<div class='task-action-row'>"
        +   "<input id='rounding_report_continue' type='button' value='Next' class='lemr-btn primary' "
        +         "onclick='create_error_check_screen()'>"
        + "</div>";
    $('.chartcol1').each(function (i, obj) {
        $(obj).html("<span class='glyphicon glyphicon-unchecked' aria-hidden='true'></span>");
    });
    $('.shower').show();
    $("#task").html(task_text);
    send_div_locations();
}

// Creates screen to gather information on error determinants


function create_error_check_screen(){

    console.log('Function create_error_check_screen in emr_3.js called to check for errors of omission and commission.');

    // Gather items selected as relevant by the participant:
    console.log('User '+user_id+' selected the following items: '+selected_items+'.');

    // Gather items selected as relevant by the judges:
    // Replace with code reading these from file data_items_relevant.txt
    let data_items_relevant = ['PLT'];
    console.log('The following labs were annotated by judges as relevant : '+data_items_relevant);

    // Compare the two lists of items to determine errors of omission:
    //    for (item in selected_items) {
    //        if (data_items_relevant.includes(item) {
    //            console.log(item+'was selected as relevant and annotated as relevant')
    //      }else {
    //            console.log(item+'was selected as relevant but not annotated as relevant')
    //        }
    //    };


    // Compare user-selected relevant items with relevant items indicated by judges here



    console.log('Function create_omission_error_check_screen in emr_3.js called to inquire about any omission errors committed.');
    create_commission_error_check_screen();
  }



function create_commission_error_check_screen(){

// If any errors of commission are identified, load the appropriate screen - else, skip to errors of omission
    console.log('Function create_commission_error_check_screen in emr_3.js called to change instructions in the task box.');
    let task_text_original =
            "Please answer the following questions:\n"
            // For each error of commission, question:
            + "<hr>You indicated that PARAMETER Y was particularly relevant to understanding this patient case. Why?\n"
            + '<form><input type="radio" name="diff" value="1" onclick="activate_continue_to_omission_errors_button(1);">  Free text<br>'
            + '</form><hr>'
            + "When done, click <input id='continue_to_omission_error_screen' type='button' value='next set of questions' "
            + "onclick='create_omission_error_check_screen()'>.";

    // Replace with appropriate loop here
    let data_item = "EXAMPLEDATAITEM"
    let task_text =
            "Please answer the following questions:\n"
            // For each error of commission, question:
            + "<hr>1. You deemed " + data_item + " particularly relevant to understanding this patient case. Why?<br><br>\n"
            + '<form method="post"><input type="text" name="commission" id="FreeTextCommission" value="Please explain"> '
            + "<input type='button' value='Submit' onclick='activate_continue_to_omission_errors_button(1)'>"
            + '</form><hr>'
            + "Once you are done, click <input id='continue_to_omission_error_screen' type='button' value='next set of questions' "
            + "onclick='create_omission_error_check_screen()'>.";




    $('.chartcol1').each(function (i, obj) {
    $(obj).html("<span class='glyphicon glyphicon-unchecked' aria-hidden='false'></span>");
    });
    $('.shower').hide();
    $("#task").html(task_text);
    console.log('Discussion of commission errors initiated.');
    console.log('Function create_commission_error_check_screen in emr_3.js called to save patient ID and timestamp the discussion of commission errors was initiated.');
}


function create_omission_error_check_screen(){

  // If any errors of omission are identified, load the appropriate screen - else, skip to next case

    console.log('Function create_omission_error_check_screen in emr_3.js called to change instructions in the task box.');
    let data_item = "EXAMPLEDATAITEM"
    let task_text =
            "Please answer the following questions:\n"
            // For each error of omission, question:
            + "<hr>You did not include " + data_item + " among the most relevant items to understanding this case. Why?<br>"
            + '<form><input type="radio" name="diff" value="1" onclick="activate_continue_to_next_case_button(1, data_item);">  I carefully considered it, and decided it was not relevant<br>'
            + '<input type="radio" name="diff" value="2" onclick="activate_continue_to_next_case_button(2, data_item);">  I did not notice it on screen<br>'
            + '<input type="radio" name="diff" value="3" onclick="activate_continue_to_next_case_button(3, data_item);">  I noticed it on screen, but did not carefully consider it<br>'
            + '<input type="radio" name="diff" value="4"> Other: <input type="text" name="diff" id="FreeTextOmission" value="Please explain"> '
            + "<input type='button' value='Submit' onclick='activate_continue_to_next_case_button(4, data_item)'><br>"
            + '</form>'
            + "<hr>When done, click <input id='continue_to_next_case_button' type='button' value='next case' "
            + "onclick='next_case_link_press()'>.";

    $('.chartcol1').each(function (i, obj) {
    $(obj).html("<span class='glyphicon glyphicon-unchecked' aria-hidden='false'></span>");
    });
    $('.shower').hide();
    $("#task").html(task_text);
    console.log('Discussion of omission errors initiated.');
    console.log('Function create_omission_error_check_screen in emr_3.js called to save patient ID and timestamp the discussion of omission errors was initiated.');
}



function activate_continue_to_omission_errors_button(selection1, data_item){

        $('#continue_to_next_case_button').removeAttr("disabled");
        console.log('User '+user_id+' commission errors:');
        if (selection1==1) {
          // Here the free text is stored in a new variable y
          var y = document.getElementById("FreeTextCommission").value;
          console.log('- ' + data_item + ': provided the following free text explanation: '+ y);
        }
        else{
            console.log('Error');
        }
}


function activate_continue_to_next_case_button(selection, data_item){

        $('#continue_to_next_case_button').removeAttr("disabled");
        console.log('User '+user_id+' omission errors:');
        if (selection==1) {
            console.log('- ' + data_item + ': considered it, but deemed it not relevant');
        }
        else if (selection==2) {
            console.log('- ' + data_item + ': did not notice it on screen');
        }
        else if (selection==3) {
            console.log('- ' + data_item + ': noticed it on screen, but did not carefully consider it');
        }
        else if (selection==4) {
            // Here the free text is stored in a new variable z
            var z = document.getElementById("FreeTextOmission").value;
            console.log('- ' + data_item + ': provided the following free text explanation:'+ z);
        }
        else{
            console.log('Error while determining omission errors');
        }
}


// Hides highlighted data panel
function hide_highlight_area(){
  $('.highlight_area').hide();
  //$('.vitmedbox').hide();
  //$('.medbox').hide();
  //$('.labbox').hide();


  var last1 = document.getElementById('all-data-panel-box').clientHeight;
  addEventListener('resize', function() {
      var current1 = document.getElementById('all-data-panel-box').clientHeight;
      if (current1 != last1) location.reload();
      last1 = current1;
    });

  var element1 = document.getElementById("all-data-panel-box");
    element1.classList.remove("all-data-panel");
    element1.classList.add("all-data-panel-increased-height");
  var element2 = document.getElementById("vitmedbox");
    element2.classList.remove("vitmedbox");
    element2.classList.add("vitmedbox-increased-height");
  var element3 = document.getElementById("medbox");
    element3.classList.remove("medbox");
    element3.classList.add("medbox-increased-height");
  var element4 = document.getElementById("lab_tracking");
    element4.classList.remove("labbox");
    element4.classList.add("labbox-increased-height");
  var element4 = document.getElementById("med_tracking");
    element4.classList.remove("medbox");
    element4.classList.add("medbox-increased-height");
  var element5 = document.getElementById("vit_tracking");
    element5.classList.remove("half-vitmedbox");
    element5.classList.add("half-vitmedbox-increased-height");
  var element6 = document.getElementById("io_tracking");
    element6.classList.remove("micro-vitmedbox");
    element6.classList.add("micro-vitmedbox-increased-height");


  //var element5 = document.getElementById("labbox");
  //element5.classList.remove("labbox");
  //element5.classList.add("labbox-increased-height");
  //var element6 = document.getElementById("scroll-box");
  //element6.classList.remove("scroll-box");
  //element6.classList.add("scroll-box-increased-height");
}

// Show all information for patient case
function show_additional_information(){
    // show all the hidden labs
    // this function will call create selection screen
    only_show_highlights = false;
    selection_screen = false;
    let task_text =
        "<p>Additional information is now being displayed.</p>"
        + "<p>Considering the additional information, if you would like to revise your presentation, please do so now."
        + "</p><p>Start the recording with "
        + "'<b>" + user_id + "</b> revisions for <b>" + short_patient_id + "</b>.'</p>"
        + "<hr>Then click <input id='selection_screen_continue' type='button' value='continue' "
        + "onclick='create_rate_clinical_impact_screen()'>.";
    $("#task").html(task_text);
    updateExtremes();
}

// Creates clinical impact rating screen
function create_rate_clinical_impact_screen(){
    // next is next_link press
    selection_screen = true;
    let task_text =
        "If you revised your presentation, rate the clinical impact those revisions would have on patient care:"
        + '<form>'
        + '<input type="radio" name="impact" value="1" onclick="activate_continue_button(1, false);">&nbsp;1. no impact<br>'
        + '<input type="radio" name="impact" value="2" onclick="activate_continue_button(2, false);">&nbsp;2. minor impact<br>'
        + '<input type="radio" name="impact" value="3" onclick="activate_continue_button(3, false);">&nbsp;3. major impact<br><br>'
        + '<input type="radio" name="impact" value="0" onclick="activate_continue_button(0, false);">&nbsp;I did not revise<br>'
        + '</form>'
        + "<hr>Then click <input id='rounding_report_continue' type='button' value='next case' "
        + "onclick='next_case_link_press()'>";
    $("#task").html(task_text);
}

// advances to next patient case
function next_case_link_press() {
    console.log('Function next_case_link_press in emr_3.js called to load the next case.');
    create_manual_input_post(next_patient_link);
}

function link_press(curr_url){
    window.location.href = curr_url;
}

// used when selection is made — this is the click handler for chart rows.
// It is the SINGLE place that mutates selected_items, so the array tracks
// exactly what the participant has chosen (the page-load auto-paint loop
// uses highlight() directly, which no longer touches selected_items).
function activate(id){
    // Toggle the .is-user-selected class on every DOM row sharing this
    // id (the highlight panel and the main panel both render the same
    // id, and the user should see consistent visual feedback in both
    // places). Class drives:
    //   * pale-green background + darker green border (via CSS, with
    //     !important so it overrides the inline yellow that highlight()
    //     set at page-load for AI-suggested items)
    //   * the chartcol1 becomes a filled-green circle with white check.
    // Removing the class restores whatever paint sat below: yellow for
    // AI-suggested rows, default grey otherwise.
    let curr = 'div[id="' + id + '"]';
    let child_2 = $(curr).find('.chartcol1');
    let child_2_html = child_2.html();
    if (child_2_html.length > 1) {
        if (child_2_html.split('-')[1][0] === 'u') {
            // Was unchecked → check it and record the selection.
            child_2.html("<span class='glyphicon glyphicon-check' aria-hidden='true'></span>");
            $(curr).addClass('is-user-selected');
            if (selected_items.indexOf(id) === -1) {
                selected_items.push(id);
            }
            console.log('[selection] picked: ' + id + ' (total now ' + selected_items.length + ')');
        } else {
            // Was checked → uncheck it and remove from the selection.
            child_2.html("<span class='glyphicon glyphicon-unchecked' aria-hidden='true'></span>");
            $(curr).removeClass('is-user-selected');
            var idx = selected_items.indexOf(id);
            if (idx !== -1) {
                selected_items.splice(idx, 1);
            }
            console.log('[selection] unpicked: ' + id + ' (total now ' + selected_items.length + ')');
        }
    }
}

function get_chart(chartTitle, type, predata, displayText){
    //console.log(displayText);
    predata = predata.replace(/'/g, '"');
    let post_data = $.parseJSON(predata);

    // [high, norm, low], curr_data['text'], abs_ranges, norm_ranges, curr_recent_result, curr_recent_units
    if (chartTitle === 'VTDIAA'){
        get_bp_chart(chartTitle, post_data, 'Pulmonary artery BP')
    }else if (chartTitle === 'VTDIAV'){
        get_bp_chart(chartTitle, post_data, 'Systemic BP')
    }else{
        get_lab_chart(chartTitle, post_data, displayText);
    }
}


// lower labs
function get_lab_chart(chartTitle, post_data, displayText) {
    let container = 'lab' + chartTitle;
    let show_y_axis_labels = true;
    let left_spacing = 10;
    let title_x_spacing = 0;

    if (post_data[0][0].data.length === 0 || post_data[0][0].name === 'discrete_values'){
        show_y_axis_labels = false;
        left_spacing = 34;
        title_x_spacing = -24
    }
    let currChart = new Highcharts.Chart({
        chart: {
            renderTo: container,
            height: 80,
            spacingLeft: left_spacing,
            //spacingLeft: 5 - post_data[2][1].toString().length,
            spacingBottom: 6,
            spacingTop: 28,  // reserve top band for the overlay (title + value/unit); 28 keeps y-axis top label clear of the (now-transparent) band
            backgroundColor: 'transparent',  // let cell background (yellow AI-highlight, green when selected, white otherwise) show through uniformly across the whole cell — including under the title band
            spacingRight: 6,
            type: 'scatter',
            events: {
                click: function () {
                    this.tooltip.hide();
                },
                // Render the "recent value + unit" text ourselves via the
                // Highcharts SVG renderer, on chart load AND after every
                // redraw. We had been using Highcharts's built-in credits
                // system for this, but credits proved unreliable across
                // cells: SvO2, Weight, and every venous blood-gas cell
                // rendered a blank top-right corner even though their
                // post_data[4] slot held a valid number. Whether the
                // culprit was plot-band overlays covering the SVG credits,
                // useHTML repositioning quirks on tight y-axis ranges, or
                // Highcharts's own reflow path clearing the credits, the
                // symptom was the same: some charts silently dropped the
                // credits. Drawing the text ourselves — with an explicit
                // reference held on the chart so we can update it on
                // redraw — is deterministic and easy to reason about.
                load:   function () { _drawRecentValueLabel(this, post_data, displayText); },
                redraw: function () { _drawRecentValueLabel(this, post_data, displayText); }
            }
        },
        credits: { enabled: false },
        // Highcharts title disabled — the title text is rendered inside
        // our own overlay (see _setOverlayLabel) in the same flex row as
        // the recent value + unit, so they can't overlap on narrow cells.
        title: { text: null },
        legend: {enabled: false},
        yAxis: {
            labels: {enabled: show_y_axis_labels},
            title: {text: null},
            gridLineColor: 'grey',
            // Force the y-axis line to render even when labels are hidden
            // (discrete cells: Tube Status, Ventilator Mode). Highcharts's
            // default drops the axis line when it has no ticks, which
            // left those cells looking like they had no y-axis at all —
            // the participant lost the visual "this is a chart" anchor
            // on the left edge. lineColor matches the row border tone so
            // it blends in on numeric cells without adding noise.
            lineWidth: 1,
            lineColor: '#c8d3e0',
            plotBands: [{
                from: post_data[3][0],
                to: post_data[3][1],
                color: 'rgba(68, 170, 213, 0.4)'
            }],
            min: post_data[2][0],
            max: post_data[2][1]
        },
        xAxis: [
            {
                tickLength: 0,
                labels: {
                    enabled: false,
                    formatter: function () {
                        return Highcharts.dateFormat('%b %e %H:%M:%S', this.value);
                    }
                },
                min: selectedMin,
                max: selectedMax,
                lineWidth: 0,
                plotBands: [{
                    from: data_max-86400000,
                    to: data_max,
                    color: '#e6e6e6',
                    id: 'plot-line-1'
                }]
            }
        ],
        series: post_data[0],
        plotOptions: {
            series: { point: { events: { click: function () { add_vertical_point(this.x); }}}}
        }, tooltip: {
            shared: false,
            positioner: function (labelWidth, labelHeight, point) {
                return {x: currChart.chartWidth / 2 - (labelWidth + 2), y: 24};

            },
            formatter: function () {
                if(this.series.name === 'numeric_values') {
                    let text = post_data[1][this.series.data.indexOf( this.point )];
                    if (text !== null && text !== undefined){
                        return cleanLabel(text);
                    }else{
                        // <span>, not <p>: with useHTML:true a <p> renders as a
                        // block with the browser's default margin (16 px top and
                        // bottom), producing a large white box that sometimes
                        // covers the chart and sometimes gets clipped by the cell
                        // boundary. <span> is inline and stays compact.
                        return '<span style="font-size:12px">' + this.y + '</span>'
                    }
                }else{
                    // <span>, not <p>: same reason as numeric branch above.
                    return '<span style="font-size:12px">' + cleanLabel(post_data[6][this.y]) + '</span>'
                }
            },
            backgroundColor: "rgba(256,256,256,1)",
            padding: 4,
            crosshairs: [false, false]
        }
    });
    // Synchronous fallback: draw the recent-value label immediately after
    // chart construction. The chart.events.load handler we wire up in the
    // config is *supposed* to fire once the chart finishes its initial
    // render, but for cells with a very sparse numeric_values series
    // (single-point series like Weight, single-point venous BGs)
    // Highcharts's initial-render path occasionally skips the load
    // dispatch, leaving the label undrawn. Belt-and-suspenders: also
    // invoke the drawer directly here so the label is on the canvas by
    // the time chartsContainers.push happens.
    _drawRecentValueLabel(currChart, post_data, displayText);
    chartsContainers.push(currChart);
    chartrowids.push(chartTitle);
}

function get_med_chart(chartTitle, predata, displayName) {
    predata = predata.replace(/'/g, '"');
    let post_data = $.parseJSON(predata);
    let container = 'med'+chartTitle;
    let currChart;
    let chart_height = 60 + 15*Math.floor(displayName.length/30);
    // Create chart
    currChart = new Highcharts.Chart({
        chart: {
                renderTo: container,
                height: chart_height,
                spacingLeft: 6,
                spacingBottom: 6,
                spacingTop: 28,  // reserve top band for the overlay (title + value/unit); 28 keeps y-axis top label clear of the (now-transparent) band
            backgroundColor: 'transparent',  // let cell background (yellow AI-highlight, green when selected, white otherwise) show through uniformly across the whole cell — including under the title band
                spacingRight: 6,
                type: 'scatter',
                events: {
                    click: function () {
                        this.tooltip.hide()
                    },
                    // Draw the recent-dose overlay ourselves — see
                    // _drawMedRecentValueLabel + _setOverlayLabel for
                    // rationale (Highcharts credits proved unreliable
                    // on sparse-data cells; a vanilla DOM overlay
                    // guarantees the label appears and stays right-
                    // aligned in the top-right corner of the cell).
                    load:   function () { _drawMedRecentValueLabel(this, post_data, displayName); },
                    redraw: function () { _drawMedRecentValueLabel(this, post_data, displayName); }
                }
        },
        credits: { enabled: false },
        // Highcharts title disabled — the title text is rendered inside
        // our own overlay (see _setOverlayLabel) alongside the recent
        // value + unit in a flex row that prevents overlap.
        title: { text: null },
        legend: {enabled: false},
        yAxis: {
            labels: {enabled: true},
            title: {text: null},
            gridLineColor: 'grey',
            min: post_data[2][0],
            max: post_data[2][1]
        },
        xAxis: [
            {
                tickLength: 0,
                labels: { enabled: false },
                min: selectedMin,
                max: selectedMax,
                lineWidth: 0,
                plotBands: [{
                    from: data_max-86400000,
                    to: data_max,
                    color: '#e6e6e6',
                    id: 'plot-line-1'
                }]
            }
        ],
        series: post_data[0],
        plotOptions: {
            series: {
                point: {
                    events: {
                        click: function () {
                            add_vertical_point(this.x);
                        }
                    }
                }
            }
        },
        tooltip: {
            positioner: function (labelWidth, labelHeight, point) {
                return {x: currChart.chartWidth/2 - (labelWidth + 2), y: 24};
            },
            formatter: function() {
                var i = this.series.data.indexOf(this.point);
                return cleanLabel(post_data[1][i][0]) + ' ' + cleanLabel(post_data[1][i][1]);
            },
            padding: 4,
            crosshairs: [false, false]
        }
    });
    //}
    // Synchronous fallback — chart.events.load doesn't always fire on
    // sparse-data charts, so draw the overlay here too.
    _drawMedRecentValueLabel(currChart, post_data, displayName);
    chartsContainers.push(currChart);
    chartrowids.push(chartTitle);
}


function get_bp_chart(chartTitle, post_data, displayText) {
    let container = 'lab'+chartTitle;
    let currChart;
    currChart = new Highcharts.Chart({
        chart: {
         renderTo: container,
         height: 120,
         spacingLeft: 6,
         spacingBottom: 6,
         spacingTop: 28,  // reserve top band for the overlay (title + value/unit); 28 keeps y-axis top label clear of the (now-transparent) band
         backgroundColor: 'transparent',  // let cell background show through uniformly (matches other chart types)
         spacingRight: 10,
         type: 'scatter',
         events: {
             click: function (e) {this.tooltip.hide()},
             // Draw the title band overlay ourselves — same overlay
             // system the lab, vital, and med charts use (see
             // _setOverlayLabel). post_data[3] is the "systolic/diastolic"
             // string for BP, e.g. "108/55".
             load:   function () { _setOverlayLabel(this, cleanLabel(post_data[3]), 'mm Hg', displayText); },
             redraw: function () { _setOverlayLabel(this, cleanLabel(post_data[3]), 'mm Hg', displayText); }
         }
     }, credits: { enabled: false },
        title: { text: null },
        legend: {enabled: false},
    yAxis: {
        labels: {enabled: true},
        title: {text: null},
        tickPixelInterval: 30,
        max: post_data[2][1],
        min: post_data[2][0]
    }, xAxis: {
         tickLength: 0,
         labels: {
             enabled: false,
             formatter: function () {
                 return Highcharts.dateFormat('%b %e %H:%M:%S', this.value);
             }
         },
         min: selectedMin,
         max: selectedMax,
         lineWidth: 0,
            plotBands: [{
                from: data_max-86400000,
                to: data_max,
                color: '#e6e6e6',
                id: 'plot-line-1'
            }]
    }, series: post_data[0],
    plotOptions: {
    series: {
         point: {
             events: {
                 click: function () {
                     add_vertical_point(this.x);
                 }
             }
         }
     }
    },
    tooltip: {
            shared: false,
            formatter: function () { // I need to show all the data in the tooltip, as well as the selected dot value to tell which one is selected
                let series = this.point.series.chart.series,
                    index = this.point.series.xData.indexOf(this.point.x),
                    sys = '',
                    dia = '';

                $.each(series, function(i, s) {
                    if (s.name === 'dias' || s.name === 'art_dia'){
                        dia = s.processedYData[index]
                    }else if (s.name === 'syst' || s.name === 'art_sys') {
                        sys = s.processedYData[index];
                    }
                });
                return sys + '/' + dia;
            },
            positioner: function (labelWidth, labelHeight, point) {
                return {x: currChart.chartWidth/2 - (labelWidth + 2), y: 24};
            },
            backgroundColor: "rgba(255,255,255,1)",
            padding: 4,
            crosshairs: [false, false]
    }
    });
    chartsContainers.push(currChart);
    chartrowids.push(chartTitle);

 }

function get_io_chart(chartTitle, predata, displayText) {
    predata = predata.replace(/'/g, '"');
    let post_data = $.parseJSON(predata);

    let container = 'lab'+chartTitle;
    let currChart;

    currChart = new Highcharts.Chart({
        chart: {
            renderTo: container,
            height: 150,
            spacingLeft:6,
            spacingBottom:6,
            spacingTop: 28,  // reserve top band for the overlay (title + value/unit); 28 keeps y-axis top label clear of the (now-transparent) band
            backgroundColor: 'transparent',  // let cell background (yellow AI-highlight, green when selected, white otherwise) show through uniformly across the whole cell — including under the title band
            spacingRight:10,
            type: 'column',
            events:{
                click: function() {this.tooltip.hide()},
                // Same overlay approach as other chart types. No per-point
                // value applies to the I/O stacked bar, so we pass empty
                // strings for val/unit — the band shows title only.
                load:   function () { _setOverlayLabel(this, '', '', 'Daily Intake and Output'); },
                redraw: function () { _setOverlayLabel(this, '', '', 'Daily Intake and Output'); }
            }
        },
        credits: {  enabled:false},
        title: { text: null },
        legend: { enabled: false},
        yAxis:
            {
                labels: { enabled:true },
                title: { text: null},
                tickPixelInterval: 50,
                plotLines:[{color:'black', width: 1, value:0}]//,
                //max: Math.min(5000, post_data[2][1]),
                //min: Math.max(-5000, post_data[2][0])
            },
        xAxis: [
            {
                tickLength: 0,
                labels: {
                    enabled:false,
                    formatter: function () { return Highcharts.dateFormat('%b %e %H:%M:%S', this.value);}
                },
                min: selectedMin,
                max: selectedMax,
                lineWidth: 0,
                plotBands: [{
                    from: data_max-86400000,
                    to: data_max,
                    color: '#e6e6e6',
                    id: 'plot-line-1'
                }]
            }
        ],
        series: post_data[0],
        plotOptions: {
            series: {point: { events: {click: function () {add_vertical_point(this.x);}}}},
            column: {stacking: 'normal'}
        },
        tooltip: {
            positioner: function (labelWidth, labelHeight, point) {
                return {x: currChart.chartWidth/2 - (labelWidth/2), y: 24};
            },
            formatter: function() {return  this.series.name + ' | ' + Math.round(this.y)},
            crosshairs: [false, false]
         }
    });

    // discrete values
    chartsContainers.push(currChart);
    chartrowids.push(chartTitle);
}
















function get_chart_highlight_area(chartTitle, type, predata, displayText){

    let post_data = $.parseJSON(predata);

    // [high, norm, low], curr_data['text'], abs_ranges, norm_ranges, curr_recent_result, curr_recent_units
    if (chartTitle === 'VTDIAA'){
        get_bp_chart_highlight_area(chartTitle, post_data, 'Pulmonary artery BP')
    }else if (chartTitle === 'VTDIAV'){
        get_bp_chart_highlight_area(chartTitle, post_data, 'Systemic BP')
    }else{
        get_lab_chart_highlight_area(chartTitle, post_data, displayText);
    }
}





function get_lab_chart_highlight_area(chartTitle, post_data, displayText) {
    let container = chartTitle;
    let show_y_axis_labels = true;
    // Kept spacingLeft at 10 for all cells (discrete + numeric) so the
    // y-axis line stays anchored at the same x on every card. For
    // discrete-value cells (Tube Status, Ventilator Mode) the y-axis
    // labels are hidden but the axis itself still draws at x=10. The
    // title's overrun into the value column, previously mitigated by
    // shifting title.x by -24 (which just clipped "Tube" off the left),
    // is now handled by chartTitleHtml: long titles wrap onto a second
    // line inside the title box, giving room for the last-value credits
    // to sit on the right.
    let left_spacing = 10;
    let title_x_spacing = 0;

    if (post_data[0][0].data.length === 0 || post_data[0][0].name === 'discrete_values'){
        show_y_axis_labels = false;
    }
    // Auto-fit x-axis to THIS chart's data — see highlightXAxisRange().
    let xRange = highlightXAxisRange((post_data && post_data[0] && post_data[0][0] && post_data[0][0].data) || []);
    let currChart = new Highcharts.Chart({
        chart: {
            renderTo: container,
            height: 80,
            spacingLeft: left_spacing,
            spacingBottom: 6,
            spacingTop: 28,  // reserve top band for the overlay (title + value/unit); 28 keeps y-axis top label clear of the (now-transparent) band
            backgroundColor: 'transparent',  // let cell background (yellow AI-highlight, green when selected, white otherwise) show through uniformly across the whole cell — including under the title band
            spacingRight: 6,
            type: 'scatter',
            events: {
                click: function () {
                    this.tooltip.hide();
                },
                // Render the "recent value + unit" text ourselves via the
                // Highcharts SVG renderer, on chart load AND after every
                // redraw. We had been using Highcharts's built-in credits
                // system for this, but credits proved unreliable across
                // cells: SvO2, Weight, and every venous blood-gas cell
                // rendered a blank top-right corner even though their
                // post_data[4] slot held a valid number. Whether the
                // culprit was plot-band overlays covering the SVG credits,
                // useHTML repositioning quirks on tight y-axis ranges, or
                // Highcharts's own reflow path clearing the credits, the
                // symptom was the same: some charts silently dropped the
                // credits. Drawing the text ourselves — with an explicit
                // reference held on the chart so we can update it on
                // redraw — is deterministic and easy to reason about.
                load:   function () { _drawRecentValueLabel(this, post_data, displayText); },
                redraw: function () { _drawRecentValueLabel(this, post_data, displayText); }
            }
        },
        credits: { enabled: false },
        // Highcharts title disabled — the title text is rendered inside
        // our own overlay (see _setOverlayLabel) in the same flex row as
        // the recent value + unit, so they can't overlap on narrow cells.
        title: { text: null },
        legend: {enabled: false},
        yAxis: {
            labels: {enabled: show_y_axis_labels},
            title: {text: null},
            gridLineColor: 'grey',
            // Force the y-axis line to render even when labels are hidden
            // (discrete cells: Tube Status, Ventilator Mode). Highcharts's
            // default drops the axis line when it has no ticks, which
            // left those cells looking like they had no y-axis at all —
            // the participant lost the visual "this is a chart" anchor
            // on the left edge. lineColor matches the row border tone so
            // it blends in on numeric cells without adding noise.
            lineWidth: 1,
            lineColor: '#c8d3e0',
            plotBands: [{
                from: post_data[3][0],
                to: post_data[3][1],
                color: 'rgba(68, 170, 213, 0.4)'
            }],
            min: post_data[2][0],
            max: post_data[2][1]
        },
        xAxis: [
            {
                tickLength: 0,
                labels: {
                    enabled: false,
                    formatter: function () {
                        return Highcharts.dateFormat('%b %e %H:%M:%S', this.value);
                    }
                },
                min: xRange.min,
                max: xRange.max,
                lineWidth: 0,
                plotBands: [{
                    from: data_max-86400000,
                    to: data_max,
                    color: '#e6e6e6',
                    id: 'plot-line-1'
                }]
            }
        ],
        series: post_data[0],
        plotOptions: {
            series: { point: { events: { click: function () { add_vertical_point(this.x); }}}}
        }, tooltip: {
            shared: false,
            positioner: function (labelWidth, labelHeight, point) {
                return {x: currChart.chartWidth / 2 - (labelWidth + 2), y: 24};

            },
            formatter: function () {
                if(this.series.name === 'numeric_values') {
                    let text = post_data[1][this.series.data.indexOf( this.point )];
                    if (text !== null && text !== undefined){
                        return cleanLabel(text);
                    }else{
                        // <span>, not <p>: with useHTML:true a <p> renders as a
                        // block with the browser's default margin (16 px top and
                        // bottom), producing a large white box that sometimes
                        // covers the chart and sometimes gets clipped by the cell
                        // boundary. <span> is inline and stays compact.
                        return '<span style="font-size:12px">' + this.y + '</span>'
                    }
                }else{
                    // <span>, not <p>: same reason as numeric branch above.
                    return '<span style="font-size:12px">' + cleanLabel(post_data[6][this.y]) + '</span>'
                }
            },
            backgroundColor: "rgba(256,256,256,1)",
            padding: 4,
            crosshairs: [false, false]
        }
    });
    // Synchronous fallback: draw the recent-value label immediately after
    // chart construction. The chart.events.load handler we wire up in the
    // config is *supposed* to fire once the chart finishes its initial
    // render, but for cells with a very sparse numeric_values series
    // (single-point series like Weight, single-point venous BGs)
    // Highcharts's initial-render path occasionally skips the load
    // dispatch, leaving the label undrawn. Belt-and-suspenders: also
    // invoke the drawer directly here so the label is on the canvas by
    // the time chartsContainers.push happens.
    _drawRecentValueLabel(currChart, post_data, displayText);
    chartsContainers.push(currChart);
    chartrowids.push(chartTitle);
}

function get_med_chart_highlight_area(chartTitle, predata, displayName) {
    // Defensive wrapper. Some med catalogs (notably "Base solution" and
    // "parenteral nutrition solution") have rendered as a fully-empty
    // cell in the past; if anything in the parse / Highcharts pipeline
    // throws we surface the error to the console AND drop a visible
    // text fallback into the cell so the participant still sees the
    // med name + last value rather than a mystery grey square.
    try {
        return _build_med_chart_highlight(chartTitle, predata, displayName);
    } catch (err) {
        console.error('[highlight-panel-med] render failed for "' + displayName +
                      '" in container ' + chartTitle + ':', err);
        var el = document.getElementById(chartTitle);
        if (el) {
            el.innerHTML =
                '<div style="padding:8px;font-size:12px;line-height:1.3;text-align:left;">' +
                '<div style="font-weight:600;color:#1F2937;">' +
                  (displayName || '').replace(/[<>&]/g, '') +
                '</div>' +
                '<div style="margin-top:4px;color:#B45309;font-size:10px;">' +
                  '(chart unavailable)' +
                '</div></div>';
        }
        return null;
    }
}

function _build_med_chart_highlight(chartTitle, predata, displayName) {
    predata = predata.replace(/'/g, '"');
    let post_data = $.parseJSON(predata);
    let container = chartTitle;
    let currChart;
    // Auto-fit x-axis to THIS chart's data — see highlightXAxisRange().
    let xRange = highlightXAxisRange((post_data && post_data[0] && post_data[0][0] && post_data[0][0].data) || []);
    // Uniform highlight-panel chart size + credits offset. All four
    // highlight chart functions (lab, BP, med, IO) use HIGHLIGHT_HEIGHT
    // / HIGHLIGHT_CREDITS_Y so every cell in the panel ends up the
    // same height and the latest-value overlay sits at the same
    // baseline.
    var HIGHLIGHT_HEIGHT = 80;
    var HIGHLIGHT_CREDITS_Y = -66;  // 14 px above the chart's bottom edge

    // Event-style med fix: catalogs like "Base solution" have data
    // points that are administrative annotations ("Begin Bag 100",
    // "50 mcg/hr") plotted at y == 0 on a timeline rather than dose
    // magnitudes. With yMin = 0 from the pickle (post_data[2][0]) the
    // markers sit exactly on the bottom axis and get clipped by the
    // spacingBottom padding, producing an empty grey box.
    //
    // Previous fix only triggered when *every* data point was zero;
    // but Base solution actually has a couple of non-zero dose-change
    // markers buried among 12 zero "Begin Bag" entries, so the
    // all-zero check returned false and the chart still rendered
    // empty-looking. New behaviour: unconditionally pad the y-axis
    // floor by 12 % of the data range, so any value at the bottom of
    // the range (including y == 0) sits visibly inside the plot area
    // rather than being clipped by the bottom padding. This is a no-
    // op cosmetic shift for charts that already use the full range
    // (vancomycin, etc.) but rescues the event-style ones.
    var data_arr = (post_data[0] && post_data[0][0] && post_data[0][0].data) || [];
    var yMin = post_data[2][0];
    var yMax = post_data[2][1];
    var ySpan = yMax - yMin;
    if (ySpan > 0) {
        yMin = yMin - ySpan * 0.12;
    } else {
        // degenerate range — give the chart at least 1 unit of vertical space.
        yMin = yMin - 1;
        yMax = yMax + 1;
    }
    // Create chart
    currChart = new Highcharts.Chart({
        chart: {
                renderTo: container,
                height: HIGHLIGHT_HEIGHT,
                spacingLeft: 10,
                spacingBottom: 6,
                spacingTop: 28,  // reserve top band for the overlay (title + value/unit); 28 keeps y-axis top label clear of the (now-transparent) band
            backgroundColor: 'transparent',  // let cell background (yellow AI-highlight, green when selected, white otherwise) show through uniformly across the whole cell — including under the title band
                spacingRight: 6,
                type: 'scatter',
                events: {
                    click: function () {
                        this.tooltip.hide()
                    },
                    // Vanilla-DOM overlay for the recent dose. Highcharts
                    // credits were dropping labels on sparse-data cells;
                    // see _drawMedRecentValueLabel + _setOverlayLabel.
                    load:   function () { _drawMedRecentValueLabel(this, post_data, displayName); },
                    redraw: function () { _drawMedRecentValueLabel(this, post_data, displayName); }
                }
        },
        credits: { enabled: false },
        // Highcharts title disabled — the title text is rendered inside
        // our own overlay (see _setOverlayLabel) alongside the recent
        // value + unit in a flex row that prevents overlap.
        title: { text: null },
        legend: {enabled: false},
        yAxis: {
            labels: {enabled: true},
            title: {text: null},
            gridLineColor: 'grey',
            min: yMin,
            max: yMax
        },
        xAxis: [
            {
                tickLength: 0,
                labels: { enabled: false },
                min: xRange.min,
                max: xRange.max,
                lineWidth: 0,
                plotBands: [{
                    from: data_max-86400000,
                    to: data_max,
                    color: '#fce1c9',
                    id: 'plot-line-1'
                }]
            }
        ],
        series: post_data[0],
        plotOptions: {
            series: {
                point: {
                    events: {
                        click: function () {
                            add_vertical_point(this.x);
                        }
                    }
                }
            }
        },
        tooltip: {
            positioner: function (labelWidth, labelHeight, point) {
                return {x: currChart.chartWidth/2 - (labelWidth + 2), y: 24};
            },
            formatter: function() {
                var i = this.series.data.indexOf(this.point);
                return cleanLabel(post_data[1][i][0]) + ' ' + cleanLabel(post_data[1][i][1]);
            },
            padding: 4,
            crosshairs: [false, false]
        }
    });
    //}
    // Synchronous fallback — chart.events.load doesn't always fire on
    // sparse-data charts, so draw the overlay here too.
    _drawMedRecentValueLabel(currChart, post_data, displayName);
    chartsContainers.push(currChart);
    chartrowids.push(chartTitle);
}


function get_bp_chart_highlight_area(chartTitle, post_data, displayText) {
    let container = chartTitle;
    let currChart;
    // Same HIGHLIGHT_HEIGHT / CREDITS_Y as the other three highlight
    // panel chart functions — see get_med_chart_highlight_area for the
    // rationale. Previously this used y: -106 left over from when the
    // chart was 120 px tall; with the current 80-px height the credits
    // floated way above the chart bottom and looked off.
    var HIGHLIGHT_HEIGHT = 80;
    var HIGHLIGHT_CREDITS_Y = -66;
    // Auto-fit x-axis to THIS chart's data — see highlightXAxisRange().
    let xRange = highlightXAxisRange((post_data && post_data[0] && post_data[0][0] && post_data[0][0].data) || []);

    currChart = new Highcharts.Chart({
        chart: {
         renderTo: container,
         height: HIGHLIGHT_HEIGHT,
         spacingLeft: 10,
         spacingBottom: 6,
         spacingTop: 28,  // reserve top band for the overlay (title + value/unit); 28 keeps y-axis top label clear of the (now-transparent) band
         backgroundColor: 'transparent',  // let cell background show through uniformly (matches other chart types)
         spacingRight: 6,
         type: 'scatter',
         events: {
             click: function (e) {this.tooltip.hide()},
             // Same overlay approach as the other chart functions —
             // see _setOverlayLabel. post_data[3] is the BP "syst/dia"
             // reading, unit is always mm Hg for this chart type.
             load:   function () { _setOverlayLabel(this, cleanLabel(post_data[3]), 'mm Hg', displayText); },
             redraw: function () { _setOverlayLabel(this, cleanLabel(post_data[3]), 'mm Hg', displayText); }
         }
     }, credits: { enabled: false },
        title: { text: null },
        legend: {enabled: false},
    yAxis: {
        labels: {enabled: true},
        title: {text: null},
        tickPixelInterval: 30,
        max: post_data[2][1],
        min: post_data[2][0]
    }, xAxis: {
         tickLength: 0,
         labels: {
             enabled: false,
             formatter: function () {
                 return Highcharts.dateFormat('%b %e %H:%M:%S', this.value);
             }
         },
         min: xRange.min,
         max: xRange.max,
         lineWidth: 0,
            plotBands: [{
                from: data_max-86400000,
                to: data_max,
                color: '#e6e6e6',
                id: 'plot-line-1'
            }]
    }, series: post_data[0],
    plotOptions: {
    series: {
         point: {
             events: {
                 click: function () {
                     add_vertical_point(this.x);
                 }
             }
         }
     }
    },
    tooltip: {
            shared: false,
            formatter: function () { // I need to show all the data in the tooltip, as well as the selected dot value to tell which one is selected
                let series = this.point.series.chart.series,
                    index = this.point.series.xData.indexOf(this.point.x),
                    sys = '',
                    dia = '';

                $.each(series, function(i, s) {
                    if (s.name === 'dias' || s.name === 'art_dia'){
                        dia = s.processedYData[index]
                    }else if (s.name === 'syst' || s.name === 'art_sys') {
                        sys = s.processedYData[index];
                    }
                });
                return sys + '/' + dia;
            },
            positioner: function (labelWidth, labelHeight, point) {
                return {x: currChart.chartWidth/2 - (labelWidth + 2), y: 24};
            },
            backgroundColor: "rgba(255,255,255,1)",
            padding: 4,
            crosshairs: [false, false]
    }
    });
    chartsContainers.push(currChart);
    chartrowids.push(chartTitle);

 }

function get_io_chart_highlight_area(chartTitle, predata, displayText) {
    predata = predata.replace(/'/g, '"');
    let post_data = $.parseJSON(predata);

    let container = chartTitle;
    let currChart;
    // Auto-fit x-axis to THIS chart's data — see highlightXAxisRange().
    let xRange = highlightXAxisRange((post_data && post_data[0] && post_data[0][0] && post_data[0][0].data) || []);

    currChart = new Highcharts.Chart({
        chart: {
            renderTo: container,
            //height: 150, //was 150
            height: 80,
            spacingLeft: 10,
            spacingBottom:6,
            spacingTop: 28,  // reserve top band for the overlay (title + value/unit); 28 keeps y-axis top label clear of the (now-transparent) band
            backgroundColor: 'transparent',  // let cell background (yellow AI-highlight, green when selected, white otherwise) show through uniformly across the whole cell — including under the title band
            spacingRight: 6,
            type: 'column',
            events:{
                click: function() {this.tooltip.hide()},
                // Same overlay approach as other chart types. No per-point
                // value applies to the I/O stacked bar, so we pass empty
                // strings for val/unit — the band shows title only.
                load:   function () { _setOverlayLabel(this, '', '', 'Daily Intake and Output'); },
                redraw: function () { _setOverlayLabel(this, '', '', 'Daily Intake and Output'); }
            }
        },
        credits: {  enabled:false},
        title: { text: null },
        legend: { enabled: false},
        yAxis:
            {
                labels: { enabled:true },
                title: { text: null},
                tickPixelInterval: 50,
                plotLines:[{color:'black', width: 1, value:0}]//,
                //max: Math.min(5000, post_data[2][1]),
                //min: Math.max(-5000, post_data[2][0])
            },
        xAxis: [
            {
                tickLength: 0,
                labels: {
                    enabled:false,
                    formatter: function () { return Highcharts.dateFormat('%b %e %H:%M:%S', this.value);}
                },
                min: xRange.min,
                max: xRange.max,
                lineWidth: 0,
                plotBands: [{
                    from: data_max-86400000,
                    to: data_max,
                    color: '#e6e6e6',
                    id: 'plot-line-1'
                }]
            }
        ],
        series: post_data[0],
        plotOptions: {
            series: {point: { events: {click: function () {add_vertical_point(this.x);}}}},
            column: {stacking: 'normal'}
        },
        tooltip: {
            positioner: function (labelWidth, labelHeight, point) {
                return {x: currChart.chartWidth/2 - (labelWidth/2), y: 24};
            },
            formatter: function() {return  this.series.name + ' | ' + Math.round(this.y)},
            crosshairs: [false, false]
         }
    });

    // discrete values
    chartsContainers.push(currChart);
    chartrowids.push(chartTitle);
}











// Creates the time selector chart
// updateExtremes function is called whenever the slider is moved
function getchartT(id,global_time) {
    $(id).highcharts('StockChart', {
            chart: {
                height:25,
                spacingLeft:40,
                spacingBottom:0,
                spacingTop:2,
                spacingRight:6,
                events: {load: function () {
                    let range = this.xAxis[0].getExtremes();
                    this.xAxis[0].setExtremes(Math.max(range.min, range.max-216000000), range.max);}} // On load update selected range // 2.5 days
            },
            scrollbar: {enabled: false},
            navigator: {enabled: false, height: 1, top:4},
            //navigator: {enabled: true, height: 500, top:40},
			rangeSelector : {
                enabled: false,
				selected : 1,
                inputEnabled: true
            },
            series:
                [
                {type: 'scatter',name:'min_max',data: [[global_time.min_t,0],[global_time.max_t,0]], visible: false,tooltip: {enabled: false}}
                ],
            tooltip:{enabled: false},
            title: {text: null},
            legend: { enabled: false},
            credits: { enabled:false},
            xAxis: {top: 2,
                labels: {format: '{value:%m/%d}', padding: 1},
                //tickPixelInterval: 25,
                min: global_time.min_t,
                max: global_time.max_t
            },
            yAxis:{ labels: { enabled:false }, title: { text: null}, top: 40} // top is what flips the navigator
		});
}

// Creates the time selector chart
// updateExtremes function is called whenever the slider is moved
function getchartTS(id,global_time) {

    $(id).highcharts('StockChart', {
            chart: {
                height:35,
                spacingLeft:5,
                spacingBottom:2,
                spacingTop:2,
                spacingRight:5,
                events: {load: function () {
                    // Default the selected window to the FULL case range on
                    // page load rather than clamping to the last 2.5 days.
                    // The old clamp (max - 216_000_000 ms) made the right
                    // handle sit at range.max and gave the impression that
                    // the max was "the visible right edge" — participants
                    // then couldn't drag right to see later data, and Coags
                    // / Urinalysis measurements that fell outside the 2.5-
                    // day window (Coags data on 08/15, Urinalysis on 08/18
                    // evening for a specific case) rendered as blank charts.
                    // Setting extremes to [range.min, range.max] shows the
                    // entire case out of the gate; the participant can
                    // narrow the window if they want to zoom in.
                    let range = this.xAxis[0].getExtremes();
                    this.xAxis[0].setExtremes(range.min, range.max);
                }}
                },
            scrollbar: {enabled: false},
            navigator: {enabled: true, height: 35, top:0},
            //navigator: {enabled: true, height: 500, top:40},
            rangeSelector : {
                enabled: false,
                selected : 1,
                inputEnabled: true,
                buttons: [{type: 'day',count: 1,text: '1d'},{type: 'day',count: 2,text: '2d'},{type: 'week',count: 1,text: '1w'},{type: 'all',text:'All'}]},
            series:
                [
                {type: 'scatter',name:'min_max',data: [[global_time.min_t,0],[global_time.max_t,0]], visible: false,tooltip: {enabled: false}}
                ],
            tooltip:{enabled: false},
            title: {text: null},
            legend: { enabled: false},
            credits: { enabled:false},
            xAxis: {top: -10,labels: {enabled: false}, min: global_time.min_t, max: global_time.max_t,
                events: {afterSetExtremes: function (e) {selectedMin = e.min;selectedMax = e.max;onUpdateOfExtremes();}}},
            yAxis:{ labels: { enabled:false }, title: { text: null}} // top is what flips the navigator
    });
}

function onUpdateOfExtremes(){
    if (!down){
        updateExtremes();
    }
}
