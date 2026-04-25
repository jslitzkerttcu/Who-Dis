---
phase: 01-foundation
verified: 2026-04-24T00:00:00Z
status: gaps_found
score: 4/5 success criteria fully verified (1 partial — SEC-01 history retention by design)
overrides_applied: 0
gaps:
  - truth: ".whodis_salt is absent from git history"
    status: partial
    reason: |
      .whodis_salt remains tracked in git (`git ls-files .whodis_salt` returns the path; commit
      cc8e921 still contains it). D-01 explicitly chose to NOT rewrite git history and instead
      rotate the encryption key + gitignore the file, making the leaked salt cryptographically
      useless. Gitignore entry is in place (.gitignore:169) and rotation tooling ships, but the
      literal wording of Success Criterion 5 and SEC-01 ("removed from git history") is not met.
      This is a documented intentional deviation, not an implementation error — recommend either
      (a) accepting via override frontmatter, or (b) running `git filter-repo` + force-push +
      rotating the key as a follow-up before any external publication of the repo.
    artifacts:
      - path: .whodis_salt
        issue: "Still tracked in git; present in commit cc8e921 history"
    missing:
      - "Either accept via override (D-01 rationale: rotation makes leaked salt useless) OR run filter-repo + force-push + rotate key"
human_verification:
  - test: "Run scripts/rotate_encryption_key.py --dry-run against a populated .env"
    expected: "Script reports per-row 're-encrypted category.key' lines, exits 0 with 'DRY RUN — no changes committed'"
    why_human: "Requires live PostgreSQL + populated WHODIS_ENCRYPTION_KEY; cannot exercise without operator credentials"
  - test: "Curl /health on a running app with DB up, then with DB stopped"
    expected: "200 with database.connected=true + latency_ms; 503 with database.connected=false when DB down"
    why_human: "Requires running Flask app + PG instance; full create_app() boot blocked locally by OPS-03 missing-config (verified isolated blueprint behavior in 01-03)"
  - test: "Boot the app with DANGEROUS_DEV_AUTH_BYPASS_USER=dev@example.com set"
    expected: "All requests authenticate as dev@example.com and a WARNING log line 'AUTH BYPASS ACTIVE' is emitted"
    why_human: "Requires running stack to confirm middleware chain end-to-end; static check confirms code path"
  - test: "Issue 31 POSTs to /search/search within 60s as the same authenticated user"
    expected: "Request 31 returns HTTP 429 with Retry-After header"
    why_human: "Requires authenticated session + multi-request load; in-memory limiter is per-worker so test is single-worker only"
  - test: "Page through admin audit log with ?page=2&size=25 and ?size=999"
    expected: "Page 2 shows entries 26-50 with bookmarkable URL; size=999 clamps to 200 max"
    why_human: "Requires admin login + populated audit_log table; static checks verify clamp + macro emission"
---

# Phase 1: Foundation Verification Report

**Phase Goal:** The codebase has a single clean initialization path, deprecated code is gone, security gaps are closed, and production operational primitives are in place.

**Verified:** 2026-04-24
**Status:** gaps_found (1 documented intentional deviation; otherwise all criteria satisfied)
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (Roadmap Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Application starts with a single code path — `app/__init__.py` is the only factory, `app_factory.py` is deleted | VERIFIED | `app/app_factory.py` does not exist; grep across `app/`, `scripts/`, `run.py` returns zero `app_factory` references; `app/__init__.py:create_app` is the canonical factory; 01-01 commit 7773991 |
| 2 | `GET /health` returns JSON with database status, usable by monitoring tools without authentication | VERIFIED | `app/blueprints/health/__init__.py` defines `/health` and `/health/live` with zero `@auth_required`/`@require_role` decorators; deep DB probe via `SELECT 1` + latency_ms, 200/503 split; registered at root in `app/__init__.py:252`; commit 101b4e8 |
| 3 | Every log line carries a request ID that can be used to trace a single user action end-to-end | VERIFIED | `app/middleware/request_id.py` defines `RequestIdFilter` + `init_request_id`; `app/__init__.py` configures `jsonlogger.JsonFormatter`, calls `handler.addFilter(RequestIdFilter())` and `init_request_id(app)`; inbound `X-Request-ID` validated `^[0-9a-fA-F-]{8,64}$`; 01-04 commit ee55246 |
| 4 | Application refuses to start with clear error messages when required configuration values are missing | VERIFIED | `app/services/config_validator.py` defines `ConfigurationError` + `validate_required_config()` over 7-key REQUIRED_KEYS; called unconditionally at `app/__init__.py:139` (no try/except wrapper); error message lists missing keys but never echoes decrypted values; commit b86357b |
| 5 | `.whodis_salt` is absent from git history and a CLI tool exists to safely rotate the encryption key | PARTIAL | CLI tool `scripts/rotate_encryption_key.py` exists with `--dry-run`, dual-key in-memory re-encrypt, single-transaction commit, post-commit verify (exit 3 on fail); runbook at `docs/runbooks/encryption-key-rotation.md`; `.gitignore:169` adds `.whodis_salt`. **However:** `git ls-files .whodis_salt` still returns the path — file remains tracked in commit cc8e921. D-01 explicitly chose to rotate-key-instead-of-rewrite-history (leaked salt becomes useless after rotation), but the literal SC wording is not met. |

**Score:** 4/5 fully verified, 1 partial (intentional deviation per D-01)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `app/app_factory.py` | DELETED (DEBT-01) | VERIFIED | Absent; grep confirms zero references |
| `app/services/data_warehouse_service.py` | DELETED (DEBT-02) | VERIFIED | Absent; zero `DataWarehouseService` references |
| `app/services/refresh_employee_profiles.py` | Owns Keystone query + Azure SQL helpers | VERIFIED | Container registers `employee_profiles_refresh` (container.py); admin/cache.py routes consume it |
| `app/services/cache_cleanup_service.py` | Hourly background prune (DEBT-03) | VERIFIED | File exists; container registers `cache_cleanup`; `__init__.py:182` starts thread under WERKZEUG_RUN_MAIN guard; `_cache_actions.html` has Run-now button posting to `admin.api_cache_cleanup_run` |
| `app/blueprints/health/__init__.py` | Unauthenticated /health + /health/live (OPS-01) | VERIFIED | Both routes present, zero auth decorators, returns JSON, 503 on DB failure, latency_ms emitted |
| `app/middleware/request_id.py` | Request-ID middleware + LogFilter (OPS-02) | VERIFIED | `RequestIdFilter`, `init_request_id`, regex `^[0-9a-fA-F-]{8,64}$` |
| `app/services/config_validator.py` | Startup validator (OPS-03) | VERIFIED | `REQUIRED_KEYS` list (7 entries), `validate_required_config()` raises `ConfigurationError` |
| `app/utils/pagination.py` | Reusable paginate helper (OPS-04) | VERIFIED | `paginate()`, `PageResult`, `MAX_PAGE_SIZE=200`, clamps applied |
| `app/templates/partials/pagination.html` | render_pagination macro | VERIFIED | Macro present; 7x `hx-push-url="true"`; size selector 25/50/100; `aria-current="page"` |
| Admin tables wired to paginate | audit, error log, sessions (OPS-04) | VERIFIED | `app/blueprints/admin/audit.py` and `app/blueprints/admin/database.py` import paginate; three new fragment templates exist |
| `.gitignore` entry `.whodis_salt` | Present (SEC-01) | VERIFIED | Line 169 |
| `scripts/rotate_encryption_key.py` | Dual-key rotation CLI (SEC-02) | VERIFIED | File exists; argparse contract; exit 2/3 codes verified per summary |
| `docs/runbooks/encryption-key-rotation.md` | Operator runbook (SEC-02) | VERIFIED | File exists with Overview/Pre-flight/Procedure/Rollback/Notes sections |
| Flask-Limiter dependency | Added (SEC-03) | VERIFIED | `requirements.txt:17` `Flask-Limiter>=3.5,<4` |
| python-json-logger dependency | Added (OPS-02) | VERIFIED | `requirements.txt:16` `python-json-logger>=2.0.7,<3` |
| `app/middleware/authentication_handler.py` | Configurable header + dev bypass (SEC-04) | VERIFIED | `config_get("auth.principal_header", "X-MS-CLIENT-PRINCIPAL-NAME")`; `DANGEROUS_DEV_AUTH_BYPASS_USER` env-var-only path; "AUTH BYPASS ACTIVE" warning log |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `app/__init__.py:create_app` | `RequestIdFilter` + `init_request_id` | import + `handler.addFilter` + `init_request_id(app)` calls | WIRED | Lines 11, 47, 69 |
| `app/__init__.py:create_app` | `validate_required_config` | import + unconditional call | WIRED | Lines 137, 139 |
| `app/__init__.py:create_app` | `health_bp` | `register_blueprint(health_bp)` | WIRED | Line 252 |
| `app/__init__.py:create_app` | `limiter` | `limiter.init_app(app)` | WIRED | Line 96 |
| `app/__init__.py:create_app` | `cache_cleanup` service | `container.get + .start()` | WIRED | Lines 180-182 |
| `app/blueprints/search/__init__.py` POST routes | `limiter` | `@limiter.limit("30/minute", key_func=_search_rate_key)` | WIRED | Lines 296, 794; `_search_rate_key` falls back to remote_addr pre-auth |
| `app/blueprints/admin/cache.py:cache_cleanup_run` | `cache_cleanup` service | `container.get("cache_cleanup")` | WIRED | Line 283; audited via `log_admin_action` |
| `_cache_actions.html` Run-now button | `admin.api_cache_cleanup_run` route | `hx-post=url_for(...)` | WIRED | Template line 87 |
| `AuthenticationHandler.authenticate_user` | `config_get("auth.principal_header", ...)` + env bypass | direct calls | WIRED | Lines 35, 44 |
| Admin audit/error/sessions endpoints | `paginate()` helper | import + invocation | WIRED | `audit.py`, `database.py` both import; render_pagination found in 11 files |

### Anti-Patterns / Asyncio Modernization

| Pattern | Status | Details |
|---------|--------|---------|
| `asyncio.get_event_loop` / `new_event_loop` / `set_event_loop` | NONE FOUND | Zero matches across `app/` and `scripts/`; DEBT-04 satisfied |
| `app_factory` references | NONE FOUND | DEBT-01 satisfied |
| `DataWarehouseService` / `data_warehouse_service` references | NONE FOUND | DEBT-02 satisfied |

### Requirements Coverage

| Requirement | Description | Status | Evidence |
|-------------|-------------|--------|----------|
| DEBT-01 | Single application initialization path | SATISFIED | `app_factory.py` deleted; canonical factory in `app/__init__.py` |
| DEBT-02 | Deprecated DataWarehouseService removed | SATISFIED | Service file deleted; logic consolidated into `EmployeeProfilesRefreshService`; container registration updated |
| DEBT-03 | Scheduled cleanup job for expired search cache | SATISFIED | `CacheCleanupService` running hourly + Run-now admin route + UI button |
| DEBT-04 | Asyncio patterns updated for 3.10+ | SATISFIED | Zero legacy asyncio API matches in repo |
| OPS-01 | `/health` JSON endpoint with DB connectivity | SATISFIED | Both endpoints registered, unauthenticated, 200/503 split |
| OPS-02 | Per-request unique request ID across all logs | SATISFIED | UUID4 + JSON logging via python-json-logger; X-Request-ID header echo; logging filter universally applied |
| OPS-03 | Startup config validation with clear errors | SATISFIED | `validate_required_config()` aborts boot via uncaught `ConfigurationError` |
| OPS-04 | Admin pagination for 100+ row tables | SATISFIED | Audit, error log, sessions wired to shared paginate() helper + render_pagination macro; clamp at 200 |
| SEC-01 | `.whodis_salt` removed from git history and gitignored | PARTIAL | Gitignored (line 169); file STILL TRACKED in git per `git ls-files`; D-01 accepted rotate-instead-of-rewrite-history |
| SEC-02 | CLI for safe encryption key rotation | SATISFIED | `scripts/rotate_encryption_key.py` with dry-run, dual-key, post-commit verify; runbook documents procedure |
| SEC-03 | Per-user rate limit on search | SATISFIED | Flask-Limiter at 30/min on POST /search/search and POST /search/user; D-08 deviation accepted (in-memory; Redis swap deferred to backlog 999.1 — SandCastle integration) |
| SEC-04 | Configurable auth header validation | SATISFIED | Header name configurable; `DANGEROUS_DEV_AUTH_BYPASS_USER` env-var-only with WARNING log |

**Coverage:** 11/12 satisfied, 1 partial (SEC-01 — intentional deviation per D-01)

### Plan Deviations Summary (Documented & Accepted)

| Deviation | Source Plan | Disposition |
|-----------|-------------|-------------|
| D-08 PostgreSQL rate-limiter backend → in-memory | 01-08 | User-approved; Redis swap tracked at backlog 999.1 (SandCastle integration phase) |
| D-01 SEC-01 git history NOT rewritten — relies on key rotation to neutralize leak | 01-07 / Phase context | Accepted at planning; partial vs literal SC wording flagged here for visibility |
| Asyncio fix bundled into Task 2 commit (5b394ca) | 01-01 | Acceptable — same file already being restructured |
| Direct `X-MS-CLIENT-PRINCIPAL-NAME` reads in `app/__init__.py` and `app/utils/error_handler.py` not migrated | 01-09 | Logging-only contexts; not auth decisions; tracked as cleanup follow-up |

### Human Verification Required

See frontmatter `human_verification` block. Five test scenarios cannot be exercised without a live database, populated encrypted-config, or a multi-request load harness:

1. Encryption key rotation dry-run against a populated .env
2. `/health` deep probe under DB up/down conditions on a running app
3. Dev auth bypass round-trip with DANGEROUS_DEV_AUTH_BYPASS_USER set
4. Rate-limit 429 trigger after 30 requests/minute (single-worker scope, per current in-memory storage)
5. Pagination round-trip on a populated admin audit_log table

Each was statically verified at the code/wiring level; behavioral confirmation requires operator action.

### Gaps Summary

The phase substantively achieves its goal: a single canonical factory, deprecated services and asyncio patterns gone, fail-fast config validation, request-ID-correlated JSON logs, an unauthenticated health endpoint, search-endpoint rate limiting, configurable auth header with a loud dev bypass, and pagination wired into three admin tables. All artifacts exist, all key links are wired, no anti-patterns linger.

The single literal gap is SEC-01 / Success Criterion 5: `.whodis_salt` remains tracked in git history. This is an explicit, documented design choice (D-01) — rotating the encryption key after gitignoring the file makes the leaked salt useless without forcing a `git filter-repo` + force-push coordination. The CLI rotation tool and runbook ship to make that follow-through possible. The deviation surfaces here so the developer can decide whether to:

- **Accept** by adding an override entry to this VERIFICATION's frontmatter (D-01 rationale already in place), OR
- **Resolve fully** by scheduling a `git filter-repo` + force-push + key rotation before the repo leaves the trusted operator boundary.

Recommended override entry (if accepting):

```yaml
overrides:
  - must_have: ".whodis_salt is absent from git history and a CLI tool exists to safely rotate the encryption key"
    reason: "D-01 chose rotate-key-over-rewrite-history. Salt is gitignored, rotation tool + runbook ship; rotating WHODIS_ENCRYPTION_KEY makes the leaked salt cryptographically useless."
    accepted_by: "jslitzker"
    accepted_at: "2026-04-24T00:00:00Z"
```

---

*Verified: 2026-04-24*
*Verifier: Claude (gsd-verifier)*
