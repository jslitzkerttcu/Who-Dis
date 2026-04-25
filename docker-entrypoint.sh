#!/usr/bin/env bash
# Phase 9 SandCastle entrypoint — Alembic auto-migrate, then gunicorn (WD-CONT-02, WD-DB-02)
set -euo pipefail

# WD-DB-02: schema applied via Alembic on container start (idempotent — no-op if already at head)
alembic upgrade head

# WD-CONT-02: production WSGI server (NOT flask run / werkzeug)
exec gunicorn \
  --bind 0.0.0.0:5000 \
  --workers "${GUNICORN_WORKERS:-2}" \
  --worker-class sync \
  --timeout 60 \
  --access-logfile - \
  --error-logfile - \
  "app:create_app()"
