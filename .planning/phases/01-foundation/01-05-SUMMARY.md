---
phase: 01-foundation
plan: 05
subsystem: infra
tags: [config, validation, fail-fast, encryption, fernet]

requires:
  - phase: 01-foundation
    provides: configuration_service, encryption_service (encrypted-config read path)
provides:
  - Startup configuration validator that aborts boot when required encrypted-config keys are missing
  - ConfigurationError exception class for missing-config signaling
  - REQUIRED_KEYS registry (code-resident, tamper-resistant) covering LDAP, Graph, Genesys
affects: [phase-01-foundation, phase-02-tests, phase-08-deploy]

tech-stack:
  added: []
  patterns:
    - "Fail-fast startup gate: validate required config in create_app() between configuration init and blueprint registration; let exceptions propagate to abort boot"

key-files:
  created:
    - app/services/config_validator.py
  modified:
    - app/__init__.py

key-decisions:
  - "REQUIRED_KEYS lives in code, not DB (T-01-05-03 mitigation): operators cannot tamper their way around the gate without a code change"
  - "Error message lists missing keys by category.key + human label only — never echoes present/decrypted values (T-01-05-01 mitigation)"
  - "Validator runs before token-refresh block so failing fast on missing Graph/Genesys creds does not leave half-initialized services running"
  - "Postgres credentials remain in .env (bootstrap chicken-and-egg); validator scope is encrypted-config only"

patterns-established:
  - "Startup gate pattern: simple module exposing validate_X() that raises a domain-specific Error; called once from create_app() with no try/except wrapper so it aborts boot cleanly"

requirements-completed: [OPS-03]

duration: ~5min
completed: 2026-04-25
---

# Phase 01 Plan 05: Config Validator Summary

**Fail-fast startup validator over 7 required encrypted-config keys (LDAP, Graph, Genesys) — boot aborts with operator-actionable message listing every missing key.**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-04-25T05:07:00Z (approx)
- **Completed:** 2026-04-25T05:08:24Z
- **Tasks:** 1
- **Files modified:** 2 (1 created, 1 modified)

## Accomplishments

- New `ConfigurationError` exception + `validate_required_config()` over 7-entry `REQUIRED_KEYS` (LDAP server/bind_dn, Graph tenant_id/client_id/client_secret, Genesys client_id/client_secret)
- Wired into `create_app()` immediately after configuration service init and before token-refresh / blueprint registration
- Missing keys produce a multi-line error listing every offender by `category.key (Human Label)` with remediation pointer to admin UI / `scripts/import_config.py`
- Present (decrypted) values are never included in error output — threat model T-01-05-01 mitigation upheld

## Task Commits

1. **Task 1: ConfigurationError + validate_required_config()** — `b86357b` (feat)

## Files Created/Modified

- `app/services/config_validator.py` — created. Exports `ConfigurationError`, `REQUIRED_KEYS`, `validate_required_config()`. Uses `config_get(key, None)` and treats `None` or empty/whitespace strings as missing.
- `app/__init__.py` — modified. Imports and calls `validate_required_config()` after the configuration-service init `try/except` block (line ~115) and before token-refresh / blueprint registration. Uncaught — `ConfigurationError` propagates and aborts `create_app()`.

## Decisions Made

- **Validator placement after the configuration init `except` (not inside it):** the `except` falls back to env vars on config-load failure, but a config-load failure itself is already a fatal misconfiguration. We still call the validator, which will then raise `ConfigurationError` listing every key — operator gets a unified missing-keys message rather than a silent fallback.
- **REQUIRED_KEYS minimum of 7:** matches plan spec. LDAP password/Graph audience/Genesys region are intentionally excluded — those have working defaults or are not strictly required for boot-time correctness. List is easy to extend in code as future plans add hard dependencies.
- **No try/except around the validator call:** intentional. The whole point is to abort boot. Wrapping it would defeat OPS-03.

## Deviations from Plan

None — plan executed exactly as written. The plan-suggested insertion point (between configuration init and blueprint registration) was honored; chose the spot immediately after the configuration init `try/except` so token refresh (which depends on Graph/Genesys creds) does not run before validation.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration changes. Existing operators with complete encrypted config will see a single new INFO log line at boot: `Configuration validation passed: 7 required keys present`. Operators with incomplete config will now see boot abort with a clear `ConfigurationError` instead of downstream 500s — this is the intended OPS-03 behavior.

## Next Phase Readiness

- OPS-03 satisfied; phase-01 foundation gains a fail-fast surface for misconfiguration.
- Next plan: 01-06 pagination (already complete per init context) — nothing in this plan blocks remaining phase-01 work.
- Future phases can extend `REQUIRED_KEYS` as new hard dependencies are introduced (e.g., reports SMTP keys in Phase 5, API rate-limit keys in Phase 7).

## Self-Check: PASSED

Verified:
- `app/services/config_validator.py` exists (FOUND)
- `app/__init__.py` references `validate_required_config` at lines 116, 118 (FOUND)
- Commit `b86357b` exists on main (FOUND)
- `REQUIRED_KEYS` length = 7, ≥ 7 required (PASS)
- `ConfigurationError` defined and not caught in `create_app()` (PASS)

---
*Phase: 01-foundation*
*Completed: 2026-04-25*
