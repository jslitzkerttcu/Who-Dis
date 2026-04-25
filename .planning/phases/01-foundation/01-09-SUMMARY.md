---
phase: 01-foundation
plan: 09
subsystem: middleware/auth
tags: [security, auth, configuration, sec-04]
requirements: [SEC-04]
dependency_graph:
  requires:
    - app/services/configuration_service.py:config_get
  provides:
    - configurable_principal_header
    - dangerous_dev_auth_bypass
  affects:
    - app/middleware/authentication_handler.py
tech_stack:
  added: []
  patterns:
    - env-var-gated dev bypass with WARNING-level audit log
    - config-driven HTTP header name (auth.principal_header)
key_files:
  created:
    - .planning/phases/01-foundation/01-09-SUMMARY.md
  modified:
    - app/middleware/authentication_handler.py
decisions:
  - Bypass is env-var-only (DANGEROUS_DEV_AUTH_BYPASS_USER) — cannot be flipped via DB config or admin UI; deployment-time gate prevents accidental enablement
  - Default header name preserved as X-MS-CLIENT-PRINCIPAL-NAME — zero behavior change for Azure deployments without the new config key
  - Direct X-MS-CLIENT-PRINCIPAL-NAME reads in app/__init__.py and app/utils/error_handler.py left untouched (logging-only, not auth decisions) — flagged as follow-up
metrics:
  duration_minutes: 5
  completed: 2026-04-25
  tasks_completed: 1
  files_modified: 1
  commit_count: 1
---

# Phase 01 Plan 09: Auth Header Config Summary

Make the Azure AD principal header name configurable for non-Azure reverse proxies and add a loud, env-var-only developer auth bypass — satisfies SEC-04.

## Outcome

`AuthenticationHandler.authenticate_user()` now reads its principal header name from `config_get("auth.principal_header", "X-MS-CLIENT-PRINCIPAL-NAME")`. When the OS environment variable `DANGEROUS_DEV_AUTH_BYPASS_USER` is set, every authentication call returns the configured user and emits a `logger.warning("AUTH BYPASS ACTIVE — authenticating as %s ...")` log line. With the env var unset and no `auth.principal_header` config key present, behavior is identical to the prior implementation (default Azure App Service header).

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Configurable auth header + dev bypass | fcfc239 | app/middleware/authentication_handler.py |

## Verification

Functional smoke test executed in a Flask test request context:

- Env var set to `dev@example.com`, no headers → returns `dev@example.com`, WARNING line emitted
- No env var, header `X-MS-CLIENT-PRINCIPAL-NAME: alice@corp.com` → returns `alice@corp.com`
- No env var, no headers → returns `None`

Static checks:

- `ruff check app/middleware/authentication_handler.py` — clean
- `python -c "from app.middleware.authentication_handler import AuthenticationHandler; AuthenticationHandler()"` — imports and instantiates
- All four required string fragments present: `DANGEROUS_DEV_AUTH_BYPASS_USER`, `auth.principal_header`, `X-MS-CLIENT-PRINCIPAL-NAME`, `AUTH BYPASS ACTIVE`

## Deviations from Plan

None — plan executed as written. The plan's code template included `.strip().lower()` normalization on the principal email, which differed from the prior raw-passthrough behavior; the plan body explicitly specified that normalization, so it was applied. Downstream `RoleResolver.get_user_role()` is case-insensitive on lookup, so this is a defense-in-depth strengthening rather than a behavior regression.

## Known Stubs

None.

## Follow-ups (Deferred)

- `app/__init__.py` and `app/utils/error_handler.py` still reference `X-MS-CLIENT-PRINCIPAL-NAME` directly for logging context. Per plan instructions these were intentionally left as-is (they do not gate auth decisions). If a future deployment uses a non-Azure header, those logging contexts will be empty until they are switched to `config_get("auth.principal_header", ...)`. Track as a small follow-up cleanup.

## Threat Flags

None — no new trust boundaries introduced beyond those documented in the plan's threat model.

## Self-Check: PASSED

- FOUND: app/middleware/authentication_handler.py
- FOUND: commit fcfc239
- FOUND: .planning/phases/01-foundation/01-09-SUMMARY.md
