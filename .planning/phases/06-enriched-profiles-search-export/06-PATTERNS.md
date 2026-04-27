# Phase 6: Enriched Profiles & Search Export - Pattern Map

**Mapped:** 2026-04-26
**Files analyzed:** 13 (6 templates, 4 service additions, 4 new endpoints, 1 new model+cache service, 1 JS module)
**Analogs found:** 13 / 13 (all have strong precedents in repo)

---

## File Classification

| New / Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---------------------|------|-----------|----------------|---------------|
| `app/blueprints/search/__init__.py` (new endpoints `/api/profile/<id>/m365`, `/genesys`, `/copy`, `/export.csv`) | blueprint route | request-response (HTMX fragment) | `app/blueprints/search/__init__.py:680-718` (`/api/signin-logs/<id>`, `/api/genesys-licenses/<id>`) | exact |
| `app/services/graph_service.py` (extend `_get_select_fields`, add `get_authentication_methods`, `get_license_details`, `get_subscribed_skus`) | service | request-response (Graph API) | `app/services/graph_service.py:391-448` (`get_sign_in_logs`) | exact (same file, same patterns) |
| `app/services/sku_catalog_cache.py` (new) | service | batch / scheduled refresh | `app/services/genesys_cache_db.py` (`GenesysCacheDB`) | exact |
| `app/models/external_service.py` (REUSE: store `subscribedSkus` as `service_name='graph', data_type='sku'`) | model | CRUD | `app/models/external_service.py:14-101` (`ExternalServiceData`) | exact (no new model needed) |
| `app/templates/search/_profile_section.html` (new partial) | component / template | server-render | (none — first generic collapsible partial) See sibling reuse: existing inline expanded card in `search/__init__.py:1584+` | new pattern, anchored to UI-SPEC |
| `app/templates/search/_m365_section.html` (new partial) | component / template | server-render (HTMX target) | inline render in `_render_signin_logs` (`search/__init__.py:2484-2559`) | role-match (extract inline → partial) |
| `app/templates/search/_genesys_section.html` (new partial) | component / template | server-render (HTMX target) | inline render in `_render_genesys_licenses` (`search/__init__.py:2574-2620`) | role-match (extract inline → partial) |
| `app/templates/search/_source_chip.html` (new partial) | component / template | server-render | inline span chips in `_render_signin_logs` (e.g. `text-xs text-gray-500`) | partial-match |
| `app/templates/search/_permission_warning.html` (new partial) | component / template | server-render | inline warning HTML in `_render_signin_logs:2487-2492` (`bg-red-50 text-red-700`) | role-match (degrade red→amber per UI-SPEC) |
| `app/templates/search/_export_buttons.html` (new partial) | component / template | server-render | search button at `app/templates/search/index.html:21-25` (`bg-ttcu-yellow`) | role-match |
| `app/static/js/clipboard.js` (new, ≤30 lines) | utility | event-driven (DOM → clipboard) | inline `htmx:responseError` listener in `app/templates/search/index.html:100-111`; `showToast()` already in `base.html:256` | role-match |
| `app/container.py` (register `sku_catalog`) | config | bootstrap | `app/container.py:143` (`container.register("genesys_cache", lambda c: GenesysCacheDB())`) | exact |
| `app/services/refresh_employee_profiles.py` or `token_refresh_service.py` (hook daily SKU refresh) | service | background-thread / scheduled | `app/services/genesys_cache_db.py:109-164` (`refresh_all_caches`) | exact |

---

## Pattern Assignments

### `app/blueprints/search/__init__.py` — new HTMX endpoints (controller, request-response)

**Analog:** `app/blueprints/search/__init__.py:680-718` (`get_signin_logs`, `get_genesys_licenses`)

**Imports pattern** (lines 1-28 of the file — already in place, do not re-add):

```python
from flask import Blueprint, render_template, request, jsonify, current_app, g
from app.middleware.auth import require_role
from app.utils.error_handler import handle_errors
from markupsafe import escape as html_escape
import logging

logger = logging.getLogger(__name__)
```

**Auth + audit + HTMX-fragment pattern (COPY VERBATIM)** (lines 680-703):

```python
@search_bp.route("/api/signin-logs/<user_id>")
@require_role("viewer")
@handle_errors(json_response=True)
def get_signin_logs(user_id):
    """Get Azure AD sign-in logs for a user via HTMX."""
    graph_service = current_app.container.get("graph_service")
    logs = graph_service.get_sign_in_logs(user_id)

    # Audit log the access
    audit_service = current_app.container.get("audit_logger")
    user_email = getattr(g, "user", "unknown")
    audit_service.log_search(
        user_email=user_email,
        search_query=f"signin_logs:{user_id}",
        results_count=len(logs) if logs else 0,
        services=["Graph"],
        ip_address=request.headers.get("X-Forwarded-For", request.remote_addr),
        user_agent=request.headers.get("User-Agent"),
        success=logs is not None,
    )

    if request.headers.get("HX-Request"):
        return _render_signin_logs(logs)
    return jsonify({"logs": logs})
```

**Apply to all four new endpoints:**
- `/api/profile/<id>/m365` — `services=["Graph"]`, `search_query=f"profile_m365:{id}"`
- `/api/profile/<id>/genesys` — `services=["Genesys"]`, `search_query=f"profile_genesys:{id}"`
- `/api/profile/<id>/copy` — returns plain text (no HTMX render); `search_query=f"profile_copy:{id}"`
- `/api/profile/<id>/export.csv` — returns `text/csv` with `Content-Disposition: attachment`; `search_query=f"profile_export:{id}"`

**For CSV response:** use `make_response()` (already imported at line 6) with headers:

```python
from flask import make_response

resp = make_response(csv_body)
resp.headers["Content-Type"] = "text/csv"
resp.headers["Content-Disposition"] = f'attachment; filename="whodis-{username}-{yyyymmdd}.csv"'
return resp
```

---

### `app/services/graph_service.py` — service additions (service, request-response)

**Analog:** same file, lines 391-448 (`get_sign_in_logs`).

**Method shape pattern (COPY VERBATIM)** (lines 391-448):

```python
def get_sign_in_logs(
    self, user_id: str, top: int = 25
) -> Optional[List[Dict[str, Any]]]:
    """Get recent sign-in logs for a user from Azure AD audit logs.

    Requires AuditLog.Read.All permission on the app registration.
    """
    token = self.get_access_token()
    if not token:
        logger.error("Failed to get Graph API access token for sign-in logs")
        return None

    try:
        url = f"{self.graph_base_url}/auditLogs/signIns"
        params = { ... }
        response = self._make_request("GET", url, token, params=params)
        data = self._handle_response(response)

        if not data or "value" not in data:
            return []
        # transform...
        return logs
    except Exception as e:
        logger.error(f"Error fetching sign-in logs for user {user_id}: {str(e)}")
        return None
```

**Three new methods follow this exact shape:**

| Method | URL | Permission docstring note |
|--------|-----|---------------------------|
| `get_authentication_methods(user_id)` | `/users/{id}/authentication/methods` | `Requires UserAuthenticationMethod.Read.All` |
| `get_license_details(user_id)` | `/users/{id}/licenseDetails` | (uses `User.Read.All` — already granted) |
| `get_subscribed_skus()` | `/subscribedSkus` | `Requires Organization.Read.All` |

**Permission-degradation pattern (D-06):** when `_make_request` returns 403, return `{"error": "permission_missing", "permission": "<name>"}` instead of `None` so the renderer can produce the inline amber banner. Log ERROR once per startup naming the missing permission (use module-level flag dict to dedupe).

**Extend `_get_select_fields` (lines 245-267)** — append:
```python
"signInActivity",     # D-01 — needs AuditLog.Read.All + Premium P1
"assignedLicenses",   # D-04
```

**Extend `_process_user_data` (lines 308-328)** — pass through the two new fields into the result dict next to `lastPasswordChangeDateTime`.

---

### `app/services/sku_catalog_cache.py` (NEW — service, scheduled refresh)

**Analog:** `app/services/genesys_cache_db.py` (`GenesysCacheDB`, lines 1-220).

**Class skeleton pattern** (mirror `genesys_cache_db.py:14-44`):

```python
"""SKU catalog cache service — daily refresh of /subscribedSkus from Graph."""
import logging
from typing import Optional
from datetime import datetime, timezone, timedelta
from app.database import db
from app.services.base import BaseConfigurableService
from app.models.external_service import ExternalServiceData

logger = logging.getLogger(__name__)


class SkuCatalogCache(BaseConfigurableService):
    """Database-backed SKU GUID → friendly name catalog (24h TTL)."""

    def __init__(self):
        super().__init__(config_prefix="graph")

    @property
    def refresh_period_hours(self) -> int:
        return int(self._get_config("sku_cache_refresh_hours", "24"))
```

**`needs_refresh()` pattern** (copy from `genesys_cache_db.py:72-107`) — substitute `service_name='graph'`, `data_type='sku'`.

**`refresh()` pattern** (copy shape from `genesys_cache_db.py:166-219` `_refresh_groups`) — call `graph_service.get_subscribed_skus()`, then for each SKU:
```python
ExternalServiceData.update_service_data(
    service_name="graph",
    data_type="sku",
    service_id=sku["skuId"],
    name=sku.get("skuPartNumber"),  # friendly fallback
    description=sku.get("displayName"),  # nicer name when present
    raw_data=sku,
)
```

**Lookup helper** — mirror `ExternalServiceData.get_genesys_skill_name` style (line 188):
```python
def get_sku_name(self, sku_id: str) -> Optional[str]:
    return ExternalServiceData.get_name_by_id("graph", "sku", sku_id)
```

**Container registration** (mirror `app/container.py:143`):
```python
container.register("sku_catalog", lambda c: SkuCatalogCache())
```

**Hook into existing daily refresh** — `app/services/refresh_employee_profiles.py` already runs daily; add `current_app.container.get("sku_catalog").refresh()` to its job loop (or `token_refresh_service.py` if scheduling lives there — verify in research).

---

### `app/models/external_service.py` — REUSE (model, CRUD)

**No new model needed.** SKU catalog reuses `ExternalServiceData` with `service_name='graph', data_type='sku'`. Lines 35-101 (`get_service_data`, `update_service_data`) provide everything needed.

**For Phase 6 enriched fields (signInActivity, MFA methods, license list):** these flow through `EmployeeProfile.raw_data` JSONB (D-07, 24h TTL — Phase 1 cache). No model change. Verify `EmployeeProfiles.create_or_update_profile` (`app/models/employee_profiles.py:64-102`) accepts the new fields via the `raw_data` payload — it does, because `raw_data` is JSONB.

---

### `app/templates/search/_m365_section.html` (NEW — component, HTMX response fragment)

**Analog:** `_render_signin_logs` at `app/blueprints/search/__init__.py:2484-2559`.

**Tailwind / FontAwesome pattern (extract inline → Jinja partial)** (lines 2501-2511):
```html
<div class="max-h-96 overflow-y-auto border border-gray-200 rounded-md">
  <table class="w-full text-xs">
    <thead class="bg-gray-50 sticky top-0">
      <tr>
        <th class="px-3 py-2 text-left text-gray-600 font-medium">Date/Time</th>
        ...
      </tr>
    </thead>
    <tbody>
      {% for log in logs %}
        <tr class="{{ 'bg-white' if loop.index0 % 2 == 0 else 'bg-gray-50' }}">
          ...
        </tr>
      {% endfor %}
    </tbody>
  </table>
</div>
```

**Empty state pattern** (lines 2494-2499):
```html
<div class="p-3 bg-gray-50 text-gray-500 rounded-md text-sm">
  <i class="fas fa-info-circle mr-1"></i>No Microsoft 365 data available for this user.
</div>
```

**Source chip pattern** (UI-SPEC, line 110): `<span class="text-xs text-gray-500">[Graph]</span>` — emit per field row via `_source_chip.html`.

**Permission-warning pattern (D-06, UI-SPEC line 112)**: `text-amber-700 bg-amber-50 border-l-4 border-amber-400 px-4 py-2 text-sm` — different color from analog's red (UI-SPEC explicitly distinguishes informational amber from error red).

---

### `app/templates/search/_genesys_section.html` (NEW)

**Analog:** `_render_genesys_licenses` at `app/blueprints/search/__init__.py:2574-2620`.

**Pill / chip rendering pattern** (lines 2590-2620): existing `flex flex-wrap gap-2` with per-license pill. Phase 6 extends to render queues, skills (with proficiency bar), and presence dot.

**Presence indicator pattern (UI-SPEC line 86):**
- `text-green-600` + filled dot — Available
- `text-amber-600` + filled dot — Away
- `text-gray-400` + filled dot — Offline

---

### `app/templates/search/_export_buttons.html` (NEW)

**Analog:** search button at `app/templates/search/index.html:21-25`:

```html
<button type="submit"
    class="absolute right-2 top-1/2 transform -translate-y-1/2
           bg-ttcu-yellow hover:bg-yellow-500 text-gray-900
           px-6 py-2 rounded-full font-medium transition-all duration-150
           hover:scale-105 hover:shadow-lg flex items-center">
    <i class="fas fa-search mr-2"></i>
    Search
</button>
```

**Apply to Copy / Export CSV** — same `bg-ttcu-yellow` + `px-6 py-2 rounded-full` precedent. Two buttons side-by-side; mobile stacks vertically with `w-full sm:w-auto` (UI-SPEC line 136).

---

### `app/static/js/clipboard.js` (NEW, ≤30 lines)

**Analog:** `app/templates/search/index.html:99-117` (`htmx:responseError` listener pattern); `showToast()` function in `app/templates/base.html:256`.

**Pattern to copy:**

```javascript
function copyProfileToClipboard(cardEl) {
    const lines = [];
    cardEl.querySelectorAll('[data-copy-field]').forEach(el => {
        const label = el.dataset.copyField;
        const value = el.textContent.trim();
        lines.push(`${label}: ${value}`);
    });
    const text = lines.join('\n');
    navigator.clipboard.writeText(text)
        .then(() => showToast('Copied profile to clipboard', 'success'))
        .catch(() => showToast("Couldn't copy. Select the text and copy manually.", 'error'));
}
```

**Reuses existing globals:** `showToast(msg, level)` from `base.html:256`, no new dependencies. WYSIWYG semantics (D-12): if a section was never expanded, its container is empty in the DOM, so `data-copy-field` markers will be absent — emit `Section: Not loaded` lines from a parent template based on `aria-expanded` state.

---

## Shared Patterns

### Authentication + Authorization
**Source:** `app/middleware/auth.py` (`@require_role`), used at `app/blueprints/search/__init__.py:681,707`
**Apply to:** All four new endpoints (`/m365`, `/genesys`, `/copy`, `/export.csv`).
```python
@search_bp.route("/api/profile/<user_id>/<section>")
@require_role("viewer")
@handle_errors(json_response=True)
def ...
```

### Error Handling (route-level)
**Source:** `app/utils/error_handler.py:12-80` (`handle_errors` decorator)
**Apply to:** All new route functions. `json_response=True` for endpoints that may be called as fallback JSON; HTMX fragment otherwise.

### Audit Logging
**Source:** `app/services/audit_service_postgres.py` via `current_app.container.get("audit_logger")`. Pattern at `search/__init__.py:689-699`.
**Apply to:** All new endpoints. Use `audit_service.log_search()` with `services=["Graph"]` or `["Genesys"]` and a descriptive `search_query` prefix.

### Service Container Resolution
**Source:** `app/container.py:143-148`
**Apply to:** All new service code. Never `from app.services.X import x_singleton`; always `current_app.container.get("service_name")`.

### Configuration Caching (service base)
**Source:** `app/services/base.py:22-60` (`BaseConfigurableService._get_config`)
**Apply to:** `SkuCatalogCache` (subclass `BaseConfigurableService` with `config_prefix="graph"`).

### Logging
**Source:** module-level `logger = logging.getLogger(__name__)` everywhere
**Apply to:** All new modules. Follow `logger.error(f"...: {str(e)}", exc_info=True)` for failures, `logger.info` for refresh events, `logger.debug` for per-request traces.

### HTMX Partial Response
**Source:** `search/__init__.py:701-703` — return raw HTML if `HX-Request` header present, JSON otherwise.
**Apply to:** `/m365` and `/genesys` endpoints.

### Permission-Degradation Banner (NEW project pattern, anchored to UI-SPEC)
**Source for color tokens:** UI-SPEC line 87 (amber, not red)
**Apply to:** `_permission_warning.html` partial. Rendered inline when `get_authentication_methods` / `get_sign_in_logs` returns the `{"error": "permission_missing", "permission": "..."}` sentinel. Logged once per startup (dedupe via module-level flag).

---

## No Analog Found

| File | Role | Data Flow | Reason | Fallback Source |
|------|------|-----------|--------|-----------------|
| `_profile_section.html` (generic collapsible shell) | template | server-render | No prior generic collapsible Jinja partial in repo; existing collapsibles are inline in admin pages and use bespoke HTML. | UI-SPEC §Component Inventory (verbatim) |
| `_source_chip.html` | template | server-render | New pattern; chips are first-class in this phase. | UI-SPEC §Color (`text-xs text-gray-500`) |
| `clipboard.js` (DOM serializer) | utility | event-driven | No prior client-side clipboard code in repo. `navigator.clipboard.writeText` is browser-standard. | UI-SPEC line 132 + D-13 |

For these three, the planner should follow UI-SPEC verbatim (file is at `.planning/phases/06-enriched-profiles-search-export/06-UI-SPEC.md`).

---

## Metadata

**Analog search scope:**
- `app/blueprints/search/__init__.py` (3,000+ lines — read targeted ranges only)
- `app/services/{graph_service, genesys_service, genesys_cache_db, base}.py`
- `app/models/{employee_profiles, external_service}.py`
- `app/templates/{base.html, search/index.html}`
- `app/utils/error_handler.py`
- `app/container.py`

**Files scanned:** 12
**Pattern extraction date:** 2026-04-26
