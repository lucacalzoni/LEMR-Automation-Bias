# Setup

This fork targets **Python 3.9** and **Django 1.11**. Django 1.11 is end-of-life; it
is pinned here because the codebase was ported from Python 2 while intentionally
retaining Django 1.11 (the study did not need a framework upgrade, and modernising
Django would have required rewriting the templating and ORM layers without changing
any of the study behaviour). A future release may modernise Django; contributions on
that path are welcome (see [CONTRIBUTING.md](../CONTRIBUTING.md)).

## Option A — Docker (recommended)

Requires Docker Desktop or Docker Engine.

```bash
docker compose up --build
# then open http://127.0.0.1:8000/WebEmrGui/
```

The compose file pins Python 3.9 + Django 1.11 in an isolated container so you do not
have to install EOL packages on your host. Data volumes are mounted from
`./resources/demo_study/` by default.

## Option B — Local Python virtualenv

Requires Python 3.9 installed on the host (pyenv, `brew install python@3.9`, or a
system package).

```bash
git clone https://github.com/<your-user>/LEMR.git
cd LEMR

# Create an isolated environment
python3.9 -m venv .venv
source .venv/bin/activate

# Install pinned dependencies
pip install -r requirements.txt

# Initialise the SQLite database (empty; used only for participant state)
cd EvaluationStudy
python manage.py migrate

# Generate the participant randomization
python scripts/generate_participants.py

# Boot the dev server on port 8000
python manage.py runserver 0.0.0.0:8000
```

Open `http://127.0.0.1:8000/WebEmrGui/` in a browser. The home screen lists the
available participants (P01–P24 by default) and the two demo users.

## Environment variables

The runtime reads the following from the environment; sensible defaults let the
dev server work out of the box.

| Variable | Purpose | Default |
| --- | --- | --- |
| `DJANGO_SECRET_KEY` | Django session/CSRF signing key. **Set this in production**, or sessions will invalidate every restart. | random per-boot value |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated list of public hostnames to whitelist behind a reverse proxy. | empty (localhost + 127.0.0.1 always allowed) |
| `LEMR_DATA_DIR` | Optional override for where case data (`.p` files) is loaded from. | `models/evaluation_study/data/` |
| `LEMR_ADMIN_PASSWORD` | Password that gates `/WebEmrGui/admin_report/`. Change this before any non-demo deployment. | `demo` |

## Case data

The Django app expects pickled `.p` files under `models/evaluation_study/data/<CASE_ID>/`
for each case ID listed in `EvaluationStudy/scripts/generate_participants.py`
(`CASE_METADATA`). The upstream King repository ships three synthetic demo cases in
`resources/demo_study/` you can copy in as a starting point; see
[CASE_FORMAT.md](CASE_FORMAT.md) for the schema.

## Deployment behind a reverse proxy

If you deploy behind nginx / Caddy / Apache terminating TLS, set:

- `DJANGO_ALLOWED_HOSTS=your-public-hostname.example.org`
- `DJANGO_SECRET_KEY=<long random string, e.g. from `python -c 'import secrets; print(secrets.token_urlsafe(50))'`>`

The `SECURE_PROXY_SSL_HEADER` and `USE_X_FORWARDED_HOST` settings in
`WebEmrProject/settings.py` are already configured for `X-Forwarded-Proto` /
`X-Forwarded-Host`. Point your reverse proxy at `127.0.0.1:8080` (or whichever port
you bind the app to) and it will honour the outer HTTPS scheme.

## Health check

```bash
python manage.py check
```

Should print `System check identified no issues (0 silenced).`
