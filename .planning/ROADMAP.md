# Roadmap: WhoDis v3.0

**Milestone:** WhoDis v3.0 — IT Operations Platform
**Defined:** 2026-04-24
**Revised:** 2026-04-24 (SandCastle integration insertion + re-prioritization)
**Granularity:** Standard (revised to 11 phases — integration work is large and naturally splits)
**Requirements:** 90 v1 requirements across 19 categories (52 original + 38 SandCastle integration)

## Revision Rationale (2026-04-24)

The SandCastle hosting integration introduces 38 new requirements that fundamentally change the deployment topology, authentication backend, and database lifecycle. Rather than appending them, the roadmap is re-sequenced so they land in the correct dependency order:

| Decision | Rationale |
|----------|-----------|
| **Split integration into 3 phases (Containerization → Auth Migration → DB Migration)** | Each phase is independently verifiable and large enough to warrant its own success criteria. A single 38-requirement phase would be unreviewable. |
| **Test Suite (Phase 2) stays early** | Tests are the safety net for the auth + DB refactors that follow. Mocking Keycloak and Alembic-managed schemas is far easier with a test harness in place. |
| **Containerization (Phase 3) before Keycloak (Phase 4)** | Container + gunicorn + Traefik can ship while still using the existing Azure AD header auth (WD-AUTH-08 / WD-CONT-* are independent). This decouples deployment-platform risk from auth-stack risk. |
| **Keycloak (Phase 4) before write ops, before REST API** | OIDC fundamentally changes how `g.user` is populated and how tokens are minted. Building write ops or token-auth APIs against Azure AD headers and then re-doing them against Keycloak is wasted work. |
| **Alembic (Phase 5) before write ops** | Write operations create new tables and audit columns. Switching to Alembic mid-feature-work would force replaying migrations on a moving schema. Land migrations infrastructure first. |
| **Enriched Profiles / Compliance / Reporting AFTER integration** | These are read-only feature phases that don't depend on auth or schema changes, but they DO ship to users — running them through one consistent post-integration topology avoids double-test churn. |
| **Backlog 999.1 (Redis-backed rate limiting) folded into Phase 3** | Multi-worker gunicorn (WD-CONT-02) makes per-worker in-memory counters incorrect. Redis is already on the SandCastle internal network. Swap belongs with the multi-worker rollout, not as a standalone backlog item. |
| **WD-OPS / WD-DOC requirements folded into Phase 3** | Portal registration, webhook, and `docs/sandcastle.md` are tightly coupled to the containerization/deployment work. Splitting them into a separate doc phase would create artificial sequencing. |
| **Phase 1 stays at #1** | Already complete. Renumbering would invalidate `.planning/phases/01-foundation/` artifacts and STATE.md history. |

## Phases

- [x] **Phase 1: Foundation** - Clean up tech debt, harden security, add operational primitives (COMPLETE)
- [x] **Phase 2: Test Suite** - Establish automated testing infrastructure before write operations (gate green at 60.12%; verified)
- [ ] **Phase 3: SandCastle Containerization & Deployment** - Containerize, gunicorn, Traefik, env-var config, structured logs, portal registration
- [ ] **Phase 4: Keycloak OIDC Authentication** - Replace Azure AD header auth with Keycloak OIDC; preserve role decorators
- [ ] **Phase 5: Database Migration & Alembic** - Move schema to Alembic, switch to DATABASE_URL, document data-migration path
- [ ] **Phase 6: Enriched Profiles & Search Export** - Surface full Graph/Genesys data on profile cards with export
- [ ] **Phase 7: Compliance Polish** - Bulk checks with progress, export, and warehouse sync visibility
- [ ] **Phase 8: Reporting** - License, security posture, and Genesys reports with scheduling
- [ ] **Phase 9: Write Operations** - AD account actions and license management from the UI
- [ ] **Phase 10: REST API** - Token-authenticated read-only API with rate limiting and docs
- [ ] **Phase 11: Workflow Automation** - Onboarding/offboarding checklists with completion tracking

## Phase Details

### Phase 1: Foundation
**Goal**: The codebase has a single clean initialization path, deprecated code is gone, security gaps are closed, and production operational primitives are in place
**Depends on**: Nothing (brownfield baseline)
**Requirements**: DEBT-01, DEBT-02, DEBT-03, DEBT-04, OPS-01, OPS-02, OPS-03, OPS-04, SEC-01, SEC-02, SEC-03, SEC-04
**Success Criteria** (what must be TRUE):
  1. Application starts with a single code path — `app/__init__.py` is the only factory, `app_factory.py` is deleted
  2. `GET /health` returns JSON with database status, usable by monitoring tools without authentication
  3. Every log line carries a request ID that can be used to trace a single user action end-to-end
  4. Application refuses to start with clear error messages when required configuration values are missing
  5. `.whodis_salt` is absent from git history and a CLI tool exists to safely rotate the encryption key
**Plans**: 9 plans
- [x] 01-01-debt-cleanup-PLAN.md — Consolidate app factory, remove DataWarehouseService, modernize asyncio (DEBT-01/02/04)
- [x] 01-02-cache-cleanup-PLAN.md — Hourly SearchCache cleanup service + admin Run-now button (DEBT-03)
- [x] 01-03-health-endpoints-PLAN.md — Unauthenticated /health and /health/live endpoints (OPS-01)
- [x] 01-04-request-id-json-logging-PLAN.md — Request-ID middleware + JSON-structured logging (OPS-02)
- [x] 01-05-config-validator-PLAN.md — Startup config validator that aborts boot on missing keys (OPS-03)
- [x] 01-06-pagination-PLAN.md — Reusable paginate helper + render_pagination macro wired into 3 admin tables (OPS-04)
- [x] 01-07-salt-key-rotation-PLAN.md — Gitignore .whodis_salt + dual-key rotation script + runbook (SEC-01/02)
- [x] 01-08-rate-limiting-PLAN.md — Flask-Limiter on /search and /api/search at 30/min per user (SEC-03)
- [x] 01-09-auth-header-config-PLAN.md — Configurable auth header + dev bypass env var (SEC-04)
**UI hint**: yes
**Acceptance notes**:
  - **SEC-01 partial accepted (2026-04-25):** `.whodis_salt` rotated and gitignored per D-01 (rotate-over-rewrite-history); the file is no longer reachable via the live encryption key but remains in git history. Risk acknowledged — both repos are private. `git filter-repo` history rewrite not pursued. CLI tool (`scripts/rotate_encryption_key.py`) exists for future key rotations.
  - **D-08 deviation (2026-04-25):** Flask-Limiter v3.x dropped PostgreSQL storage support; shipped in-memory limits per Option 1 user decision. Redis swap folded into Phase 3 success criterion (multi-worker target per WD-CONT-02; Redis available on SandCastle internal network per WD-NET-01).

### Phase 2: Test Suite
**Goal**: Developers can run a full test suite that covers services and middleware, with mocked external APIs, preventing regressions before any auth/DB refactor or write operations ship
**Depends on**: Phase 1
**Requirements**: TEST-01, TEST-02, TEST-03, TEST-04
**Success Criteria** (what must be TRUE):
  1. `pytest tests/ -v` runs to completion without real LDAP, Graph, or Genesys calls
  2. Coverage report shows 60%+ on services and middleware packages
  3. Authentication middleware pipeline and full search flow are verified by integration tests
  4. A failing test blocks a developer from merging (even without CI, the suite is runnable as a gate)
**Plans**: 6 plans
- [x] 02-01-test-infra-scaffolding-PLAN.md — requirements split, pyproject.toml pytest+coverage config, Makefile, pre-push hook, .gitignore verification (TEST-01, TEST-04)
- [x] 02-02-fixtures-fakes-factories-PLAN.md — TESTING gate in app/__init__.py, conftest tree (Postgres+SAVEPOINT), fakes (LDAP/Graph/Genesys), factories (User/ApiToken/JobCode/SystemRole) (TEST-01, TEST-02)
- [x] 02-03-targeted-and-integration-tests-PLAN.md — Unit tests for orchestrator/LDAP/Genesys (D-12 hot paths) + integration tests for auth pipeline + search flow (D-13/D-14) (TEST-01, TEST-02, TEST-03)
- [x] 02-04-coverage-gate-and-docs-PLAN.md — Full-suite verification, coverage report, README hook installer docs, pre-push gate human verification (TEST-04)
- [x] 02-05-coverage-closure-PLAN.md — Round-1 boundary tests for compliance/genesys-cache/mapping/warehouse/refresh-profiles (5 files, +9.3pp aggregate) (TEST-04, gap closure round 1, PARTIAL — per-file targets met, aggregate gate still failed)
- [x] 02-06-coverage-closure-round-2-PLAN.md — Round-2 boundary tests for result_merger/search_enhancer/graph_service/token_refresh/audit_service_postgres + 5 middleware modules (137 tests, +13pp to clear gate at 60.12%) (TEST-04, gap closure round 2 — COMPLETE)
**Acceptance notes**:
  - **Coverage gate progression:** baseline 32.0% → after Plan 02-05: 41.31% → after integration-test repair (Phase 9 OIDC collateral): 47.08% → Plan 02-06 target: ≥60%.
  - **Plan 02-05 partial closure (2026-04-25):** Per-file targets met for 4/5 services (compliance_checking 0%→68.8%, genesys_cache_db 11.9%→65.4%, job_role_mapping 13.3%→66.7%, job_role_warehouse 14.7%→56.6%; refresh_employee_profiles 16.4%→36.5% — 3.5pp short). 81 tests added, no production code modified. Gate still failed because unscoped files (graph_service, result_merger, search_enhancer, token_refresh, audit_service_postgres) retained ~700 missed stmts. See `02-VERIFICATION.md` Gap Closure section for details.
  - **Plan 02-06 scope:** the remaining 5 files in the order graph_service > result_merger > search_enhancer > audit_service_postgres > token_refresh_service, targeting ~50% per-file coverage. Aggregate forecast: ~60-62% combined.
  - **Hook gate verified programmatically (2026-04-25):** AUTO-MODE auto-approved the human-verify checkpoint; executor reproduced green/red/coverage-drop pytest exit codes (0/1/non-zero) — recorded in `02-VERIFICATION.md`.

### Phase 3: SandCastle Containerization & Deployment
**Goal**: WhoDis runs as a hosted SandCastle application — packaged in a production Docker image, served by gunicorn through Traefik at `whodis.sandcastle.ttcu.com`, configured entirely via environment variables, observable through structured logs and health probes
**Depends on**: Phase 2 (tests must exist before refactoring init/config paths)
**Requirements**: WD-CONT-01, WD-CONT-02, WD-CONT-03, WD-CONT-04, WD-CONT-05, WD-CFG-01, WD-CFG-02, WD-CFG-03, WD-CFG-04, WD-CFG-05, WD-HEALTH-01, WD-HEALTH-02, WD-HEALTH-03, WD-HEALTH-04, WD-NET-01, WD-NET-02, WD-NET-03, WD-NET-04, WD-NET-05, WD-OPS-01, WD-OPS-02, WD-OPS-03, WD-OPS-04, WD-DOC-01, WD-DOC-02
**Success Criteria** (what must be TRUE):
  1. `docker compose -f docker-compose.sandcastle.yml up` against a populated `.env` brings the app online and serves traffic at `https://whodis.sandcastle.ttcu.com` through Traefik with HTTPS-only and a valid Let's Encrypt cert
  2. The container runs gunicorn as a non-root user with `GUNICORN_WORKERS` configurable (default 2), and Flask-Limiter rate counters are shared across workers via Redis (`REDIS_URL` from the SandCastle internal network)
  3. All runtime configuration comes from environment variables documented in `.env.sandcastle.example` — no hardcoded secrets, no `instance/` files, no JSON config baked into the image
  4. `/health` returns 200 unauthenticated for the SandCastle poller; `/health/ready` returns 503 when the database is unreachable; structured JSON logs go to stdout/stderr; the Dockerfile `HEALTHCHECK` exercises `/health` every 30s
  5. WhoDis is registered in the SandCastle portal catalog with auto-deploy on `main` push via webhook; `docs/sandcastle.md` documents the env var matrix, deployment flow, and rollback procedure; legacy Azure App Service notes are removed or marked deprecated
**Plans**: 3 plans
- [x] 03-01-PLAN.md — Redis-backed Flask-Limiter swap (RATELIMIT_STORAGE_URI; closes Phase 1 D-08 deviation / SC#2)
- [x] 03-02-PLAN.md — DATABASE_URL refactor in app/database.py + .env.example + verify_deployment.py (WD-CFG-02, WD-DB-01 cross-phase)
- [ ] 03-03-PLAN.md — README deployment-pointer cleanup + docs/sandcastle.md Operational Verification + verify_deployment.py --sandcastle (WD-OPS-01, WD-OPS-04, WD-DOC-02)
**UI hint**: no
**Planning notes**:
  - **Gap-closure framing:** PR #25 shipped ~80% of this phase. Plans 03-01..03-03 close the 4 remaining gaps (WD-CFG-02, WD-OPS-01, WD-OPS-04, WD-DOC-02) plus SC#2 Redis swap. All 25 WD-* requirements are covered across the 3 plans.
  - **Cross-phase:** Plan 03-02 also satisfies WD-DB-01 (Phase 5). Phase 5 retains WD-DB-02..05 only.

### Phase 4: Keycloak OIDC Authentication
**Goal**: WhoDis authenticates users through the SandCastle Keycloak realm via OIDC — Azure AD header reads are gone, role-based decorators continue to work unchanged, and existing user records match by email
**Depends on**: Phase 2 (auth middleware tests), Phase 3 (container topology + env-var config in place)
**Requirements**: WD-AUTH-01, WD-AUTH-02, WD-AUTH-03, WD-AUTH-04, WD-AUTH-05, WD-AUTH-06, WD-AUTH-07, WD-AUTH-08
**Success Criteria** (what must be TRUE):
  1. An unauthenticated request to any non-public route redirects to Keycloak and, after successful login, lands the user back at the originally requested URL
  2. `g.user` (email) and `g.role` are populated from Keycloak ID-token claims (`email`, `realm_access.roles`); existing `@auth_required` and `@require_role()` decorators work without modification
  3. First-time SSO arrivals provision a local user record with the default `viewer` role; existing users match by email and retain their stored role
  4. Logout terminates both the Flask session and the Keycloak session via RP-initiated logout, and a subsequent request restarts the OIDC flow
  5. `grep -r "X-MS-CLIENT-PRINCIPAL"` across the codebase returns zero matches; `app/middleware/authentication_handler.py` no longer reads Azure AD headers
**Plans**: TBD
**UI hint**: yes
**Planning notes**:
  - **OIDC library:** Deferred to `/gsd-plan-phase 4`. Recommendation noted: **`authlib`** (most active maintenance, strong Flask integration, less hand-rolling than `python-jose`). Alternatives considered: `flask-oidc` (older, less active), hand-rolled with `python-jose` + manual session handling. Final selection during planning.

### Phase 5: Database Migration & Alembic
**Goal**: Schema changes are managed by Alembic, the app connects via a single `DATABASE_URL`, and a documented one-time path moves data from the current Postgres instance to the SandCastle shared instance
**Depends on**: Phase 3 (container needs DATABASE_URL injection in place)
**Requirements**: WD-DB-01, WD-DB-02, WD-DB-03, WD-DB-04, WD-DB-05
**Success Criteria** (what must be TRUE):
  1. The app connects to PostgreSQL exclusively via `DATABASE_URL`; legacy `POSTGRES_*` connection-string composition is removed
  2. Container start applies pending Alembic migrations automatically before gunicorn binds; existing `database/create_tables.sql` is replaced (or invoked) by an Alembic baseline migration
  3. A documented runbook (`docs/runbooks/sandcastle-data-migration.md`) lets an operator export the current WhoDis database, provision the SandCastle DB via `provision-db.sh whodis`, and restore data with row counts verified
  4. SQLAlchemy connection pool is configured for a containerized deployment (`pool_size=5`, `pool_pre_ping=True`); pool exhaustion logs surface as structured errors, not stack traces
  5. A new schema change can be authored, committed, deployed via portal webhook, and applied on container start without any manual `psql` step
**Plans**: TBD
**UI hint**: no

### Phase 6: Enriched Profiles & Search Export
**Goal**: Profile cards show the full picture of an employee — Graph licenses, MFA, last sign-in, Genesys queues and skills — without cluttering the default view, and users can export what they see
**Depends on**: Phase 1, Phase 5 (ships against final auth + DB topology)
**Requirements**: PROF-01, PROF-02, PROF-03, PROF-04, PROF-05, PROF-06, SRCH-01, SRCH-02
**Success Criteria** (what must be TRUE):
  1. Profile card shows department, manager, assigned licenses, MFA status, and last sign-in date from Graph
  2. Profile card shows Genesys queues, skills with proficiency levels, and current presence
  3. Extended data lives in collapsible sections that are closed by default — the default card is not cluttered
  4. Expensive fields (sign-in logs, licenses) load after the initial card render via HTMX, not blocking page paint
  5. User can copy a structured text summary to clipboard or download a CSV of all visible fields
**Plans**: TBD
**UI hint**: yes

### Phase 7: Compliance Polish
**Goal**: Admins running bulk compliance checks get real-time progress feedback, can export results, and can see when warehouse data was last synced — without encountering raw stack traces
**Depends on**: Phase 5
**Requirements**: COMP-01, COMP-02, COMP-03, COMP-04, COMP-05
**Success Criteria** (what must be TRUE):
  1. Bulk compliance check shows a live progress indicator (HTMX polling) — admin sees checks completing in real time
  2. Compliance results table is sortable by severity (critical first) without a page reload
  3. Admin can download compliance results as CSV with employee, job code, expected/actual roles, violation type, and severity columns
  4. Warehouse sync failures display a human-readable error message instead of a stack trace or blank screen
  5. Admin UI shows the timestamp of the last successful warehouse sync with a manual re-sync trigger button
**Plans**: TBD
**UI hint**: yes

### Phase 8: Reporting
**Goal**: Admins have a dedicated Reports section with license utilization, security posture, and Genesys agent status — all cached and schedulable
**Depends on**: Phase 5, Phase 6
**Requirements**: REPT-01, REPT-02, REPT-03, REPT-04, REPT-05, REPT-06, REPT-07, REPT-08
**Success Criteria** (what must be TRUE):
  1. Admin can view a license dashboard showing all M365 SKUs with assigned/available counts and unused license flags (no sign-in 30+ days)
  2. Admin can view MFA adoption rate as a percentage and a list of users without MFA configured
  3. Admin can view a failed sign-in table filterable by date range showing user, timestamp, failure reason, and IP
  4. Genesys section shows current presence, routing status, and queue memberships for Genesys-enabled users
  5. Admin can create, edit, and delete report schedules (daily/weekly/monthly) with a history view of past runs
  6. Report data is served from cache (4h licenses, 1h security, 5min Genesys) — a stale-cache indicator is visible
**Plans**: TBD
**UI hint**: yes

### Phase 9: Write Operations
**Goal**: Editors and admins can act on search results — unlocking accounts, resetting passwords, toggling AD account state, and managing licenses — with every action confirmed, audited, and reversible-by-audit-trail
**Depends on**: Phase 2 (tests), Phase 4 (Keycloak roles), Phase 5 (Alembic for new audit columns), Phase 6
**Requirements**: WRIT-01, WRIT-02, WRIT-03, WRIT-04, WRIT-05, WRIT-06, WRIT-07, WRIT-08
**Success Criteria** (what must be TRUE):
  1. Editor can unlock a locked AD account, reset a password (shown once), or enable/disable an account directly from the search result view
  2. Every write action presents a confirmation modal requiring a typed reason before proceeding — the action does not fire without it
  3. Every write action (AD or license) creates an audit log entry with who, what, to whom, when, IP address, and the typed reason
  4. Admin can assign or remove an M365 license from the profile view with confirmation
  5. License swap (remove old SKU, assign new SKU) executes as an atomic operation — partial state is not left if one step fails
**Plans**: TBD
**UI hint**: yes

### Phase 10: REST API
**Goal**: External systems and automation can query WhoDis via a documented, rate-limited, token-authenticated API without touching the web UI
**Depends on**: Phase 2, Phase 4 (Keycloak token validation co-exists with API tokens), Phase 6
**Requirements**: API-01, API-02, API-03, API-04, API-05, API-06
**Success Criteria** (what must be TRUE):
  1. Admin can create, view, and revoke API tokens from the admin UI using the existing ApiToken model
  2. External caller can search users via `GET /api/v1/search?q=` and retrieve a full profile via `GET /api/v1/user/{email}` using a bearer token
  3. Every API call is logged to the audit trail with the token ID, endpoint, and result status
  4. Rate limit is enforced per token — exceeding the limit returns 429 with a Retry-After header
  5. OpenAPI spec is accessible at `/api/v1/docs` without authentication

### Phase 11: Workflow Automation
**Goal**: Admins can generate onboarding and offboarding checklists from job role mappings, track each item's completion, and see active workflows on a dashboard
**Depends on**: Phase 7, Phase 9
**Requirements**: WKFL-01, WKFL-02, WKFL-03, WKFL-04
**Success Criteria** (what must be TRUE):
  1. Admin can select a job code and generate an onboarding checklist pre-populated from job role compliance mappings
  2. Admin can generate an offboarding checklist that mirrors and reverses all provisioning steps from onboarding
  3. Each checklist item records who completed it and when — the audit trail is queryable
  4. A workflow dashboard shows all active checklists with per-item progress and highlights overdue items
**Plans**: TBD
**UI hint**: yes

## Progress Table

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation | 9/9 | Complete | 2026-04-25 |
| 2. Test Suite | 4/4 | Complete | 2026-04-25 |
| 3. SandCastle Containerization & Deployment | 0/3 | In progress | - |
| 4. Keycloak OIDC Authentication | 0/? | Not started | - |
| 5. Database Migration & Alembic | 0/? | Not started | - |
| 6. Enriched Profiles & Search Export | 0/? | Not started | - |
| 7. Compliance Polish | 0/? | Not started | - |
| 8. Reporting | 0/? | Not started | - |
| 9. Write Operations | 0/? | Not started | - |
| 10. REST API | 0/? | Not started | - |
| 11. Workflow Automation | 0/? | Not started | - |

## Backlog

*(Empty — backlog item 999.1 "Swap Flask-Limiter storage to Redis" was promoted into Phase 3 success criterion 2 during the 2026-04-24 revision.)*

---
*Roadmap defined: 2026-04-24*
*Last updated: 2026-04-24 — SandCastle integration insertion + re-prioritization (3 new phases inserted at positions 3-5; original Phases 3-8 renumbered to 6-11)*
*Revised: 2026-04-26 — Phase 3 plans finalized (3 gap-closure plans: 03-01 Redis, 03-02 DATABASE_URL, 03-03 README+ops)*
