#!/bin/sh
# Container entrypoint: apply migrations, then serve. The platform sets PORT (Render: 10000).
set -e
python manage.py migrate --noinput
# Analyses wait on external providers (retries included), so allow longer than the 30 s default.
exec gunicorn config.wsgi:application \
  --bind "0.0.0.0:${PORT:-8000}" \
  --workers "${WEB_CONCURRENCY:-2}" \
  --timeout "${GUNICORN_TIMEOUT:-90}" \
  --access-logfile -
