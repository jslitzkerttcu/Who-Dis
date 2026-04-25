---
phase: 01-foundation
plan: 08
type: execute
wave: 2
depends_on: [01]
files_modified:
  - requirements.txt
  - app/__init__.py
  - app/container.py
  - app/blueprints/search/__init__.py
autonomous: true
requirements: [SEC-03]
must_haves:
  truths:
    - "/search and /api/search are limited to 30 requests per minute per authenticated user; the 31st request in a window returns HTTP 429 with a Retry-After header"
    - "Limits aggregate across gunicorn workers via Flask-Limiter's PostgreSQL storage backend"
    - "Admin endpoints and /health remain unlimited"
    - "When g.user is unset (pre-auth), the limiter falls back to the remote IP address as the key"
  artifacts:
    - path: "app/__init__.py"
      provides: "Flask-Limiter initialized with PostgreSQL storage_uri"
      contains: "Limiter"
    - path: "app/blueprints/search/__init__.py"
      provides: "@limiter.limit('30/minute', key_func=...) on /search and /api/search"
      contains: "30/minute"
  key_links:
    - from: "app/__init__.py"
      to: "PostgreSQL via SQLALCHEMY_DATABASE_URI"
      via: "storage_uri argument"
      pattern: "storage_uri"
    - from: "app/blueprints/search/__init__.py"
      to: "limiter from container"
      via: "from app import limiter (or container.get('limiter'))"
      pattern: "limiter.limit"
---

<objective>
Add per-user rate limiting to search endpoints so a runaway client cannot hammer LDAP/Graph/Genesys. Satisfies SEC-03.

Purpose: Search endpoints fan out to three external APIs per request — abuse drains rate budgets and slows everyone. 30/min per user is generous for a 4-5 person team and tight enough to stop a buggy script.
Output: Flask-Limiter dependency added, initialized with PostgreSQL storage, decorator applied to search routes only.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/01-foundation/01-CONTEXT.md
@.planning/phases/01-foundation/01-PATTERNS.md
@CLAUDE.md
@app/__init__.py
@app/container.py
@app/blueprints/search/__init__.py
@requirements.txt
</context>

<tasks>

<task type="auto">
  <name>Task 1: Install Flask-Limiter + initialize with PostgreSQL storage</name>
  <read_first>
    - requirements.txt (existing pinning style — model the new entry on it)
    - app/__init__.py (find where SQLALCHEMY_DATABASE_URI is set; the limiter must initialize AFTER that)
    - PATTERNS.md "Limiter init in app/__init__.py" excerpt (lines 433–447)
    - app/container.py (location for `container.register("limiter", ...)`)
  </read_first>
  <action>
    Per D-08 + PATTERNS.md:

    1. Add to `requirements.txt`: `Flask-Limiter>=3.5,<4` (pinned in line with neighboring entries — match the formatting used by `Flask-WTF` and `Flask-SQLAlchemy`).
    2. Verify Flask-Limiter's PostgreSQL storage backend has no required schema migration. Flask-Limiter creates its counter table automatically on first use (verify against the library's docs at install time). If a manual table creation step IS required by the installed version, add the SQL to `database/create_tables.sql` and document it in this plan's SUMMARY.
    3. In `app/__init__.py`, add a module-level `limiter` instance so it can be imported by route modules:
       ```python
       from flask_limiter import Limiter
       from flask_limiter.util import get_remote_address

       limiter = Limiter(key_func=get_remote_address)  # default key_func; route-level decorators override
       ```
    4. Inside `create_app()` after `SQLALCHEMY_DATABASE_URI` is configured (read app/__init__.py to find the exact line) AND after `db.init_app(app)`, initialize the limiter against the same PostgreSQL URI:
       ```python
       limiter.init_app(app)
       limiter.storage_uri = app.config["SQLALCHEMY_DATABASE_URI"]
       ```
       (If the installed Flask-Limiter version requires `storage_uri` at construction time rather than after, set it on the constructor instead and re-instantiate inside `create_app()`. Pick the form supported by the pinned version; the inner mechanic does not matter to consumers.)
    5. Register in container per PATTERNS.md:
       ```python
       container.register("limiter", lambda c: limiter)
       ```
       in `app/container.py:register_services()`.
    6. Smoke test: `python -c "from app import create_app, limiter; app=create_app()"` exits 0.
  </action>
  <verify>
    <automated>grep -q 'Flask-Limiter' requirements.txt &amp;&amp; grep -q 'from flask_limiter import Limiter' app/__init__.py &amp;&amp; grep -q 'limiter.init_app(app)' app/__init__.py &amp;&amp; grep -q '"limiter"' app/container.py &amp;&amp; python -c 'from app import create_app, limiter; app=create_app(); assert limiter is not None'</automated>
  </verify>
  <acceptance_criteria>
    - `grep -n "Flask-Limiter" requirements.txt` matches with a pinned version
    - `grep -n "from flask_limiter import Limiter" app/__init__.py` matches
    - `grep -n "limiter.init_app(app)" app/__init__.py` matches
    - `grep -n "limiter" app/container.py` matches at least once (registered)
    - `python -c "from app import create_app, limiter; app=create_app()"` exits 0
    - `app.test_client().get("/health/live")` still works (health endpoints unaffected)
  </acceptance_criteria>
  <done>Limiter is wired with PostgreSQL storage; importable as `from app import limiter`.</done>
</task>

<task type="auto">
  <name>Task 2: Apply 30/minute limit to /search and /api/search</name>
  <read_first>
    - app/blueprints/search/__init__.py (find /search and /api/search routes — confirm decorator stack)
    - PATTERNS.md "app/blueprints/search/__init__.py modification" section
    - app/middleware/auth.py (confirm @auth_required runs AFTER the limiter and sets g.user)
  </read_first>
  <action>
    Per D-09 / D-10:

    1. In `app/blueprints/search/__init__.py`, import the limiter and `get_remote_address`:
       ```python
       from flask import g
       from flask_limiter.util import get_remote_address
       from app import limiter
       ```
    2. Define a key function that prefers the authenticated user but falls back to remote address (the limiter decorator runs BEFORE `@auth_required` so `g.user` may not be set yet — per PATTERNS.md NOTE):
       ```python
       def _search_rate_key():
           return getattr(g, "user", None) or get_remote_address()
       ```
    3. Apply to BOTH `/search` and `/api/search` routes — decorator placed ABOVE `@auth_required` so the limiter check runs first:
       ```python
       @search_bp.route("/", methods=["GET", "POST"])
       @limiter.limit("30/minute", key_func=_search_rate_key)
       @auth_required
       @require_role("viewer")
       def search():
           ...

       @search_bp.route("/api/search", methods=["GET", "POST"])
       @limiter.limit("30/minute", key_func=_search_rate_key)
       @auth_required
       @require_role("viewer")
       def api_search():
           ...
       ```
       (Use the actual route paths/method lists already in the file; only add the limiter decorator — do not change any other decorator or signature.)
    4. Do NOT apply the limiter to admin routes, health endpoints, or session endpoints (per D-10 "admin endpoints remain unlimited").
    5. Confirm Flask-Limiter's default 429 response includes a `Retry-After` header. If the installed version does not by default, set `app.config["RATELIMIT_HEADERS_ENABLED"] = True` next to the `limiter.init_app(app)` call.
  </action>
  <verify>
    <automated>grep -q '30/minute' app/blueprints/search/__init__.py &amp;&amp; grep -q '_search_rate_key' app/blueprints/search/__init__.py &amp;&amp; grep -q 'limiter.limit' app/blueprints/search/__init__.py &amp;&amp; ! grep -q 'limiter.limit' app/blueprints/admin/__init__.py</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "@limiter.limit" app/blueprints/search/__init__.py` returns at least 2 (search + api_search)
    - `grep -n "30/minute" app/blueprints/search/__init__.py` matches
    - `grep -n "_search_rate_key" app/blueprints/search/__init__.py` matches and the function is defined in the same module
    - `grep -n "limiter.limit" app/blueprints/admin/__init__.py` returns NO matches (admin unlimited per D-10)
    - Functional check: 31 rapid GETs to `/search` from the same authenticated user produce a 429 with a `Retry-After` header on request 31
    - App boots: `python -c "from app import create_app; create_app()"` exits 0
  </acceptance_criteria>
  <done>Search endpoints rate-limited per user; admin and health unaffected; 429 response includes Retry-After.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| browser → /search | Authenticated user can fan out to 3 external APIs per request |
| Flask-Limiter → PostgreSQL | Counter table writes per request |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-01-08-01 | Denial of Service | Search endpoint flood | mitigate | 30/min per authenticated user — generous for human use, restrictive for runaway scripts. Limits aggregate across workers via PostgreSQL storage so multi-process abuse cannot bypass the cap. |
| T-01-08-02 | Spoofing | Pre-auth IP key | mitigate | When g.user is unset (request reaches limiter before @auth_required completes), key falls back to `get_remote_address()`. Spoofed `X-Forwarded-For` is the operator's reverse proxy concern — Flask-Limiter respects whatever address Flask `request.remote_addr` reports. |
| T-01-08-03 | Information Disclosure | 429 response body | mitigate | Default Flask-Limiter 429 body contains the limit name only ("30 per 1 minute") — no user identity disclosed. `Retry-After` header is the only timing disclosure (intentional for client-side backoff). |
| T-01-08-04 | Denial of Service | Limiter storage exhaustion | accept | PostgreSQL counter table grows linearly with active users × time-window; with ≤5 users it cannot grow large. Re-evaluate if user count > 100. |
</threat_model>

<verification>
- `requirements.txt` lists `Flask-Limiter>=3.5,<4`
- App boots; `pip show flask-limiter` reports the installed version
- 31 rapid requests to `/search` from one user → request 31 returns 429 with `Retry-After`
- 31 rapid requests to `/admin/audit-logs` from same user → all succeed (admin unlimited)
- Cold-start request to `/search` succeeds (PostgreSQL counter table auto-created on first use)
</verification>

<success_criteria>
SEC-03 acceptance criterion satisfied: search endpoint has per-user rate limiting to prevent abuse.
</success_criteria>

<output>
After completion, create `.planning/phases/01-foundation/01-08-SUMMARY.md`.
</output>
