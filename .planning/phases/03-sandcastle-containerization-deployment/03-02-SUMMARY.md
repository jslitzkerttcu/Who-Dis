---
phase: 03-sandcastle-containerization-deployment
plan: 02
subsystem: database
tags: [database, postgres, configuration, env-vars, sandcastle, alembic]

# Dependency graph
requires:
  - phase: 09-sandcastle-onboarding
    provides: docker-entrypoint.sh DATABASE_URL guard (line 12) — guard now becomes truthful after this plan
provides:
  - "DATABASE_URL-only database connection bootstrap (single canonical connection string)"
  - "Hard removal of POSTGRES_HOST/PORT/DB/USER/PASSWORD composition path"
  - "Fail-fast RuntimeError on missing DATABASE_URL (replaces silent misconfiguration with default localhost values)"
  - "Aligned local dev, container runtime, Alembic, and verify_deployment.py on a single env var"
affects:
  - phase: 04-keycloak-oidc-authentication
  - phase: 05-database-migration-alembic
  - phase: 06-write-operations
  - operator runbooks (RuntimeError message includes operator-actionable hint)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "DATABASE_URL is the single canonical PostgreSQL connection string for Flask-SQLAlchemy and Alembic"
    - "Bootstrap env vars (read at startup before encrypted-config service is available) fail loudly with RuntimeError rather than fall back to silent defaults"

key-files:
  created: []
  modified:
    - app/database.py
    - .env.example
    - scripts/verify_deployment.py

key-decisions:
  - "DATABASE_URL is read directly with os.getenv — no fallback to POSTGRES_* vars (D-G1-01)"
  - "Missing DATABASE_URL raises RuntimeError with operator hint pointing to .env.example and .env.sandcastle.example (D-G1-03)"
  - "DatabaseConnection.connect() and init_db() retain their existing get_database_uri() call sites — single point of change (D-G1-04)"
  - "scripts/verify_deployment.py uses psycopg2.connect(dsn=...) form to consume DATABASE_URL DSN directly (D-G1-05)"

patterns-established:
  - "Bootstrap env-var reads use os.getenv (not config_get) and fail with RuntimeError on missing required values"
  - "Connection-string env vars use full DSN form (postgresql://user:pass@host:port/db) instead of host/port/db/user/password decomposition"

requirements-completed: [WD-CFG-02, WD-CFG-01, WD-CFG-03, WD-CFG-04, WD-CFG-05]

# Metrics
duration: 2min
completed: 2026-04-26
---

# Phase 03 Plan 02: DATABASE_URL Refactor Summary

**Replaced POSTGRES_HOST/PORT/DB/USER/PASSWORD composition with a single os.getenv("DATABASE_URL") read in app/database.py; .env.example and scripts/verify_deployment.py aligned to the same DSN.**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-04-26T17:35:07Z
- **Completed:** 2026-04-26T17:37:12Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- `app/database.py:get_database_uri()` rewritten to read `DATABASE_URL` exclusively; raises `RuntimeError` on missing var
- All five POSTGRES_* environment variables fully removed from `app/database.py`, `.env.example`, and `scripts/verify_deployment.py`
- Closes Gap G1 from the PR #25 audit: `docker-entrypoint.sh:12` was already validating `DATABASE_URL`, but the running app never read it. The guard is now truthful.
- This plan satisfies BOTH WD-CFG-02 (Phase 3) and WD-DB-01 (Phase 5). Phase 5 retains WD-DB-02..05 only.

## RuntimeError Message (Operator Runbook Reference)

The exact text raised by `get_database_uri()` when `DATABASE_URL` is unset:

> DATABASE_URL environment variable is not set. Set it in .env (local dev: see .env.example) or the portal env-var store (SandCastle: see .env.sandcastle.example).

This message is intentionally operator-actionable — it points to the two canonical .env templates and never echoes the env-var value.

## Task Commits

Each task was committed atomically:

1. **Task 1: Rewrite get_database_uri() in app/database.py** — `8b90fb2` (refactor)
2. **Task 2: Update .env.example and scripts/verify_deployment.py** — `fc44ccf` (refactor)

_Plan metadata commit will be added by execute-plan.md after this SUMMARY is written._

## Files Created/Modified

- `app/database.py` — `get_database_uri()` rewritten to read `DATABASE_URL` only, with `RuntimeError` on missing var and updated docstring; `DatabaseConnection.connect()` and `init_db()` unchanged (single call sites)
- `.env.example` — POSTGRES_HOST/PORT/DB/USER/PASSWORD block replaced with single `DATABASE_URL=postgresql://whodis_user:password@localhost:5432/whodis_db` line; encryption-key block and dev-bypass comment preserved verbatim
- `scripts/verify_deployment.py` — `get_db_connection()` now uses `psycopg2.connect(dsn=os.getenv("DATABASE_URL"))`; raises `ConnectionError` with operator-actionable hint when `DATABASE_URL` is unset

## POSTGRES_* Removal Verification

| File | POSTGRES_* count before | POSTGRES_* count after |
|------|------------------------:|-----------------------:|
| `app/database.py` | 5 (host/port/db/user/password) | 0 |
| `.env.example` | 5 | 0 |
| `scripts/verify_deployment.py` | 5 | 0 |

`scripts/verify_deployment.py get_db_connection()` confirmed using `DATABASE_URL`:
- Line 63 docstring: "Get database connection using DATABASE_URL (aligned with app/database.py D-G1-01)."
- Line 65: `dsn = os.getenv("DATABASE_URL")`
- Line 70: `return psycopg2.connect(dsn=dsn)`

## Decisions Made

None beyond the decisions already locked in `03-CONTEXT.md` (D-G1-01 through D-G1-05). Plan executed as specified.

## Deviations from Plan

None — plan executed exactly as written. Both tasks' acceptance criteria passed on first attempt; no auto-fixes triggered. The Windows `python -c "open(...)"` invocation in the verification step initially failed with a `cp1252` UnicodeDecodeError because `verify_deployment.py` contains UTF-8 emoji glyphs in log messages — this is a Windows shell artifact, not a code defect, and was resolved by passing `encoding='utf-8'` to the verification command. The file itself is valid UTF-8 Python and the project's Python runtime opens source files via the standard import system, which uses UTF-8.

## Issues Encountered

None substantive. (See note above re: cp1252 verification artifact on Windows.)

## User Setup Required

None for this plan. The DATABASE_URL value itself is set per environment:

- **Local dev:** edit `.env` (template in `.env.example`)
- **SandCastle:** injected by the portal env-var system (template in `.env.sandcastle.example`, populated by `./scripts/provision-db.sh who-dis` per Plan 03-03)

## Threat Flags

None — no new security-relevant surface introduced beyond what the plan's `<threat_model>` already covers (T-03-02-01 information disclosure, T-03-02-02 fail-fast tampering posture, T-03-02-03 operator confusion mitigation).

## Next Phase Readiness

- WD-CFG-02 closed; WD-DB-01 (Phase 5 cross-phase requirement) also closed by this plan
- Phase 5 (Alembic migration) can now rely on `DATABASE_URL` being the only valid path; no fallback handling needed in alembic env.py
- Phase 03-03 (ops evidence + dev-onboarding doc) builds on this — README dev-onboarding section will reference the new `DATABASE_URL=` line in `.env.example` per Plan 03-03's task list

## Self-Check

- [x] `app/database.py` exists and contains `os.getenv("DATABASE_URL")` (line 24) and `raise RuntimeError` (line 26) — verified
- [x] `.env.example` exists and contains `DATABASE_URL=postgresql://...` (line 8) with no POSTGRES_* — verified
- [x] `scripts/verify_deployment.py` exists and contains `psycopg2.connect(dsn=dsn)` (line 70) and `os.getenv("DATABASE_URL")` (line 65) — verified
- [x] Commit `8b90fb2` exists in git log (Task 1) — verified
- [x] Commit `fc44ccf` exists in git log (Task 2) — verified

## Self-Check: PASSED

---
*Phase: 03-sandcastle-containerization-deployment*
*Completed: 2026-04-26*
