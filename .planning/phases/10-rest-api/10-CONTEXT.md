# Phase 10: REST API - Context

**Gathered:** 2026-05-17
**Status:** Ready for planning

<domain>
## Phase Boundary

External systems and automation can query WhoDis via a documented, rate-limited, token-authenticated API without touching the web UI. Delivers read-only endpoints for user search and full profile retrieval, authenticated via admin-created bearer tokens, with per-token rate limiting and interactive OpenAPI documentation. Covers API-01 through API-06.

</domain>

<decisions>
## Implementation Decisions

### Token Design
- **D-01:** Tokens are opaque random strings (hex/base64), stored hashed in the database. No JWT — simple, instantly revocable, no crypto overhead.
- **D-02:** A NEW model is required for external API tokens — the existing `ApiToken` model stores internal service tokens (Genesys, Graph) and is NOT suitable for this purpose.
- **D-03:** Admin must provide a required name/label when creating a token (e.g., "ServiceNow Integration", "Monitoring Script"). Makes audit logs and token list meaningful.

### Response Shape
- **D-04:** All API responses use an envelope format: `{"data": ..., "meta": {...}, "errors": [...]}`. Consistent structure with built-in pagination metadata.
- **D-05:** Full profile data exposed — API returns the same merged result as the web UI (AD fields, Graph data, Genesys status, M365 licenses).
- **D-06:** Search results are always paginated (default page_size, offset/cursor params in envelope `meta`).
- **D-07:** Error responses include machine-readable error codes: `{"error": {"code": "RATE_LIMITED", "message": "...", "details": {...}}}` alongside HTTP status codes.

### Rate Limiting
- **D-08:** Rate limits are per-token — each token has its own bucket via Flask-Limiter's custom key function.
- **D-09:** Single default rate threshold for all tokens (e.g., 60 req/min), stored in encrypted config. No per-token custom limits.

### OpenAPI Documentation
- **D-10:** OpenAPI spec is auto-generated from code using a library (flask-smorest or apispec — researcher determines best fit).
- **D-11:** Swagger UI serves interactive docs at `/api/v1/docs` — standard "Try it" explorer.
- **D-12:** Docs endpoint is publicly accessible (no authentication required), per API-06 success criteria.

### Claude's Discretion
- **D-02a:** Token scoping — whether all tokens get full read access or per-token permission scopes. Consider the 4-5 person team context and API-01..06 requirements.
- **D-02b:** Token expiration policy — never-expire with revoke-only vs. configurable TTL at creation. Balance security vs. operational simplicity for a small team.
- **D-10a:** Specific library choice between flask-smorest and apispec — researcher determines best fit for the existing Flask blueprint architecture.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project Planning
- `.planning/ROADMAP.md` §"Phase 10: REST API" — 5 success criteria, depends on Phases 2/4/6
- `.planning/REQUIREMENTS.md` §"API" — API-01..06
- `.planning/STATE.md` §"Key Decisions Locked In" — "API starts read-only — write endpoints are v2+ scope"

### Codebase Maps
- `.planning/codebase/STRUCTURE.md` — directory layout, blueprint/service/model locations
- `.planning/codebase/INTEGRATIONS.md` — Graph + LDAP + Genesys integration shape
- `.planning/codebase/CONVENTIONS.md` — service patterns, decorator usage, error handling

### Existing Code (extend, do NOT redesign)
- `app/models/api_token.py` — EXISTING model for internal service tokens. DO NOT reuse for external API tokens — create a new model.
- `app/__init__.py:34` — Flask-Limiter already initialized (in-memory, `get_remote_address` key). API needs custom key function for per-token limiting.
- `app/services/audit_service_postgres.py:71` — `log_admin_action()` for audit trail
- `app/middleware/auth.py:131` — `require_role()` decorator for admin-gating token management
- `app/blueprints/admin/` — admin UI blueprint where token CRUD management lives
- `app/services/search_orchestrator.py` — search logic to expose via API (reuse, don't duplicate)

### Prior Phase Context
- `.planning/phases/09-write-operations/09-CONTEXT.md` — confirmation UX patterns, admin action audit conventions
- `.planning/phases/08-reporting/08-CONTEXT.md` — report API patterns, CSV export conventions

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `SearchOrchestrator`: orchestrates parallel LDAP/Graph/Genesys searches — expose via API without duplicating logic
- `ResultMerger`: merges multi-source results into unified profile — same merge for API responses
- `audit_service.log_admin_action()`: audit trail for token creation/revocation
- Flask-Limiter (`from app import limiter`): rate limiting infrastructure already initialized
- `@auth_required` + `@require_role("admin")`: gate token management endpoints

### Established Patterns
- Blueprint-based routing: new `app/blueprints/api/` blueprint for v1 API routes
- Service registration in `app/container.py`: register API token service
- `@handle_service_errors` decorator: consistent error handling for service methods
- JSON responses from existing admin API routes (health, cache status): follow same Flask `jsonify()` pattern

### Integration Points
- New blueprint: `app/blueprints/api/` with versioned routes (`/api/v1/search`, `/api/v1/user/{email}`)
- New model: External API token model (separate from existing `ApiToken`)
- New middleware: Bearer token authentication for API routes (bypasses Azure AD SSO auth)
- Extend Flask-Limiter: custom key function to rate-limit by token ID
- Admin UI: token CRUD pages in `app/blueprints/admin/` (create, list, revoke)
- OpenAPI library integration: auto-spec generation from route decorators

</code_context>

<specifics>
## Specific Ideas

- Token format: opaque random string, displayed once at creation (like GitHub PATs). Admin copies it immediately — never shown again.
- Envelope response example: `{"data": [{...}], "meta": {"page": 1, "page_size": 25, "total": 3}, "errors": null}`
- Error code examples: TOKEN_EXPIRED, TOKEN_REVOKED, RATE_LIMITED, INVALID_TOKEN, SEARCH_FAILED, USER_NOT_FOUND
- Swagger UI at `/api/v1/docs` — public, no auth. Interactive "Try it" requires a valid bearer token in the authorize dialog.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 10-REST API*
*Context gathered: 2026-05-17*
