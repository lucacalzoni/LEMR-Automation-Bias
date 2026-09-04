# -*- coding: utf-8 -*-
from django.conf.urls import url
from . import views

# nothing is for home screen
# \NUM\ is a patient id in demo mode
# \NUM\NUM\ is patient id and user id (used during labeling study)
# \NUM\NUM\\NUM\ is patient id, user id, and previous patient id (used during labeling study)
# \retrain\ will be used later when model building
# \save_input\ saves elemnt selections and likert scale data
# \eye_test\NUM\NUM\ is user_id and next patient Id. (always initiated from home screen)
# end \NUM\NUM\ is user_id and previous patient id. It closes study
# \load_cases\ is used to load the cases.

urlpatterns = [
    url(r'^$', views.index, name='index'),
    url(r'^home/(?P<user_id>\w+)/$', views.index, name='index'),
    url(r'^end/(?P<user_id>\w+)/$', views.end_of_study, name='end'),
    url(r'^(?P<patient_id>\d+)/(?P<user_id>\w+)/$', views.detail, name='detail'),
    url(r'^retrain/$', views.train, name='retrain'),
    url(r'^recording/$', views.recording, name='recording'),
    # `save_input` was the old eye-tracking-era catch-all for selection +
    # case-difficulty + clinical-impact rating. Replaced by the per-
    # participant JSON results store in Phase 6 (see results_io.py and
    # the save_phase_time / save_selection / save_commission / save_omission
    # endpoints). URL removed so no stale clients can write to it.
    url(r'^eye_test/(?P<user_id>\w+)/$', views.eye_test, name='eye_test'),
    url(r'^load_cases/$', views.loadcasedata, name='load_cases'),
    # Phase 6 — study data persistence + admin report.
    url(r'^save_phase_time/$',  views.save_phase_time,  name='save_phase_time'),
    url(r'^save_selection/$',   views.save_selection,   name='save_selection'),
    url(r'^save_commission/$',  views.save_commission,  name='save_commission'),
    url(r'^save_omission/$',    views.save_omission,    name='save_omission'),
    url(r'^save_trust/$',       views.save_trust,       name='save_trust'),
    url(r'^save_demographic/$', views.save_demographic, name='save_demographic'),
    url(r'^save_intro_seen/$',  views.save_intro_seen,  name='save_intro_seen'),
    url(r'^admin_report/$',     views.admin_report,     name='admin_report'),
    url(r'^reset_participant/$',views.reset_participant,name='reset_participant'),
    ]
# The .* catches all the special cases for lab names
