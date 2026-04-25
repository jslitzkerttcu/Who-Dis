#!/usr/bin/env bash
# Phase 9 cutover helper — dump the LIVE Who-Dis schema for Alembic baseline generation.
# Run on a host that has network access to the legacy Who-Dis Postgres.
#
# Usage:
#   set -o allexport; source secrets.env; set +o allexport   # never pass via argv
#   bash scripts/cutover/dump_live_schema.sh > /tmp/live_schema.sql
#
# After dumping, chmod 600 /tmp/live_schema.sql and delete it after cutover (T-09-04-01).
#
# Required env: PGHOST, PGPORT, PGUSER, PGPASSWORD, PGDATABASE
set -euo pipefail

: "${PGHOST:?PGHOST is required}"
: "${PGPORT:?PGPORT is required}"
: "${PGUSER:?PGUSER is required}"
: "${PGPASSWORD:?PGPASSWORD is required}"
: "${PGDATABASE:?PGDATABASE is required}"

# --schema-only: DDL only, no data (data comes via pg_restore in restore_to_sandcastle.sh)
# --no-owner / --no-privileges: portable across hosts (no role assumption)
# --no-comments: cleaner diff for Alembic autogenerate
exec pg_dump \
  --schema-only \
  --no-owner \
  --no-privileges \
  --no-comments \
  --format=plain \
  "$PGDATABASE"
