# LEMR study fork — minimal container for reviewers + reproducers.
# Ships Python 3.9 + Django 1.11 pinned so users don't have to fight
# EOL versions on their host.
FROM python:3.9-slim

# System deps: minimal, just what Django + Pillow need.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libjpeg-dev zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy the app tree
COPY . /app/

WORKDIR /app/EvaluationStudy

# Initialise the sqlite DB at build time so first-boot is instant
RUN python manage.py migrate --noinput

EXPOSE 8000
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
