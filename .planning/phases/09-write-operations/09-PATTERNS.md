# Phase 9: Write Operations - Pattern Map

**Mapped:** 2026-05-17
**Files analyzed:** 11 (new/modified)
**Analogs found:** 11 / 11

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `app/services/ldap_service.py` (MODIFY) | service | request-response | self (existing read methods) | exact |
| `app/services/graph_service.py` (MODIFY) | service | request-response | self (`get_license_details`) | exact |
| `app/services/write_operations.py` (NEW) | service | request-response | `app/services/audit_service_postgres.py` | role-match |
| `app/blueprints/search/__init__.py` (MODIFY) or `write_routes.py` (NEW) | controller | request-response | `app/blueprints/admin/api_tokens.py` | exact |
| `app/templates/search/_write_confirm_modal.html` (NEW) | component | event-driven | `app/templates/admin/compliance_violations.html:184-200` | role-match |
| `app/templates/search/_password_banner.html` (NEW) | component | event-driven | `app/templates/base.html` showBanner (lines 336-360) | role-match |
| `app/templates/search/_ad_actions.html` (NEW) | component | event-driven | `app/templates/search/_m365_section.html` | role-match |
| `app/templates/search/_license_actions.html` (NEW) | component | event-driven | `app/templates/search/_m365_section.html` | role-match |
| `app/templates/search/_license_select.html` (NEW) | component | request-response | `app/templates/search/_permission_warning.html` | partial |
| `app/static/js/write-actions.js` (NEW) | utility | event-driven | `app/templates/base.html` showToast (lines 256-334) | role-match |
| `app/container.py` (MODIFY) | config | N/A | self (existing registrations) | exact |

## Pattern Assignments

### `app/services/ldap_service.py` (service, request-response) -- MODIFY

**Analog:** Self -- existing `test_connection()` and `search_user()` methods

**Connection pattern** (lines 69-99):
```python
def test_connection(self) -> bool:
    """Test if the service is available and properly configured."""
    try:
        server = Server(
            self.host,
            port=self.port,
            use_ssl=self.use_ssl,
            get_info=ALL,
            connect_timeout=self.connect_timeout,
        )

        with Connection(
            server,
            user=self.bind_dn,
            password=self.bind_password,
            auto_bind=True,
            receive_timeout=self.operation_timeout,
        ) as conn:
            # Test with a simple search
            conn.search(
                self.base_dn,
                "(objectClass=*)",
                search_scope=SUBTREE,
                attributes=["dn"],
                size_limit=1,
            )
            return True
    except Exception as e:
        logger.error(f"LDAP connection test failed: {str(e)}")
        return False
```

**Key pattern notes:** Each method creates its own `Server` + `Connection` with `with` statement. Properties (`self.host`, `self.bind_dn`, etc.) pull from encrypted config via `_get_config()`. New write methods (`unlock_account`, `reset_password`, `set_account_enabled`) must follow this same per-operation connection pattern. Import `MODIFY_REPLACE` from `ldap3` alongside existing imports at line 4.

**Imports to add** (extend existing line 4):
```python
from ldap3 import Server, Connection, ALL, SUBTREE, MODIFY_REPLACE
```

**Error handling pattern** (consistent across all methods):
```python
except LDAPException as e:
    logger.error(f"LDAP operation error for {user_dn}: {e}")
    return False
```

---

### `app/services/graph_service.py` (service, request-response) -- MODIFY

**Analog:** Self -- `get_license_details()` (lines 455-487) and `_permission_missing()` (lines 402-414)

**Read method pattern to copy for writes** (lines 455-487):
```python
def get_license_details(self, user_id: str) -> Optional[Any]:
    """Get assigned license details for a user from Graph."""
    token = self.get_access_token()
    if not token:
        logger.error("Failed to get Graph API access token for license details")
        return None

    try:
        url = f"{self.graph_base_url}/users/{user_id}/licenseDetails"
        response = self._make_request("GET", url, token)
        data = self._handle_response(response)
        if not data or "value" not in data:
            return []
        return data["value"]
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 403:
            return self._permission_missing("User.Read.All")
        logger.error(
            f"HTTP error fetching license details for user {user_id}: {str(e)}",
            exc_info=True,
        )
        return None
    except Exception as e:
        logger.error(
            f"Error fetching license details for user {user_id}: {str(e)}",
            exc_info=True,
        )
        return None
```

**Permission missing sentinel** (lines 402-414):
```python
def _permission_missing(self, permission: str) -> Dict[str, Any]:
    """Return the D-06 sentinel and log ERROR once per startup per permission."""
    if permission not in _logged_missing_perms:
        logger.error(
            f"Graph permission missing: {permission} -- feature will display "
            f"inline degradation banner",
        )
        _logged_missing_perms.add(permission)
    return {"error": "permission_missing", "permission": permission}
```

**`_make_request` from base** (`app/services/base.py` lines 105-165):
```python
@handle_service_errors(raise_errors=True)
def _make_request(
    self, method: str, url: str, token: Optional[str] = None, **kwargs
) -> requests.Response:
    kwargs.setdefault("timeout", self.timeout)
    if "headers" not in kwargs:
        kwargs["headers"] = self._get_headers(token)
    elif token and "Authorization" not in kwargs["headers"]:
        kwargs["headers"]["Authorization"] = f"Bearer {token}"

    try:
        logger.debug(f"{method} {url}")
        response = requests.request(method, url, **kwargs)
        logger.debug(f"Response: {response.status_code}")
        response.raise_for_status()
        return response
    except Timeout:
        raise TimeoutError(...)
    except ConnectionError as e:
        raise ConnectionError(...)
    except requests.HTTPError as e:
        logger.error(f"HTTP error from {url}: {e.response.status_code} - {e.response.text}")
        raise
```

**Key pattern notes:** New write methods (`assign_license`, `remove_license`, `swap_license`) use `self._make_request("POST", url, token, json=body)`. The `json=` kwarg is passed through to `requests.request()`. Use the same `try/except requests.HTTPError` + `_permission_missing()` sentinel for 403 responses. Write methods need `LicenseAssignment.ReadWrite.All` permission.

---

### `app/services/write_operations.py` (service, request-response) -- NEW

**Analog:** `app/services/audit_service_postgres.py` (lines 71-93) for audit pattern; `app/services/base.py` (lines 22-60) for base class

**Base class pattern** (`app/services/base.py` lines 22-51):
```python
class BaseConfigurableService:
    """Base class for services that use configuration."""

    def __init__(self, config_prefix: str):
        self._config_prefix = config_prefix
        self._config_cache: Dict[str, Any] = {}

    def _get_config(self, key: str, default: Any = None) -> Any:
        full_key = f"{self._config_prefix}.{key}"
        if full_key not in self._config_cache:
            self._config_cache[full_key] = config_get(full_key, default)
        return self._config_cache[full_key]
```

**Audit logging pattern** (`app/services/audit_service_postgres.py` lines 71-93):
```python
def log_admin_action(
    self,
    user_email: str,
    action: str,
    target: str,
    details: Dict[str, Any],
    **kwargs,
) -> None:
    """Log an administrative action."""
    try:
        AuditLog.log_admin_action(
            user_email=user_email,
            action=action,
            target_resource=target,
            additional_data=details,
            **kwargs,
        )
    except Exception as e:
        logger.error(f"Failed to log admin action: {e}")
        try:
            db.session.rollback()
        except Exception:
            pass
```

**Key pattern notes:** `WriteOperationsService` is a coordinator -- it calls LDAPService/GraphService methods and wraps each call with audit logging. Access underlying services via `current_app.container.get()`. Follow the DI lazy-property pattern from CLAUDE.md.

---

### `app/blueprints/search/write_routes.py` or `__init__.py` (controller, request-response) -- NEW/MODIFY

**Analog:** `app/blueprints/admin/api_tokens.py` (lines 1-76) for admin write endpoint with HX-Trigger + audit

**Imports pattern** (`api_tokens.py` lines 1-12):
```python
import logging

from flask import current_app, g, jsonify, render_template, request
from app.middleware.auth import require_role
from app.middleware.csrf import csrf_double_submit

logger = logging.getLogger(__name__)
```

**Write endpoint with CSRF + audit + HX-Trigger** (`api_tokens.py` lines 23-76):
```python
@require_role("admin")
@csrf_double_submit.protect
def create_api_token():
    token_service = current_app.container.get("external_api_token_service")

    name = request.form.get("name", "").strip()

    # Validate name
    if not name or len(name) < 2:
        return jsonify({
            "success": False,
            "error": "Token name must be at least 2 characters."
        }), 400

    try:
        model, raw_token = token_service.create_token(
            name=name, created_by=g.user
        )

        # Audit log
        current_app.container.get("audit_logger").log_admin_action(
            user_email=g.user,
            action="api_token_created",
            target=name,
            details={
                "token_id": model.id,
                "token_prefix": model.token_prefix,
            },
            user_role=getattr(request, "user_role", None),
            ip_address=request.headers.get("X-Forwarded-For", request.remote_addr),
            user_agent=request.headers.get("User-Agent"),
        )

        response = jsonify({
            "success": True,
            "token": raw_token,
            "name": name,
        })
        response.headers["HX-Trigger"] = "tokenCreated"
        return response

    except Exception as e:
        logger.error(f"Token creation failed: {str(e)}", exc_info=True)
        return jsonify({...}), 500
```

**HTMX POST endpoint pattern from search blueprint** (`search/__init__.py` lines 560-613):
```python
@search_bp.route("/api/notes/<email>", methods=["POST"])
@require_role("viewer")
@handle_errors(json_response=True)
def add_search_note(email):
    from app.models.user_note import UserNote

    # Check if this is an Htmx request
    if request.headers.get("HX-Request"):
        note_text = request.form.get("note", "").strip()
    else:
        data = request.get_json()
        note_text = data.get("note", "").strip()

    if not note_text:
        if request.headers.get("HX-Request"):
            return '<div class="text-red-600 text-sm">Note cannot be empty</div>', 400
        return jsonify({"success": False, "message": "Note cannot be empty"}), 400
    # ... service call + response
```

**Key pattern notes:** Write endpoints use `@require_role("admin")` (not viewer). Include `@csrf_double_submit.protect` for CSRF. Use `make_response("", 200)` with `HX-Trigger` header containing `json.dumps({"showToast": {...}})` for toast feedback. For password reset, return HTML fragment (password banner) instead of empty response.

---

### `app/templates/search/_write_confirm_modal.html` (component, event-driven) -- NEW

**Analog:** `app/templates/admin/compliance_violations.html` (lines 184-200)

**Modal structure pattern:**
```html
<!-- Violation Details Modal -->
<div id="violation-modal" class="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full hidden">
    <div class="relative top-20 mx-auto p-5 border w-5/6 max-w-4xl shadow-lg rounded-md bg-white">
        <div class="mt-3">
            <div class="flex items-center justify-between mb-4">
                <h3 class="text-lg font-medium text-gray-900" id="violation-modal-title">Violation Details</h3>
                <button onclick="closeViolationModal()" class="text-gray-400 hover:text-gray-600">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            
            <div id="violation-modal-content">
                <!-- Content loaded dynamically -->
            </div>
        </div>
    </div>
</div>
```

**Key pattern notes:** Confirmation modal must add: target user name/email display, freeform reason textarea, Confirm button disabled until reason >= 3 chars. High-risk actions (disable, license remove) get amber warning banner + red confirm button per D-14. Use `hidden` class toggle for show/hide. Form submits via `hx-post` with `hx-swap="none"`.

---

### `app/templates/search/_password_banner.html` (component, event-driven) -- NEW

**Analog:** `app/templates/base.html` `showBanner()` function (lines 336-360)

**Banner styling pattern:**
```javascript
function showBanner(message, type = 'info', duration = 6000) {
    const banner = document.getElementById('alert-banner');
    // Style based on type
    let bgColor, borderColor, iconClass, textColor;
    switch(type) {
        case 'success':
            bgColor = 'bg-green-100';
            borderColor = 'border-green-400';
            iconClass = 'fas fa-check-circle text-green-400';
            textColor = 'text-green-700';
            break;
        case 'error':
            bgColor = 'bg-red-100';
            borderColor = 'border-red-400';
            iconClass = 'fas fa-times-circle text-red-400';
            textColor = 'text-red-700';
            break;
```

**Key pattern notes:** Password banner is NOT auto-dismissing (stays until manually closed per D-05). Include show/hide toggle for password and copy-to-clipboard button. Use Tailwind classes consistent with the existing banner styling. This is a Jinja partial returned as HTMX fragment from the password reset endpoint.

---

### `app/templates/search/_ad_actions.html` and `_license_actions.html` (component, event-driven) -- NEW

**Analog:** `app/templates/search/_m365_section.html` (lines 1-40 for structure and conditional rendering)

**Template guard pattern:**
```html
{# Conditional rendering with .get() for safety #}
{% set warnings = data.get('permission_warnings', []) %}
{% set has_data = (
    data.get('department') or data.get('manager') or data.get('employee_id')
    or data.get('licenses') or data.get('mfa') or data.get('last_sign_in')
) %}
```

**Key pattern notes:** Action buttons render inside existing profile section fragments. Gate with `{% if g.role == 'admin' %}` per D-12. Buttons use `hx-post` targeting write endpoints, `hx-swap="none"`, and trigger the confirmation modal via JS. Follow Tailwind button classes from existing templates.

---

### `app/container.py` (config) -- MODIFY

**Analog:** Self -- existing service registration (lines 115-174)

**Registration pattern:**
```python
# Import services here to avoid circular imports
from app.services.ldap_service import LDAPService

# Search services (depend on config)
container.register("ldap_service", lambda c: LDAPService())
container.register("genesys_service", lambda c: GenesysCloudService())
container.register("graph_service", lambda c: GraphService())
```

**Key pattern notes:** Register `write_operations` service: `container.register("write_operations", lambda c: WriteOperationsService())`. Import inside `register_services()` to avoid circular imports.

---

## Shared Patterns

### Authentication + Authorization
**Source:** `app/middleware/auth.py` (used in `app/blueprints/admin/api_tokens.py` lines 15,23)
**Apply to:** All write endpoints

```python
@require_role("admin")
@csrf_double_submit.protect
def write_endpoint():
    # g.user contains authenticated user email
    # g.role contains resolved role
```

### CSRF Protection
**Source:** `app/middleware/csrf.py` via `csrf_double_submit.protect`
**Apply to:** All write endpoints (POST)

```python
from app.middleware.csrf import csrf_double_submit

@csrf_double_submit.protect
def my_write_endpoint():
    ...
```

### Error Handling (Routes)
**Source:** `app/utils/error_handler.py` lines 12-60
**Apply to:** All write endpoints

```python
@handle_errors(json_response=True)
def my_endpoint():
    ...
```

### Error Handling (Services)
**Source:** `app/utils/error_handler.py` via `handle_service_errors`
**Apply to:** `WriteOperationsService` methods

```python
from app.utils.error_handler import handle_service_errors

@handle_service_errors(raise_errors=False)
def my_service_method(self):
    ...
```

### Audit Logging
**Source:** `app/services/audit_service_postgres.py` lines 71-93
**Apply to:** Every write action endpoint

```python
current_app.container.get("audit_logger").log_admin_action(
    user_email=g.user,
    action="unlock_account",
    target=user_dn,
    details={"reason": reason, "success": success, "target_name": display_name},
    ip_address=request.headers.get("X-Forwarded-For", request.remote_addr),
    user_agent=request.headers.get("User-Agent"),
)
```

### HX-Trigger Response Pattern
**Source:** `app/blueprints/admin/api_tokens.py` line 75
**Apply to:** All write endpoint success responses

```python
import json
from flask import make_response

response = make_response("", 200)
response.headers["HX-Trigger"] = json.dumps({
    "showToast": {"message": "Account unlocked successfully", "type": "success"}
})
return response
```

### DI Container Access
**Source:** `CLAUDE.md` and `app/blueprints/admin/api_tokens.py` line 31
**Apply to:** All route handlers and service coordinator

```python
ldap_service = current_app.container.get("ldap_service")
graph_service = current_app.container.get("graph_service")
audit_service = current_app.container.get("audit_logger")
```

### Toast/Banner Notification (Client-side)
**Source:** `app/templates/base.html` lines 256-334 (showToast), lines 336-360 (showBanner)
**Apply to:** `write-actions.js` HTMX event listener bridge

```javascript
// showToast already exists globally in base.html
function showToast(message, type = 'info', duration = 4000) { ... }
function showBanner(message, type = 'info', duration = 6000) { ... }
```

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `app/static/js/write-actions.js` | utility | event-driven | No existing standalone JS files for HTMX event bridging; closest is inline script in `base.html`. Pattern is straightforward: listen for HTMX `htmx:afterRequest` events and call existing `showToast()`/`showBanner()` functions. |

**Note:** The password generation utility (word list + digits + symbol) has no analog in the codebase. RESEARCH.md provides the complete implementation pattern for `generate_temp_password()`.

## Metadata

**Analog search scope:** `app/services/`, `app/blueprints/`, `app/templates/`, `app/middleware/`, `app/utils/`, `app/container.py`
**Files scanned:** ~25 (targeted by role classification)
**Pattern extraction date:** 2026-05-17
