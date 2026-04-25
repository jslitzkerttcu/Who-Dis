---
phase: 01-foundation
plan: 03
type: execute
wave: 2
depends_on: [01]
files_modified:
  - app/blueprints/health/__init__.py
  - app/__init__.py
autonomous: true
requirements: [OPS-01]
must_haves:
  truths:
    - "GET /health/live returns 200 with {\"status\": \"ok\"} without authentication and without touching the database"
    - "GET /health returns 200 with database connection info (latency_ms) when DB reachable, 503 when not"
    - "Both endpoints are unauthenticated — no @auth_required, no role check"
  artifacts:
    - path: "app/blueprints/health/__init__.py"
      provides: "health_bp blueprint with /health and /health/live routes"
      contains: "health_bp = Blueprint"
  key_links:
    - from: "app/__init__.py"
      to: "app/blueprints/health/__init__.py"
      via: "app.register_blueprint(health_bp)"
      pattern: "register_blueprint\\(health_bp"
---

<objective>
Add unauthenticated `/health` (deep DB probe) and `/health/live` (shallow liveness) endpoints for monitoring tooling. Satisfies OPS-01.

Purpose: External monitors (Azure App Service, uptime checks) need a probe that does not require Azure AD auth and exits fast.
Output: New `health` blueprint registered at root, two routes, no DB-write side effects.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/01-foundation/01-CONTEXT.md
@.planning/phases/01-foundation/01-PATTERNS.md
@CLAUDE.md
@app/blueprints/session/__init__.py
@app/blueprints/admin/database.py
@app/__init__.py
@app/utils/error_handler.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create health blueprint with /health and /health/live</name>
  <read_first>
    - app/blueprints/session/__init__.py (analog — smallest blueprint with @handle_errors(json_response=True) per PATTERNS.md)
    - app/blueprints/admin/database.py::database_health (existing DB probe — copy SELECT 1 + perf_counter pattern)
    - app/__init__.py (location for blueprint registration around lines 171–181)
  </read_first>
  <action>
    Per D-11 / D-12 / OPS-01:

    1. Create `app/blueprints/health/__init__.py`:
       ```python
       import logging
       import time
       from flask import Blueprint, jsonify, g
       from sqlalchemy import text
       from app.database import db
       from app.utils.error_handler import handle_errors

       logger = logging.getLogger(__name__)
       health_bp = Blueprint("health", __name__)

       APP_VERSION = "3.0.0-phase1"  # static for now; future phase wires from package metadata

       @health_bp.route("/health/live", methods=["GET"])
       @handle_errors(json_response=True)
       def liveness():
           return jsonify({"status": "ok"}), 200

       @health_bp.route("/health", methods=["GET"])
       @handle_errors(json_response=True)
       def health():
           start = time.perf_counter()
           try:
               db.session.execute(text("SELECT 1"))
               latency_ms = round((time.perf_counter() - start) * 1000, 2)
               return jsonify({
                   "status": "ok",
                   "database": {"connected": True, "latency_ms": latency_ms},
                   "version": APP_VERSION,
                   "request_id": getattr(g, "request_id", None),
               }), 200
           except Exception as exc:
               logger.error("Health check DB probe failed: %s", exc, exc_info=True)
               return jsonify({
                   "status": "degraded",
                   "database": {"connected": False, "error": str(exc)[:200]},
                   "version": APP_VERSION,
                   "request_id": getattr(g, "request_id", None),
               }), 503
       ```
    2. CRITICAL: Do NOT apply `@auth_required` or `@require_role(...)` to either route. Per D-11 both endpoints must be unauthenticated.
    3. CRITICAL: Do NOT call any LDAP/Graph/Genesys probes from `/health` per D-12.
    4. In `app/__init__.py`, register the blueprint near the existing `app.register_blueprint(...)` block (around lines 171–181 per PATTERNS.md):
       ```python
       from app.blueprints.health import health_bp
       app.register_blueprint(health_bp)  # No url_prefix — root paths /health and /health/live
       ```
       The auth middleware uses route-level decorators, not a global before_request that requires auth — confirm by reading `app/middleware/auth.py` that unauthenticated routes work without explicit allowlisting. If a global `before_request` does enforce auth, add `/health` and `/health/live` to its allow-list (see how `/api/session/check` is handled today).
  </action>
  <verify>
    <automated>grep -q 'health_bp = Blueprint' app/blueprints/health/__init__.py &amp;&amp; grep -q 'register_blueprint(health_bp)' app/__init__.py &amp;&amp; python -c 'from app import create_app; app=create_app(); c=app.test_client(); r=c.get(\"/health/live\"); assert r.status_code == 200, r.status_code; r2=c.get(\"/health\"); assert r2.status_code in (200, 503), r2.status_code'</automated>
  </verify>
  <acceptance_criteria>
    - `app/blueprints/health/__init__.py` exists and contains `health_bp = Blueprint("health", __name__)`
    - `grep -n "register_blueprint(health_bp)" app/__init__.py` matches
    - `grep -n "@auth_required" app/blueprints/health/__init__.py` returns NO matches (must be unauthenticated)
    - `app.test_client().get("/health/live")` returns status 200 with JSON `{"status": "ok"}`
    - `app.test_client().get("/health")` returns status 200 (DB up) or 503 (DB down) with JSON containing `database.connected` field
    - Both responses have `Content-Type: application/json`
  </acceptance_criteria>
  <done>Two unauthenticated health endpoints respond correctly; failing DB probe returns 503; monitoring-tool ready.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| public internet → /health, /health/live | Unauthenticated external probes |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-01-03-01 | Information Disclosure | /health response body | mitigate | Response includes only `connected: bool`, latency in ms, static version string, and request_id — no DSN, no credentials, no row counts; error messages truncated to 200 chars |
| T-01-03-02 | Denial of Service | Anonymous /health flood | accept | SELECT 1 is the cheapest possible query; rate limiting not applied to allow uptime monitors free access. SEC-03 limits search endpoints separately. |
| T-01-03-03 | Spoofing | /health/live returns "ok" without DB | accept | Liveness is intentionally trivial — only proves the Python process is up. /health is the deep check for monitors that want DB verification. |
</threat_model>

<verification>
- `curl -s http://localhost:5000/health/live` returns `{"status":"ok"}` with HTTP 200
- `curl -s http://localhost:5000/health` returns JSON with `database.connected=true` and HTTP 200 when DB up
- Stop PostgreSQL, repeat: `/health` returns HTTP 503 with `database.connected=false`
- Neither endpoint redirects to login
</verification>

<success_criteria>
OPS-01 acceptance criterion satisfied: `/health` endpoint returning JSON with database connectivity check, usable by monitoring tools without authentication.
</success_criteria>

<output>
After completion, create `.planning/phases/01-foundation/01-03-SUMMARY.md`.
</output>
