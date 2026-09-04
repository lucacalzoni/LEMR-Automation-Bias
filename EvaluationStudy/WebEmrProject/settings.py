# -*- coding: utf-8 -*-
# Django settings for WebEmrProject project.

import os

DEBUG = True

ADMINS = (
    # ('Your Name', 'your_email@example.com'),
)

MANAGERS = ADMINS

# --------------------------------------------------------------------------
# Phase 6 — coordinator admin report
# --------------------------------------------------------------------------
# Password protecting /WebEmrGui/admin_report/. Change this string to set a
# new password. The report is accessed by appending ?password=<value> to the
# URL (or via the login form on the report page).
#
# Phase 7 will move this to a gitignored local_settings.py for production.
LEMR_ADMIN_PASSWORD = 'changeme-lemr-2026'

# Phase 6 fix: switched from MySQL to SQLite.
#
# The Phase-6 simplified study persists everything to per-participant
# JSON files via results_io.py — the Django ORM is not used by any
# view. Django still requires *some* database backend to be configured
# at startup, so SQLite (Python stdlib, zero-install, file-based) is
# the lowest-friction choice. The same configuration works on the
# Bitnami Windows stack, on the developer's Mac, and on the Pitt VM —
# no MySQL server, no credentials, no network.
#
# The previous configuration carried two MySQL DSNs (a local 'default'
# for development and a 'remote' for a training-data server) from the
# original eye-tracking-era prototype. Both have been removed.
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'db.sqlite3'),
    },
}

# Hosts/domain names that are valid for this site; required if DEBUG is False
# See https://docs.djangoproject.com/en/1.4/ref/settings/#allowed-hosts
#
# When deployed behind a reverse proxy (e.g. nginx forwarding to Django
# on 127.0.0.1:8080), the reverse proxy makes the Host header equal to
# the public hostname, so the public hostname must be whitelisted below
# or Django's CommonMiddleware.process_request will raise DisallowedHost.
# In production, set DJANGO_ALLOWED_HOSTS to a comma-separated list of
# hostnames that should be allowed (e.g. "lemr.example.org,127.0.0.1").
# Localhost and 127.0.0.1 are always allowed so the developer runserver +
# browser-on-same-machine workflow keeps working without configuration.
ALLOWED_HOSTS = ['localhost', '127.0.0.1'] + [
    h.strip() for h in os.environ.get('DJANGO_ALLOWED_HOSTS', '').split(',') if h.strip()
]

# When TLS is eventually installed on the reverse proxy, nginx will
# terminate HTTPS and forward plain HTTP to Django on 8080. These two
# settings tell Django to trust the X-Forwarded-Proto / X-Forwarded-Host
# headers so `request.is_secure()` returns True for the outer HTTPS
# connection (matters for secure-cookie flags and CSRF) and generated
# absolute URLs use the public hostname rather than `localhost:8080`.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True

# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# In a Windows environment this must be set to your system time zone.
TIME_ZONE = 'America/Chicago'

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = 'en-us'

SITE_ID = 1

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# If you set this to False, Django will not format dates, numbers and
# calendars according to the current locale.
USE_L10N = True

# If you set this to False, Django will not use timezone-aware datetimes.
USE_TZ = True

# Absolute filesystem path to the directory that will hold user-uploaded files.
# Example: "/home/media/media.lawrence.com/media/"
MEDIA_ROOT = ''

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash.
# Examples: "http://media.lawrence.com/media/", "http://example.com/media/"
MEDIA_URL = ''

# Absolute path to the directory static files should be collected to.
# Don't put anything in this directory yourself; store your static files
# in apps' "static/" subdirectories and in STATICFILES_DIRS.
# Example: "/home/media/media.lawrence.com/static/"
STATIC_ROOT = ''

# URL prefix for static files.
# Example: "http://media.lawrence.com/static/"
STATIC_URL = '/static/'

# Additional locations of static files
STATICFILES_DIRS = (
    # Put strings here, like "/home/html/static" or "C:/www/django/static".
    # Always use forward slashes, even on Windows.
    # Don't forget to use absolute paths, not relative paths.
)

# List of finder classes that know how to find static files in
# various locations.
STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
#    'django.contrib.staticfiles.finders.DefaultStorageFinder',
)

# SECRET_KEY is read from the environment. For local development a random
# per-boot value is generated so 'manage.py runserver' works without setup;
# NEVER rely on this in production — set DJANGO_SECRET_KEY in the environment
# (see SETUP.md) so sessions, CSRF tokens, and signed cookies stay valid
# across restarts. This is a public code release; the previous hardcoded
# development key has been removed.
SECRET_KEY = os.environ.get(
    'DJANGO_SECRET_KEY',
    # Dev fallback: fresh random key each import — safe for local dev only.
    __import__('secrets').token_urlsafe(50),
)


MIDDLEWARE_CLASSES = (
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    # Uncomment the next line for simple clickjacking protection:
    # 'django.middleware.clickjacking.XFrameOptionsMiddleware',
)

ROOT_URLCONF = 'WebEmrProject.urls'

# Python dotted path to the WSGI application used by Django's runserver.
WSGI_APPLICATION = 'WebEmrProject.wsgi.application'

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

"""
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': []  # Django's APP_DIRS loader finds WebEmrGui/templates/ automatically
        ,
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
            'debug': DEBUG
        },
    },
]
"""
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                # Insert your TEMPLATE_CONTEXT_PROCESSORS here or use this
                # list if you haven't customized them:
                'django.contrib.auth.context_processors.auth',
                'django.template.context_processors.debug',
                'django.template.context_processors.i18n',
                'django.template.context_processors.media',
                'django.template.context_processors.static',
                'django.template.context_processors.tz',
                'django.contrib.messages.context_processors.messages',
            ]
        },
    },
]

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'WebEmrGui'
    # Uncomment the next line to enable the admin:
    # 'django.contrib.admin',
    # Uncomment the next line to enable admin documentation:
    # 'django.contrib.admindocs',
)

# A sample logging configuration. The only tangible logging
# performed by this configuration is to send an email to
# the site admins on every HTTP 500 error when DEBUG=False.
# See http://docs.djangoproject.com/en/dev/topics/logging for
# more details on how to customize your logging configuration.
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse'
        }
    },
    'handlers': {
        'mail_admins': {
            'level': 'ERROR',
            'filters': ['require_debug_false'],
            'class': 'django.utils.log.AdminEmailHandler'
        }
    },
    'loggers': {
        'django.request': {
            'handlers': ['mail_admins'],
            'level': 'ERROR',
            'propagate': True,
        },
    }
}
