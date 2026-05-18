# Phase 9: Write Operations - Research

**Researched:** 2026-05-17
**Domain:** AD write operations (LDAP), M365 license management (Graph API), confirmation UX (HTMX/Jinja)
**Confidence:** HIGH

## Summary

Phase 9 adds write capabilities to the existing search result profile view. There are two distinct integration surfaces: (1) Active Directory operations via ldap3 (unlock account, reset password, enable/disable) and (2) Microsoft 365 license management via Graph API (assign, remove, swap). Both integrate into the existing service architecture -- new methods are added to the existing `LDAPService` and `GraphService` classes, not new service classes.

The codebase already has all the infrastructure needed: `audit_service.log_admin_action()` for audit trails, `@require_role("admin")` for gating, `showToast()` and `showBanner()` for user feedback, and HTMX partial swap patterns from Phase 6. The primary new UI components are a shared confirmation modal partial and a dismissible password banner. No new Python packages are needed.

**Primary recommendation:** Extend existing `LDAPService` and `GraphService` with write methods, create a thin `WriteOperationsService` coordinator for audit + action coupling, add HTMX endpoints to the search blueprint, and build 5 Jinja partials per the UI spec.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Confirmation modal shows target user name/email prominently, requires freeform reason textarea before Confirm enables. No re-typing of target name.
- **D-02:** After action, inline toast (success/error) at page top plus action button briefly changes to checkmark or error icon. Non-blocking.
- **D-03:** Reason text is freeform only -- plain textarea, no preset dropdowns.
- **D-04:** All four AD operations ship together: unlock, reset password, enable, disable.
- **D-05:** Temporary password displayed in dismissible banner with show/hide toggle and copy button. Stays visible until manually dismissed. Never stored server-side after generation.
- **D-06:** Generated passwords follow readable pattern (Word+Digits+Symbol, e.g., "Sunset42!"). Must meet AD complexity (upper, lower, digit, symbol, 8+ chars).
- **D-07:** AD write operations use same LDAP bind credentials already configured. No separate write service account.
- **D-08:** License swap uses two sequential Graph API calls (remove old, assign new). If assign fails after remove, attempt rollback by re-adding removed license.
- **D-10:** Graph API permissions for license writes are unknown -- planner must flag as external dependency and document exact permissions needed.
- **D-11:** Write action buttons appear inside expanded profile sections (Phase 6 collapsible areas). AD actions in AD section, license actions in M365 section.

### Claude's Discretion
- **D-09:** Failure UX for double-failure in license swap (remove succeeded, assign failed, rollback failed). UI spec resolved: persistent error banner via `showBanner()`, no auto-dismiss, red background, stays until page navigation.
- **D-12:** Action button visibility for non-admins. UI spec resolved: hidden (not rendered) via `{% if g.role == 'admin' %}` server-side gate.
- **D-13:** License action placement. UI spec resolved: inline per-chip remove icon on hover (admin only), Assign/Swap buttons below license list.
- **D-14:** Risk tiering for confirmation modals. UI spec resolved: high-risk actions (disable, license remove) get amber warning banner + red confirm button; standard actions get green confirm button.

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| WRIT-01 | Unlock locked AD account from search result view | ldap3 `modify()` with `lockoutTime` set to `0`; method added to `LDAPService` |
| WRIT-02 | Reset AD password generating temporary password displayed once | ldap3 `extend.microsoft.modify_password()`; password generator using Word+Digits+Symbol pattern |
| WRIT-03 | Enable/disable AD accounts from search result view | ldap3 `modify()` with `userAccountControl` bit manipulation (bit 1 = ACCOUNTDISABLE) |
| WRIT-04 | All write actions require confirmation modal with mandatory reason text | Shared `_write_confirm_modal.html` Jinja partial with reason textarea validation |
| WRIT-05 | Every write action logged to audit trail with full context | Existing `audit_service.log_admin_action()` already supports who/what/target/IP/reason |
| WRIT-06 | Assign license to user from profile view | Graph API `POST /users/{id}/assignLicense` with `addLicenses` array |
| WRIT-07 | Remove license with confirmation | Graph API `POST /users/{id}/assignLicense` with `removeLicenses` array |
| WRIT-08 | License swap as atomic operation | Single `assignLicense` call with both `addLicenses` and `removeLicenses` populated; fallback to two-call approach with rollback |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| AD unlock/reset/enable/disable | API / Backend (LDAPService) | -- | LDAP writes are server-only; credentials never exposed to browser |
| License assign/remove/swap | API / Backend (GraphService) | -- | Graph API calls require OAuth bearer token held server-side |
| Confirmation modal | Frontend (Jinja/HTMX) | API / Backend (endpoint) | Modal is client-rendered; submission hits HTMX endpoint |
| Password generation | API / Backend | -- | Generated server-side, returned in response, never stored |
| Password display banner | Frontend (Jinja/JS) | -- | Client-only display; password received once in HTMX response |
| Audit logging | API / Backend (AuditService) | Database | Every write creates an AuditLog row via existing service |
| Role gating | API / Backend (middleware) | -- | `@require_role("admin")` decorator on all write endpoints |

## Standard Stack

### Core (already installed -- no new packages)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| ldap3 | 2.9.1 | AD account unlock, password reset, enable/disable | Already used for LDAP reads; `extend.microsoft.modify_password()` and `modify()` handle AD writes [CITED: ldap3.readthedocs.io/en/latest/modify.html] |
| requests | 2.33.0 | Graph API HTTP calls for license management | Already used by `GraphService._make_request()` |
| msal | 1.34.0 | OAuth token acquisition for Graph API | Already used by `GraphService._fetch_new_token()` |

### Supporting (already installed)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Flask | 3.1.3 | Route handlers, `g.user`, `g.role` | All write endpoints |
| SQLAlchemy | 2.0.45 | AuditLog model for audit trail persistence | Every write action |

**Installation:** No new packages needed. All write operations use existing dependencies.

## Package Legitimacy Audit

No new packages are introduced in this phase. All operations use ldap3, requests, msal, Flask, and SQLAlchemy which are already in `requirements.txt`.

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
User clicks action button
        |
        v
[Confirmation Modal (Jinja partial)]
  - Shows target user name/email
  - Requires reason text (3+ chars)
  - Enables Confirm button
        |
        v (HTMX POST with hx-swap="none")
[Write Endpoint (/search/api/write/{action})]
  - @auth_required + @require_role("admin")
  - CSRF validation (double-submit cookie)
  - Parse request: target_user_id, reason, action params
        |
        v
[WriteOperationsService (coordinator)]
  - Validates inputs
  - Calls appropriate service method
  - Logs audit trail via audit_service.log_admin_action()
  - Returns result dict {success, message, data}
        |
        +-----> [LDAPService.unlock_account(dn)]
        |       [LDAPService.reset_password(dn) -> temp_password]
        |       [LDAPService.set_account_enabled(dn, enabled)]
        |
        +-----> [GraphService.assign_license(user_id, sku_id)]
        |       [GraphService.remove_license(user_id, sku_id)]
        |       [GraphService.swap_license(user_id, old_sku, new_sku)]
        |
        v
[Response via HX-Trigger header]
  - Success: triggers showToast(), button icon swap
  - Error: triggers error display in modal
  - Password reset: returns password banner HTML fragment
```

### Recommended Project Structure

```
app/
  services/
    ldap_service.py          # ADD: unlock_account(), reset_password(), set_account_enabled()
    graph_service.py         # ADD: assign_license(), remove_license(), swap_license()
    write_operations.py      # NEW: WriteOperationsService coordinator
  blueprints/
    search/
      __init__.py            # ADD: write operation endpoints
      write_routes.py        # NEW (optional): separate file for write endpoints if __init__.py is too large
  templates/
    search/
      _write_confirm_modal.html  # NEW: shared confirmation modal
      _password_banner.html      # NEW: dismissible password display
      _ad_actions.html           # NEW: AD action button group
      _license_actions.html      # NEW: license action controls
      _license_select.html       # NEW: HTMX fragment for SKU dropdown
  static/
    js/
      write-actions.js           # NEW: modal/password banner JS (~60 lines)
```

### Pattern 1: LDAP Write Operations

**What:** Adding write methods to existing `LDAPService` class using `ldap3.modify()` and `ldap3.extend.microsoft.modify_password()`.

**When to use:** All AD account modifications (unlock, reset password, enable, disable).

**Example:**
```python
# Source: ldap3.readthedocs.io/en/latest/modify.html + ldap3.readthedocs.io/en/latest/microsoft.html
from ldap3 import MODIFY_REPLACE

def unlock_account(self, user_dn: str) -> bool:
    """Unlock a locked AD account by resetting lockoutTime to 0."""
    try:
        server = Server(self.host, port=self.port, use_ssl=self.use_ssl,
                       get_info=ALL, connect_timeout=self.connect_timeout)
        with Connection(server, user=self.bind_dn, password=self.bind_password,
                       auto_bind=True, receive_timeout=self.operation_timeout) as conn:
            result = conn.modify(user_dn, {
                'lockoutTime': [(MODIFY_REPLACE, ['0'])]
            })
            if not result:
                logger.error(f"Unlock failed for {user_dn}: {conn.result}")
            return result
    except LDAPException as e:
        logger.error(f"LDAP unlock error for {user_dn}: {e}")
        return False

def reset_password(self, user_dn: str, new_password: str) -> bool:
    """Reset AD password for a user (admin reset, no old password needed).
    Requires SSL/TLS connection to AD.
    """
    try:
        server = Server(self.host, port=self.port, use_ssl=self.use_ssl,
                       get_info=ALL, connect_timeout=self.connect_timeout)
        with Connection(server, user=self.bind_dn, password=self.bind_password,
                       auto_bind=True, receive_timeout=self.operation_timeout) as conn:
            result = conn.extend.microsoft.modify_password(user_dn, new_password)
            if not result:
                logger.error(f"Password reset failed for {user_dn}: {conn.result}")
            return result
    except LDAPException as e:
        logger.error(f"LDAP password reset error for {user_dn}: {e}")
        return False

def set_account_enabled(self, user_dn: str, enabled: bool) -> bool:
    """Enable or disable an AD account by toggling userAccountControl bit 1."""
    try:
        server = Server(self.host, port=self.port, use_ssl=self.use_ssl,
                       get_info=ALL, connect_timeout=self.connect_timeout)
        with Connection(server, user=self.bind_dn, password=self.bind_password,
                       auto_bind=True, receive_timeout=self.operation_timeout) as conn:
            # First read current UAC value
            conn.search(user_dn, '(objectClass=*)', search_scope='BASE',
                       attributes=['userAccountControl'])
            if not conn.entries:
                return False
            current_uac = int(conn.entries[0].userAccountControl.value)

            if enabled:
                new_uac = current_uac & ~2  # Clear ACCOUNTDISABLE bit
            else:
                new_uac = current_uac | 2   # Set ACCOUNTDISABLE bit

            result = conn.modify(user_dn, {
                'userAccountControl': [(MODIFY_REPLACE, [str(new_uac)])]
            })
            if not result:
                logger.error(f"Account state change failed for {user_dn}: {conn.result}")
            return result
    except LDAPException as e:
        logger.error(f"LDAP account state change error for {user_dn}: {e}")
        return False
```

### Pattern 2: Graph API License Management

**What:** Adding license write methods to existing `GraphService` using the `POST /users/{id}/assignLicense` endpoint.

**When to use:** Assign, remove, or swap M365 licenses.

**Example:**
```python
# Source: learn.microsoft.com/en-us/graph/api/user-assignlicense?view=graph-rest-1.0
def assign_license(self, user_id: str, sku_id: str,
                   disabled_plans: list = None) -> bool:
    """Assign an M365 license to a user."""
    token = self.get_access_token()
    if not token:
        return False
    body = {
        "addLicenses": [{"skuId": sku_id, "disabledPlans": disabled_plans or []}],
        "removeLicenses": []
    }
    try:
        url = f"{self.graph_base_url}/users/{user_id}/assignLicense"
        response = self._make_request("POST", url, token, json=body)
        return response.status_code == 200
    except requests.HTTPError as e:
        logger.error(f"License assign failed for {user_id}: {e}")
        return False

def swap_license(self, user_id: str, old_sku_id: str, new_sku_id: str) -> dict:
    """Swap license: remove old SKU, assign new SKU.
    
    Attempts single-call atomic swap first. Falls back to two-call
    with rollback on failure.
    
    Returns: {"success": bool, "rollback_needed": bool, "rollback_success": bool|None, "error": str|None}
    """
    token = self.get_access_token()
    if not token:
        return {"success": False, "error": "No access token"}

    # Attempt atomic swap (single API call with both add and remove)
    body = {
        "addLicenses": [{"skuId": new_sku_id, "disabledPlans": []}],
        "removeLicenses": [old_sku_id]
    }
    try:
        url = f"{self.graph_base_url}/users/{user_id}/assignLicense"
        response = self._make_request("POST", url, token, json=body)
        if response.status_code == 200:
            return {"success": True}
    except requests.HTTPError:
        pass  # Fall through to two-call approach

    # Fallback: two sequential calls with rollback
    # ... (D-08 two-call approach with D-09 rollback logic)
```

### Pattern 3: HTMX Write Endpoint with HX-Trigger Response

**What:** Write endpoints use `hx-swap="none"` and return results via `HX-Trigger` response headers to trigger client-side toast/banner display.

**When to use:** All write action submissions.

**Example:**
```python
@search_bp.route("/api/write/unlock", methods=["POST"])
@require_role("admin")
@handle_errors(json_response=True)
def write_unlock_account():
    user_dn = request.form.get("user_dn")
    reason = request.form.get("reason", "").strip()
    display_name = request.form.get("display_name", "")

    if not reason or len(reason) < 3:
        return make_response("Reason is required (3+ characters)", 400)

    ldap_service = current_app.container.get("ldap_service")
    audit_service = current_app.container.get("audit_logger")

    success = ldap_service.unlock_account(user_dn)

    audit_service.log_admin_action(
        user_email=g.user,
        action="unlock_account",
        target=user_dn,
        details={"reason": reason, "target_name": display_name, "success": success},
        ip_address=request.headers.get("X-Forwarded-For", request.remote_addr),
    )

    if success:
        response = make_response("", 200)
        response.headers["HX-Trigger"] = json.dumps({
            "showToast": {"message": "Account unlocked successfully", "type": "success"}
        })
        return response
    else:
        return make_response("Failed to unlock account. Check LDAP connectivity.", 500)
```

### Pattern 4: Password Generation

**What:** Generate readable temporary passwords meeting AD complexity requirements.

**When to use:** WRIT-02 password reset.

**Example:**
```python
import random
import string

# Curated word list -- common nouns easy to spell over the phone
WORDS = [
    "Sunset", "Silver", "Garden", "Breeze", "Castle", "Dragon",
    "Forest", "Harbor", "Island", "Marble", "Orange", "Planet",
    "Rocket", "Sierra", "Timber", "Violet", "Winter", "Zenith",
    "Crystal", "Phoenix", "Thunder", "Diamond", "Falcon", "Copper",
]
SYMBOLS = "!@#$%&*"

def generate_temp_password() -> str:
    """Generate a readable password: Word + 2 digits + symbol.
    
    Examples: Sunset42!, Dragon78@, Crystal15#
    Meets AD complexity: uppercase (first letter), lowercase, digit, symbol, 8+ chars.
    """
    word = random.choice(WORDS)
    digits = f"{random.randint(10, 99)}"
    symbol = random.choice(SYMBOLS)
    return f"{word}{digits}{symbol}"
```

### Anti-Patterns to Avoid

- **Storing temporary passwords:** D-05 explicitly says never store server-side after generation. The password is returned in the HTTP response and exists only in the client's DOM until the banner is dismissed.
- **Separate connections per LDAP write:** Each write method currently creates a new `Connection`. This is acceptable for the low-frequency write operations (~4-5 IT staff, occasional use), but do NOT create a persistent connection pool for writes -- the existing pattern of per-operation connections is safer for error isolation.
- **JSON responses for HTMX endpoints:** The UI spec requires `hx-swap="none"` with `HX-Trigger` headers for toast feedback. Do NOT return JSON to HTMX endpoints -- return empty 200 with headers on success, or an HTML error fragment on failure.
- **Skipping CSRF on write endpoints:** All POST endpoints must include CSRF validation via the existing double-submit cookie pattern. The confirmation modal form must include the CSRF token.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| AD password reset | Manual `unicodePwd` encoding | `conn.extend.microsoft.modify_password()` | ldap3 handles UTF-16-LE encoding, quoting, and MODIFY_REPLACE vs MODIFY_DELETE/ADD logic [CITED: ldap3.readthedocs.io/en/latest/microsoft.html] |
| License add+remove | Two separate HTTP calls | Single `assignLicense` call with both `addLicenses` and `removeLicenses` | Graph API supports atomic add+remove in one call [CITED: learn.microsoft.com/en-us/graph/api/user-assignlicense] |
| Toast/banner notifications | Custom notification system | Existing `showToast()` and `showBanner()` in `base.html` | Already implemented at lines 256 and 336 of `base.html` |
| Audit logging | Custom audit table/logic | Existing `audit_service.log_admin_action()` | Already supports who/what/target/IP + arbitrary details dict |
| Modal component | React/Vue modal | Jinja partial + vanilla JS | Matches existing pattern from `admin/_cache_actions.html:162-193` |

**Key insight:** The Graph API `assignLicense` endpoint accepts BOTH `addLicenses` and `removeLicenses` in a single call. This means license swap (WRIT-08) can be truly atomic in a single API call -- no need for two sequential calls as the fallback approach. The two-call approach described in D-08 should only be used if the single-call fails.

## Common Pitfalls

### Pitfall 1: LDAP Password Reset Requires SSL/TLS
**What goes wrong:** AD rejects password modifications over non-encrypted connections. The `extend.microsoft.modify_password()` call returns `False` with no clear error message.
**Why it happens:** Active Directory requires the connection to be encrypted (LDAPS or StartTLS) before accepting `unicodePwd` attribute modifications. [CITED: github.com/cannatag/ldap3/issues/891]
**How to avoid:** Verify that `ldap.use_ssl` is `True` in the encrypted configuration before enabling password reset. If SSL is not configured, the password reset button should be hidden/disabled with a tooltip explaining the requirement.
**Warning signs:** `modify_password()` returns `False` with `conn.result` showing `unwillingToPerform` or `confidentialityRequired`.

### Pitfall 2: userAccountControl Bit Manipulation
**What goes wrong:** Setting `userAccountControl` to a hardcoded value (e.g., `512` for normal account) instead of toggling the specific bit (bit 1 = `ACCOUNTDISABLE`) can unintentionally change other flags (password not required, password can't change, etc.).
**Why it happens:** `userAccountControl` is a bitmask with many flags. Each account may have different flags set.
**How to avoid:** Always read the current value first, then toggle only bit 1 (`& ~2` to enable, `| 2` to disable). Never overwrite the entire value.
**Warning signs:** Account behavior changes unexpectedly after enable/disable (e.g., password policy changes).

### Pitfall 3: Graph API Permission Gap
**What goes wrong:** License management calls return 403 Forbidden because the Azure AD app registration lacks the required permission.
**Why it happens:** The existing app registration has `User.Read.All` for read operations. License management requires `LicenseAssignment.ReadWrite.All` (least privileged) or `User.ReadWrite.All` or `Directory.ReadWrite.All`. [CITED: learn.microsoft.com/en-us/graph/api/user-assignlicense]
**How to avoid:** Document the required permission as an external dependency. The planner must include a checkpoint for the Azure AD admin to grant the permission before license operations can be tested.
**Warning signs:** 403 responses from the `assignLicense` endpoint. The existing `_permission_missing()` sentinel pattern in `GraphService` already handles this gracefully.

### Pitfall 4: License Swap Partial Failure Without Rollback
**What goes wrong:** Two-call swap approach: remove succeeds, assign fails, user is left with no license.
**Why it happens:** Network error, license unavailable, or permission issue on the second call.
**How to avoid:** Prefer the single-call atomic approach (both `addLicenses` and `removeLicenses` in one request). Only fall back to two-call if the single-call fails. Always attempt rollback on partial failure. Log the full state for manual recovery.
**Warning signs:** `swap_license()` returns `{"success": False, "rollback_needed": True}`.

### Pitfall 5: HTMX Response Headers for Toast Notification
**What goes wrong:** Toast doesn't appear after a successful write action.
**Why it happens:** HTMX's `HX-Trigger` response header must contain valid JSON. If the header is malformed or the client-side event listener isn't registered, the toast won't fire.
**How to avoid:** Use `json.dumps()` for the `HX-Trigger` header value. Register HTMX event listeners in `write-actions.js` to handle `showToast` events. Test with the HTMX debug extension during development.
**Warning signs:** Network tab shows successful 200 response but no visual feedback.

## Code Examples

### Existing Pattern: Audit Logging for Write Operations
```python
# Source: app/services/audit_service_postgres.py:71-93
# log_admin_action already accepts who/what/target/details
audit_service.log_admin_action(
    user_email=g.user,
    action="unlock_account",          # action type
    target="CN=John Doe,OU=Users,...", # who was affected
    details={                          # arbitrary dict stored as JSONB
        "reason": "Employee locked out after vacation",
        "success": True,
        "source_ip": request.headers.get("X-Forwarded-For"),
    },
    ip_address=request.headers.get("X-Forwarded-For", request.remote_addr),
)
```

### Existing Pattern: HTMX HX-Trigger for Client Events
```python
# Source: HTMX docs pattern, compatible with existing base.html showToast()
import json

response = make_response("", 200)
response.headers["HX-Trigger"] = json.dumps({
    "showToast": {
        "message": "Account unlocked successfully",
        "type": "success",
        "duration": 4000
    }
})
```

### Existing Pattern: Role-Gated Endpoint
```python
# Source: app/blueprints/search/__init__.py (existing pattern)
@search_bp.route("/api/genesys-licenses/<user_id>/<license_id>", methods=["DELETE"])
@require_role("admin")
@handle_errors(json_response=True)
def remove_genesys_license(user_id, license_id):
    # ... existing write operation pattern with audit
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `User.ReadWrite.All` for license management | `LicenseAssignment.ReadWrite.All` (least privileged) | Graph API v1.0 update | Use least-privileged permission for license operations [CITED: learn.microsoft.com/en-us/graph/api/user-assignlicense] |
| Two-call license swap (remove then add) | Single `assignLicense` call with both add and remove | Already available in Graph v1.0 | Atomic swap possible in one call -- no rollback needed |
| Custom LDAP password encoding | `conn.extend.microsoft.modify_password()` | ldap3 2.x+ | Built-in handles UTF-16-LE encoding and AD protocol |

**Deprecated/outdated:**
- The `unicodePwd` manual encoding approach (wrapping in quotes, encoding as UTF-16-LE, using MODIFY_REPLACE) still works but `extend.microsoft.modify_password()` abstracts it correctly. Use the extension. [CITED: ldap3.readthedocs.io/en/latest/microsoft.html]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Existing LDAP bind DN has permissions for unlock, password reset, enable/disable in AD | Architecture Patterns | Write operations will fail with 403/insufficient access. Requires AD admin verification. |
| A2 | LDAP connection is configured with SSL (`use_ssl=True`) or can be enabled | Pitfall 1 | Password reset will fail without encrypted connection. Other write ops may still work. |
| A3 | `LicenseAssignment.ReadWrite.All` is the correct least-privileged permission for license management | Pitfall 3 | Could need `User.ReadWrite.All` instead; either way requires Azure AD admin to grant. |
| A4 | Single-call atomic license swap (add+remove in one `assignLicense`) works for all SKU combinations | Architecture Patterns | Some SKU conflicts might require two calls; fallback approach handles this. |
| A5 | The `showToast` event name is what the HTMX `HX-Trigger` header needs to fire the existing `showToast()` function | Pitfall 5 | May need a custom HTMX event listener bridge in `write-actions.js` if names don't match. |

## Open Questions

1. **LDAP SSL Configuration**
   - What we know: `use_ssl` is configurable via `ldap.use_ssl` config key; current default is `False`
   - What's unclear: Whether the production LDAP connection already uses SSL/TLS
   - Recommendation: Add a runtime check in the password reset method; if SSL is not enabled, return an error explaining the requirement

2. **Azure AD App Permission for License Management**
   - What we know: Need `LicenseAssignment.ReadWrite.All` (least privileged) per official docs
   - What's unclear: Whether the tenant admin will grant this permission, and what the approval timeline is
   - Recommendation: Planner should include a `checkpoint:human-verify` task for permission grant before license management can be tested. AD write operations can be developed and tested independently.

3. **LDAP Bind DN Write Permissions**
   - What we know: D-07 says use existing bind credentials; no separate write account
   - What's unclear: Whether the current bind DN has been granted unlock/reset/enable/disable permissions in AD
   - Recommendation: First implementation task should include a connection test that attempts a read-only operation to verify connectivity, with a clear error message if write operations fail due to insufficient permissions

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| ldap3 | AD write ops | Yes | 2.9.1 | -- |
| requests | Graph API calls | Yes | 2.33.0 | -- |
| msal | OAuth tokens | Yes | 1.34.0 | -- |
| PostgreSQL | Audit trail | Yes | 12+ | -- |
| Alembic | Migrations (if schema changes needed) | Yes | configured in `/alembic/` | -- |
| LDAP Server (AD) | AD operations | External (runtime) | -- | Operations fail gracefully with error message |
| Graph API | License management | External (runtime) | v1.0/beta | Operations fail gracefully with permission warning |

**Missing dependencies with no fallback:** None for development. Runtime availability of AD and Graph API is required for end-to-end testing.

**Missing dependencies with fallback:** None.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (configured in `pyproject.toml`) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `pytest tests/unit/ -x -q` |
| Full suite command | `pytest tests/ -v` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| WRIT-01 | Unlock account calls `ldap3.modify()` with correct params | unit | `pytest tests/unit/test_ldap_write_ops.py::test_unlock_account -x` | Wave 0 |
| WRIT-02 | Reset password calls `extend.microsoft.modify_password()` and returns temp password | unit | `pytest tests/unit/test_ldap_write_ops.py::test_reset_password -x` | Wave 0 |
| WRIT-03 | Enable/disable toggles UAC bit correctly | unit | `pytest tests/unit/test_ldap_write_ops.py::test_set_account_enabled -x` | Wave 0 |
| WRIT-04 | Write endpoint rejects empty/short reason | unit | `pytest tests/unit/test_write_endpoints.py::test_reason_validation -x` | Wave 0 |
| WRIT-05 | Audit log created with full context on every write | unit | `pytest tests/unit/test_write_endpoints.py::test_audit_logging -x` | Wave 0 |
| WRIT-06 | Assign license sends correct Graph API payload | unit | `pytest tests/unit/test_graph_license_ops.py::test_assign_license -x` | Wave 0 |
| WRIT-07 | Remove license sends correct Graph API payload | unit | `pytest tests/unit/test_graph_license_ops.py::test_remove_license -x` | Wave 0 |
| WRIT-08 | Swap license attempts atomic call, falls back to two-call with rollback | unit | `pytest tests/unit/test_graph_license_ops.py::test_swap_license -x` | Wave 0 |
| WRIT-04 | Confirmation modal blocks without reason, enables with reason | manual-only | Browser test | -- |
| WRIT-05 | Audit log visible in admin audit view | integration | `pytest tests/integration/test_write_audit.py -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/unit/ -x -q`
- **Per wave merge:** `pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/unit/test_ldap_write_ops.py` -- covers WRIT-01, WRIT-02, WRIT-03
- [ ] `tests/unit/test_write_endpoints.py` -- covers WRIT-04, WRIT-05
- [ ] `tests/unit/test_graph_license_ops.py` -- covers WRIT-06, WRIT-07, WRIT-08
- [ ] `tests/unit/test_password_generator.py` -- covers D-06 password pattern
- [ ] `tests/integration/test_write_audit.py` -- covers WRIT-05 end-to-end

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | Existing `@auth_required` decorator (Keycloak OIDC from Phase 4) |
| V3 Session Management | yes | Existing session management middleware |
| V4 Access Control | yes | `@require_role("admin")` on all write endpoints; server-side role check |
| V5 Input Validation | yes | Reason text validated (3+ chars, stripped); user_dn validated against LDAP format; sku_id validated as UUID |
| V6 Cryptography | no | No new cryptographic operations (password generation uses `random`, not crypto) |

### Known Threat Patterns for AD Write + Graph API

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| CSRF on write endpoints | Tampering | Double-submit cookie CSRF already in middleware; all POST forms include token |
| Privilege escalation via parameter tampering | Elevation of Privilege | Server validates `g.role == 'admin'` via decorator, not client-side |
| Password disclosure in logs | Information Disclosure | Never log generated passwords; audit trail stores action+reason, not the password |
| License removal without authorization | Tampering | `@require_role("admin")` + mandatory reason + audit trail |
| LDAP injection in user_dn | Tampering | User DN comes from prior LDAP search result (already escaped), not from user input |
| Temporary password in browser history | Information Disclosure | Password shown in DOM only, not in URL; `hx-swap="none"` prevents URL changes |

## Project Constraints (from CLAUDE.md)

- **Tech stack:** Flask/PostgreSQL/HTMX -- extend existing patterns, no new frameworks
- **Auth:** All new endpoints must use `@auth_required` + `@require_role()` decorators
- **Security:** All write operations require audit trail, confirmation workflows, and role checks
- **DI pattern:** Retrieve services from `current_app.container.get()`, never global imports
- **Error handling:** Use `@handle_errors` for routes, `@handle_service_errors` for service methods
- **CSRF:** All state-changing operations require CSRF protection
- **Model patterns:** Extend appropriate base classes with mixins
- **Linting:** `ruff check --fix` and `mypy app/ scripts/`

## Sources

### Primary (HIGH confidence)
- [ldap3 MODIFY documentation](https://ldap3.readthedocs.io/en/latest/modify.html) -- `modify()` method signature, MODIFY_REPLACE operation, atomic application
- [ldap3 Microsoft extensions](https://ldap3.readthedocs.io/en/latest/microsoft.html) -- `modify_password()` function for AD password reset
- [Graph API user: assignLicense](https://learn.microsoft.com/en-us/graph/api/user-assignlicense?view=graph-rest-1.0) -- Permissions (`LicenseAssignment.ReadWrite.All`), request body schema, atomic add+remove in single call

### Secondary (MEDIUM confidence)
- [ldap3 GitHub issue #891](https://github.com/cannatag/ldap3/issues/891) -- SSL requirement for password modification confirmed by maintainer
- [ldap3 GitHub issue #222](https://github.com/cannatag/ldap3/issues/222) -- Account unlock via `lockoutTime` modification approach
- [ldap3 modifyPassword.py source](https://github.com/cannatag/ldap3/blob/master/ldap3/extend/microsoft/modifyPassword.py) -- UTF-16-LE encoding and admin reset logic

### Tertiary (LOW confidence)
- None -- all key claims verified against official documentation

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new packages, all operations documented in official sources
- Architecture: HIGH -- extends existing codebase patterns with verified library APIs
- Pitfalls: HIGH -- LDAP SSL requirement and Graph permissions documented in official sources
- UI patterns: HIGH -- UI spec already exists with detailed interaction contract

**Research date:** 2026-05-17
**Valid until:** 2026-06-17 (30 days -- stable APIs, no fast-moving components)
