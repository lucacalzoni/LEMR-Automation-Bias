# -*- coding: utf-8 -*-
"""
Trust-in-automation instrument used by the 2026 LEMR simplified study.

Adapted from:
    McKnight, D. H., Choudhury, V., & Kacmar, C. (2002). Developing and
    validating trust measures for e-commerce: An integrative typology.

The pre-use battery (administered before the introductory case) has 18
items spread across 6 categories of 3 questions each. The post-use
battery (administered after the final test case) has 9 items spread
across 3 categories of 3 questions each — only the LEMR-specific
"Trusting Belief — Specific Technology" sub-scales are repeated post-use.

UI policy:
  * Category labels are tracked internally for analysis but NEVER shown
    to the participant. Each question is rendered with its sequential id
    only (e.g. "Question 7 of 18").
  * All items use the same 5-point Likert anchors:
        1 = Strongly disagree
        2 = Somewhat disagree
        3 = Neither agree nor disagree
        4 = Somewhat agree
        5 = Strongly agree
"""

from __future__ import print_function, unicode_literals
# `unicode_literals` makes every plain string literal in this file a
# Python-2 `unicode` object rather than a `bytes` object. Without this,
# json.dumps(...) on PRE_QUESTIONS would raise UnicodeDecodeError when it
# encounters the em-dashes / curly quotes in the question text, because
# Py2 json.dumps tries to decode byte strings as ASCII.


# Category codes used internally for grouping. Stable strings — do NOT
# change without also updating the admin report aggregation code.
SN_TECH         = 'situational_normality_technology'
FAITH_TECH      = 'faith_in_general_technology'
TRUSTING_STANCE = 'trusting_stance_general_technology'
TB_RELIABILITY  = 'trusting_belief_reliability'
TB_FUNCTIONALITY = 'trusting_belief_functionality'
TB_HELPFULNESS  = 'trusting_belief_helpfulness'


LIKERT_ANCHORS = [
    {'value': 1, 'label': 'Strongly disagree'},
    {'value': 2, 'label': 'Somewhat disagree'},
    {'value': 3, 'label': 'Neither agree nor disagree'},
    {'value': 4, 'label': 'Somewhat agree'},
    {'value': 5, 'label': 'Strongly agree'},
]


# ---------------------------------------------------------------------
# Pre-use questions (18 items in 6 categories)
# ---------------------------------------------------------------------
PRE_QUESTIONS = [
    # Situational Normality — Technology
    {'id': 'pre_01', 'category': SN_TECH,
     'text': 'I am totally comfortable working with computer decision support tools.'},
    {'id': 'pre_02', 'category': SN_TECH,
     'text': 'I feel very good about how things go when I use computer decision support tools.'},
    {'id': 'pre_03', 'category': SN_TECH,
     'text': 'I always feel confident that the right things will happen when I use computer decision support tools.'},

    # Faith in General Technology
    {'id': 'pre_04', 'category': FAITH_TECH,
     'text': 'I believe that most technologies are effective at what they are designed to do.'},
    {'id': 'pre_05', 'category': FAITH_TECH,
     'text': 'Most technologies have the features needed for their domain.'},
    {'id': 'pre_06', 'category': FAITH_TECH,
     'text': 'I think most technologies enable me to do what I need to do.'},

    # Trusting Stance — General Technology
    {'id': 'pre_07', 'category': TRUSTING_STANCE,
     'text': 'My typical approach is to trust new technologies until they prove to me that I shouldn’t trust them.'},
    {'id': 'pre_08', 'category': TRUSTING_STANCE,
     'text': 'I usually trust a technology until it gives me a reason not to trust it.'},
    {'id': 'pre_09', 'category': TRUSTING_STANCE,
     'text': 'I generally give a technology the benefit of the doubt when I first use it.'},

    # Trusting Belief — Specific Technology — Reliability
    {'id': 'pre_10', 'category': TB_RELIABILITY,
     'text': 'I expect the Learning EMR to be a very reliable piece of software.'},
    {'id': 'pre_11', 'category': TB_RELIABILITY,
     'text': 'I expect the Learning EMR to be dependable.'},
    {'id': 'pre_12', 'category': TB_RELIABILITY,
     'text': 'I expect the Learning EMR to not malfunction for me.'},

    # Trusting Belief — Specific Technology — Functionality
    {'id': 'pre_13', 'category': TB_FUNCTIONALITY,
     'text': 'I expect the Learning EMR to have the functionality I need.'},
    {'id': 'pre_14', 'category': TB_FUNCTIONALITY,
     'text': 'I expect the Learning EMR to have the features required for my tasks.'},
    {'id': 'pre_15', 'category': TB_FUNCTIONALITY,
     'text': 'I expect the Learning EMR to have the ability to do what I want it to do.'},

    # Trusting Belief — Specific Technology — Helpfulness
    {'id': 'pre_16', 'category': TB_HELPFULNESS,
     'text': 'I expect the Learning EMR to be potentially helpful in a clinical setting.'},
    {'id': 'pre_17', 'category': TB_HELPFULNESS,
     'text': 'I expect the Learning EMR to supply my need to easily identify the most relevant information to understanding each patient case.'},
    {'id': 'pre_18', 'category': TB_HELPFULNESS,
     'text': 'I expect the Learning EMR to provide very sensible and effective advice, if needed.'},
]


# ---------------------------------------------------------------------
# Post-use questions (9 items in 3 categories — LEMR-specific only)
# ---------------------------------------------------------------------
POST_QUESTIONS = [
    # Trusting Belief — Specific Technology — Reliability
    {'id': 'post_01', 'category': TB_RELIABILITY,
     'text': 'The Learning EMR was a very reliable piece of software.'},
    {'id': 'post_02', 'category': TB_RELIABILITY,
     'text': 'The Learning EMR was extremely dependable.'},
    {'id': 'post_03', 'category': TB_RELIABILITY,
     'text': 'The Learning EMR did not malfunction for me.'},

    # Trusting Belief — Specific Technology — Functionality
    {'id': 'post_04', 'category': TB_FUNCTIONALITY,
     'text': 'The Learning EMR has the functionality I need.'},
    {'id': 'post_05', 'category': TB_FUNCTIONALITY,
     'text': 'The Learning EMR has the features required for my tasks.'},
    {'id': 'post_06', 'category': TB_FUNCTIONALITY,
     'text': 'The Learning EMR has the ability to do what I want it to do.'},

    # Trusting Belief — Specific Technology — Helpfulness
    {'id': 'post_07', 'category': TB_HELPFULNESS,
     'text': 'I find the Learning EMR potentially helpful in a clinical setting.'},
    {'id': 'post_08', 'category': TB_HELPFULNESS,
     'text': 'The Learning EMR supplies my need to easily identify the most relevant information to understanding each patient case.'},
    {'id': 'post_09', 'category': TB_HELPFULNESS,
     'text': 'The Learning EMR provides very sensible and effective advice, if needed.'},
]


def questions_for(when):
    """Return the question list for `when` ('pre' or 'post')."""
    if when == 'pre':
        return PRE_QUESTIONS
    if when == 'post':
        return POST_QUESTIONS
    return []


def valid_question_id(when, qid):
    """True iff qid is a known question id for the given timing."""
    return any(q['id'] == qid for q in questions_for(when))


def category_for(when, qid):
    """Return the category code for a question id, or None if unknown."""
    for q in questions_for(when):
        if q['id'] == qid:
            return q['category']
    return None


CATEGORY_LABELS = {
    SN_TECH:          'Situational Normality — Technology',
    FAITH_TECH:       'Faith in General Technology',
    TRUSTING_STANCE:  'Trusting Stance — General Technology',
    TB_RELIABILITY:   'Trusting Belief — Reliability',
    TB_FUNCTIONALITY: 'Trusting Belief — Functionality',
    TB_HELPFULNESS:   'Trusting Belief — Helpfulness',
}
