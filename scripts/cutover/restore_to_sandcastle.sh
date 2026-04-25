#!/usr/bin/env bash
# Phase 9 cutover helper — restore live Who-Dis data into the SandCastle whodis_db.
# Run on the SandCastle host. ASSUMES `provision-db.sh who-dis` has already run.
#
# Usage:
#   # 1) Dump from the legacy host (data only — we already have schema via Alembic baseline):
#   pg_dump --data-only --disable-triggers --no-owner --no-privileges \
#           -h LEGACY_HOST -U LEGACY_USER LEGACY_DB > /tmp/live_data.sql
#
#   # 2) On the SandCastle host with the file copied over:
#   set -o allexport; source secrets.env; set +o allexport
#   bash scripts/cutover/restore_to_sandcastle.sh /tmp/live_data.sql
#
# After restore, chmod 600 /tmp/live_data.sql and delete after cutover is confirmed (T-09-04-01).
#
# Required env: WHODIS_DATABASE_URL (from `provision-db.sh who-dis` output)
#
# Procedure (per D-08, D-10, Pitfall 5):
#   a) Run `alembic upgrade head` once against the empty whodis_db to create the schema
#      (the baseline migration MUST already be populated — see 001_baseline_from_live_schema.py).
#   b) `pg_restore` (or `psql` for plain SQL) the data-only dump.
#   c) Run `alembic stamp head` (no-op since we already upgraded; included for clarity).
set -euo pipefail

: "${WHODIS_DATABASE_URL:?WHODIS_DATABASE_URL is required (from provision-db.sh who-dis)}"

DUMP_FILE="${1:?Usage: restore_to_sandcastle.sh <data-dump.sql>}"
test -r "$DUMP_FILE" || { echo "ERROR: cannot read $DUMP_FILE" >&2; exit 1; }

echo "==> Step 1/3: alembic upgrade head (creates schema from baseline)"
DATABASE_URL="$WHODIS_DATABASE_URL" alembic upgrade head

echo "==> Step 2/3: psql restore (data only)"
psql "$WHODIS_DATABASE_URL" < "$DUMP_FILE"

echo "==> Step 3/3: alembic stamp head (idempotent confirmation)"
DATABASE_URL="$WHODIS_DATABASE_URL" alembic stamp head

echo "==> Done. Verify with: psql \"\$WHODIS_DATABASE_URL\" -c '\dt' and 'SELECT COUNT(*) FROM users;'"
