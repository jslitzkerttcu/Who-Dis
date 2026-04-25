# Phase 9 Cutover Bundle — Operator Runbook

This directory contains the scripts that execute the one-time Who-Dis ->
SandCastle migration. They are designed to run in order; each is idempotent
(Pitfall 6 in 09-RESEARCH.md), so re-runs on partial failure are safe.

## Pre-flight (operator-side)

1. Create a `secrets.env` file with the following variables. **Never pass
   secrets via command-line arguments** (they appear in process lists and shell
   history):

   ```
   WHODIS_LIVE_DATABASE_URL=postgresql://user:pass@legacy-host:5432/whodis_db
   WHODIS_ENCRYPTION_KEY=<44-char Fernet key from legacy .env>
   PORTAL_BASE=https://sandcastle.ttcu.com
   PORTAL_TOKEN=<admin OIDC bearer token from portal UI>
   WHODIS_APP_ID=<UUID from portal app catalog after Plan 06 registration>
   KEYCLOAK_BASE=https://auth.sandcastle.ttcu.com
   KC_ADMIN_USER=<Keycloak admin console username>
   KC_ADMIN_PASS=<Keycloak admin console password>
   # Optional overrides (defaults shown):
   # KC_REALM=sandcastle
   # KC_CLIENT=who-dis
   ```

2. Source it: `set -o allexport; source secrets.env; set +o allexport`

3. Lock down the file: `chmod 600 secrets.env`. Delete after cutover.

4. Ensure pre-requisites are complete:
   - `provision-db.sh who-dis` has run on the SandCastle host
   - Who-Dis is registered in the portal catalog (Plan 06 Task 1) — `WHODIS_APP_ID` known
   - The `who-dis` Keycloak client exists with `viewer` and `admin` client roles
   - The legacy Who-Dis DB is in read-only / quiesced state (D-10)

## Execution order

### Step 1 — Migrate secrets to portal (D-12, this plan)

```bash
# Dry run first — inspect what will be migrated and flag unmapped keys
python scripts/cutover/migrate_secrets_to_portal.py --dry-run

# Execute for real
python scripts/cutover/migrate_secrets_to_portal.py
```

On success, every required env var is in the portal store. `KEYCLOAK_CLIENT_SECRET`
is NOT migrated by this script — Plan 06 Task 2 (operator) copies it from the
Keycloak admin console into the portal env-var store separately.

If the script warns about unmapped keys, extend `KEY_MAP` in the script and
re-run, or pass `--acknowledge-unmapped` if you have verified those keys are
not needed at runtime.

### Step 2 — Seed Keycloak admins (D-07, this plan)

```bash
# Dry run first — shows which emails will be seeded
python scripts/cutover/seed_keycloak_admins.py --dry-run --include-editors

# Execute for real
python scripts/cutover/seed_keycloak_admins.py --include-editors
```

`--include-editors` is the recommended default per the auto-mode editor -> admin
remap (Plan 03). This prevents day-1 lockout for users who had the legacy
`editor` role.

### Step 3 — Dump live schema -> generate Alembic baseline (Plan 04 / Pitfall 5)

```bash
bash scripts/cutover/dump_live_schema.sh > /tmp/live_schema.sql
```

See `alembic/versions/001_baseline_from_live_schema.py` docstring for the
autogen + hand-review steps. Commit the populated baseline before step 4.

### Step 4 — Restore live data -> stamp Alembic head (Plan 04)

```bash
# Dump data-only from the legacy DB:
pg_dump --data-only --disable-triggers --no-owner --no-privileges \
        -h LEGACY_HOST -U LEGACY_USER LEGACY_DB > /tmp/live_data.sql

# Restore on the SandCastle host:
bash scripts/cutover/restore_to_sandcastle.sh /tmp/live_data.sql
```

### Step 5 — Deploy via portal (Plan 06)

The portal triggers `git clone + compose build + compose up` for the who-dis
app. The container's `docker-entrypoint.sh` runs `alembic upgrade head` (no-op
because step 4 already stamped head) then starts gunicorn.

### Step 6 — Verify (Plan 06 UAT checkpoint)

- https://who-dis.sandcastle.ttcu.com/ -> Keycloak login -> land on home page
- Existing user can search a name; cached results visible (audit_log preserved)
- Admin user can reach admin pages (legacy editor users mapped to admin per
  `--include-editors`)
- Portal catalog shows who-dis as healthy

## Failure recovery

All five steps are idempotent; re-run on failure.

- **Step 1 fails with HTTP 4xx**: inspect portal logs; common causes: stale
  `PORTAL_TOKEN` (refresh it), wrong `WHODIS_APP_ID`, malformed key in `KEY_MAP`.
- **Step 1 warns UNMAPPED keys**: verify each key in the live DB; either add
  it to `KEY_MAP` or pass `--acknowledge-unmapped` if it is genuinely not needed.
- **Step 2 warns `<email> not found`**: investigate whether the user is still
  in Azure AD; if not, manually assign in Keycloak admin console post-cutover.
- **Step 3/4 fails**: the legacy DB remains untouched (read-only); fix the
  script and re-run.
- **Step 5 fails during compose up**: check portal deploy logs; env vars
  missing? Run step 1 again with `--force` to re-push any that were dropped.

## Post-cutover cleanup

```bash
rm /tmp/live_schema.sql /tmp/live_data.sql secrets.env
```

- Decommission of the legacy Azure App Service is OUT of scope for Phase 9
  (deferred per CONTEXT.md).
- The `configuration` table in the SandCastle DB is preserved for forensics but
  is no longer read by the running app; it will be dropped during a future
  maintenance window after production verification.
