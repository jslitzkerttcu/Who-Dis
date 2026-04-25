# Requirements: WhoDis v3.0

**Defined:** 2026-04-24
**Revised:** 2026-04-24 (added 38 SandCastle integration requirements across 8 categories)
**Core Value:** IT staff can find everything about any employee and act on it from a single interface

## v1 Requirements

Requirements for this milestone. Each maps to roadmap phases.

### Testing

- [x] **TEST-01**: Developer can run `pytest tests/ -v` and get passing unit tests for all service classes
- [x] **TEST-02**: External APIs (LDAP, Graph, Genesys) are mocked at container level in test fixtures
- [x] **TEST-03**: Integration tests verify authentication middleware pipeline and search flow end-to-end
- [x] **TEST-04**: Coverage report generated with `pytest --cov=app` showing 60%+ on services and middleware

### Profile Data

- [ ] **PROF-01**: User can see department, manager, employee ID, assigned licenses, and last sign-in date from Graph API on profile card
- [ ] **PROF-02**: User can see MFA status and authentication methods from Graph API on profile card
- [ ] **PROF-03**: User can see Genesys queues, skills with proficiency levels, and current presence on profile card
- [ ] **PROF-04**: Extended data renders in collapsible sections that don't clutter the default view
- [ ] **PROF-05**: Expensive fields (sign-in activity, licenses) load asynchronously via HTMX after initial render
- [ ] **PROF-06**: Result merger handles missing fields gracefully without errors

### Search Export

- [ ] **SRCH-01**: User can click "Copy to Clipboard" to copy a structured text summary of displayed user data
- [ ] **SRCH-02**: User can click "Export CSV" to download all displayed fields with data source attribution

### Compliance

- [ ] **COMP-01**: Admin can see real-time progress during bulk compliance checks via HTMX polling
- [ ] **COMP-02**: Admin can sort violations by severity (critical > high > medium > low)
- [ ] **COMP-03**: Admin can export compliance results as CSV (employee, job code, expected/actual roles, violation type, severity)
- [ ] **COMP-04**: Warehouse sync failures display clear user-facing error messages instead of stack traces
- [ ] **COMP-05**: Admin UI shows when warehouse data was last synced with manual sync trigger

### Reporting

- [ ] **REPT-01**: Admin can view license utilization dashboard showing all M365 SKUs with assigned/available/consumed counts
- [ ] **REPT-02**: Dashboard highlights unused licenses (assigned but no sign-in in 30+ days) with utilization percentage per SKU
- [ ] **REPT-03**: Admin can view MFA adoption rate as percentage with list of non-MFA users
- [ ] **REPT-04**: Admin can view failed sign-in table with user, timestamp, failure reason, IP/location filterable by date range
- [ ] **REPT-05**: Contact center section shows current Genesys presence, routing status, and queue memberships for Genesys-enabled users
- [ ] **REPT-06**: Admin can create/edit/delete report schedules with daily/weekly/monthly presets
- [ ] **REPT-07**: Reports generate on schedule using background thread infrastructure with history view
- [ ] **REPT-08**: Report data cached with configurable TTL (4h licenses, 1h security, 5min Genesys status)

### Write Operations

- [ ] **WRIT-01**: Editor can unlock a locked AD account from the search result view
- [ ] **WRIT-02**: Editor can reset an AD password generating a temporary password displayed once
- [ ] **WRIT-03**: Editor can enable/disable AD accounts from the search result view
- [ ] **WRIT-04**: All write actions require confirmation modal with mandatory reason text
- [ ] **WRIT-05**: Every write action is logged to audit trail with full context (who, what, to whom, when, where, reason)
- [ ] **WRIT-06**: Admin can assign a license to a user from the profile view
- [ ] **WRIT-07**: Admin can remove a license with confirmation
- [ ] **WRIT-08**: License swap (remove old, assign new) supported as atomic operation

### API

- [ ] **API-01**: Admin can create and manage API tokens via admin UI
- [ ] **API-02**: External system can search users via `GET /api/v1/search?q=...` returning JSON
- [ ] **API-03**: External system can retrieve full user profile via `GET /api/v1/user/{email}`
- [ ] **API-04**: All API calls logged to audit trail with token identification
- [ ] **API-05**: Rate limiting prevents abuse with configurable per-token limits
- [ ] **API-06**: OpenAPI spec available at `/api/v1/docs`

### Workflow

- [ ] **WKFL-01**: Admin can generate onboarding checklist from job role mappings for a given job code
- [ ] **WKFL-02**: Admin can generate offboarding checklist that reverses all provisions
- [ ] **WKFL-03**: Each checklist item tracks completion status (who completed, when)
- [ ] **WKFL-04**: Dashboard shows active workflows with progress and overdue items

### Operational Hardening

- [x] **OPS-01**: Application exposes `/health` endpoint returning JSON status with database connectivity check
- [x] **OPS-02**: Every request gets a unique request ID propagated through all logs and async tasks
- [x] **OPS-03**: Application validates required configuration values at startup with clear error messages
- [x] **OPS-04**: Admin list views paginate tables with 100+ rows using offset/limit pattern

### Security Hardening

- [ ] **SEC-01**: `.whodis_salt` file removed from git history and properly gitignored
- [ ] **SEC-02**: CLI tool exists for safe encryption key rotation with dual-key migration and verification
- [x] **SEC-03**: Search endpoint has per-user rate limiting to prevent abuse
- [x] **SEC-04**: Authentication header validation configurable for non-Azure environments

### Tech Debt

- [x] **DEBT-01**: Single application initialization path (consolidate `__init__.py` and `app_factory.py`)
- [x] **DEBT-02**: Deprecated `DataWarehouseService` removed, logic consolidated into `EmployeeProfilesRefreshService`
- [x] **DEBT-03**: Scheduled cleanup job removes expired search cache entries
- [x] **DEBT-04**: Asyncio patterns updated for Python 3.10+ compatibility (`get_running_loop`, `Runner`)

### SandCastle — Containerization

- [ ] **WD-CONT-01**: A `Dockerfile` exists at the repo root that builds a runnable image of the Flask app on `python:3.12-slim`. The image runs as a non-root user.
- [ ] **WD-CONT-02**: The app is served by `gunicorn` (not `flask run` / `werkzeug`) with a configurable worker count via `GUNICORN_WORKERS` env var (default 2).
- [ ] **WD-CONT-03**: The Dockerfile installs only what is needed for production runtime (no dev tools, no test deps); image size under 500 MB.
- [ ] **WD-CONT-04**: A `docker-compose.sandcastle.yml` exists at the repo root with the service definition, Traefik labels, and connections to the `proxy` and `internal` networks.
- [ ] **WD-CONT-05**: The container starts cleanly with `docker compose up` against a populated `.env` and serves traffic on port 5000 inside the container.

### SandCastle — Configuration

- [ ] **WD-CFG-01**: All runtime configuration is read from environment variables. No values are hardcoded in source. No values are read from `instance/`, `config.py`, or `*.json` config files baked into the image.
- [ ] **WD-CFG-02**: `DATABASE_URL` (PostgreSQL DSN) replaces any current connection-string composition logic. The app connects only via this URL.
- [ ] **WD-CFG-03**: Secrets currently held by the encrypted-config system are exposed via env vars instead (or the encrypted-config system reads its master key from an env var injected by the SandCastle portal).
- [ ] **WD-CFG-04**: `FLASK_ENV=production` and `DEBUG` is forced false in the container. Debug-mode toggling via the database remains available but defaults to off.
- [ ] **WD-CFG-05**: A `.env.sandcastle.example` file documents every required environment variable with comments.

### SandCastle — Authentication (Keycloak OIDC)

- [ ] **WD-AUTH-01**: `app/middleware/authentication_handler.py` no longer reads `X-MS-CLIENT-PRINCIPAL-NAME`. User identity comes from a Keycloak OIDC session.
- [ ] **WD-AUTH-02**: A new auth integration uses an OIDC library (e.g., `authlib`, `flask-oidc`, or hand-rolled with `python-jose`) configured against the SandCastle Keycloak realm `sandcastle`.
- [ ] **WD-AUTH-03**: A Keycloak OIDC client `whodis` exists in the `sandcastle` realm with redirect URI `https://whodis.sandcastle.ttcu.com/*` and post-logout redirect `https://whodis.sandcastle.ttcu.com/`.
- [ ] **WD-AUTH-04**: Unauthenticated requests to any non-public route are redirected to Keycloak; on successful auth the user lands back at the originally requested URL.
- [ ] **WD-AUTH-05**: `g.user` (email) and `g.role` are populated from the Keycloak ID token claims (`email`, `realm_access.roles`). Existing role-check decorators continue to work unchanged.
- [ ] **WD-AUTH-06**: Existing local-DB user records are matched by email; first-time SSO arrivals provision a record automatically with default role.
- [ ] **WD-AUTH-07**: Logout terminates both the Flask session and the Keycloak session (RP-initiated logout).
- [ ] **WD-AUTH-08**: All references to "Azure AD basic auth", `X-MS-CLIENT-PRINCIPAL-*` headers, and Easy Auth assumptions are removed from the codebase.

### SandCastle — Database

- [ ] **WD-DB-01**: App runs against a dedicated PostgreSQL database on the shared SandCastle instance, provisioned via the portal's `scripts/provision-db.sh whodis`.
- [ ] **WD-DB-02**: Schema is applied via Alembic (or equivalent migration tool) on container start, not via a manual `psql` step.
- [ ] **WD-DB-03**: A documented one-time data migration path exists to move data from the current Who-Dis database to the SandCastle Postgres instance.
- [ ] **WD-DB-04**: Connection pool is configured for a containerized environment (e.g., `pool_size=5`, `pool_pre_ping=True`).
- [ ] **WD-DB-05**: `database/create_tables.sql` and `database/analyze_tables.sql` are either replaced by Alembic migrations or invoked automatically on first run.

### SandCastle — Health & Observability

- [ ] **WD-HEALTH-01**: `GET /health` returns HTTP 200 with JSON `{"status": "healthy"}` and does not require authentication. Used by the SandCastle portal poller.
- [ ] **WD-HEALTH-02**: `GET /health/ready` returns HTTP 200 only when the database is reachable; HTTP 503 otherwise.
- [ ] **WD-HEALTH-03**: Application logs are written to stdout/stderr in a structured (JSON) format compatible with `docker logs`. No file logging in container mode.
- [ ] **WD-HEALTH-04**: The Docker `HEALTHCHECK` directive in the Dockerfile hits `/health` every 30 s with a 10 s timeout.

### SandCastle — Networking & Routing

- [ ] **WD-NET-01**: The compose service is on the `proxy` external network for Traefik routing and the `internal` network for Postgres/Redis access.
- [ ] **WD-NET-02**: Traefik labels route `whodis.sandcastle.ttcu.com` traffic to port 5000 with `certResolver=letsencrypt` and HTTPS-only.
- [ ] **WD-NET-03**: Outbound calls to Microsoft Graph and Genesys Cloud APIs continue to work from inside the container (no special outbound rules required beyond standard egress).
- [ ] **WD-NET-04**: The Flask app honors `X-Forwarded-Proto` and `X-Forwarded-Host` (e.g., via `werkzeug.middleware.proxy_fix.ProxyFix`) so URL generation is HTTPS-aware behind Traefik.
- [ ] **WD-NET-05**: Static assets (`/static/*`) are served correctly through the Traefik proxy. No assumption of being at a specific server-relative path.

### SandCastle — Deployment & Operations

- [ ] **WD-OPS-01**: The app is registered in the SandCastle portal catalog with framework `Flask`, GitHub repo URL, and the Traefik-routed URL.
- [ ] **WD-OPS-02**: Deploys triggered via the portal (manual or webhook) succeed end-to-end without manual intervention.
- [ ] **WD-OPS-03**: `docs/deployment.md` is updated to describe the SandCastle deployment path; legacy Azure App Service deployment notes are clearly marked as deprecated or removed.
- [ ] **WD-OPS-04**: A GitHub webhook endpoint is configured on the repo to call SandCastle's `/api/webhooks/github` for auto-deploy on `main` push.

### SandCastle — Documentation

- [ ] **WD-DOC-01**: `docs/sandcastle.md` exists describing: env var matrix, Keycloak OIDC setup, DB provisioning, deployment flow, and rollback procedure.
- [ ] **WD-DOC-02**: `README.md` "Deployment" section points at `docs/sandcastle.md` for the SandCastle path and notes that local development still works via `python run.py`.

## v2 Requirements

Deferred to future milestone. Tracked but not in current roadmap.

### CI/CD

- **CI-01**: GitHub Actions CI workflow runs tests on every PR and blocks merge on failure
- **CI-02**: Automated deployment pipeline to Azure App Service

### Advanced Reporting

- **ARPT-01**: Email/Exchange mailbox analytics and mail flow reporting
- **ARPT-02**: Teams usage reports with call logs and membership tracking
- **ARPT-03**: SharePoint/OneDrive storage and activity reporting

### Advanced Automation

- **AUTO-01**: Onboarding checklist items auto-execute AD actions and license assignments
- **AUTO-02**: Self-service portal for common IT requests

## Out of Scope

| Feature | Reason |
|---------|--------|
| Real-time chat integration | Not core to identity/operations mission |
| Mobile native app | Web responsive design sufficient for 4-5 user team |
| AI/ML features | Premature for current user base and scale |
| HR system integration | No HR API access available |
| Ticketing system integration | Requires ITSM vendor commitment not in place |
| Multi-tenant support | Single-organization deployment only |
| PowerBI/analytics embedding | Adds complexity without clear ROI for team size |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| DEBT-01 | Phase 1 | Complete |
| DEBT-02 | Phase 1 | Complete |
| DEBT-03 | Phase 1 | Complete |
| DEBT-04 | Phase 1 | Complete |
| OPS-01 | Phase 1 | Complete |
| OPS-02 | Phase 1 | Complete |
| OPS-03 | Phase 1 | Complete |
| OPS-04 | Phase 1 | Complete |
| SEC-01 | Phase 1 | Partial (D-01 deviation) |
| SEC-02 | Phase 1 | Complete |
| SEC-03 | Phase 1 | Complete |
| SEC-04 | Phase 1 | Complete |
| TEST-01 | Phase 2 | Complete |
| TEST-02 | Phase 2 | Complete |
| TEST-03 | Phase 2 | Complete |
| TEST-04 | Phase 2 | Complete |
| WD-CONT-01 | Phase 3 | Pending |
| WD-CONT-02 | Phase 3 | Pending |
| WD-CONT-03 | Phase 3 | Pending |
| WD-CONT-04 | Phase 3 | Pending |
| WD-CONT-05 | Phase 3 | Pending |
| WD-CFG-01 | Phase 3 | Pending |
| WD-CFG-02 | Phase 3 | Pending |
| WD-CFG-03 | Phase 3 | Pending |
| WD-CFG-04 | Phase 3 | Pending |
| WD-CFG-05 | Phase 3 | Pending |
| WD-HEALTH-01 | Phase 3 | Pending |
| WD-HEALTH-02 | Phase 3 | Pending |
| WD-HEALTH-03 | Phase 3 | Pending |
| WD-HEALTH-04 | Phase 3 | Pending |
| WD-NET-01 | Phase 3 | Pending |
| WD-NET-02 | Phase 3 | Pending |
| WD-NET-03 | Phase 3 | Pending |
| WD-NET-04 | Phase 3 | Pending |
| WD-NET-05 | Phase 3 | Pending |
| WD-OPS-01 | Phase 3 | Pending |
| WD-OPS-02 | Phase 3 | Pending |
| WD-OPS-03 | Phase 3 | Pending |
| WD-OPS-04 | Phase 3 | Pending |
| WD-DOC-01 | Phase 3 | Pending |
| WD-DOC-02 | Phase 3 | Pending |
| WD-AUTH-01 | Phase 4 | Pending |
| WD-AUTH-02 | Phase 4 | Pending |
| WD-AUTH-03 | Phase 4 | Pending |
| WD-AUTH-04 | Phase 4 | Pending |
| WD-AUTH-05 | Phase 4 | Pending |
| WD-AUTH-06 | Phase 4 | Pending |
| WD-AUTH-07 | Phase 4 | Pending |
| WD-AUTH-08 | Phase 4 | Pending |
| WD-DB-01 | Phase 5 | Pending |
| WD-DB-02 | Phase 5 | Pending |
| WD-DB-03 | Phase 5 | Pending |
| WD-DB-04 | Phase 5 | Pending |
| WD-DB-05 | Phase 5 | Pending |
| PROF-01 | Phase 6 | Pending |
| PROF-02 | Phase 6 | Pending |
| PROF-03 | Phase 6 | Pending |
| PROF-04 | Phase 6 | Pending |
| PROF-05 | Phase 6 | Pending |
| PROF-06 | Phase 6 | Pending |
| SRCH-01 | Phase 6 | Pending |
| SRCH-02 | Phase 6 | Pending |
| COMP-01 | Phase 7 | Pending |
| COMP-02 | Phase 7 | Pending |
| COMP-03 | Phase 7 | Pending |
| COMP-04 | Phase 7 | Pending |
| COMP-05 | Phase 7 | Pending |
| REPT-01 | Phase 8 | Pending |
| REPT-02 | Phase 8 | Pending |
| REPT-03 | Phase 8 | Pending |
| REPT-04 | Phase 8 | Pending |
| REPT-05 | Phase 8 | Pending |
| REPT-06 | Phase 8 | Pending |
| REPT-07 | Phase 8 | Pending |
| REPT-08 | Phase 8 | Pending |
| WRIT-01 | Phase 9 | Pending |
| WRIT-02 | Phase 9 | Pending |
| WRIT-03 | Phase 9 | Pending |
| WRIT-04 | Phase 9 | Pending |
| WRIT-05 | Phase 9 | Pending |
| WRIT-06 | Phase 9 | Pending |
| WRIT-07 | Phase 9 | Pending |
| WRIT-08 | Phase 9 | Pending |
| API-01 | Phase 10 | Pending |
| API-02 | Phase 10 | Pending |
| API-03 | Phase 10 | Pending |
| API-04 | Phase 10 | Pending |
| API-05 | Phase 10 | Pending |
| API-06 | Phase 10 | Pending |
| WKFL-01 | Phase 11 | Pending |
| WKFL-02 | Phase 11 | Pending |
| WKFL-03 | Phase 11 | Pending |
| WKFL-04 | Phase 11 | Pending |

**Coverage:**
- v1 requirements: 90 total (52 original + 38 SandCastle integration)
- Mapped to phases: 90
- Unmapped: 0

---
*Requirements defined: 2026-04-24*
*Last updated: 2026-04-24 — added 38 SandCastle integration requirements (WD-CONT/CFG/AUTH/DB/HEALTH/NET/OPS/DOC) and re-mapped traceability to revised 11-phase roadmap*
