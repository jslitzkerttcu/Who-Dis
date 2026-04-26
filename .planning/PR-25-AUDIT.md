# PR #25 Cross-Phase Audit

**Audit date:** 2026-04-26
**Audited PR:** [#25](https://github.com/jslitzkerttcu/Who-Dis/pull/25) — *Phase 9: SandCastle onboarding (containerization, Authlib OIDC, Alembic, encrypted-config retirement)*
**Audited commits:** `fdb6ff2` (PR #25 merge) + post-merge fixes `11161a0`, `e760af5`, `fbbfa4d`, `4ee7d3c`, `35c1c1f`, `01b291c`
**Phases covered:** 3 (Containerization), 4 (Keycloak OIDC), 5 (Database/Alembic)
**Source of truth:** This audit. Per-phase `CONTEXT.md` files reference here for both the inventory of shipped work and the HOW decisions for each gap.

---

## Why this audit exists

PR #25 was authored under sandcastle-portal phase numbering (its commit message says "Phase 9 SandCastle onboarding") and merged into Who-Dis without ever being recorded as Who-Dis Phase 3, 4, or 5 in the GSD planning system. The PR shipped a vertical slice that crosses all three phase boundaries:

- **Phase 3 (Containerization):** ~80% complete via PR #25
- **Phase 4 (Keycloak OIDC):** ~95% complete; one cleanup gap
- **Phase 5 (DB/Alembic):** ~80% complete; same DATABASE_URL gap as Phase 3

Because no per-phase CONTEXT/PLAN/VERIFICATION docs were written, this audit is the single source of truth for what's actually deployed and what remains.

---

## Method

For each requirement (WD-CONT/CFG/HEALTH/NET/OPS/DOC for Phase 3; WD-AUTH for Phase 4; WD-DB for Phase 5):

1. Read the cited code path or doc.
2. Mark `DONE` (verified by file/line evidence), `PARTIAL` (some criteria met), or `OPEN` (not started or false claim).
3. For OPEN/PARTIAL items, record the closure decision in the **Gap Closure** section.

All 38 SandCastle requirements (WD-* prefix) were inspected.

---

## Phase 3 — SandCastle Containerization & Deployment (25 requirements)

### Containerization (WD-CONT-01..05)

| Req | Status | Evidence |
|---|---|---|
| WD-CONT-01 — Dockerfile, python:3.12-slim, non-root user | DONE | `Dockerfile:1-7` (FROM python:3.12-slim, USER app, uid 10001) |
| WD-CONT-02 — gunicorn with `GUNICORN_WORKERS` env (default 2) | DONE | `docker-entrypoint.sh:56-63`, `Dockerfile:36` (`ENV GUNICORN_WORKERS=2`) |
| WD-CONT-03 — Production deps only, image <500 MB | DONE | `requirements-dev.txt` separates pytest/ruff/mypy; `Dockerfile:21-22` installs only `requirements.txt` |
| WD-CONT-04 — `docker-compose.sandcastle.yml` with Traefik labels + proxy/internal nets | DONE | `docker-compose.sandcastle.yml:6-41` |
| WD-CONT-05 — Container starts cleanly with `docker compose up` | DONE | Verified by deploy via portal (post-merge fixes 11161a0/4ee7d3c address env-var injection issues) |

### Configuration (WD-CFG-01..05)

| Req | Status | Evidence |
|---|---|---|
| WD-CFG-01 — All runtime config from env vars | DONE | Encrypted-config layer fully retired (PR #25 deleted `app/services/encryption_service.py`, `app/services/simple_config.py`, all admin config blueprints). `app/services/configuration_service.py:1-77` retains only the debug-mode toggle. |
| **WD-CFG-02 — `DATABASE_URL` replaces POSTGRES_* composition** | **OPEN** | `app/database.py:13-29` still composes URI from `POSTGRES_HOST/PORT/DB/USER/PASSWORD`. `docker-entrypoint.sh:12` validates DATABASE_URL but the running app never reads it. **Same gap as WD-DB-01 — see Gap Closure.** |
| WD-CFG-03 — Secrets via env (no encrypted-config table reads) | DONE | Verified by `grep config_get` — only the debug-toggle bridge survives. |
| WD-CFG-04 — `FLASK_ENV=production`, DEBUG forced false | DONE | `Dockerfile:35` (`ENV FLASK_ENV=production`); debug toggle still readable from DB but defaults False (`configuration_service.py:get_debug_mode`) |
| WD-CFG-05 — `.env.sandcastle.example` documents every var | DONE | `.env.sandcastle.example` exists with grouped sections (Flask, DB, Keycloak, LDAP, Graph, Genesys). **Will need `REDIS_URL` added — see Gap Closure.** |

### Health & Observability (WD-HEALTH-01..04)

| Req | Status | Evidence |
|---|---|---|
| WD-HEALTH-01 — `GET /health` 200 unauthenticated | DONE | `app/blueprints/health/__init__.py:32-36` |
| WD-HEALTH-02 — `GET /health/ready` 200/503 by DB | DONE | `app/blueprints/health/__init__.py:46-71` (SELECT 1, returns latency_ms) |
| WD-HEALTH-03 — JSON logs to stdout/stderr | DONE | `app/__init__.py:30-51` (`_configure_json_logging` via python-json-logger, `StreamHandler`) |
| WD-HEALTH-04 — Dockerfile HEALTHCHECK every 30s | DONE | `Dockerfile:32-33` (interval=30s, timeout=10s, start-period=20s, retries=3) |

### Networking (WD-NET-01..05)

| Req | Status | Evidence |
|---|---|---|
| WD-NET-01 — `proxy` + `internal` networks | DONE | `docker-compose.sandcastle.yml:19-21, 37-41` (both marked `external: true`) |
| WD-NET-02 — Traefik HTTPS with letsencrypt | DONE | `docker-compose.sandcastle.yml:22-29` (entrypoints=websecure, certresolver=letsencrypt) |
| WD-NET-03 — Outbound Graph/Genesys calls work | DONE | No code change required; standard egress works. Implicitly verified by working deploy. |
| WD-NET-04 — `X-Forwarded-Proto/Host` honored | DONE | `app/__init__.py:60` (`ProxyFix(x_for=1, x_proto=1, x_host=1, x_prefix=0)` — single hop = Traefik only) |
| WD-NET-05 — Static assets work through Traefik | DONE | No path-prefix assumption found in templates; default Flask `/static/*` serves correctly. |

### Deployment & Operations (WD-OPS-01..04)

| Req | Status | Evidence |
|---|---|---|
| **WD-OPS-01 — App registered in SandCastle portal catalog** | **PARTIAL** | Documented as required prerequisite in `scripts/cutover/README.md:23` (operator captures `WHODIS_APP_ID`). No in-repo evidence of completion. **See Gap Closure.** |
| WD-OPS-02 — Portal-triggered deploys work end-to-end | DONE | Documented in `docs/sandcastle.md:136-156`. Implicitly verified by post-merge fix commits being deployed via portal. |
| WD-OPS-03 — `docs/deployment.md` updated, legacy marked deprecated | DONE | `docs/deployment.md:1-5` carries DEPRECATED banner pointing at `docs/sandcastle.md`. |
| **WD-OPS-04 — GitHub webhook configured for `main` push** | **PARTIAL** | Documented in `docs/sandcastle.md:156-167`. No in-repo evidence (webhook lives in GitHub repo settings, not the codebase). **See Gap Closure.** |

### Documentation (WD-DOC-01..02)

| Req | Status | Evidence |
|---|---|---|
| WD-DOC-01 — `docs/sandcastle.md` exists with env-var matrix, Keycloak, DB, deploy, rollback | DONE | `docs/sandcastle.md` (233 lines, all 5 sections present) |
| **WD-DOC-02 — README "Deployment" section points at `docs/sandcastle.md`** | **PARTIAL** | `README.md:683-693` has the SandCastle pointer but `README.md:186` and `README.md:716` still treat `docs/deployment.md` as the canonical deploy doc. **See Gap Closure.** |

---

## Phase 4 — Keycloak OIDC Authentication (8 requirements)

| Req | Status | Evidence |
|---|---|---|
| WD-AUTH-01 — `authentication_handler.py` no longer reads `X-MS-CLIENT-PRINCIPAL-NAME` | DONE | `app/middleware/authentication_handler.py:1-26` (reads `session.get("user")` populated by OIDC callback) |
| WD-AUTH-02 — OIDC library used (Authlib chosen) | DONE | `requirements.txt:18` (`Authlib==1.7.0`); `app/auth/oidc.py` is the integration |
| WD-AUTH-03 — Keycloak client `whodis` exists in `sandcastle` realm | DONE | Documented in `docs/sandcastle.md:42-67`; realm-export.json lives in sandcastle-portal repo |
| WD-AUTH-04 — Unauth redirects to Keycloak; lands at original URL | DONE | `app/auth/oidc.py:123-132` (login stashes `next`); `app/auth/oidc.py:183-186` (authorize restores) |
| WD-AUTH-05 — `g.user`/`g.role` from Keycloak claims; decorators unchanged | DONE | `app/auth/oidc.py:154-171` (claims → session); `app/middleware/authentication_handler.py:25-29` (set_user_context) |
| WD-AUTH-06 — First SSO provisions local user; existing matched by email | DONE | `app/auth/oidc.py:174-181` (UserProvisioner.get_or_create_user); `35c1c1f` adds auto-grant of default client role |
| WD-AUTH-07 — Logout terminates Flask + Keycloak (RP-initiated) | DONE | `app/auth/oidc.py:189-208` (clears session, redirects to `end_session_endpoint`) |
| **WD-AUTH-08 — Zero `X-MS-CLIENT-PRINCIPAL` matches in codebase** | **OPEN** | `grep -rn "X-MS-CLIENT-PRINCIPAL" --include="*.py"` returns **35+ matches across 8 files**: `app/blueprints/search/__init__.py` (4), `app/blueprints/admin/cache.py` (7), `app/blueprints/admin/admin_users.py` (3), `app/blueprints/admin/users.py` (9), `app/blueprints/admin/audit.py` (1), `app/blueprints/admin/job_role_compliance.py` (3), `app/blueprints/admin/database.py` (6), `app/utils/error_handler.py` (3). All are `request.headers.get("X-MS-CLIENT-PRINCIPAL-NAME", request.remote_user or "unknown")` audit-attribution fallbacks that should now read `g.user`. The header is never set in the SandCastle deployment, so these silently fall back to `"unknown"`/`"system"`/`"admin"` strings in audit rows. **See Gap Closure.** |

---

## Phase 5 — Database Migration & Alembic (5 requirements)

| Req | Status | Evidence |
|---|---|---|
| **WD-DB-01 — App connects via `DATABASE_URL` exclusively** | **OPEN** | Same gap as WD-CFG-02. Alembic uses DATABASE_URL (`alembic/env.py:17-22`) but `app/database.py:13-29` still composes from POSTGRES_*. **See Gap Closure.** |
| WD-DB-02 — Alembic on container start | DONE | `docker-entrypoint.sh:31` (`alembic upgrade head` before gunicorn); `01b291c` populated the baseline body |
| WD-DB-03 — Documented data-migration runbook | DONE | `docs/sandcastle.md:94-134` ("Initial data migration"); `scripts/cutover/README.md` (full operator runbook); `scripts/cutover/{migrate_secrets_to_portal.py, restore_to_sandcastle.sh, dump_live_schema.sh, seed_keycloak_admins.py}` |
| WD-DB-04 — Connection pool tuned (`pool_size=5`, `pool_pre_ping=True`) | DONE | `app/database.py:41-46` (pool_size=5, pool_recycle=1800, pool_pre_ping=True, max_overflow=5) |
| WD-DB-05 — `create_tables.sql`/`analyze_tables.sql` replaced by Alembic | DONE | PR #25 deleted both files (706 line deletion in stat); `alembic/versions/001_baseline_from_live_schema.py` is the schema source |

---

## Cross-cut gap inventory

Five distinct technical gaps survive PR #25:

| Gap | Affects | Phase ownership | Severity |
|---|---|---|---|
| G1 — `app/database.py` reads POSTGRES_*, not DATABASE_URL | WD-CFG-02, WD-DB-01 | Phase 3 (per REQUIREMENTS.md traceability) | High — the entrypoint guard creates a false sense of safety |
| G2 — Flask-Limiter is in-memory, not Redis-backed | Phase 3 SC#2, fmly backlog 999.1 | Phase 3 | High — multi-worker rate counters are wrong today |
| G3 — 35+ `X-MS-CLIENT-PRINCIPAL-NAME` references remain | WD-AUTH-08 | Phase 4 | Medium — audit rows show `"unknown"`/`"system"`/`"admin"` instead of real user |
| G4 — Portal catalog registration + GitHub webhook lack in-repo evidence | WD-OPS-01, WD-OPS-04 | Phase 3 | Low — operational facts; documentation exists |
| G5 — README still treats `docs/deployment.md` as canonical | WD-DOC-02 | Phase 3 | Low — pure documentation |

---

## Gap Closure — HOW decisions

These decisions were captured during `/gsd-discuss-phase 3` on 2026-04-26 and drive the gap-closure plans.

### G1 — DATABASE_URL refactor (`app/database.py`)

**Plan slot:** `03-02-database-url-refactor-PLAN.md`

**Decisions:**
- **D-G1-01** — Refactor `app/database.py:get_database_uri()` to read `DATABASE_URL` directly. Delete the POSTGRES_* composition entirely (no fallback) — this aligns local dev with the portal contract and removes the silent inconsistency. The entrypoint guard (`docker-entrypoint.sh:12`) becomes truthful.
- **D-G1-02** — Local dev migration: update `.env.example` to use `DATABASE_URL=postgresql://whodis_user:password@localhost:5432/whodis_db` instead of POSTGRES_* keys. Add a one-line note in the dev-onboarding section of README.md.
- **D-G1-03** — Cross-phase coordination: This satisfies BOTH WD-CFG-02 (Phase 3) and WD-DB-01 (Phase 5). Mark both complete in REQUIREMENTS.md after the plan ships. Phase 5 retains ownership of WD-DB-02..05 only.
- **D-G1-04** — `DatabaseConnection` (the standalone non-Flask path at `app/database.py:60-93`) reads via the same `get_database_uri()` — single point of change.
- **D-G1-05** — Test impact: `tests/conftest.py` builds DSN from a testcontainers Postgres URL — no change needed (it's already a DSN, not POSTGRES_*).

### G2 — Flask-Limiter Redis swap

**Plan slot:** `03-01-redis-limiter-swap-PLAN.md`

**Decisions:**
- **D-G2-01** — Storage URI shape: `RATELIMIT_STORAGE_URI=redis://redis:6379/0` (the `redis` hostname resolves on the SandCastle `internal` network per WD-NET-01). Set in `.env.sandcastle.example`.
- **D-G2-02** — Initialization pattern: `Limiter(key_func=get_remote_address, storage_uri=os.environ.get("RATELIMIT_STORAGE_URI", "memory://"))` in `app/__init__.py:27`. The `memory://` fallback keeps local dev and tests working without Redis. **`memory://` MUST NOT be used in production** — add a startup warning if `FLASK_ENV=production` and `RATELIMIT_STORAGE_URI` is unset or `memory://`.
- **D-G2-03** — Add `redis>=5,<6` to `requirements.txt`. Flask-Limiter 3.x requires the `redis` Python client for the redis storage backend.
- **D-G2-04** — Health probe scope: do NOT add Redis to `/health/ready`. Rate-limit failure is degraded-but-functional (limiter falls open per Flask-Limiter default) — adding it to readiness would cause unnecessary 503s during Redis maintenance. Document this choice in the plan.
- **D-G2-05** — Update Phase 1 D-08 deviation note in `.planning/STATE.md` "Key Decisions Locked In" — change "swap to redis:// during SandCastle integration phase" to "shipped via Plan 03-01 on `<date>`."

### G3 — `X-MS-CLIENT-PRINCIPAL-NAME` cleanup (Phase 4 closure)

**Plan slot:** `04-01-azure-header-removal-PLAN.md` (Phase 4 plan)

**Decisions:**
- **D-G3-01** — Replace every `request.headers.get("X-MS-CLIENT-PRINCIPAL-NAME", request.remote_user or "unknown")` with `g.user or "unknown"`. The OIDC middleware sets `g.user` before any blueprint runs.
- **D-G3-02** — Mechanical sweep across the 8 files (35+ sites). Pattern is uniform; can be done in a single pass with one commit. Avoid breaking change to audit row format — keep the fallback string (`"unknown"`/`"system"`/`"admin"` per existing site).
- **D-G3-03** — Verify by `grep -rn "X-MS-CLIENT-PRINCIPAL" --include="*.py"` returning zero matches (the WD-AUTH-08 acceptance criterion).
- **D-G3-04** — `app/utils/error_handler.py:51-52` and `:239` are special-cased: line 239 is in a sensitive-headers redaction list — keep the string literal as a defensive measure (in case any deployment ever sets the header, redact it from logs). This is the only acceptable surviving reference; document this carve-out in the plan.

### G4 — Portal registration + webhook evidence (WD-OPS-01, WD-OPS-04)

**Plan slot:** `03-03-readme-and-ops-evidence-PLAN.md`

**Decisions:**
- **D-G4-01** — Closure mechanism: extend `scripts/verify_deployment.py` (existing script per `README.md:518`) to print three checks against the live deployment:
  - `GET https://who-dis.sandcastle.ttcu.com/health` → 200
  - `GET https://who-dis.sandcastle.ttcu.com/health/ready` → 200
  - DNS resolves the canonical hostname
  Output a checklist that the operator confirms with a test push to `main` (webhook smoke test).
- **D-G4-02** — Add an "Operational Verification" subsection to `docs/sandcastle.md` listing the WD-OPS-01 and WD-OPS-04 manual confirmation steps (portal UI shows the app, GitHub Settings → Webhooks shows the SandCastle hook with green delivery status).
- **D-G4-03** — Mark WD-OPS-01 and WD-OPS-04 complete in REQUIREMENTS.md once the operator has confirmed via the checklist. Record the confirmation date in `03-VERIFICATION.md`.

### G5 — README "Deployment" pointer cleanup (WD-DOC-02)

**Plan slot:** `03-03-readme-and-ops-evidence-PLAN.md` (bundled with G4)

**Decisions:**
- **D-G5-01** — Replace `README.md:186` line: `- **[Deployment Guide](docs/sandcastle.md)** - SandCastle deployment (canonical)`. Add secondary line: `- **[Legacy Deployment](docs/deployment.md)** - Deprecated; pre-Phase-9 Azure App Service notes`.
- **D-G5-02** — Replace `README.md:716` line: `- **System administrators?** Check the [Admin Tasks Guide](docs/user-guide/admin-tasks.md) and [SandCastle Deployment Guide](docs/sandcastle.md)`.
- **D-G5-03** — Lines 683-693 (the existing SandCastle paragraph) stay as-is — they're already accurate. Just elevate the docs/sandcastle.md links above docs/deployment.md throughout.
- **D-G5-04** — Do NOT delete `docs/deployment.md` — Azure App Service runbook is referenced by historical ticket links. Keep with DEPRECATED banner. Schedule deletion for a future cleanup phase once the legacy environment is decommissioned.

---

## Plan structure (Phase 3 only)

Three atomic plans, sequenced by independence:

| Plan | Files touched | Wave | Risk |
|---|---|---|---|
| 03-01 — Redis-Limiter swap | `app/__init__.py`, `requirements.txt`, `.env.sandcastle.example` | 1 (independent) | Low — `memory://` fallback preserves dev |
| 03-02 — DATABASE_URL refactor | `app/database.py`, `.env.example`, `README.md` (dev section) | 1 (independent) | Medium — exercises the test suite's testcontainers DSN path |
| 03-03 — README + ops evidence | `README.md`, `docs/sandcastle.md`, `scripts/verify_deployment.py` | 2 (after 01/02 to capture in README) | Low — pure docs + script |

03-01 and 03-02 touch disjoint files and can wave-parallelize. 03-03 runs after so the README accurately describes the post-refactor state.

---

## Verification artifact

After all three Phase 3 plans complete, `/gsd-verify-work 3` produces `.planning/phases/03-sandcastle-containerization-deployment/03-VERIFICATION.md` covering:

- All 25 WD-CONT/CFG/HEALTH/NET/OPS/DOC requirements with file/line evidence (or operator-confirmation date for WD-OPS-01/04)
- The 5 ROADMAP success criteria for Phase 3
- Cross-references to PR #25 commit SHAs for the pre-shipped work
- Operator confirmation entry for WD-OPS-01/04 (date + initials)

Phase 4 and Phase 5 follow the same pattern but are scoped to their own discussions (`/gsd-discuss-phase 4`, `/gsd-discuss-phase 5`) — see the thin CONTEXT.md files in each phase directory.

---

## REQUIREMENTS.md updates (post-merge of all three plans)

Mark these as `Complete` (currently `Pending`) once verified:

**Phase 3:** WD-CONT-01..05 (5), WD-CFG-01, WD-CFG-03, WD-CFG-04, WD-CFG-05, WD-HEALTH-01..04 (4), WD-NET-01..05 (5), WD-OPS-02, WD-OPS-03, WD-DOC-01 → **20 items**, marked done by audit evidence.

**Phase 3 closed by gap-closure plans:** WD-CFG-02, WD-OPS-01, WD-OPS-04, WD-DOC-02 → **4 items**.

**Phase 3 also-shipped here, but transferred to Phase 5 ownership:** none — WD-DB-01..05 stay in Phase 5's traceability row.

**Phase 4:** WD-AUTH-01..07 (7) marked done by audit evidence; WD-AUTH-08 closed by Phase 4 plan 04-01 (the AUTH-header sweep). All 8.

**Phase 5:** WD-DB-02..05 (4) marked done by audit evidence; WD-DB-01 closed by Plan 03-02 (cross-phase satisfaction).

---

## Session of record

This audit was produced during `/gsd-discuss-phase 3` (2026-04-26) after the user opted to triage all three phases in one cross-phase audit (option 2 of the framing decision tree). See `03-DISCUSSION-LOG.md` for the full Q&A trail.
