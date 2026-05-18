---
phase: 10-rest-api
reviewed: 2026-05-17T22:30:00Z
depth: standard
files_reviewed: 20
files_reviewed_list:
  - alembic/versions/004_external_api_tokens.py
  - app/__init__.py
  - app/blueprints/admin/__init__.py
  - app/blueprints/admin/api_tokens.py
  - app/blueprints/api/__init__.py
  - app/blueprints/api/auth.py
  - app/blueprints/api/errors.py
  - app/blueprints/api/schemas.py
  - app/blueprints/api/search.py
  - app/blueprints/api/users.py
  - app/container.py
  - app/models/external_api_token.py
  - app/services/external_api_token_service.py
  - app/static/js/api-tokens.js
  - app/templates/admin/_external_api_tokens.html
  - app/templates/admin/_token_create_modal.html
  - app/templates/admin/_token_reveal_modal.html
  - app/templates/admin/_token_revoke_modal.html
  - app/templates/admin/index.html
  - requirements.txt
findings:
  critical: 3
  warning: 5
  info: 2
  total: 10
status: issues_found
---

# Phase 10: Code Review Report

**Reviewed:** 2026-05-17T22:30:00Z
**Depth:** standard
**Files Reviewed:** 20
**Status:** issues_found

## Summary

Phase 10 introduces a REST API with bearer token authentication, flask-smorest OpenAPI integration, and admin token management UI. The implementation is generally well-structured, but contains a critical decorator ordering bug that silently defeats per-token rate limiting, a missing CSRF protection gap on admin token management endpoints, and an XSS vector in the admin blueprint. Several quality and robustness issues were also found.

## Critical Issues

### CR-01: Decorator ordering defeats per-token rate limiting

**File:** `app/blueprints/api/search.py:49-52`
**Issue:** The `@require_api_token` decorator is the innermost decorator (runs first), but Flask-Limiter's `@limiter.limit()` decorator evaluates its `key_func` *before* calling the wrapped function. Since decorators execute outer-to-inner, the call chain is: `arguments` -> `response` -> `limiter.limit` (evaluates key) -> `require_api_token` (sets `g.api_token`) -> `get()`. The `_api_token_rate_key()` function on line 39 reads `g.api_token`, which has not been set yet when the limiter evaluates the key. Result: rate limiting always falls back to IP address, silently defeating per-token rate limiting entirely. The same issue exists in `app/blueprints/api/users.py:53`.
**Fix:** Move `@require_api_token` above `@limiter.limit()` so it executes first:
```python
@api_search_bp.arguments(SearchQuerySchema, location="query")
@api_search_bp.response(200, SearchResponseSchema)
@require_api_token
@limiter.limit(lambda: API_RATE_LIMIT, key_func=_api_token_rate_key)
def get(self, args: Dict[str, Any]) -> Dict[str, Any]:
```
Apply the same reordering in `users.py`.

### CR-02: Missing CSRF protection on admin token create/revoke POST endpoints

**File:** `app/blueprints/admin/api_tokens.py:25-84`, `app/blueprints/admin/api_tokens.py:87-125`
**Issue:** The `create_api_token` and `revoke_api_token` endpoints accept POST requests via HTMX but have no CSRF protection. The CSRF middleware in this project is decorator-based (`@csrf_required`), not automatic. A malicious page visited by a logged-in admin could forge a POST to `/admin/api-tokens/create` or `/admin/api-tokens/<id>/revoke`, creating rogue tokens or revoking legitimate ones. Token creation is especially dangerous since the raw token is returned in the response. The HTMX create modal template also lacks a CSRF token hidden input or header inclusion.
**Fix:** Add CSRF validation to both endpoints. Either:
1. Apply the `csrf_required` decorator from `app/middleware/csrf.py`, or
2. Include a CSRF token in HTMX requests via `hx-headers` and validate it server-side:
```html
<!-- In _token_create_modal.html, on the confirm button -->
hx-headers='{"X-CSRF-Token": "{{ csrf_token() }}"}'
```

### CR-03: XSS via unescaped UPN in admin blueprint HTML response

**File:** `app/blueprints/admin/__init__.py:363`
**Issue:** When no employee profile is found, the UPN is interpolated directly into raw HTML using Python `.format()`:
```python
return """...<span class="text-yellow-800">No employee profile found for UPN: {}</span>...""".format(upn)
```
The `upn` value comes from user-supplied query parameter `request.args.get("search_upn")` (line 289) and is only `.strip()`-ped, not HTML-escaped. An attacker could inject `<script>alert(1)</script>` as the UPN, causing reflected XSS against the admin user. Although this requires admin auth, it is still a stored-XSS vector exploitable via crafted link.
**Fix:** Use `markupsafe.escape()` or `render_template_string` with Jinja2 auto-escaping:
```python
from markupsafe import escape
# ...
return """...<span class="text-yellow-800">No employee profile found for UPN: {}</span>...""".format(escape(upn))
```

## Warnings

### WR-01: record_usage() issues a full database commit on every API request

**File:** `app/models/external_api_token.py:71-75`
**Issue:** `record_usage()` calls `self.save()` which issues a `db.session.commit()` on every authenticated API request. This has two problems: (1) it does a read-modify-write of `usage_count` without atomicity (`self.usage_count = (self.usage_count or 0) + 1`), creating a race condition under concurrent requests that can lose count increments, and (2) it commits the session mid-request, which can interfere with other transactional work in the same request.
**Fix:** Use an atomic SQL UPDATE instead:
```python
def record_usage(self) -> None:
    from app.database import db
    db.session.execute(
        db.update(ExternalApiToken)
        .where(ExternalApiToken.id == self.id)
        .values(
            usage_count=ExternalApiToken.usage_count + 1,
            last_used_at=datetime.now(timezone.utc),
        )
    )
    # Let the request's normal commit handle this, or commit here if needed
```

### WR-02: API error handlers registered on app, not scoped to API blueprint

**File:** `app/blueprints/api/__init__.py:47`
**Issue:** `register_api_error_handlers(app)` registers error handlers on the Flask application, not on the API blueprint. This means the JSON error handlers for 400, 401, 403, 404, 422, 429, and 500 will override the existing HTML error handlers in `app/__init__.py` (lines 329-378) for ALL routes, not just `/api/v1/*`. For example, a 404 on the web UI (`/admin/nonexistent`) would now return JSON instead of HTML.
**Fix:** Register handlers on the API blueprint instead of the app:
```python
# In init_api():
register_api_error_handlers(api_search_bp)
register_api_error_handlers(api_users_bp)
```
Or scope the handlers to only respond when the request path starts with `/api/v1/`.

### WR-03: Genesys results always accessed even when search returns no result

**File:** `app/blueprints/api/search.py:98`
**Issue:** `genesys_result.get("result")` is called unconditionally, but if the Genesys service times out or fails, `genesys_result` might not have the expected structure. The code from `execute_concurrent_search` returns a dict, but the contract is not guaranteed for all error paths. If `genesys_result` is `None` or not a dict, this will raise `AttributeError`.
**Fix:** Add a guard:
```python
genesys_data = genesys_result.get("result") if isinstance(genesys_result, dict) else None
```
Apply the same pattern in `users.py:105`.

### WR-04: API token creation returns raw token in HX-Trigger header to any HTTP observer

**File:** `app/blueprints/admin/api_tokens.py:70-76`
**Issue:** The raw API token is returned in the `HX-Trigger` response header as JSON. While the HTMX flow requires this, HTTP response headers are logged by many proxies, WAFs, and monitoring tools. The raw token in a response header is more likely to be captured in infrastructure logs than if it were in the response body. Combined with the missing CSRF (CR-02), this increases the blast radius.
**Fix:** Consider returning the raw token in the response body instead:
```python
response = jsonify({"success": True, "token": raw_token, "name": name})
response.headers["HX-Trigger"] = "tokenCreated"
```
Then read the token from the response body in the JS event handler.

### WR-05: SearchOrchestrator and ResultMerger instantiated per request instead of using DI container

**File:** `app/blueprints/api/search.py:70-71`, `app/blueprints/api/users.py:67-68`
**Issue:** Both API endpoints create new `SearchOrchestrator()` and `ResultMerger()` instances on every request rather than retrieving them from the DI container. This bypasses the singleton pattern the project relies on, potentially losing cached state, and violates the project's established pattern documented in CLAUDE.md: "Retrieve services from container, never use global imports."
**Fix:**
```python
from flask import current_app
orchestrator = current_app.container.get("search_orchestrator")  # register if not yet
merger = current_app.container.get("result_merger")
```
Or register these in `container.py` if not already registered.

## Info

### IN-01: Unused import in schemas.py

**File:** `app/blueprints/api/schemas.py:7`
**Issue:** `ErrorDetailSchema` is defined but only used internally by `ErrorResponseSchema`. The `ErrorResponseSchema` itself is defined but never referenced by any endpoint (the error handlers in `errors.py` build error responses manually via `_error_response()` rather than using Marshmallow serialization).
**Fix:** Either use `ErrorResponseSchema` in the error handlers for consistency with the flask-smorest pattern, or remove the unused schema class to reduce dead code.

### IN-02: OPTIONS requests blocked globally but CORS may be needed for API

**File:** `app/__init__.py:293-295`
**Issue:** The `before_request` handler globally blocks all OPTIONS requests with a 405. This would prevent CORS preflight requests from succeeding if the API is ever called from browser-based JavaScript clients on different origins. While the current API is bearer-token-based (likely server-to-server), the Swagger UI at `/api/v1/docs` may also need OPTIONS for "Try it out" functionality from browser contexts.
**Fix:** Consider exempting `/api/v1/*` paths from the OPTIONS block, or removing the blanket block in favor of proper CORS headers if cross-origin API access is planned.

---

_Reviewed: 2026-05-17T22:30:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
