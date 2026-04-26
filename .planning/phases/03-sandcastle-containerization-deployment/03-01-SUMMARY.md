---
phase: 03-sandcastle-containerization-deployment
plan: 01
subsystem: infra
tags: [flask-limiter, redis, rate-limiting, sandcastle, containerization, env-config]

# Dependency graph
requires:
  - phase: 01-foundation
    provides: Flask-Limiter SEC-03 in-memory init at app/__init__.py with documented D-08 deferral
  - phase: 02-test-suite
    provides: testcontainers-based test fixtures unaffected by env-var contract change
provides:
  - Redis-backed Flask-Limiter storage via RATELIMIT_STORAGE_URI env var
  - memory:// fallback preserved for local dev and CI (no Redis dependency for tests)
  - Production-mode startup warning when memory:// is misconfigured (JSON log line)
  - redis>=5,<6 Python client added so Flask-Limiter can connect to redis://
  - .env.sandcastle.example contract updated with RATELIMIT_STORAGE_URI section
affects: [03-02-database-url-refactor, 03-03-readme-and-ops-evidence, 03-VERIFICATION]

# Tech tracking
tech-stack:
  added: [redis>=5 (Python client)]
  patterns:
    - "Bootstrap env-var read with sane default: os.environ.get('VAR', 'fallback') for non-critical config"
    - "JSON-logger-aware startup warning via app.logger.warning() inside create_app() (post-init)"

key-files:
  created: []
  modified:
    - app/__init__.py
    - requirements.txt
    - .env.sandcastle.example

key-decisions:
  - "Storage URI shape: redis://redis:6379/0 (D-G2-01) — hostname resolves on SandCastle internal network per WD-NET-01"
  - "memory:// fallback preserved for local dev and CI (D-G2-02) — production mode emits startup warning if memory:// is in use"
  - "redis>=5,<6 added to requirements.txt (D-G2-03) — required by Flask-Limiter 3.x to connect to redis://"
  - "Redis NOT added to /health/ready (D-G2-04) — rate-limit failure is degraded-but-functional; would cause unnecessary 503s during Redis maintenance"
  - "Phase 1 D-08 deviation (SEC-03 in-memory deferral) closed by this plan on 2026-04-26"

patterns-established:
  - "Bootstrap env-var read for non-critical config: os.environ.get('VAR', 'sensible-default')"
  - "Post-init startup warning: emit through app.logger.warning() inside create_app() so the JSON handler (already attached) routes the message to docker logs"

requirements-completed: [WD-OPS-02]

# Metrics
duration: ~10min
completed: 2026-04-26
---

# Phase 03 Plan 01: Redis-backed Flask-Limiter Swap Summary

**Flask-Limiter swapped from in-memory storage to Redis-backed via RATELIMIT_STORAGE_URI env var, with memory:// fallback for local dev and a structured production-mode startup warning when misconfigured.**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-04-26T17:30:00Z (approx)
- **Completed:** 2026-04-26T17:36:28Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Module-level `Limiter` constructor now reads `RATELIMIT_STORAGE_URI` from env (default `memory://`) — multi-worker gunicorn on SandCastle gets a shared Redis counter store while local dev and CI continue to work without Redis.
- Production-mode startup warning (D-G2-02) emits through `app.logger.warning()` immediately after `limiter.init_app(app)`, surfaces in structured docker logs, and tells the operator exactly which env var to set and where.
- `redis>=5,<6` Python client added to `requirements.txt` directly after the `Flask-Limiter>=3.5,<4` line — required for Flask-Limiter 3.x to connect to a redis:// URI.
- `.env.sandcastle.example` documents the new contract with a labeled "Rate limiting (WD-NET-01 / SEC-03)" section explaining the Redis hostname is provided by the SandCastle internal network.
- Phase 1 D-08 deviation (SEC-03: Flask-Limiter in-memory storage) **closed by this plan on 2026-04-26**. Plan 03-01 closes backlog 999.1.

## Task Commits

Each task was committed atomically:

1. **Task 1: Update Limiter init and add production-mode startup warning** - `3263d77` (feat)
2. **Task 2: Add redis client to requirements.txt and RATELIMIT_STORAGE_URI to .env.sandcastle.example** - `91c20db` (chore)

**Plan metadata:** _to be appended by execute-plan metadata commit (SUMMARY.md)_

## Files Created/Modified

- `app/__init__.py` — Module-level `Limiter(...)` constructor now passes `storage_uri=os.environ.get("RATELIMIT_STORAGE_URI", "memory://")`; new production-mode warning block added immediately after `limiter.init_app(app)` (lines 116-124) emits through `app.logger.warning` so the JSON handler routes it to stdout.
- `requirements.txt` — Inserted `redis>=5,<6` on a new line directly after `Flask-Limiter>=3.5,<4`. Total line count went from 20 → 21. No other lines changed.
- `.env.sandcastle.example` — Appended a new `# --- Rate limiting (WD-NET-01 / SEC-03)` section after the Genesys Cloud block, documenting `RATELIMIT_STORAGE_URI=redis://redis:6379/0`. Existing sections unchanged.

## Decisions Made

- **Followed plan as written** — all four HOW decisions (D-G2-01 through D-G2-04) from `PR-25-AUDIT.md` § "G2 — Flask-Limiter Redis swap" applied verbatim. The plan author had already nailed the wording for the warning string and the section header in `.env.sandcastle.example`, so no tactical rewording was needed.
- **STATE.md update note (D-G2-05) deferred to orchestrator:** This worktree agent does NOT modify STATE.md per parallel-execution policy. The orchestrator updates the SEC-03 entry under "Key Decisions Locked In" after merging — recommended replacement text:
  > **SEC-03:** Flask-Limiter v3.x dropped PostgreSQL storage. Shipped via Plan 03-01 (2026-04-26): `RATELIMIT_STORAGE_URI=redis://redis:6379/0` on SandCastle internal network with memory:// fallback for local dev. Production-mode startup warning fires if memory:// is misconfigured. Phase 1 D-08 deviation closed.

## Deviations from Plan

None — plan executed exactly as written. Both tasks completed with all acceptance criteria met on first attempt; no auto-fixes (Rules 1/2/3) needed.

## Issues Encountered

None.

## Plan-Level Verification (all 5 checks PASS)

```
=== Verify 1: storage_uri exact match ===
1
=== Verify 2: redis>= in requirements ===
1
=== Verify 3: env-var line ===
1
=== Verify 4: import limiter ===
OK
=== Verify 5: old form gone ===
0
```

`python -c "from app import limiter; print('OK')"` succeeds without Redis running — confirms memory:// fallback works in dev and CI as designed.

## Threat Model Compliance

The plan's threat register (T-03-01-01 through T-03-01-03) was honored:

- **T-03-01-01 (Information Disclosure of RATELIMIT_STORAGE_URI):** The implementation reads the value via `os.environ.get` and never logs it — the startup warning logs only the env-var name and a corrective hint, never the URI value. ✓ Mitigated.
- **T-03-01-02 (Tampering — in-memory fallback in production):** The post-init guard block at `app/__init__.py:116-124` emits a structured `app.logger.warning` when `FLASK_ENV=production` and `RATELIMIT_STORAGE_URI` is unset or `memory://`. The warning surfaces in docker logs immediately on startup. ✓ Mitigated.
- **T-03-01-03 (DoS — unauthenticated Redis on internal network):** Risk **accepted** per the threat register; Redis lives on the SandCastle internal network, not the public proxy network. No code change required.

## User Setup Required

None — no external service configuration required for this plan. The SandCastle portal env-var injection sequence (worker writes `.env`, compose loads via `env_file`) handles `RATELIMIT_STORAGE_URI` through the same path as every other portal-managed env var. No compose-file changes needed; `redis` hostname resolves on the SandCastle internal network without any compose-side service definition (D-G2-01 confirms this).

For local development: omitting `RATELIMIT_STORAGE_URI` from `.env` falls back to `memory://` automatically — existing dev workflow unchanged.

## Cross-Phase Note (D-G2-05 + REQUIREMENTS.md)

- **REQUIREMENTS.md updates:** This plan does not directly close a unique Phase 3 WD-* requirement (the plan's `requirements:` frontmatter lists `WD-OPS-02` because Plan 03-01 is the first SandCastle-deployment-related code change in Phase 3, but WD-OPS-02 closure is operationally driven and recorded in `03-VERIFICATION.md`). The substantive closure here is **backlog 999.1 / Phase 1 D-08** — the SEC-03 in-memory deferral. The orchestrator should record this in STATE.md "Key Decisions Locked In" per D-G2-05.
- **Local dev parity:** Tests under `tests/conftest.py` are unaffected — they neither set `RATELIMIT_STORAGE_URI` (so they fall through to `memory://`) nor exercise rate limits in CI.

## Next Plan Readiness

- **Plan 03-02 (DATABASE_URL refactor)** — independent files, can wave-parallelize with this plan. No dependency on 03-01 work.
- **Plan 03-03 (README + ops evidence)** — runs after 03-01 and 03-02 so the README accurately describes the post-refactor state.
- **`/gsd-verify-work 3`** — will produce `03-VERIFICATION.md` after all three Phase 3 plans complete; this plan's evidence is the `Limiter(storage_uri=...)` line at `app/__init__.py:25-30` plus the `.env.sandcastle.example:36-40` block.

## Self-Check: PASSED

- [x] `app/__init__.py` modified (FOUND)
- [x] `requirements.txt` modified (FOUND, line 18: `redis>=5,<6`)
- [x] `.env.sandcastle.example` modified (FOUND, RATELIMIT_STORAGE_URI line)
- [x] Commit `3263d77` (Task 1) exists in git log
- [x] Commit `91c20db` (Task 2) exists in git log
- [x] All 5 plan-level verification checks pass
- [x] `python -c "from app import limiter; print('OK')"` succeeds (memory:// fallback works)

---
*Phase: 03-sandcastle-containerization-deployment*
*Completed: 2026-04-26*
