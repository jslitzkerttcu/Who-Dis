# Phase 13: Schema Visualization - Pattern Map

**Mapped:** 2026-05-19
**Files analyzed:** 4 (files to modify)
**Analogs found:** 4 / 4

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `app/blueprints/admin/database.py` | controller | request-response | `app/blueprints/admin/database.py` (self — `database_tables()` + `_render_table_statistics()`) | exact |
| `app/blueprints/admin/__init__.py` | route-registry | config | `app/blueprints/admin/__init__.py` (self — database route block lines 113-176) | exact |
| `app/templates/admin/database.html` | template | request-response | `app/templates/admin/database.html` (self — Table Statistics accordion lines 206-231) | exact |
| `app/middleware/security_headers.py` | middleware | request-response | `app/middleware/security_headers.py` (self — CSP policy lines 22-32) | exact |

## Pattern Assignments

### `app/blueprints/admin/database.py` — Add schema endpoint + Mermaid generation (controller, request-response)

**Analog:** Same file — `database_tables()` function (lines 124-281) and `_render_table_statistics()` (lines 1111-1155)

**Imports pattern** (lines 1-16):
```python
from flask import render_template, jsonify, request, Response, g
from app.middleware.auth import require_role
from app.database import db
from datetime import datetime, timedelta, timezone
```

**Lazy import pattern inside function** (line 126):
```python
def database_tables():
    """Get table statistics."""
    from sqlalchemy import text, inspect
```

**pg_catalog query pattern** (lines 137-155) — reuse and extend for schema metadata:
```python
query = text("""
    SELECT 
        n.nspname as schemaname,
        c.relname as tablename,
        CASE 
            WHEN c.reltuples < 0 THEN 0
            ELSE c.reltuples::bigint 
        END as row_count,
        pg_size_pretty(pg_total_relation_size(c.oid)) as size,
        s.last_vacuum,
        s.last_autovacuum,
        s.n_live_tup as live_tuples
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    LEFT JOIN pg_stat_user_tables s ON s.schemaname = n.nspname AND s.relid = c.oid
    WHERE n.nspname = 'public' 
    AND c.relkind = 'r'
    ORDER BY c.relname
""")

results = db.session.execute(query)
```

**HTMX request detection + HTML fragment return pattern** (lines 246-249):
```python
# Check if this is an Htmx request
if request.headers.get("HX-Request"):
    return _render_table_statistics(tables)

return jsonify({"tables": tables})
```

**Private render function pattern** (`_render_table_statistics`, lines 1111-1155) — f-string HTML fragment with Tailwind classes:
```python
def _render_table_statistics(tables):
    """Render table statistics as HTML for Htmx."""
    if not tables:
        return """
        <div class="text-center py-8 text-gray-500">
            No tables found
        </div>
        """

    html = """
    <table class="min-w-full divide-y divide-gray-200">
        <thead class="bg-gray-50">
    ...
    """
    return html
```

**Auth decorator pattern** (line 18) — applied at function level, not on route:
```python
@require_role("admin")
def database():
    """Display database management page."""
```

**Error handling pattern** (lines 250-281) — try/except with logger + fallback:
```python
except Exception as e:
    import traceback
    from flask import current_app

    current_app.logger.error(f"Error getting table statistics: {str(e)}")
    current_app.logger.error(traceback.format_exc())
    # fallback logic...
```

---

### `app/blueprints/admin/__init__.py` — Register schema route (route-registry, config)

**Analog:** Same file — database route registration block (lines 113-176)

**Route registration pattern** (lines 113-119):
```python
# Database management routes
admin_bp.route("/database")(database.database)
admin_bp.route("/api/database/health")(database.database_health)
admin_bp.route("/api/database/tables")(database.database_tables)
admin_bp.route("/api/database/errors/stats")(database.error_stats)
admin_bp.route("/api/sessions/stats")(database.session_stats)
admin_bp.route("/api/database/optimize", methods=["POST"])(database.optimize_database)
```

New schema route should follow the same pattern — add after the existing database routes:
```python
admin_bp.route("/api/database/schema")(database.database_schema)
```

---

### `app/templates/admin/database.html` — Add Schema accordion card (template, request-response)

**Analog:** Same file — Table Statistics accordion section (lines 206-231)

**Accordion card pattern** (lines 206-231):
```html
<!-- Row 4: Table Statistics (full-width accordion on mobile) -->
<div class="bg-white rounded-2xl shadow-md border border-gray-200">
    <div class="bg-gray-700 text-white px-6 py-4 rounded-t-2xl cursor-pointer hover:bg-gray-600 transition duration-150"
         onclick="toggleTableStats()">
        <h2 class="text-xl font-semibold text-white flex items-center justify-between">
            <span>
                <i class="fas fa-table mr-2"></i>
                Table Statistics
            </span>
            <i id="table-stats-icon" class="fas fa-chevron-down transition-transform"></i>
        </h2>
    </div>
    <div id="table-stats-content" class="hidden">
        <div class="overflow-x-auto"
             hx-get="{{ url_for('admin.database_tables') }}"
             hx-trigger="revealed"
             hx-swap="innerHTML">
            <div class="text-center py-8">
                <div class="inline-flex items-center">
                    <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-700 mr-3"></div>
                    <span class="text-gray-600">Loading table statistics...</span>
                </div>
            </div>
        </div>
    </div>
</div>
```

**Key elements to replicate for Schema card:**
- `bg-white rounded-2xl shadow-md border border-gray-200` card wrapper
- Gradient header with icon + title + chevron toggle
- `hidden` class on content div (collapsed by default)
- `hx-trigger="revealed"` for lazy loading when accordion opens
- Loading spinner matching the section's gradient color
- Toggle JS function following `toggleTableStats()` pattern

**Toggle JS pattern** (lines 255-266):
```javascript
function toggleTableStats() {
    const content = document.getElementById('table-stats-content');
    const icon = document.getElementById('table-stats-icon');
    
    if (content.classList.contains('hidden')) {
        content.classList.remove('hidden');
        icon.classList.add('rotate-180');
    } else {
        content.classList.add('hidden');
        icon.classList.remove('rotate-180');
    }
}
```

**Full-width card header gradient pattern** (line 21 — Database Health card):
```html
<div class="bg-gradient-to-r from-blue-600 to-blue-700 text-white px-6 py-4 rounded-t-2xl">
    <h2 class="text-xl font-semibold text-white flex items-center">
        <i class="fas fa-heartbeat mr-2 animate-pulse"></i>
        Database Health
    </h2>
</div>
```

Schema card should use `from-indigo-600 to-indigo-700` per UI-SPEC.

---

### `app/middleware/security_headers.py` — Verify/update CSP (middleware, request-response)

**Analog:** Same file — CSP policy (lines 22-32)

**Current CSP pattern** (lines 22-32):
```python
csp_policy = (
    "default-src 'self'; "
    "script-src 'self' https://cdn.jsdelivr.net 'unsafe-eval'; "
    "style-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; "
    "font-src 'self' https://cdn.jsdelivr.net; "
    "img-src 'self' data: blob:; "
    "connect-src 'self'; "
    "form-action 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'self';"
)
```

**Finding:** `cdn.jsdelivr.net` is already allowed in `script-src`, `style-src`, and `font-src`. No CSP change is needed for Mermaid.js CDN (RESEARCH Pitfall 5 confirmed). This file may not require modification.

---

## Shared Patterns

### Authentication
**Source:** `app/middleware/auth.py` via `app/blueprints/admin/database.py` line 18
**Apply to:** New `database_schema()` function
```python
@require_role("admin")
def database_schema():
    """Return schema ER diagram as HTMX fragment."""
```

Note: In this codebase, `@require_role("admin")` is applied directly on the function in the module file (e.g., `database.py`), NOT on the route registration in `__init__.py`. The route in `__init__.py` just wires the function: `admin_bp.route("/api/database/schema")(database.database_schema)`.

### Error Handling
**Source:** `app/blueprints/admin/database.py` lines 250-281
**Apply to:** `database_schema()` function
```python
try:
    # query logic
    if request.headers.get("HX-Request"):
        return _render_schema_diagram(mermaid_definition, fk_map, table_count, fk_count)
    return jsonify({"mermaid": mermaid_definition})
except Exception as e:
    import traceback
    from flask import current_app
    current_app.logger.error(f"Error generating schema diagram: {str(e)}")
    current_app.logger.error(traceback.format_exc())
    # Return error fragment for HTMX
```

### HTMX Fragment Response
**Source:** `app/blueprints/admin/database.py` lines 246-249, 1111-1155
**Apply to:** Schema endpoint response
- Check `request.headers.get("HX-Request")` to decide HTML vs JSON
- Return f-string HTML fragment from private `_render_*` function
- Use Tailwind utility classes consistent with existing fragments

### HTMX Lazy Loading (accordion)
**Source:** `app/templates/admin/database.html` lines 218-230
**Apply to:** Schema accordion content div
- `hx-trigger="revealed"` triggers the HTMX GET only when the element becomes visible (accordion opens)
- Content starts with `class="hidden"` and is toggled by JS
- Loading spinner shown as placeholder until HTMX swaps in the response

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| (inline JS in fragment) | client-script | event-driven | SVG click-to-highlight interaction has no existing analog in the codebase. Use RESEARCH.md Pattern 4 (vanilla JS DOM manipulation on Mermaid SVG) as the reference. |
| (Mermaid.js CDN include) | config | N/A | No existing Mermaid usage in the project. Follow the CDN include pattern from HTMX/Tailwind/FontAwesome but add to `database.html` only (not `base.html`), since Mermaid is only needed on this page. |

## Metadata

**Analog search scope:** `app/blueprints/admin/`, `app/middleware/`, `app/templates/admin/`
**Files scanned:** 4 primary analogs (all self-modifications to existing files)
**Pattern extraction date:** 2026-05-19
