# Who-Dis SandCastle Integration Requirements

Requirements for onboarding Who-Dis as a hosted application on the SandCastle platform.
Each requirement is falsifiable and maps to a SandCastle platform constraint.

**Target platform host:** `whodis.sandcastle.ttcu.com`
**Standard stack reference:** `C:\repos\sandcastle-portal\CLAUDE.md`

---

## Containerization

- **WD-CONT-01** — A `Dockerfile` exists at the repo root that builds a runnable image of the Flask app on `python:3.12-slim`. The image runs as a non-root user.
- **WD-CONT-02** — The app is served by `gunicorn` (not `flask run` / `werkzeug`) with a configurable worker count via `GUNICORN_WORKERS` env var (default 2).
- **WD-CONT-03** — The Dockerfile installs only what is needed for production runtime (no dev tools, no test deps); image size under 500 MB.
- **WD-CONT-04** — A `docker-compose.sandcastle.yml` exists at the repo root with the service definition, Traefik labels, and connections to the `proxy` and `internal` networks.
- **WD-CONT-05** — The container starts cleanly with `docker compose up` against a populated `.env` and serves traffic on port 5000 inside the container.

## Configuration

- **WD-CFG-01** — All runtime configuration is read from environment variables. No values are hardcoded in source. No values are read from `instance/`, `config.py`, or `*.json` config files baked into the image.
- **WD-CFG-02** — `DATABASE_URL` (PostgreSQL DSN) replaces any current connection-string composition logic. The app connects only via this URL.
- **WD-CFG-03** — Secrets currently held by the encrypted-config system are exposed via env vars instead (or the encrypted-config system reads its master key from an env var injected by the SandCastle portal).
- **WD-CFG-04** — `FLASK_ENV=production` and `DEBUG` is forced false in the container. Debug-mode toggling via the database remains available but defaults to off.
- **WD-CFG-05** — A `.env.sandcastle.example` file documents every required environment variable with comments.

## Authentication

- **WD-AUTH-01** — `app/middleware/authentication_handler.py` no longer reads `X-MS-CLIENT-PRINCIPAL-NAME`. User identity comes from a Keycloak OIDC session.
- **WD-AUTH-02** — A new auth integration uses an OIDC library (e.g., `authlib`, `flask-oidc`, or hand-rolled with `python-jose`) configured against the SandCastle Keycloak realm `sandcastle`.
- **WD-AUTH-03** — A Keycloak OIDC client `whodis` exists in the `sandcastle` realm with redirect URI `https://whodis.sandcastle.ttcu.com/*` and post-logout redirect `https://whodis.sandcastle.ttcu.com/`.
- **WD-AUTH-04** — Unauthenticated requests to any non-public route are redirected to Keycloak; on successful auth the user lands back at the originally requested URL.
- **WD-AUTH-05** — `g.user` (email) and `g.role` are populated from the Keycloak ID token claims (`email`, `realm_access.roles`). Existing role-check decorators continue to work unchanged.
- **WD-AUTH-06** — Existing local-DB user records are matched by email; first-time SSO arrivals provision a record automatically with default role.
- **WD-AUTH-07** — Logout terminates both the Flask session and the Keycloak session (RP-initiated logout).
- **WD-AUTH-08** — All references to "Azure AD basic auth", `X-MS-CLIENT-PRINCIPAL-*` headers, and Easy Auth assumptions are removed from the codebase.

## Database

- **WD-DB-01** — App runs against a dedicated PostgreSQL database on the shared SandCastle instance, provisioned via the portal's `scripts/provision-db.sh whodis`.
- **WD-DB-02** — Schema is applied via Alembic (or equivalent migration tool) on container start, not via a manual `psql` step.
- **WD-DB-03** — A documented one-time data migration path exists to move data from the current Who-Dis database to the SandCastle Postgres instance.
- **WD-DB-04** — Connection pool is configured for a containerized environment (e.g., `pool_size=5`, `pool_pre_ping=True`).
- **WD-DB-05** — `database/create_tables.sql` and `database/analyze_tables.sql` are either replaced by Alembic migrations or invoked automatically on first run.

## Health & Observability

- **WD-HEALTH-01** — `GET /health` returns HTTP 200 with JSON `{"status": "healthy"}` and does not require authentication. Used by the SandCastle portal poller.
- **WD-HEALTH-02** — `GET /health/ready` returns HTTP 200 only when the database is reachable; HTTP 503 otherwise.
- **WD-HEALTH-03** — Application logs are written to stdout/stderr in a structured (JSON) format compatible with `docker logs`. No file logging in container mode.
- **WD-HEALTH-04** — The Docker `HEALTHCHECK` directive in the Dockerfile hits `/health` every 30 s with a 10 s timeout.

## Networking & Routing

- **WD-NET-01** — The compose service is on the `proxy` external network for Traefik routing and the `internal` network for Postgres/Redis access.
- **WD-NET-02** — Traefik labels route `whodis.sandcastle.ttcu.com` traffic to port 5000 with `certResolver=letsencrypt` and HTTPS-only.
- **WD-NET-03** — Outbound calls to Microsoft Graph and Genesys Cloud APIs continue to work from inside the container (no special outbound rules required beyond standard egress).
- **WD-NET-04** — The Flask app honors `X-Forwarded-Proto` and `X-Forwarded-Host` (e.g., via `werkzeug.middleware.proxy_fix.ProxyFix`) so URL generation is HTTPS-aware behind Traefik.
- **WD-NET-05** — Static assets (`/static/*`) are served correctly through the Traefik proxy. No assumption of being at a specific server-relative path.

## Deployment & Operations

- **WD-OPS-01** — The app is registered in the SandCastle portal catalog with framework `Flask`, GitHub repo URL, and the Traefik-routed URL.
- **WD-OPS-02** — Deploys triggered via the portal (manual or webhook) succeed end-to-end without manual intervention.
- **WD-OPS-03** — `docs/deployment.md` is updated to describe the SandCastle deployment path; legacy Azure App Service deployment notes are clearly marked as deprecated or removed.
- **WD-OPS-04** — A GitHub webhook endpoint is configured on the repo to call SandCastle's `/api/webhooks/github` for auto-deploy on `main` push.

## Documentation

- **WD-DOC-01** — `docs/sandcastle.md` exists describing: env var matrix, Keycloak OIDC setup, DB provisioning, deployment flow, and rollback procedure.
- **WD-DOC-02** — `README.md` "Deployment" section points at `docs/sandcastle.md` for the SandCastle path and notes that local development still works via `python run.py`.

---

## Out of scope for v1 integration

- Replacing PySide6 / desktop concerns (none in Who-Dis — pure web app)
- Changing core search functionality (Azure AD, Genesys Cloud lookups stay as-is)
- Multi-tenant data isolation (Who-Dis remains single-org)

## Dependencies on SandCastle platform

- Phase 6 (Production Wiring) complete — env var injection, webhook routing, alembic auto-migration ✅ being unblocked
- Keycloak `whodis` OIDC client created in `sandcastle` realm
- Postgres `whodis_db` provisioned via `provision-db.sh`
