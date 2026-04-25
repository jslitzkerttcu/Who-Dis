#!/usr/bin/env bash
# Phase 9 SandCastle entrypoint — Alembic auto-migrate, schema guard, then gunicorn (WD-CONT-02, WD-DB-02).
# The schema guard catches the "fresh redeploy against empty DB" footgun:
# the Phase-9 baseline migration is a no-op scaffold (populated only during the
# one-time cutover via pg_restore + alembic stamp head — see Plan 04 docstring
# and scripts/cutover/restore_to_sandcastle.sh). Running this entrypoint against
# a freshly-provisioned empty who-dis_db would silently leave the DB schemaless
# and the app would 5xx on every request. Fail fast instead.
set -euo pipefail

# DATABASE_URL must be set before we can wait on it or run migrations.
: "${DATABASE_URL:?DATABASE_URL must be set}"

# Wait for Postgres to accept connections before attempting migrations.
# In containerized deployments the DB pod may not be ready when the app
# container starts; without this loop alembic fails fast and the container
# crash-loops. postgresql-client is installed in the Dockerfile (WD-DB-02).
WAIT_TIMEOUT="${DB_WAIT_TIMEOUT:-60}"
WAIT_ELAPSED=0
until pg_isready -d "$DATABASE_URL" >/dev/null 2>&1; do
  if [ "$WAIT_ELAPSED" -ge "$WAIT_TIMEOUT" ]; then
    echo "FATAL: database not ready after ${WAIT_TIMEOUT}s — giving up." >&2
    exit 1
  fi
  echo "Waiting for database (${WAIT_ELAPSED}s/${WAIT_TIMEOUT}s)..."
  sleep 2
  WAIT_ELAPSED=$((WAIT_ELAPSED + 2))
done

# WD-DB-02: schema applied via Alembic on container start (idempotent — no-op if at head)
alembic upgrade head

USERS_TABLE=$(psql "$DATABASE_URL" -tAc "SELECT to_regclass('public.users')")
if [ -z "$USERS_TABLE" ] || [ "$USERS_TABLE" = "" ]; then
  cat >&2 <<'GUARD'
FATAL: public.users does not exist after `alembic upgrade head`.

This container is running against an empty schema. The Phase 9 Alembic
baseline (001_baseline_from_live_schema.py) is a no-op scaffold; the schema
must be loaded BEFORE the container starts via the documented cutover path:

  1. provision-db.sh who-dis  (creates empty who-dis_db)
  2. pg_restore the live data (or alembic upgrade head against a populated
     baseline, IF the operator has run the autogen procedure and committed
     the body of 001_baseline_from_live_schema.py)
  3. alembic stamp head       (idempotent confirmation)

See docs/sandcastle.md "Rollback / Disaster Recovery" and
scripts/cutover/README.md for the full runbook. Container will not start
with an empty schema — fix the DB then redeploy.
GUARD
  exit 1
fi

# WD-CONT-02: production WSGI server
exec gunicorn \
  --bind 0.0.0.0:5000 \
  --workers "${GUNICORN_WORKERS:-2}" \
  --worker-class sync \
  --timeout 60 \
  --access-logfile - \
  --error-logfile - \
  "app:create_app()"
