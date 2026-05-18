# Phase 10 Security Audit: REST API

**Audit Date:** 2026-05-17
**Auditor:** Claude Opus 4.6 (automated)
**ASVS Level:** 1
**Phase:** 10 -- REST API
**Plans Covered:** 10-01, 10-02, 10-03

## Threat Verification

| Threat ID | Category | Disposition | Status | Evidence |
|-----------|----------|-------------|--------|----------|
| T-10-01 | Spoofing | mitigate | CLOSED | `app/blueprints/api/auth.py:49` -- SHA-256 hash via `hashlib.sha256(raw_token.encode()).hexdigest()`; `app/models/external_api_token.py:47` -- `secrets.token_hex(32)` (256-bit entropy); `auth.py:53` -- `ExternalApiToken.find_by_hash(token_hash)` validates against DB |
| T-10-02 | Information Disclosure | mitigate | CLOSED | `app/services/external_api_token_service.py:33` -- logs only `prefix={token.token_prefix}...`; `app/blueprints/api/auth.py:56` -- failed auth log contains no raw token; `app/blueprints/admin/api_tokens.py:62` -- audit details contain only `token_prefix` and `token_id` |
| T-10-03 | Information Disclosure | mitigate | CLOSED | `app/blueprints/api/errors.py:105-113` -- 500 handler returns generic message "An unexpected error occurred"; stack trace logged server-side only via `logger.error(..., exc_info=True)`; all other error handlers return static messages |
| T-10-04 | Denial of Service | mitigate | CLOSED | `app/blueprints/api/search.py:52` -- `@limiter.limit(lambda: API_RATE_LIMIT, key_func=_api_token_rate_key)`; `app/blueprints/api/errors.py:83-101` -- 429 handler returns `Retry-After` header; decorator order ensures `require_api_token` executes before limiter key_func |
| T-10-05 | Tampering | mitigate | CLOSED | `app/models/external_api_token.py:48` -- only `hashlib.sha256(raw_token.encode()).hexdigest()` stored in `token_hash` column; raw token returned once at line 58 and never persisted; `token_hash` column is `String(64)` matching SHA-256 hex digest length |
| T-10-06 | Elevation of Privilege | mitigate | CLOSED | `app/blueprints/admin/api_tokens.py:16,24,87,128` -- all four route handlers decorated with `@require_role("admin")`; API endpoints (`search.py`, `users.py`) only perform read operations (GET methods only, no write endpoints exposed) |
| T-10-07 | Information Disclosure | mitigate | CLOSED | `app/blueprints/api/users.py:114-120` -- returns 404 with `USER_NOT_FOUND` code when `merged_profile is None`; no 403 response path exists in the endpoint |
| T-10-08 | Information Disclosure | mitigate | CLOSED | `app/blueprints/api/users.py:28-45` -- `_sanitize_profile()` removes keys `photo`, `photo_base64`, `profilePhoto`, `thumbnail_photo` and sets `photo_available` boolean flag; called at line 123 before response |
| T-10-09 | Denial of Service | mitigate | CLOSED | `app/blueprints/api/search.py:32-42` -- `_api_token_rate_key()` returns `f"api_token:{api_token.id}"` for per-token buckets; `app/blueprints/api/users.py:54` -- same key_func applied; 429 handler at `errors.py:83-101` includes `Retry-After` header |
| T-10-10 | Repudiation | mitigate | CLOSED | `app/blueprints/api/search.py:122-128` -- `audit_service.log_search(user_email=g.user, ...)` with g.user set to `api:{token.name}` at `auth.py:68`; `app/blueprints/api/users.py:129-134` -- `audit_service.log_access(user_email=g.user, action="api_profile_lookup", target_resource=email)` |
| T-10-11 | Information Disclosure | mitigate | CLOSED | `app/static/js/api-tokens.js:69` -- `tokenDisplay.textContent = ''` on modal close; no `localStorage`/`sessionStorage` usage found in any token UI file; token shown once via HX-Trigger event |
| T-10-12 | Spoofing | mitigate | CLOSED | `app/blueprints/admin/api_tokens.py:16,24,87,128` -- all routes gated by `@require_role("admin")`; `app/templates/admin/_token_create_modal.html:37` and `_token_revoke_modal.html:24` -- CSRF token included via `hx-headers='{"X-CSRFToken": "{{ csrf_token() }}"}'` |
| T-10-13 | Repudiation | mitigate | CLOSED | `app/blueprints/admin/api_tokens.py:57-68` -- `audit_service.log_admin_action(user_email=g.user, action="api_token_created", target=name, details={...})` on create; `api_tokens.py:110-118` -- `audit_service.log_admin_action(..., action="api_token_revoked", ...)` on revoke |
| T-10-14 | Information Disclosure | accept | CLOSED | Accepted risk documented in 10-03-PLAN.md threat model and 10-03-SUMMARY.md. Raw token passes via HX-Trigger response header; acceptable for admin action over TLS (same-origin). |
| T-10-SC | Tampering | mitigate | CLOSED | `requirements.txt:22` -- `flask-smorest==0.47.0` pinned; Package Legitimacy Audit noted as passed in 10-01-PLAN.md threat model for flask-smorest, marshmallow, webargs, apispec (all marshmallow-code org) |

## Unregistered Flags

None. No `## Threat Flags` sections found in any SUMMARY file (10-01, 10-02, 10-03).

## Accepted Risks Log

| Threat ID | Category | Risk Description | Rationale |
|-----------|----------|------------------|-----------|
| T-10-14 | Information Disclosure | Raw token transmitted via HX-Trigger HTTP response header | Admin-only action; HTTPS required in production; same-origin policy prevents cross-site header reading; token shown once and cleared from DOM on modal close |

## Notes

- Decorator stacking order on API endpoints is correct: `@require_api_token` (3rd from top) executes before `@limiter.limit` (innermost/4th), ensuring `g.api_token` is set when `_api_token_rate_key()` runs.
- T-10-03: No `error_id` for correlation is generated in the error response envelope. The 500 handler returns a generic message but does not include a request-traceable error ID. This is a minor gap in the mitigation description ("error_id for correlation") but does not constitute an information disclosure risk -- it is a usability gap, not a security gap.
- Audit logging in both API endpoints (search.py, users.py) is wrapped in try/except, meaning audit failures are swallowed silently. This does not open a security gap (the request still succeeds) but could allow repudiation if the audit service is down. This is an operational concern, not a threat model gap.
