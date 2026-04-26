# Deploying Who-Dis on SandCastle

This document is the canonical SandCastle deployment guide for Who-Dis. The
legacy Azure App Service path is documented in `docs/deployment.md` and is
deprecated post-Phase 9.

## Architecture summary

Who-Dis runs as a single gunicorn-served Flask container on the SandCastle
host. Traffic flows: Browser -> Traefik (TLS termination, letsencrypt) ->
Container (port 5000). Auth is delegated to Keycloak OIDC (federated to
TTCU Azure AD). Data lives in the shared SandCastle Postgres instance
(`who-dis_db`). Secrets are injected at deploy time from the portal env-var
store; no `.env` files are baked into images and no host-mounted config
files exist on the SandCastle host.

## Environment variable matrix (WD-CFG-05)

The canonical list lives in `.env.sandcastle.example` at the repo root.
Every key listed there must exist in the portal env-var store before the
container will start.

| Group | Keys | Source |
|-------|------|--------|
| Flask runtime | `FLASK_ENV`, `SECRET_KEY`, `GUNICORN_WORKERS` | Operator (generate `SECRET_KEY` with `python -c "import secrets; print(secrets.token_hex(32))"`) |
| Database | `DATABASE_URL` | Output of `./scripts/provision-db.sh who-dis` on the SandCastle host |
| Keycloak OIDC | `KEYCLOAK_ISSUER`, `KEYCLOAK_CLIENT_ID`, `KEYCLOAK_CLIENT_SECRET` | Realm-export.json values + Keycloak admin console Credentials tab |
| LDAP / AD | `LDAP_SERVER`, `LDAP_BIND_DN`, `LDAP_BIND_PASSWORD` | Migrated from legacy encrypted-config via `scripts/cutover/migrate_secrets_to_portal.py` (D-12) |
| Microsoft Graph | `GRAPH_TENANT_ID`, `GRAPH_CLIENT_ID`, `GRAPH_CLIENT_SECRET` | Migrated by D-12 cutover |
| Genesys Cloud | `GENESYS_CLIENT_ID`, `GENESYS_CLIENT_SECRET`, `GENESYS_REGION` | Migrated by D-12 cutover |

### Values not handled by the cutover script

These three keys must be set manually in the portal env-var UI (Apps ->
who-dis -> Env Vars) after app registration:

- `SECRET_KEY` — generate fresh: `python -c "import secrets; print(secrets.token_hex(32))"`
- `KEYCLOAK_ISSUER` = `https://auth.sandcastle.ttcu.com/realms/sandcastle`
- `KEYCLOAK_CLIENT_SECRET` — copy from Keycloak admin console
  (Clients -> who-dis -> Credentials tab) after realm import

## Keycloak OIDC setup (WD-AUTH-03)

The `who-dis` Keycloak client is defined in
`sandcastle-portal/keycloak/realm-export.json`:

- Realm: `sandcastle`
- Client ID: `who-dis` (confidential)
- Client Roles: `viewer`, `admin` (collapsed from legacy three-tier per D-05)
- Redirect URI: `https://who-dis.sandcastle.ttcu.com/*`
- Post-logout redirect: `https://who-dis.sandcastle.ttcu.com/*`
- Discovery URL (used by Authlib):
  `https://auth.sandcastle.ttcu.com/realms/sandcastle/.well-known/openid-configuration`

### Re-importing the realm after changes

```bash
# Restart Keycloak with auto-import (simplest path):
cd /path/to/sandcastle-portal
docker-compose restart keycloak

# Or: Keycloak admin console -> Realms -> sandcastle ->
#   Action -> Partial Import -> upload keycloak/realm-export.json
```

Verify: admin console -> sandcastle realm -> Clients -> `who-dis` exists with
`viewer` and `admin` client roles.

### Generating the client secret

Keycloak generates the secret on first realm import. Copy it from the admin
console (Clients -> who-dis -> Credentials) and paste into the portal env-var
store as `KEYCLOAK_CLIENT_SECRET`.

### Granting admin access to a new user

Keycloak admin console -> Users -> select user -> Role Mappings ->
Client Roles -> who-dis -> assign `admin`. The change takes effect on the
user's next login (token refresh).

## Database provisioning (WD-DB-01)

Run on the SandCastle host:

```bash
cd /path/to/sandcastle-portal
./scripts/provision-db.sh who-dis
```

Creates `who-dis_db` and `who-dis_user` with a generated password and emits
the `DATABASE_URL` string. Paste the output into the portal env-var store for
the who-dis app.

## Initial data migration (one-time, WD-DB-03)

The Phase 9 cutover bundle moves live Who-Dis data from the legacy host to
SandCastle. See `scripts/cutover/README.md` for the full operator runbook.
Summary of steps:

1. Source `secrets.env`:
   ```bash
   set -o allexport; source secrets.env; set +o allexport
   chmod 600 secrets.env
   ```

2. Migrate secrets to the portal (D-12):
   ```bash
   python scripts/cutover/migrate_secrets_to_portal.py --dry-run  # review first
   python scripts/cutover/migrate_secrets_to_portal.py
   ```

3. Seed Keycloak admins (D-07):
   ```bash
   python scripts/cutover/seed_keycloak_admins.py --dry-run --include-editors
   python scripts/cutover/seed_keycloak_admins.py --include-editors
   ```

4. Generate and commit the Alembic baseline body (Pitfall 5):
   ```bash
   bash scripts/cutover/dump_live_schema.sh > /tmp/live_schema.sql
   # Restore /tmp/live_schema.sql into a temp Postgres, run autogenerate,
   # hand-review, and commit the populated baseline migration.
   # See alembic/versions/001_baseline_from_live_schema.py docstring.
   ```

5. Restore live data:
   ```bash
   pg_dump --data-only --disable-triggers --no-owner --no-privileges \
     -h LEGACY_HOST -U LEGACY_USER LEGACY_DB > /tmp/live_data.sql
   bash scripts/cutover/restore_to_sandcastle.sh /tmp/live_data.sql
   ```

After step 5 the SandCastle `who-dis_db` mirrors the legacy DB content and
Alembic is stamped at `001_baseline_from_live_schema`.

## Deploy flow (WD-OPS-02)

The portal handles the full deploy lifecycle. Two trigger paths:

- **Manual** — Portal UI -> Apps -> who-dis -> Deploy
- **Automatic** — GitHub push to `main` triggers a webhook to
  `https://sandcastle.ttcu.com/api/webhooks/github` (HMAC-SHA256 verified)

Either path: the portal arq worker clones the repo, writes `.env` from the
portal env-var store, runs:

```
docker compose -f docker-compose.sandcastle.yml build
docker compose -f docker-compose.sandcastle.yml up -d
```

The container's `docker-entrypoint.sh` runs `alembic upgrade head` (idempotent
no-op after initial migration) before starting gunicorn. Live deploy logs stream
in the portal UI via SSE.

### GitHub webhook configuration

GitHub -> Who-Dis repo -> Settings -> Webhooks -> Add webhook:

| Field | Value |
|-------|-------|
| Payload URL | `https://sandcastle.ttcu.com/api/webhooks/github` |
| Content type | `application/json` |
| Secret | Portal `WEBHOOK_SECRET` (platform-wide, already configured) |
| Events | Just the push event |

Verify by pushing a trivial change to `main` and watching the portal deploy log.

## Rollback / Disaster Recovery (DEPL-04)

### Image rollback (routine)

Portal UI -> Apps -> who-dis -> Deployments -> select a previous successful
deployment -> Rollback. The portal swaps the running container for the prior
image version. Database state is NOT rolled back — deployments are stateless;
data migrations require a forward-only Alembic migration to revert.

### Fresh redeploy on a new or rebuilt SandCastle host (DR)

The Phase 9 Alembic baseline (`alembic/versions/001_baseline_from_live_schema.py`)
was generated from the live schema during the one-time cutover. On a fresh host
or DR rebuild, the schema is loaded via `pg_restore` of a recent backup, NOT
via `alembic upgrade head` against an empty DB. The container entrypoint enforces
this: if `public.users` does not exist after `alembic upgrade head`, the
container fails fast with a FATAL message rather than serving 500s.

**Standard DR sequence:**

1. Run `./scripts/provision-db.sh who-dis` on the SandCastle host.

2. Restore the latest `who-dis_db` backup into the freshly-provisioned database
   (out-of-band; SandCastle backup tooling is documented in Phase 11).

3. Use `bash scripts/cutover/restore_to_sandcastle.sh /path/to/backup.sql` —
   this runs `alembic upgrade head`, re-applies data via psql, then runs
   `alembic stamp head`. If you have a full schema+data dump, restore it
   directly and run `alembic stamp head` once.

4. Trigger a portal deploy. The container entrypoint guard verifies the schema
   is in place before starting gunicorn.

**Do NOT** start a fresh container against an empty `who-dis_db` expecting the
baseline migration to populate it. The baseline body is operator-populated from
a live-schema dump (Pitfall 5 in `09-RESEARCH.md`); fresh hosts have no live
schema to autogenerate from. The entrypoint guard catches this and aborts with
an actionable error pointing here.

## Health monitoring

| Endpoint | Depth | Used by |
|----------|-------|---------|
| `GET /health` | Shallow (process alive) | Portal poller + Dockerfile HEALTHCHECK |
| `GET /health/ready` | Deep (DB connectivity + latency) | Traefik optional health route |
| `GET /health/live` | Alias for `/health` (deprecated) | Kept one release for backward compat |

Expected responses:

```
GET /health      -> 200  {"status": "healthy"}
GET /health/ready -> 200  {"status": "healthy", "database": {"connected": true, "latency_ms": <n>}}
                   503  {"status": "unhealthy", "database": {"connected": false, "error": "..."}}
```

## Phase 9 reference

| Resource | Location |
|----------|----------|
| Phase 9 plan directory | `sandcastle-portal/.planning/phases/09-who-dis-onboarding/` |
| Implementation decisions (D-01..D-17) | `09-CONTEXT.md` |
| Research notes, pitfalls, Authlib pattern | `09-RESEARCH.md` |
| Cutover operator runbook | `scripts/cutover/README.md` |
| Editor remap audit | `.planning/editor-remap-audit.md` |
| Env-var contract | `.env.sandcastle.example` |

## Operational Verification (WD-OPS-01, WD-OPS-04)

These two requirements close via operator confirmation, not code. Complete
both steps and record the date and your initials in
`.planning/phases/03-sandcastle-containerization-deployment/03-VERIFICATION.md`.

### WD-OPS-01 — SandCastle portal catalog registration

**Confirm:**
1. Open the SandCastle portal at `https://sandcastle.ttcu.com`
2. Navigate to Apps (or Services catalog)
3. Verify `who-dis` appears with a green/healthy status badge
4. Record the app UUID as `WHODIS_APP_ID` in `scripts/cutover/README.md` step 4 (if not already done)

### WD-OPS-04 — GitHub webhook configured for `main` push

**Confirm:**
1. Open the Who-Dis GitHub repo settings → Webhooks
2. Verify the SandCastle webhook (`https://sandcastle.ttcu.com/api/webhooks/github`) is listed
3. Verify the last delivery has a green tick (successful)
4. Smoke test: re-deliver the last event from the GitHub webhook UI (or push a trivial commit to `main`) and confirm the portal deploy log shows a successful build

### Live-deployment checklist

Run the bundled verification script against the production URL:

```bash
python scripts/verify_deployment.py --sandcastle
```

Expected output (all three lines must show `[PASS]`):

```
[PASS] DNS who-dis.sandcastle.ttcu.com resolves
[PASS] GET https://who-dis.sandcastle.ttcu.com/health -> 200
[PASS] GET https://who-dis.sandcastle.ttcu.com/health/ready -> 200
```

Once all three pass, record the date and your initials in `03-VERIFICATION.md`
under the WD-OPS-01 and WD-OPS-04 entries. That is the in-repo evidence of
portal registration and webhook configuration.

**If `health/ready` returns 503:** The database is unreachable. Check
`DATABASE_URL` in the portal env-var store and confirm the SandCastle Postgres
instance is running (`provision-db.sh who-dis` idempotently re-provisions if
needed).
