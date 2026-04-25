---
gsd_state_version: 1.0
milestone: v3.0
milestone_name: milestone
status: executing
stopped_at: Phase 2 context gathered
last_updated: "2026-04-25T17:37:35.567Z"
progress:
  total_phases: 11
  completed_phases: 1
  total_plans: 13
  completed_plans: 11
  percent: 85
---

# Project State: WhoDis v3.0

**Project:** WhoDis v3.0 — IT Operations Platform
**Initialized:** 2026-04-24
**Last Updated:** 2026-04-24

## Project Reference

**Core Value:** IT staff can find everything about any employee and act on it from a single interface — no switching between AD, Azure portal, Genesys admin, or M365 admin center.

**Current Focus:** Phase 02 — test-suite

## Current Position

Phase: 02 (test-suite) — EXECUTING
Plan: 3 of 4
**Phase:** 1 — Foundation ✓
**Status:** Ready to execute
**Next:** Phase 2 (Test Suite) — see revised ROADMAP.md
**Progress:** [█████████░] 85%

## Accumulated Context

### Key Decisions Locked In

- Test suite (Phase 2) ships before write operations (Phase 6) — tests are the safety net for higher-risk ops
- Reports blueprint (Phase 5) builds its own shared infrastructure — REPT-01/02 are the foundation for REPT-06/07 scheduling
- API (Phase 7) starts read-only — write endpoints are v2+ scope
- Operational hardening items (OPS-01..04, SEC-01..04, DEBT-01..04) grouped in Phase 1 to clean the slate before feature work
- Pagination pattern locked: `paginate(query, page, size)` helper + `render_pagination` Jinja macro with `hx-push-url` for bookmarkable URLs (D-13/D-14/D-15) — pattern inherited by Phases 4 and 5
- SEC-04: dev auth bypass is env-var-only (DANGEROUS_DEV_AUTH_BYPASS_USER) — cannot be enabled via DB config or admin UI; deployment-time gate prevents accidental enablement
- OPS-02: per-request UUID4 correlation IDs propagated through JSON logs via python-json-logger; inbound X-Request-ID validated against `^[0-9a-fA-F-]{8,64}$` to prevent log injection
- OPS-03: REQUIRED_KEYS list lives in code (not DB) so operators cannot tamper around the startup gate; error messages list missing key names + labels but never echo decrypted values; Postgres creds remain in .env (bootstrap), validator scope is encrypted-config only
- OPS-01: /health and /health/live are unauthenticated public probes registered at root; /health does DB-only deep check (SELECT 1 + latency_ms, 503 on failure) per D-12 — no LDAP/Graph/Genesys probes; error text truncated to 200 chars; rate limiting deliberately omitted so uptime monitors get free access
- DEBT-03: CacheCleanupService is the third instance of the background-thread pattern (token_refresh, employee_profiles_refresh now joined by cache_cleanup); future scheduled jobs copy this skeleton verbatim. run_now() is the synchronous public entry point for admin invocations (caller already holds a request context). No confirmation modal on Run-now because the operation only deletes already-expired rows.
- SEC-03: Flask-Limiter v3.x dropped PostgreSQL storage support. Shipped in-memory limits now (per-worker scope, acceptable for single/low-worker WhoDis deployment). Swap to redis:// during SandCastle integration phase — Redis available on internal network per WD-NET-01, multi-worker target per WD-CONT-02. Rate-limit decorator placed ABOVE @require_role; key function `_search_rate_key` falls back to remote_addr when g.user is unset (limiter runs before auth check).

### Architecture Constraints

- Flask/PostgreSQL/HTMX only — no new frameworks introduced
- All new endpoints use existing `@auth_required` + `@require_role` decorators
- All write operations require confirmation modal + audit trail + role check (editor minimum)
- Container-based DI — new services registered in `app/container.py`

### Known Concerns to Address by Phase

- Phase 1: `app_factory.py` duplication (DEBT-01), `DataWarehouseService` removal (DEBT-02), asyncio patterns (DEBT-04), `.whodis_salt` in git history (SEC-01)
- Phase 2: Zero test coverage baseline — result_merger.py (537 lines), search_orchestrator.py (332 lines) are highest priority
- Phase 6: Write ops against AD require Graph API additional permissions — document per operation

### Blockers / Risks

- None at initialization — Phase 1 has no external dependencies

## Session Continuity

**Last session:** 2026-04-25T17:37:18.402Z
**Next action:** Phase 2 (Test Suite) — `/gsd-discuss-phase 2`
**Stopped at:** Phase 2 context gathered
**Blockers:** None
**Follow-ups (carry into later phases):**

- Phase 3 (SandCastle Containerization): Swap Flask-Limiter storage from in-memory to Redis (per WD-NET-01, WD-CONT-02) — formerly backlog 999.1, now folded into Phase 3 success criterion
- Phase 4 (Keycloak OIDC Authentication): OIDC library choice deferred to planning. Recommendation noted: `authlib` (most active, best Flask integration). Final selection during `/gsd-plan-phase 4`.
- SEC-01 status: Accepted as partial. Salt rotated and gitignored; git history not rewritten. Both repos are private — risk acknowledged.

---
*State initialized: 2026-04-24*
