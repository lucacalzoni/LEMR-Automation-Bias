# -*- coding: utf-8 -*-
"""Generate the full synthetic study set for a public demo."""
import json, os, pickle, random

HERE  = os.path.dirname(os.path.abspath(__file__))
STUDY = os.path.abspath(os.path.join(HERE, os.pardir, 'models', 'evaluation_study'))
DAY = 86400.0
T_ADMIT_BASE = 1735689600.0

GROUP_COLOR = {
    'Basic Chemistry': '#1f77b4', 'Other Chemistry': '#7b7bdd',
    'CBC': '#d62728', 'Blood Gases': '#2ca02c',
    'Coagulation': '#9467bd', 'Liver Function': '#8c564b',
    'Cardiac': '#e377c2', 'Vitals': '#ff7f0e', 'Ventilator': '#17becf',
}

LABS = [
    ('K','Potassium','Basic Chemistry','mEq/L',3.5,5.1,4.2,0.3),
    ('NA','Sodium','Basic Chemistry','mEq/L',135,145,139,3),
    ('CL','Chloride','Basic Chemistry','mEq/L',98,107,103,3),
    ('CO2','Bicarbonate','Basic Chemistry','mEq/L',22,29,24,2),
    ('BUN','BUN','Basic Chemistry','mg/dL',7,20,22,6),
    ('CREAT','Creatinine','Basic Chemistry','mg/dL',0.6,1.3,1.9,0.5),
    ('GLUC','Glucose','Basic Chemistry','mg/dL',70,140,155,30),
    ('CA','Calcium','Basic Chemistry','mg/dL',8.5,10.5,8.7,0.4),
    ('MG','Magnesium','Basic Chemistry','mg/dL',1.7,2.2,1.9,0.2),
    ('PHOS','Phosphate','Basic Chemistry','mg/dL',2.5,4.5,3.3,0.6),
    ('HGB','Hemoglobin','CBC','g/dL',12,17,10.8,1.2),
    ('HCT','Hematocrit','CBC','%',36,50,33,3),
    ('WBC','White blood cells','CBC','X10E+09/L',4.0,11.0,13.5,3.0),
    ('PLT','Platelets','CBC','X10E+09/L',150,450,190,40),
    ('RBC','Red blood cells','CBC','X10E+12/L',4.2,5.9,3.8,0.3),
    ('PHA','pH (arterial)','Blood Gases','',7.35,7.45,7.31,0.05),
    ('PACO2','PaCO2','Blood Gases','mmHg',35,45,48,5),
    ('PAO2','PaO2','Blood Gases','mmHg',80,100,72,9),
    ('HCO3','HCO3','Blood Gases','mEq/L',22,26,21,2),
    ('LACT','Lactate','Blood Gases','mmol/L',0.5,2.0,3.1,0.8),
    ('PT','Prothrombin time','Coagulation','sec',11,14,13.2,0.9),
    ('INR','INR','Coagulation','',0.9,1.2,1.3,0.15),
    ('PTT','Partial TT','Coagulation','sec',25,35,34,4),
    ('ALT','ALT','Liver Function','U/L',7,56,62,14),
    ('AST','AST','Liver Function','U/L',10,40,58,12),
    ('TBIL','Total bilirubin','Liver Function','mg/dL',0.2,1.2,1.5,0.4),
    ('ALB','Albumin','Liver Function','g/dL',3.4,5.4,2.8,0.3),
    ('TROP','Troponin I','Cardiac','ng/mL',0.0,0.04,0.03,0.02),
    ('BNP','BNP','Cardiac','pg/mL',0,100,250,80),
    # --- Other Chemistry ---
    ('AGAP',  'Anion Gap',           'Other Chemistry', 'mEq/L',   8,   16,   13,   3),
    ('GFR',   'GFR',                 'Other Chemistry', 'mL/min',  90,  120,  38,   10),
    ('LIPASE','Lipase',              'Other Chemistry', 'U/L',     10,  60,   28,   8),
    ('OSMO',  'Osmolality',          'Other Chemistry', 'mOsm/kg', 275, 295,  289,  6),
    ('TP',    'Total Protein',       'Other Chemistry', 'g/dL',    6.0, 8.3,  5.8,  0.5),
    ('CAI',   'Ionized Calcium',     'Other Chemistry', 'mmol/L',  1.05,1.30, 1.12, 0.05),
    # --- Additional Blood Gases (venous + more) ---
    ('PHV',   'pH (venous)',         'Blood Gases', '',           7.32, 7.42, 7.28, 0.05),
    ('PVCO2', 'PCO2 (venous)',       'Blood Gases', 'mmHg',       41,   51,   52,   4),
    ('PVO2',  'PO2 (venous)',        'Blood Gases', 'mmHg',       35,   45,   38,   5),
    ('HCO3V', 'HCO3 (venous)',       'Blood Gases', 'mEq/L',      23,   27,   20,   2),
    ('BDA',   'Base Deficit (art)',  'Blood Gases', 'mEq/L',      -2,   2,    4,    2),
    ('BDV',   'Base Deficit (ven)',  'Blood Gases', 'mEq/L',      -2,   2,    3,    2),
    ('SATA',  'SO2 (arterial)',      'Blood Gases', '%',          95,   100,  93,   3),
    ('SATV',  'SO2 (venous)',        'Blood Gases', '%',          65,   80,   72,   6),
    # --- Additional Liver ---
    ('ALKP',  'Alk Phosphatase',     'Liver Function', 'U/L',     44,  147,  188,  30),
]
VITALS = [
    ('VTHR','Heart rate','Vitals','bpm',60,100,95,10),
    ('VTSPO2','SpO2','Vitals','%',95,100,93,3),
    ('VTTMP','Temperature','Vitals','C',36.5,37.5,38.1,0.5),
    ('VTRR','Respiratory rate','Vitals','/min',12,20,24,4),
    ('VTSYS','Systolic BP','Vitals','mmHg',90,140,105,15),
    ('VTDIA','Diastolic BP','Vitals','mmHg',60,90,62,10),
    ('VTMAP','Mean arterial P','Vitals','mmHg',70,105,77,12),
    ('VTWT',  'Weight',           'Vitals',     'kg',    50,  120, 72,  1.5),
    ('VTFIO2','FiO2','Ventilator','%',21,100,60,15),
    ('VTPEEP','PEEP','Ventilator','cmH2O',5,15,10,2),
    ('VTVT','Tidal volume','Ventilator','mL',350,550,420,40),
]
GROUP_ORDER = ['Basic Chemistry','CBC','Blood Gases','Coagulation','Liver Function','Cardiac','Vitals','Ventilator']

CASES = [
    ('99999991','ARF',101,{'age':58,'sex':'F','height':165,'weight':72,'bmi':26.4,'race':'Unknown'}),
    ('99999992','ARF',202,{'age':67,'sex':'M','height':178,'weight':84,'bmi':26.5,'race':'Unknown'}),
    ('99999993','AKF',303,{'age':71,'sex':'F','height':160,'weight':65,'bmi':25.4,'race':'Unknown'}),
    ('99999994','ARF',404,{'age':54,'sex':'M','height':182,'weight':95,'bmi':28.7,'race':'Unknown'}),
    ('99999995','AKF',505,{'age':63,'sex':'F','height':168,'weight':78,'bmi':27.6,'race':'Unknown'}),
    ('99999996','ARF',606,{'age':45,'sex':'M','height':175,'weight':82,'bmi':26.8,'race':'Unknown'}),
    ('99999997','ARF',707,{'age':76,'sex':'F','height':158,'weight':60,'bmi':24.0,'race':'Unknown'}),
]
CASE_HIGHLIGHTS = {
    '99999991': (['CREAT','BUN','K','LACT','HGB'], ['HGB'], ['TROP','BNP']),
    '99999992': (['NA','CO2','GLUC','WBC','ALB'],  ['ALB'], ['PT','TBIL']),
    '99999993': (['CREAT','BUN','K','MG','PHOS'],  ['PHOS'],['ALT','INR']),
    '99999994': (['HGB','HCT','PLT','WBC','LACT'], ['LACT'],['CA','MG']),
    '99999995': (['CREAT','BUN','K','NA','CL'],    ['CL'],  ['BNP','TROP']),
    '99999996': (['LACT','PHA','PAO2','PACO2','HGB'],['HGB'],['AST','ALT']),
    '99999997': (['CREAT','BUN','K','HGB','ALB'],  ['ALB'], ['TROP','INR']),
}
CONDITIONS = {'none':(0,0,0),'correct':(1,0,0),'mixed':(1,0,1)}
P01_SEQUENCE = [
    ('99999991','none'),('99999992','none'),('99999993','none'),
    ('99999994','correct'),('99999995','correct'),
    ('99999996','mixed'),('99999997','mixed'),
]

FAKE_HP_NOTE = """== HISTORY & PHYSICAL (SYNTHETIC PLACEHOLDER) ==
This is placeholder demonstration text - not derived from any real patient.

CHIEF COMPLAINT: Shortness of breath and confusion.

HISTORY OF PRESENT ILLNESS:
Patient presenting to the ED with 3-day history of progressive dyspnea,
low-grade fever, and worsening mental status.

PAST MEDICAL HISTORY: Hypertension, T2DM, CKD stage III.
MEDICATIONS ON ADMISSION: Lisinopril, Metformin, Aspirin.

PHYSICAL EXAM:
- Vitals: T 38.1 C, HR 95, BP 105/62, RR 24, SpO2 93% RA
- General: ill-appearing, mild respiratory distress
- Cardiac: tachycardic, regular
- Pulmonary: bilateral basilar crackles

ASSESSMENT & PLAN:
1. Acute respiratory failure - supplemental O2, blood gas, CXR
2. AKI on CKD - nephrology consult, monitor UOP, hold nephrotoxins
3. Sepsis workup - blood cultures, empiric broad-spectrum antibiotics
4. T2DM - hold metformin, insulin sliding scale

Demonstration case only. Do not use for clinical training or evaluation
of real patients.
"""


FAKE_PROGRESS_NOTE = """== PROGRESS NOTE (SYNTHETIC PLACEHOLDER) ==

SUBJECTIVE: Overnight, patient tolerated NIV. Reports mild dyspnea on
exertion. No new complaints.

OBJECTIVE:
- Vitals: T 37.6 C, HR 88, BP 118/72, RR 20, SpO2 96% on NC 4L
- Labs: WBC 12.4, Cr 1.6 (improved), Lactate 2.1
- I/O: net positive 400 mL

ASSESSMENT: 58 yo F with sepsis/AKI, clinically improving.

PLAN:
1. Continue empiric antibiotics x 48 hr, narrow with culture data.
2. Continue nephrology consult; hold nephrotoxins.
3. Wean supplemental O2 as tolerated.
4. Nutrition consult if not tolerating diet by day 3.

Demonstration text only.
"""

FAKE_OP_NOTE = """== OPERATIVE NOTE (SYNTHETIC PLACEHOLDER) ==

PROCEDURE: Right internal jugular central venous catheter placement.
INDICATION: Vasopressor support and central access.

DESCRIPTION:
After informed consent, the right neck was prepped and draped in
sterile fashion. Under ultrasound guidance, the right IJ was accessed
on first pass with a 21g needle. Guidewire advanced without resistance.
Dilation performed. Triple-lumen catheter passed to 16 cm and secured.
CXR confirmed appropriate position without pneumothorax.

Demonstration text only.
"""

FAKE_RAD_NOTE = """== RADIOLOGY REPORT (SYNTHETIC PLACEHOLDER) ==

STUDY: Chest X-ray, portable AP.
INDICATION: Hypoxemia, evaluate for pneumonia.

FINDINGS:
Bibasilar patchy opacities with slight right lower lobe predominance,
compatible with early pneumonia. No pneumothorax. Cardiomediastinal
silhouette within normal limits. No pleural effusion.

IMPRESSION:
1. Bibasilar opacities, likely pneumonia.
2. No pneumothorax or effusion.

Demonstration text only.
"""

FAKE_EKG_NOTE = """== EKG (SYNTHETIC PLACEHOLDER) ==

Sinus tachycardia at 105 bpm. Normal axis. No acute ST-T changes.
No Q waves. QTc 420 ms. No prior for comparison.

IMPRESSION: Sinus tachycardia. No acute ischemic changes.

Demonstration text only.
"""

FAKE_MICRO_REPORT = """== MICROBIOLOGY (SYNTHETIC PLACEHOLDER) ==

SPECIMEN: Blood culture x 2 (drawn 09/12 at 06:15).
RESULT (preliminary, 24 hr): No growth to date.

Note: Cultures held for total of 5 days. Preliminary result should be
correlated with clinical picture and repeat cultures if indicated.

Demonstration text only.
"""

def _note_list(prefix, base_ms, count, kind, body):
    """Build a list of note dicts (upk, date, js_time, type, text) matching
    the shape report_template.html iterates. Each note is spaced 6 hours
    apart starting from base_ms; each gets a distinct header so tab-switching
    within a category is visibly different."""
    import datetime
    out = []
    for i in range(count):
        t_ms = base_ms + i * 6 * 3600 * 1000
        dt = datetime.datetime.fromtimestamp(t_ms / 1000.0)
        header = ("<div style='background:#eef; padding:6px 10px; "
                  "margin-bottom:10px; font-family:monospace;'>"
                  "&larr; {kind} · Note {n} of {tot} · {when}</div>").format(
                  kind=kind, n=i+1, tot=count, when=dt.strftime("%Y-%m-%d %H:%M"))
        variant = ("\n\n[--- Note {n} of {tot} variant ---]\n"
                   "This is the {n}th note in the {kind} sequence for this "
                   "synthetic case; the header above and this line change per "
                   "note so tab-switching is visible.").format(
                   n=i+1, tot=count, kind=kind)
        out.append({
            'upk':     "{}_{:03d}".format(prefix, i),
            'date':    dt.strftime("%Y-%m-%d %H:%M"),
            'js_time': str(t_ms),
            'type':    "{} #{}".format(kind, i+1),
            'text':    header + "<pre style='white-space:pre-wrap'>" + body + variant + "</pre>",
        })
    return out

def make_series(mean, std, low, high, t_admit, t_end, n_points=48):
    dt = (t_end - t_admit) / max(1, n_points - 1)
    out = []
    trend = random.uniform(-std/3, std/3)
    for i in range(n_points):
        t = (t_admit + i * dt) * 1000
        v = mean + trend * i / n_points + random.gauss(0, std * 0.6)
        v = max(low * 0.5, min(high * 1.5, v))
        out.append([int(t), round(v, 2)])
    return out

def _series_dict(items, t_admit, t_end, n_points):
    d = {}
    for abbr, name, group, unit, lo, hi, mean, std in items:
        series = make_series(mean, std, lo, hi, t_admit, t_end, n_points)
        color = GROUP_COLOR.get(group, '#2c3e50')
        s = [{'name': abbr, 'data': series, 'color': color, 'marker': {'radius': 3}}]
        r = [round(lo * 0.5, 2), round(hi * 1.6, 2)]
        d[abbr] = json.dumps([s, [], r, [lo, hi], str(series[-1][1]), unit])
    return d

def build_labs_dict(t_admit, t_end):   return _series_dict(LABS, t_admit, t_end, 48)
def build_vitals_dict(t_admit, t_end):
    d = _series_dict(VITALS, t_admit, t_end, 72)
    # Add I/O as a special stacked-column series under key 'IO'
    d['IO'] = build_io_series(t_admit, t_end)
    return d

def build_recent_results():
    r = {}
    for abbr, _, _, _, lo, hi, mean, std in LABS + VITALS:
        r[abbr] = round(mean, 2)
    return r

def build_demographics(case_id, demo):
    d = dict(demo); d['id'] = case_id; return d

def build_global_time(t_admit, t_end):
    return {'min_t': int(t_admit*1000), 'max_t': int(t_end*1000),
            'cut1': int((t_admit + 2*DAY)*1000), 'cut2': int((t_admit + 2.5*DAY)*1000)}

def build_display_names():
    return {abbr: name for abbr, name, *_ in LABS + VITALS}

def build_group_membership():
    d = {name: [] for name in ('Vitals','Ventilator','CBC','Basic Chemistry','Blood Gases',
                                'Coagulation','Liver Function','Cardiac','CMP','Meds','IO')}
    for abbr, _, group, *_ in LABS + VITALS:
        d.setdefault(group, []).append(abbr)
    return d

def build_group_order():   return list(GROUP_ORDER)

def build_global_params():
    d = {}
    for abbr, name, group, unit, lo, hi, mean, std in LABS + VITALS:
        d[abbr] = {'unit': unit, 'norm_range': [lo, hi], 'abs_range': [lo*0.5, hi*1.6]}
    return d

def dump(obj, *path_parts):
    path = os.path.join(*path_parts)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'wb') as f: pickle.dump(obj, f)

def write_text(text, *path_parts):
    path = os.path.join(*path_parts)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f: f.write(text)

def build_case(case_id, diagnosis, seed, demo):
    print("  case " + case_id + " (" + diagnosis + ")...")
    random.seed(seed)
    t_admit = T_ADMIT_BASE + seed * DAY
    t_end   = t_admit + 3 * DAY
    d = os.path.join(STUDY, 'cases_t2', case_id)
    dump(build_demographics(case_id, demo), d, 'demographics.p')
    dump(build_global_time(t_admit, t_end), d, 'global_time.p')
    dump(build_labs_dict(t_admit, t_end),   d, 'labs.p')
    dump(build_vitals_dict(t_admit, t_end), d, 'vitals.p')
    dump(build_recent_results(),            d, 'recent_results.p')
    # Meds (case_test_meds + display + routes_mapping + med_routes)
    med_info, display_meds, routes_map, med_routes = build_meds(t_admit, t_end)
    dump(med_info,     d, 'case_test_meds.p')
    dump(display_meds, d, 'display_med_names.p')
    dump(routes_map,   d, 'routes_mapping.p')
    dump(med_routes,   d, 'med_routes.p')
    dump({},           d, 'procedures.p')
    # Notes are stored as lists of dicts; the template counts len(list) for
    # the "Cons 3", "Prog 2" etc. badges above the notes panel. Each note
    # dict has: upk (unique key), date (display), js_time (ms since epoch),
    # type (subtype label), text (body content).
    hp_time = int((t_admit + 0.1 * DAY) * 1000)
    dump(_note_list('HP',  hp_time, count=2, kind='H&P',
                    body=FAKE_HP_NOTE), d, 'HP.p')
    dump(_note_list('PGN', hp_time, count=3, kind='Progress note',
                    body=FAKE_PROGRESS_NOTE), d, 'PGN.p')
    dump(_note_list('OP',  hp_time, count=1, kind='Operative note',
                    body=FAKE_OP_NOTE), d, 'OP.p')
    dump(_note_list('RAD', hp_time, count=2, kind='Radiology report',
                    body=FAKE_RAD_NOTE), d, 'RAD.p')
    dump(_note_list('EKG', hp_time, count=1, kind='EKG',
                    body=FAKE_EKG_NOTE), d, 'EKG.p')
    dump([],  d, 'other_notes.p')
    dump(_note_list('MICRO', hp_time, count=1, kind='Blood culture',
                    body=FAKE_MICRO_REPORT), d, 'micro_report.p')
    write_text('# id\tcatalog_display_name\tordered_as\n',
               d, 'med-display-id_to_name.txt')

def build_all_cases():
    print("Generating 7 synthetic cases:")
    for c in CASES: build_case(*c)

def build_globals_and_highlights():
    print("Generating global tests/ pickles and highlight files")
    tests_dir = os.path.join(STUDY, 'tests')
    dump(build_display_names(),   tests_dir, 'display_names.p')
    dump(build_group_membership(),tests_dir, 'group_membership.p')
    dump(build_group_order(),     tests_dir, 'group_order_labs.p')
    dump(build_global_params(),   tests_dir, 'global_params.p')
    ir = '\n'.join(cid + ': ' + ','.join(h[0]) for cid, h in CASE_HIGHLIGHTS.items()) + '\n'
    rn = '\n'.join(cid + ': ' + ','.join(h[1]) for cid, h in CASE_HIGHLIGHTS.items()) + '\n'
    nr = '\n'.join(cid + ': ' + ','.join(h[2]) for cid, h in CASE_HIGHLIGHTS.items()) + '\n'
    write_text(ir, STUDY, 'items_relevant_judges.txt')
    write_text(rn, STUDY, 'relevant_data_items_not_to_be_highlighted.txt')
    write_text(nr, STUDY, 'non_relevant_data_items_to_be_highlighted.txt')

def build_participant_files():
    print("Generating participant files (P01 + demo users)")
    pi_dir = os.path.join(STUDY, 'participant_info')
    write_text(
        '#username,access_code,cases_completed,status\n'
        'P01,0001,0,pending\n'
        'Interface_demo_without_highlights,0000,0,pending\n'
        'Interface_demo_with_highlights,0002,0,pending\n',
        pi_dir, 'participant_info.txt')
    header = ('#visitID,cuttime1,cuttime2,t1,t2,condition,'
              'show_highlights,highlights_only,incorrect_highlights\n')
    rows = []
    for case_id, cond_key in P01_SEQUENCE:
        sh, ho, ih = CONDITIONS[cond_key]
        diag = next(c[1] for c in CASES if c[0] == case_id)
        rows.append('{},0.0,0.0,0,0,{},{},{},{}\n'.format(case_id, diag, sh, ho, ih))
    write_text(header + ''.join(rows), pi_dir, 'P01.txt')
    write_text(header + '99999991,0.0,0.0,0,0,ARF,0,0,0\n',
               pi_dir, 'Interface_demo_without_highlights.txt')
    write_text(header + '99999991,0.0,0.0,0,0,ARF,1,0,1\n',
               pi_dir, 'Interface_demo_with_highlights.txt')

# ==== Meds + I/O =========================================================
# Meds are keyed by INTEGER med_id. Each med produces:
#   med_info[id]         = JSON [series, annotations, abs_range, [], recent, unit]
#   display_med_names[id]= "Drug 500 mg"
#   routes_mapping[route]= [id, id, ...]
# med_routes is the ordered list of route names.

MED_ROUTES_ORDER = ['By Mouth', 'IVPB', 'subQ', 'Home Medication', 'IV']

# (route, name, unit, dose, n_admins) — n_admins is how many dose events
MEDS = [
    ('By Mouth',        'Acetaminophen', 'mg',   650,  6),
    ('By Mouth',        'Metoprolol',    'mg',   25,   4),
    ('IVPB',            'Vancomycin',    'mg',   1000, 3),
    ('IVPB',            'Cefepime',      'g',    2,    4),
    ('IVPB',            'Metronidazole', 'mg',   500,  3),
    ('subQ',            'Heparin',       'units', 5000, 6),
    ('subQ',            'Insulin',       'units', 4,    8),
    ('Home Medication', 'Lisinopril',    'mg',   10,   1),
    ('Home Medication', 'Metformin',     'mg',   500,  1),
    ('IV',              'Norepinephrine','mcg/kg/min', 0.1, 40),
    ('IV',              'Propofol',      'mcg/kg/min', 20,  60),
    ('IV',              'Fentanyl',      'mcg/hr',     50,  30),
]

def build_meds(t_admit, t_end):
    """Return (med_info, display_med_names, routes_mapping, med_routes)."""
    med_info = {}
    display  = {}
    routes_map = {r: [] for r in MED_ROUTES_ORDER}
    for i, (route, name, unit, dose, n) in enumerate(MEDS, start=101):
        # Scatter points at even intervals spanning the case duration
        span_ms = int((t_end - t_admit) * 1000)
        step = span_ms // max(1, n)
        base = int(t_admit * 1000)
        # Use a fixed y-value per med so scatter dots line up horizontally
        y_val = round(dose, 2) if isinstance(dose, (int, float)) else 1
        pts = []
        for k in range(n):
            t = base + k * step + random.randint(0, step // 4)
            pts.append([t, y_val])
        series = [{'name': str(i), 'data': pts, 'color': '#000000',
                   'marker': {'symbol': 'circle'}}]
        # annotations parallel to series data: [value, unit] per point
        annotations = [[str(y_val), unit] for _ in pts]
        # IMPORTANT: store as Python LIST (not json.dumps string). The template
        # interpolates the value into a double-quoted JS string; a JSON string
        # with double-quotes would terminate the JS literal early. Python repr
        # uses single quotes, and get_med_chart in emr_3.js does .replace(/'/g,
        # '"') to convert to JSON before parseJSON. Matches loaddata.py's
        # curr_data shape (three elements: series list, text list, [min, max]).
        med_info[i] = [series, annotations, [0, y_val * 2 or 1]]
        display[i]  = '{} {} {}'.format(name, dose, unit)
        routes_map[route].append(i)
    return med_info, display, routes_map, list(MED_ROUTES_ORDER)


def build_io_series(t_admit, t_end):
    """I/O stacked columns — 3 days of intake (positive) and output (negative)."""
    days = 3
    step = 86400 * 1000  # ms
    base = int(t_admit * 1000)
    intake_oral = [[base + d * step, random.randint(200, 800)] for d in range(days)]
    intake_iv   = [[base + d * step, random.randint(1500, 3500)] for d in range(days)]
    output_urn  = [[base + d * step, -random.randint(600, 2000)] for d in range(days)]
    output_stl  = [[base + d * step, -random.randint(100, 400)] for d in range(days)]
    series = [
        {'name': 'Oral',     'data': intake_oral, 'color': '#f0ad4e'},
        {'name': 'IV',       'data': intake_iv,   'color': '#e37f42'},
        {'name': 'Urine',    'data': output_urn,  'color': '#5bc0de'},
        {'name': 'Stool',    'data': output_stl,  'color': '#337ab7'},
    ]
    # Return a Python LIST, not a json.dumps string — the template
    # interpolates I/O into a double-quoted JS argument, and JSON's
    # double quotes would terminate that string. Python repr uses single
    # quotes; get_io_chart in emr_3.js does .replace(/'/g, '"') to convert
    # to valid JSON before parsing.
    return [series, [], [-5000, 5000], [], '', 'mL']

if __name__ == '__main__':
    build_all_cases()
    build_globals_and_highlights()
    build_participant_files()
    print("\nDone. Restart the Django server so it picks up the new files.")
