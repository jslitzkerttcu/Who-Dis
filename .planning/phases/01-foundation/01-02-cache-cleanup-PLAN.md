---
phase: 01-foundation
plan: 02
type: execute
wave: 2
depends_on: [01]
files_modified:
  - app/services/cache_cleanup_service.py
  - app/blueprints/admin/cache.py
  - app/blueprints/admin/__init__.py
  - app/templates/admin/_cache_actions.html
  - app/container.py
  - app/__init__.py
autonomous: true
requirements: [DEBT-03]
must_haves:
  truths:
    - "A background thread deletes SearchCache rows where expires_at < NOW() approximately every hour"
    - "Admin can click a 'Run now' button on the cache management page and see a feedback fragment with the count of removed rows"
    - "Every Run-now click writes an audit log entry with action='cache_cleanup_run'"
  artifacts:
    - path: "app/services/cache_cleanup_service.py"
      provides: "CacheCleanupService background thread with run_now() method"
      contains: "class CacheCleanupService"
    - path: "app/blueprints/admin/cache.py"
      provides: "cache_cleanup_run() route handler returning HTMX HTML fragment"
      contains: "def cache_cleanup_run"
    - path: "app/templates/admin/_cache_actions.html"
      provides: "New cache row with Run now button and result div"
      contains: "fa-broom"
  key_links:
    - from: "app/__init__.py"
      to: "app/services/cache_cleanup_service.py"
      via: "container.get('cache_cleanup').start() inside WERKZEUG_RUN_MAIN guard"
      pattern: "cache_cleanup.*start"
    - from: "app/templates/admin/_cache_actions.html"
      to: "app.api_cache_cleanup_run"
      via: "hx-post=url_for('admin.api_cache_cleanup_run')"
      pattern: "api_cache_cleanup_run"
---

<objective>
Add a scheduled cleanup job that removes expired `SearchCache` rows hourly, plus an admin "Run now" button to trigger it on demand. Satisfies DEBT-03.

Purpose: Stop unbounded growth of `search_cache` table; give admins a manual escape hatch when the thread is misbehaving.
Output: New background service following the token_refresh_service.py pattern, new admin route, new row in `_cache_actions.html`.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/01-foundation/01-CONTEXT.md
@.planning/phases/01-foundation/01-PATTERNS.md
@.planning/phases/01-foundation/01-UI-SPEC.md
@CLAUDE.md
@app/services/token_refresh_service.py
@app/blueprints/admin/database.py
@app/blueprints/admin/__init__.py
@app/blueprints/admin/cache.py
@app/templates/admin/_cache_actions.html
@app/container.py
@app/__init__.py
@app/models/search_cache.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: CacheCleanupService background thread</name>
  <read_first>
    - app/services/token_refresh_service.py (analog — copy lifecycle pattern verbatim per PATTERNS.md lines 36–66)
    - app/models/search_cache.py (confirm SearchCache.expires_at column name)
    - app/container.py (location for new registration)
    - app/__init__.py (location for startup wiring inside WERKZEUG_RUN_MAIN guard)
  </read_first>
  <action>
    Per D-13 / DEBT-03:

    1. Create `app/services/cache_cleanup_service.py`. Module-level: `import logging; logger = logging.getLogger(__name__)`.
    2. Define class `CacheCleanupService` with this exact shape (mirroring `TokenRefreshService`):
       - `__init__(self, container=None, app=None)` sets `self.container, self.app, self.is_running=False, self.thread=None, self.check_interval=3600`.
       - `def init_app(self, app: Flask) -> None: self.app = app`
       - `def start(self) -> None`: idempotent guard on `is_running`; spawn `threading.Thread(target=self._run, daemon=True)`; log `"Cache cleanup service started"`.
       - `def _run(self) -> None`: while `self.is_running`: try `with self.app.app_context(): self._cleanup()` except log error; `time.sleep(self.check_interval)`.
       - `def _cleanup(self) -> tuple[int, float]`: returns `(deleted_count, duration_ms)`. Implementation: `start = time.perf_counter(); from app.database import db; from app.models.search_cache import SearchCache; deleted = SearchCache.query.filter(SearchCache.expires_at < datetime.utcnow()).delete(synchronize_session=False); db.session.commit(); return deleted, (time.perf_counter() - start) * 1000`.
       - `def run_now(self) -> tuple[int, float]`: synchronous public wrapper that calls `self._cleanup()` inside the current app context (caller is the Flask request, so app context already exists). Returns `(deleted_count, duration_ms)`.
       - `def stop(self) -> None`: sets `is_running = False`.
    3. Register in `app/container.py` register_services(): `container.register("cache_cleanup", lambda c: CacheCleanupService(container))`.
    4. Wire startup in `app/__init__.py` next to the existing `token_refresh` block (around lines 110–115 per PATTERNS.md), inside the `if os.environ.get("WERKZEUG_RUN_MAIN") == "true" or not app.debug:` guard. Use the exact 4-line pattern: `cache_cleanup = app.container.get("cache_cleanup"); cache_cleanup.app = app; cache_cleanup.start(); app.logger.info("Cache cleanup background service started")`.
  </action>
  <verify>
    <automated>grep -q 'class CacheCleanupService' app/services/cache_cleanup_service.py &amp;&amp; grep -q 'cache_cleanup' app/container.py &amp;&amp; grep -q 'Cache cleanup background service started' app/__init__.py &amp;&amp; python -c 'from app import create_app; app = create_app(); svc = app.container.get(\"cache_cleanup\"); assert hasattr(svc, \"run_now\")'</automated>
  </verify>
  <acceptance_criteria>
    - `app/services/cache_cleanup_service.py` exists and contains `class CacheCleanupService`
    - `grep -n "check_interval = 3600" app/services/cache_cleanup_service.py` matches
    - `grep -n "container.register(\"cache_cleanup\"" app/container.py` matches
    - `grep -n "Cache cleanup background service started" app/__init__.py` matches
    - `python -c "from app import create_app; app=create_app(); svc=app.container.get('cache_cleanup'); assert hasattr(svc,'run_now') and hasattr(svc,'start')"` exits 0
  </acceptance_criteria>
  <done>Service class registered, hourly thread starts on app boot, run_now() callable.</done>
</task>

<task type="auto">
  <name>Task 2: Admin Run-now route returning HTMX HTML fragments</name>
  <read_first>
    - app/blueprints/admin/database.py lines 358–412 (refresh_cache analog — verbatim audit + HTMX fragment pattern per PATTERNS.md)
    - app/blueprints/admin/cache.py (target file for the new handler)
    - app/blueprints/admin/__init__.py lines 81–93 (cache route wiring pattern)
    - app/services/audit_service_postgres.py (confirm audit_service.log_admin_action signature)
  </read_first>
  <action>
    Per UI-SPEC §"Component Contract — Admin 'Run now' Button" and PATTERNS.md "admin/__init__.py modification":

    1. In `app/blueprints/admin/cache.py` add function:
       ```python
       def cache_cleanup_run():
           from app.services.audit_service_postgres import audit_service
           from datetime import datetime
           admin_email = request.headers.get("X-MS-CLIENT-PRINCIPAL-NAME", request.remote_user or "unknown")
           admin_role = getattr(request, "user_role", None)
           user_ip = request.headers.get("X-Forwarded-For", request.remote_addr)
           try:
               deleted, duration_ms = current_app.container.get("cache_cleanup").run_now()
               audit_service.log_admin_action(
                   user_email=admin_email, action="cache_cleanup_run",
                   target="cache:search", user_role=admin_role,
                   ip_address=user_ip, user_agent=request.headers.get("User-Agent"),
                   success=True, details={"deleted": deleted, "duration_ms": round(duration_ms, 1)},
               )
               return (
                   '<div role="status" aria-live="polite" '
                   'class="p-2 bg-green-50 border border-green-200 rounded text-xs text-green-800">'
                   f'<i class="fas fa-check-circle mr-1"></i>'
                   f'Cleaned up {deleted} expired entries at {datetime.now().strftime("%H:%M:%S")}'
                   '</div>'
               )
           except Exception as exc:
               logger.exception("Cache cleanup run_now failed")
               audit_service.log_admin_action(
                   user_email=admin_email, action="cache_cleanup_run",
                   target="cache:search", user_role=admin_role,
                   ip_address=user_ip, user_agent=request.headers.get("User-Agent"),
                   success=False, details={"error": str(exc)},
               )
               return (
                   '<div role="status" aria-live="polite" '
                   'class="p-2 bg-red-50 border border-red-200 rounded text-xs text-red-800">'
                   f'<i class="fas fa-exclamation-triangle mr-1"></i>'
                   f'Cleanup failed: {str(exc)[:120]}. Check error logs for details.'
                   '</div>'
               ), 500
       ```
    2. In `app/blueprints/admin/__init__.py` register the route alongside other cache routes (lines 81–93 area) — apply `@auth_required` then `@require_role("admin")` decorators, route path `/api/cache/cleanup/run`, methods `["POST"]`, endpoint name `api_cache_cleanup_run`. Match the existing decorator-stacked registration style used for `api_cache_refresh`.
    3. Use `@handle_errors` decorator on the route per PATTERNS.md "Error decorator on routes".
  </action>
  <verify>
    <automated>grep -q 'def cache_cleanup_run' app/blueprints/admin/cache.py &amp;&amp; grep -q 'api_cache_cleanup_run' app/blueprints/admin/__init__.py &amp;&amp; grep -q 'cache_cleanup_run' app/blueprints/admin/__init__.py</automated>
  </verify>
  <acceptance_criteria>
    - `grep -n "def cache_cleanup_run" app/blueprints/admin/cache.py` matches
    - `grep -n "api_cache_cleanup_run" app/blueprints/admin/__init__.py` matches (endpoint name)
    - `grep -n "/api/cache/cleanup/run" app/blueprints/admin/__init__.py` matches (route path)
    - `grep -n "require_role(\"admin\")" app/blueprints/admin/__init__.py | wc -l` is at least one MORE than baseline (new admin-gated route)
    - `grep -n "log_admin_action" app/blueprints/admin/cache.py` matches (audit wired)
    - App boots: `python -c "from app import create_app; create_app()"` exits 0
  </acceptance_criteria>
  <done>POST /admin/api/cache/cleanup/run returns HTMX HTML fragment, audit-logged, admin-gated.</done>
</task>

<task type="auto">
  <name>Task 3: Add Run-now row to _cache_actions.html</name>
  <read_first>
    - app/templates/admin/_cache_actions.html (lines 5–37 — Search Cache row analog)
    - .planning/phases/01-foundation/01-UI-SPEC.md §"Component Contract — Admin 'Run now' Button" (verbatim HTML required)
  </read_first>
  <action>
    Append a new card row to `app/templates/admin/_cache_actions.html` matching the exact HTML in UI-SPEC lines 178–204. Use:
    - Icon circle: `bg-blue-100` containing `<i class="fas fa-broom text-blue-600 text-lg" aria-hidden="true">`
    - Title: `Search Cache Cleanup` (text-sm, font-semibold, gray-900)
    - Subtitle: `Remove expired entries (runs hourly automatically)` (text-xs gray-500)
    - Button: `bg-blue-500 hover:bg-blue-600 text-white text-xs font-medium rounded-md px-3 py-2` with broom icon, `Run now` label, inline spinner
    - HTMX attributes: `hx-post="{{ url_for('admin.api_cache_cleanup_run') }}" hx-target="#cleanup-result" hx-swap="innerHTML" hx-indicator="#cleanup-spinner"`
    - Result `<div id="cleanup-result" class="mt-3" role="status" aria-live="polite">`

    Do NOT add a confirmation modal (per UI-SPEC: idempotent + non-destructive). Do NOT touch other rows in the file.
  </action>
  <verify>
    <automated>grep -q 'fa-broom' app/templates/admin/_cache_actions.html &amp;&amp; grep -q 'cleanup-result' app/templates/admin/_cache_actions.html &amp;&amp; grep -q 'api_cache_cleanup_run' app/templates/admin/_cache_actions.html &amp;&amp; grep -q 'Search Cache Cleanup' app/templates/admin/_cache_actions.html</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "fa-broom" app/templates/admin/_cache_actions.html` returns ≥ 2 (icon circle + button icon)
    - `grep -n "id=\"cleanup-result\"" app/templates/admin/_cache_actions.html` matches
    - `grep -n "url_for('admin.api_cache_cleanup_run')" app/templates/admin/_cache_actions.html` matches
    - `grep -n "Search Cache Cleanup" app/templates/admin/_cache_actions.html` matches
    - `grep -n "aria-live=\"polite\"" app/templates/admin/_cache_actions.html` matches
    - No new `confirm`/modal markup added (`grep -n "cleanupModal\|confirm" app/templates/admin/_cache_actions.html` shows no new entries)
  </acceptance_criteria>
  <done>New card row visible in cache management UI; Run-now button posts to admin endpoint and swaps the result div.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| browser → admin endpoint | Authenticated admin user invokes destructive-shaped (but actually idempotent) DB operation |
| background thread → DB | Long-lived thread issues DELETE every hour |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-01-02-01 | Elevation of Privilege | /admin/api/cache/cleanup/run | mitigate | Route stacks @auth_required + @require_role("admin"); audit log every invocation success or failure |
| T-01-02-02 | Tampering | DELETE on search_cache | mitigate | DELETE filter is `expires_at < NOW()` only — already-expired rows are safe to drop; verified by tests in Phase 2 |
| T-01-02-03 | Denial of Service | Background thread loop | mitigate | Exception in `_cleanup()` is caught + logged inside `_run()`; thread keeps the 1h cadence and never crashes |
| T-01-02-04 | Repudiation | Manual Run-now invocation | mitigate | audit_service.log_admin_action() records who/when/result/IP/user-agent for every click |
</threat_model>

<verification>
- App boots and the cache cleanup thread logs "Cache cleanup background service started"
- Click Run-now in `/admin/cache` → result div shows green "Cleaned up N expired entries at HH:MM:SS"
- `audit_log` table has a row with `action='cache_cleanup_run'` after each click
</verification>

<success_criteria>
DEBT-03 acceptance criteria satisfied: scheduled cleanup runs hourly; admin can trigger manually; UI matches UI-SPEC verbatim; audit trail recorded.
</success_criteria>

<output>
After completion, create `.planning/phases/01-foundation/01-02-SUMMARY.md`.
</output>
