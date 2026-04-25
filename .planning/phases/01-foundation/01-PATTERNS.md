# Phase 1: Foundation - Pattern Map

**Mapped:** 2026-04-24
**Files analyzed:** 16 (8 new, 8 modified)
**Analogs found:** 14 / 16 (2 have no exact analog — see No Analog Found)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `app/middleware/request_id.py` | middleware | request-response | `app/middleware/audit_logger.py` | role-match |
| `app/blueprints/health/__init__.py` | blueprint (route) | request-response | `app/blueprints/session/__init__.py` | exact (Blueprint pattern) |
| `app/services/cache_cleanup_service.py` | service (background thread) | batch / scheduled | `app/services/token_refresh_service.py` | exact |
| `app/utils/pagination.py` | utility | transform | `app/utils/error_handler.py` (decorator-style util) | role-match |
| `app/templates/partials/pagination.html` | template (Jinja partial) | request-response (HTMX) | `app/templates/admin/partials/_compliance_violations_table.html` (lines 143–223) | exact |
| `scripts/rotate_encryption_key.py` | script | batch / one-shot | `scripts/verify_encrypted_config.py` + `scripts/export_config.py` | exact |
| `app/services/config_validator.py` | service (startup gate) | request-response (one-shot) | `app/services/encryption_service.py` (constructor-raises pattern) | role-match |
| `docs/runbooks/encryption-key-rotation.md` | docs (runbook) | n/a | (no existing runbook — see No Analog) | none |
| `app/__init__.py` (modify) | factory | request-response | self (existing `create_app`) | exact |
| `app/container.py` (modify) | DI registry | n/a | self (existing `register_services`) | exact |
| `app/middleware/auth.py` (modify) | middleware | request-response | self + `app/middleware/authentication_handler.py` | exact |
| `requirements.txt` (modify) | config | n/a | self | exact |
| `.gitignore` (modify) | config | n/a | self | exact |
| `app/blueprints/admin/__init__.py` (modify — add Run-now route) | blueprint (route) | request-response (HTMX) | `app/blueprints/admin/database.py::refresh_cache` (line 359) | exact |
| `app/blueprints/search/__init__.py` (modify — add rate-limit decorator) | blueprint (route) | request-response | self + Flask-Limiter docs | role-match |
| `app/templates/admin/_cache_actions.html` (modify — add Run-now row) | template fragment | request-response (HTMX) | self (lines 5–37 — Search Cache row) | exact |

---

## Pattern Assignments

### `app/services/cache_cleanup_service.py` (background thread)

**Analog:** `app/services/token_refresh_service.py` (canonical reference for any phase-1 background job).

**Class skeleton + lifecycle pattern** (token_refresh_service.py lines 16–62):

```python
class TokenRefreshService:
    def __init__(self, container=None, app=None):
        self.container = container
        self.app = app
        self.is_running = False
        self.thread: Optional[threading.Thread] = None
        self.check_interval = 300  # Check every 5 minutes

    def init_app(self, app: Flask):
        self.app = app

    def start(self):
        if self.is_running:
            logger.warning("Token refresh service is already running")
            return
        self.is_running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        logger.info("Token refresh service started")

    def _run(self):
        while self.is_running:
            try:
                self._check_and_refresh_tokens()
            except Exception as e:
                logger.error(f"Error in token refresh service: {str(e)}")
            time.sleep(self.check_interval)
```

**Adapt for cleanup service:** `check_interval = 3600` (hourly per D-13/DEBT-03), method renamed to `_run_cleanup()`, body deletes `SearchCache` rows where `expires_at < NOW()`. Wrap each iteration in `with self.app.app_context():` (token_refresh_service.py:69). Expose a public `run_now()` method that the admin "Run now" route calls synchronously and returns `(deleted_count, duration_ms)`.

**Container registration** (token_refresh_service.py:154 + app/container.py:155):
```python
container.register("cache_cleanup", lambda c: CacheCleanupService(container))
```

**Startup wiring** (app/__init__.py lines 110–115 — copy verbatim, swap service name):
```python
cache_cleanup = app.container.get("cache_cleanup")
cache_cleanup.app = app
cache_cleanup.start()
app.logger.info("Cache cleanup background service started")
```

---

### `app/middleware/request_id.py` (middleware + LogFilter)

**Analog:** `app/middleware/audit_logger.py` (closest middleware module — small, single-responsibility class with no Flask boilerplate around it). For Flask `before_request`/`after_request` registration, see `app/__init__.py` lines 158–166.

**Module shape pattern** (audit_logger.py lines 1–42 — small class, module-level logger optional, used via Flask context):

```python
from flask import request
from typing import Optional


class AuditLogger:
    """Handles audit logging for authentication events"""

    def log_access_denied(self, user_email=None, user_role=None) -> None:
        ...
```

**Flask hook registration pattern** (app/__init__.py lines 158–166 — `before_request` is the existing hook style):

```python
@app.before_request
def before_request():
    if request.method == "OPTIONS":
        return "Method Not Allowed", 405
    g.user = None
    g.role = None
```

**Adapt:** New module exports `init_request_id(app)` that registers:
- `@app.before_request` — read `X-Request-ID` header (validate UUID4 shape) or generate `uuid.uuid4().hex`; set `g.request_id`.
- `@app.after_request` — set `response.headers["X-Request-ID"] = g.request_id`.
- A `logging.Filter` subclass `RequestIdFilter` whose `filter(record)` does `record.request_id = getattr(g, "request_id", "-")`. Attach via `logging.getLogger().addFilter(...)` and update the JSON formatter to include the field.

**JSON formatter wiring** (replaces app/__init__.py lines 17–20):
- Add `python-json-logger` to `requirements.txt` (D-06).
- Replace `logging.basicConfig(... format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")` with `pythonjsonlogger.jsonlogger.JsonFormatter` configured to emit `timestamp, level, request_id, user, logger, message`.
- The existing `app/app_factory.py:configure_logging()` (lines 12–22) shows the additional `logging.getLogger("urllib3").setLevel(logging.WARNING)` quieting calls — preserve those (DEBT-01 deletes `app_factory.py` but its quieting logic must migrate into `__init__.py`).

---

### `app/blueprints/health/__init__.py` (health endpoints)

**Analog:** `app/blueprints/session/__init__.py` (smallest existing blueprint, demonstrates `@handle_errors(json_response=True)` + `jsonify` pattern).

**Blueprint registration pattern** (session/__init__.py lines 1–8, 178–187):

```python
from flask import Blueprint, jsonify
from app.utils.error_handler import handle_errors

session_bp = Blueprint("session", __name__)


@session_bp.route("/api/session/config", methods=["GET"])
@handle_errors(json_response=True)
def get_session_config():
    config = {...}
    return jsonify(config), 200
```

**Adapt:** Two routes — `/health/live` returns `jsonify({"status": "ok"}), 200` with NO auth decorator and NO DB hit. `/health` runs `db.session.execute(text("SELECT 1"))` inside a `time.perf_counter()` block; on success returns `200` with `{status, database: {connected: True, latency_ms}, version, request_id: g.request_id}`; on failure returns `503`. Per D-11 both endpoints are unauthenticated — DO NOT apply `@auth_required`.

**Register in app factory** (app/__init__.py lines 171–181):
```python
from app.blueprints.health import health_bp
app.register_blueprint(health_bp)  # No url_prefix — exposes /health and /health/live at root
```

**Database health probe template** — `app/blueprints/admin/database.py::database_health` (already wired at `/admin/api/database/health`) is the existing pattern; the new public `/health` should perform the same `SELECT 1` probe but without admin auth and with a tighter timeout.

---

### `app/utils/pagination.py` (paginate helper)

**Analog:** `app/utils/error_handler.py` — closest existing util with named-export, type-hinted, decorator-style API. The `paginate()` function is a plain helper, not a decorator, but the module conventions (module logger, type hints, docstrings) match.

**Module conventions** (error_handler.py lines 1–10):
```python
from functools import wraps
from flask import jsonify, render_template, request
from sqlalchemy.exc import SQLAlchemyError
from typing import Callable, Any, Optional, Dict
import logging

logger = logging.getLogger(__name__)
```

**Existing pagination math** that the helper must reproduce (already in use at `_compliance_violations_table.html` lines 172–177):
```jinja
((data.pagination.page - 1) * data.pagination.per_page) + 1   # start_index
min(data.pagination.page * data.pagination.per_page, data.pagination.total)  # end_index
```

**SQLAlchemy paginate pattern already used** — the codebase uses Flask-SQLAlchemy's built-in `query.paginate(page=N, per_page=M, error_out=False)` which returns an object with the exact attributes the UI-SPEC (lines 119) requires: `items, page, per_page, total, pages, has_prev, has_next, prev_num, next_num`. The new helper should be a thin wrapper that:
1. Coerces `page`/`size` query args (`request.args.get("page", 1, type=int)`, clamped `size` to `<= 200` per D-14).
2. Calls `query.paginate(...)`.
3. Adds derived `start_index`, `end_index` attributes to the returned object (or returns a small dataclass `PageResult` wrapping it).

**Apply to:** `app/blueprints/admin/database.py::api_error_logs`, `database.py::sessions/api_sessions`, and the audit-log endpoint (per CONTEXT "OPS-04 Pagination wiring" Claude's Discretion — the three known >100-row admin tables). Each currently builds its own pagination dict; replace with `paginate(query, page, size)`.

---

### `app/templates/partials/pagination.html` (Jinja partial)

**Analog:** `app/templates/admin/partials/_compliance_violations_table.html` lines 143–223 — verbatim source-of-truth for visual structure per UI-SPEC. UI-SPEC explicitly states "Existing admin templates ARE the design system. This document locks current conventions."

**Excerpt to copy (mobile + desktop pagination)** — `_compliance_violations_table.html:144–222` (already read above; reuse `bg-white px-4 py-3 flex items-center justify-between border-t border-gray-200 sm:px-6` outer; `relative z-0 inline-flex rounded-md shadow-sm -space-x-px` button group; `z-10 bg-blue-50 border-blue-500 text-blue-600` active state; `rounded-l-md`/`rounded-r-md` chevron buttons; `range(max(1, page-2), min(pages+1, page+3))` window).

**Convert to macro** per UI-SPEC §"Component Contract — Pagination Partial":
```jinja
{% macro render_pagination(pagination, endpoint, target, include='', item_noun='results', min_total=100) %}
  {% if pagination.total == 0 %}{# render nothing — empty state is caller's job #}
  {% elif pagination.total <= min_total %}
    {# status text only, no nav controls #}
  {% else %}
    {# full pagination chrome, with page-size selector + hx-push-url="true" #}
  {% endif %}
{% endmacro %}
```

**NEW additions vs the analog** (flagged in UI-SPEC §"Flagged Assumptions"):
1. Page-size selector (`<select>` with options 25/50/100) — visual style matches existing form selects in `audit_logs.html` (`px-2 py-1 text-sm border border-gray-300 rounded-md focus:border-ttcu-green`).
2. `hx-push-url="true"` on every paginator HTMX action (D-13 bookmarkable URLs).

**Empty-state contract:** Macro renders nothing when `total == 0`; caller owns the empty-state block (matches `_compliance_violations_table.html:224–232`).

---

### `scripts/rotate_encryption_key.py`

**Analog:** `scripts/verify_encrypted_config.py` (structure: dotenv → encryption service → psycopg2 connect → cursor.execute → tabulated output) and `scripts/export_config.py` (decryption + iteration over all `Configuration` rows).

**Script header pattern** (verify_encrypted_config.py lines 1–17 / export_config.py lines 1–17):
```python
#!/usr/bin/env python3
"""<description>"""

import os
import sys
import psycopg2
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.encryption_service import EncryptionService
```

**DB connection block** (verify_encrypted_config.py lines 53–60 / export_config.py lines 41–47) — copy verbatim (uses `os.getenv("POSTGRES_*")` directly per CLAUDE.md "Environment Variables Bootstrap Problem"):
```python
conn = psycopg2.connect(
    host=os.getenv("POSTGRES_HOST", "localhost"),
    port=os.getenv("POSTGRES_PORT", "5432"),
    database=os.getenv("POSTGRES_DB", "whodis_db"),
    user=os.getenv("POSTGRES_USER", "whodis_user"),
    password=os.getenv("POSTGRES_PASSWORD", ""),
)
cursor = conn.cursor()
```

**Decrypt-and-re-encrypt loop** (adapt from export_config.py lines 60–88):
```python
# Read both keys from env per D-03
old_key = os.getenv("OLD_WHODIS_ENCRYPTION_KEY")
new_key = os.getenv("NEW_WHODIS_ENCRYPTION_KEY")
old_svc = EncryptionService(old_key)
new_svc = EncryptionService(new_key)  # Will use the NEW salt file once rotated

cursor.execute("SELECT id, category, setting_key, encrypted_value FROM configuration WHERE encrypted_value IS NOT NULL")
for row_id, category, key, encrypted_value in cursor.fetchall():
    plaintext = old_svc.decrypt(bytes(encrypted_value))  # CLAUDE.md "Memory Objects" — bytes(memoryview) before decrypt
    new_encrypted = new_svc.encrypt(plaintext)
    cursor.execute("UPDATE configuration SET encrypted_value = %s WHERE id = %s", (new_encrypted, row_id))
```

**Required flags per D-03:**
- `--dry-run` (default false): decrypt with old key, re-encrypt with new key, but do NOT commit.
- Post-rotation verify step: after commit, instantiate a fresh `EncryptionService(new_key)` and decrypt every row to confirm.
- Wrap entire mutation in a single `psycopg2` transaction; only `conn.commit()` at the end on success.

**Memoryview gotcha** (CLAUDE.md "Memory Objects" + encryption_service.py:118): `encrypted_value` returned from `BYTEA` columns is a `memoryview`/`buffer`. Always `bytes(value)` before passing to `Fernet.decrypt`.

---

### `app/services/config_validator.py` (startup validation gate)

**Analog:** `app/services/encryption_service.py` constructor pattern (lines 21–27) — raises immediately on missing required value:

```python
def __init__(self, passphrase: Optional[str] = None):
    self.passphrase = passphrase or os.getenv("WHODIS_ENCRYPTION_KEY")
    if not self.passphrase:
        raise ValueError(
            "WHODIS_ENCRYPTION_KEY must be set in environment variables"
        )
```

**Config access pattern** (services/configuration_service.py — `config_get`):
```python
from app.services.configuration_service import config_get
value = config_get("ldap.server", None)  # None means missing
```

**Adapt:** Define `class ConfigurationError(Exception)` in module. Define a hardcoded list of required keys (from CONTEXT "Claude's Discretion / OPS-03"): LDAP server, LDAP bind DN, Graph tenant_id, Graph client_id, Graph client_secret, Genesys client_id, Genesys client_secret, Flask secret key (already loaded). Iterate, collect missing, raise `ConfigurationError(f"Missing required config keys: {', '.join(missing)}")` if any missing. Call from `app/__init__.py:create_app()` AFTER configuration_service is initialized (after line 76) and BEFORE blueprint registration — failure aborts boot per CONTEXT.

---

### `app/middleware/auth.py` modifications (SEC-04: configurable header + dev bypass)

**Existing analog:** `app/middleware/authentication_handler.py` lines 8–22 — the only place that reads `X-MS-CLIENT-PRINCIPAL-NAME`:

```python
def authenticate_user(self) -> Optional[str]:
    ms_principal = request.headers.get("X-MS-CLIENT-PRINCIPAL-NAME")
    if ms_principal:
        return ms_principal
    return None
```

**Adapt for SEC-04:** The header name comes from config; dev bypass returns the configured user when an explicit env flag is set:

```python
from app.services.configuration_service import config_get

def authenticate_user(self) -> Optional[str]:
    # Dev bypass — explicit, loud, never enabled in production
    bypass_user = os.getenv("DANGEROUS_DEV_AUTH_BYPASS_USER")
    if bypass_user:
        logger.warning(f"AUTH BYPASS ACTIVE — authenticating as {bypass_user}")
        return bypass_user

    header_name = config_get("auth.principal_header", "X-MS-CLIENT-PRINCIPAL-NAME")
    ms_principal = request.headers.get(header_name)
    if ms_principal:
        return ms_principal
    return None
```

NOTE: also update `app/__init__.py:188` and `app/utils/error_handler.py:51` which both read `X-MS-CLIENT-PRINCIPAL-NAME` directly — those sites hardcode the header for error logging context. SEC-04 should leave them as-is (they read for logging not auth) OR migrate to a shared helper. Recommend leaving for Phase 1 simplicity and noting in the plan.

---

### `app/blueprints/admin/__init__.py` modification — Run-now route

**Analog:** `app/blueprints/admin/database.py::refresh_cache` (lines 358–412) — exact same pattern (admin role, audit log, HTMX HTML fragment response).

**Excerpt to copy** (database.py:358–412):
```python
@require_role("admin")
def refresh_cache(cache_type):
    from app.services.audit_service_postgres import audit_service

    admin_email = request.headers.get(
        "X-MS-CLIENT-PRINCIPAL-NAME", request.remote_user or "unknown"
    )
    admin_role = getattr(request, "user_role", None)
    user_ip = request.headers.get("X-Forwarded-For", request.remote_addr)

    result = ...do work...

    audit_service.log_admin_action(
        user_email=admin_email,
        action="refresh_cache",
        target=f"cache:{cache_type}",
        user_role=admin_role,
        ip_address=user_ip,
        user_agent=request.headers.get("User-Agent"),
        success=True,
        details=result,
    )

    if request.headers.get("HX-Request"):
        return f"""
        <div class="bg-green-50 border-l-4 border-green-400 p-4 rounded-lg">
            ...success HTML...
        </div>
        """
    return jsonify({...})
```

**Adapt for Run-now:** Add `def cache_cleanup_run():` in `app/blueprints/admin/cache.py` (existing module — keep cache concerns colocated). Call `current_app.container.get("cache_cleanup").run_now()`, audit with `action="cache_cleanup_run"`, target=`"cache:search"`. Return the success/error HTML fragments specified in UI-SPEC §"Component Contract — Admin 'Run now' Button" (green-50 success div, red-50 error div). Wire via `admin_bp.route("/api/cache/cleanup/run", methods=["POST"], endpoint="api_cache_cleanup_run")(cache.cache_cleanup_run)` in `app/blueprints/admin/__init__.py` alongside the other cache routes (lines 81–93).

---

### `app/templates/admin/_cache_actions.html` modification — Run-now row

**Analog:** lines 5–37 (Search Cache row) of the same file — verbatim layout pattern.

**Excerpt to copy** (_cache_actions.html:5–37):
```html
<div class="border rounded-lg p-4 hover:shadow-md transition-shadow duration-200">
    <div class="flex items-center justify-between">
        <div class="flex items-center min-w-0 flex-1">
            <div class="flex-shrink-0 w-10 h-10 bg-blue-100 rounded-full flex items-center justify-center">
                <i class="fas fa-search text-blue-600 text-lg"></i>
            </div>
            <div class="ml-4 min-w-0 flex-1">
                <h5 class="font-semibold text-gray-900 text-sm">Search Cache</h5>
                <p class="text-xs text-gray-500 mt-0.5">User search results cache</p>
            </div>
        </div>
        <div class="flex items-center space-x-2 ml-4">
            <button class="px-3 py-2 bg-blue-500 hover:bg-blue-600 text-white text-xs font-medium rounded-md transition duration-150 flex items-center whitespace-nowrap"
                    hx-post="{{ url_for('admin.api_cache_refresh', cache_type='search') }}"
                    hx-target="#search-cache-result"
                    hx-swap="innerHTML"
                    hx-indicator="#search-refresh-spinner">
                <i class="fas fa-sync-alt mr-1.5"></i>
                Refresh
                <span id="search-refresh-spinner" class="htmx-indicator ml-1.5">
                    <i class="fas fa-spinner fa-spin"></i>
                </span>
            </button>
        </div>
    </div>
    <div id="search-cache-result" class="mt-3"></div>
</div>
```

**Adapt:** Swap icon to `fa-broom`, label to `Search Cache Cleanup`, subtitle to `Remove expired entries (runs hourly automatically)`, button label to `Run now`, `hx-post` to `url_for('admin.api_cache_cleanup_run')`, IDs to `cleanup-result`/`cleanup-spinner`. Per UI-SPEC: NO destructive Clear button (cleanup is non-destructive — only deletes already-expired rows). NO confirmation modal.

---

### `app/blueprints/search/__init__.py` modification — rate limit decorator

**Analog:** Existing decorator stack on search routes (search/__init__.py and `app/middleware/auth.py:97`). Apply Flask-Limiter's `@limiter.limit("30/minute", key_func=lambda: g.user)` ABOVE `@auth_required` per CONTEXT D-09.

**Decorator stack pattern** (admin/__init__.py:23–25 — model for layered decorators):
```python
@admin_bp.route("/")
@require_role("admin")
def index():
    ...
```

**Adapt for D-09:**
```python
@search_bp.route("/", methods=["GET", "POST"])
@limiter.limit("30/minute", key_func=lambda: g.user)
@auth_required
@require_role("viewer")
def search():
    ...
```

NOTE: `g.user` is set by `auth_required` which runs AFTER the limiter — so `key_func` must default to IP when `g.user` is unset. Use `key_func=lambda: getattr(g, "user", get_remote_address())`.

**Limiter init in app/__init__.py** (Flask-Limiter standard):
```python
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=app.config["SQLALCHEMY_DATABASE_URI"],  # PostgreSQL per D-08
)
limiter.init_app(app)
```

Register in container per CONTEXT "Integration Points":
```python
container.register("limiter", lambda c: limiter)
```

---

## Shared Patterns

### Module logger initialization
**Source:** Universal — every service/module uses this.
**Apply to:** Every new `.py` file in this phase (request_id, cache_cleanup_service, config_validator, pagination, health blueprint, rotate script).
```python
import logging
logger = logging.getLogger(__name__)
```

### Audit-logged admin actions
**Source:** `app/blueprints/admin/database.py:366–384` (refresh_cache).
**Apply to:** Run-now route in admin/cache.py.
```python
from app.services.audit_service_postgres import audit_service

admin_email = request.headers.get("X-MS-CLIENT-PRINCIPAL-NAME", request.remote_user or "unknown")
admin_role = getattr(request, "user_role", None)
user_ip = request.headers.get("X-Forwarded-For", request.remote_addr)

audit_service.log_admin_action(
    user_email=admin_email,
    action="...",
    target="...",
    user_role=admin_role,
    ip_address=user_ip,
    user_agent=request.headers.get("User-Agent"),
    success=True,
    details=result,
)
```

### Error decorator on routes
**Source:** `app/utils/error_handler.py` — `@handle_errors` and `@handle_errors(json_response=True)`.
**Apply to:** `/health`, `/health/live`, Run-now route, any new admin route.
```python
@blueprint.route("/path")
@handle_errors(json_response=True)  # json for /health, default for HTMX fragments
def route():
    ...
```

### DI container service retrieval (NEVER global imports)
**Source:** CLAUDE.md "Dependency Injection" + `app/__init__.py:111` (`token_refresh = app.container.get("token_refresh")`).
**Apply to:** Run-now route accessing cache_cleanup, any new code reaching for a registered service.
```python
service = current_app.container.get("cache_cleanup")
```

### Background-thread service registration + startup
**Source:** `app/services/token_refresh_service.py` + `app/__init__.py:111–115`.
**Apply to:** `cache_cleanup_service` only (the lone new background service in Phase 1).
- Service exposes `init_app(app)` and `start()`.
- Container registers it (`container.py:154` analog).
- `__init__.py` calls `service.app = app; service.start()` inside the `WERKZEUG_RUN_MAIN` guarded block (line 81) so the reloader does not double-start.

### HTMX HTML fragment response shape
**Source:** `app/blueprints/admin/database.py:387–404` (success) and the UI-SPEC §"State contract".
**Apply to:** Run-now route success/error responses.
- Success: `<div class="p-2 bg-green-50 border border-green-200 rounded text-xs text-green-800">…</div>`
- Error: `<div class="p-2 bg-red-50 border border-red-200 rounded text-xs text-red-800">…</div>`

### CLAUDE.md "Memory Objects" gotcha
**Source:** `CLAUDE.md` "Important Database Notes" + `encryption_service.py:118`.
**Apply to:** `rotate_encryption_key.py` when reading `encrypted_value` from `Configuration` rows.
```python
plaintext = old_svc.decrypt(bytes(encrypted_value))  # bytes() coerces memoryview/buffer
```

---

## No Analog Found

| File | Role | Data Flow | Reason / Recommendation |
|------|------|-----------|-------------------------|
| `docs/runbooks/encryption-key-rotation.md` | docs (runbook) | n/a | No `docs/runbooks/` directory exists yet. Create it. Use existing `docs/database.md` and `docs/architecture.md` markdown style (H1 title, `## Overview`, numbered ordered steps, fenced code blocks for shell commands). Sections required by CONTEXT D-04: Pre-flight (`scripts/export_config.py` backup), Step-by-step rotation order (generate new salt → set OLD/NEW env vars → run `rotate_encryption_key.py --dry-run` → run for real → restart app → verify), Rollback procedure. |
| Flask-Limiter init code | infrastructure | n/a | New library — no existing analog in this codebase. Use Flask-Limiter's documented PostgreSQL storage backend (`storage_uri` = the existing `SQLALCHEMY_DATABASE_URI`). Library may auto-create its counter table; `database/create_tables.sql` may need an addendum — verify against Flask-Limiter docs during planning (CONTEXT explicitly calls this out). |

---

## Metadata

**Analog search scope:** `app/middleware/`, `app/blueprints/`, `app/services/`, `app/utils/`, `app/templates/admin/`, `app/templates/admin/partials/`, `scripts/`, `app/__init__.py`, `app/container.py`, `.gitignore`.
**Files scanned:** ~25 read; ~12 deeply analyzed for excerpt extraction.
**Pattern extraction date:** 2026-04-24
**Phase:** 01-foundation
