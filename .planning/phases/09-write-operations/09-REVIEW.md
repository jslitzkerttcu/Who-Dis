---
phase: 09-write-operations
reviewed: 2025-05-17T14:30:00Z
depth: standard
files_reviewed: 20
files_reviewed_list:
  - app/blueprints/search/__init__.py
  - app/blueprints/search/write_routes.py
  - app/container.py
  - app/services/graph_service.py
  - app/services/ldap_service.py
  - app/services/write_operations.py
  - app/static/js/write-actions.js
  - app/templates/search/_ad_actions.html
  - app/templates/search/_license_actions.html
  - app/templates/search/_license_select.html
  - app/templates/search/_m365_section.html
  - app/templates/search/_password_banner.html
  - app/templates/search/_write_confirm_modal.html
  - app/templates/search/index.html
  - app/utils/password_generator.py
  - tests/unit/services/test_graph_license_ops.py
  - tests/unit/services/test_ldap_write_ops.py
  - tests/unit/services/test_password_generator.py
  - tests/unit/services/test_write_operations_service.py
  - tests/unit/test_license_endpoints.py
  - tests/unit/test_write_endpoints.py
findings:
  critical: 3
  warning: 4
  info: 1
  total: 8
status: issues_found
---

# Phase 9: Code Review Report

**Reviewed:** 2025-05-17T14:30:00Z
**Depth:** standard
**Files Reviewed:** 20
**Status:** issues_found

## Summary

Phase 9 implements write operations (AD unlock/reset/enable/disable and M365 license management) with audit logging and HTMX-driven UI. The architecture follows project patterns well (DI container, role checks, CSRF protection). However, there are critical security issues: the password generator uses a non-cryptographic PRNG with only ~14 bits of entropy, there is no input validation on `user_dn` or `user_id` before they are interpolated into LDAP operations and Graph API URLs, and the swap-license endpoint returns HTTP 200 on rollback-success scenarios that represent a partial failure.

## Critical Issues

### CR-01: Password Generator Uses Non-Cryptographic PRNG with Dangerously Low Entropy

**File:** `app/utils/password_generator.py:31-34`
**Issue:** The `generate_temp_password()` function uses Python's `random` module, which is not cryptographically secure (uses Mersenne Twister, predictable if seeded). Worse, the password space is only 24 words x 90 digits x 7 symbols = 15,120 possible passwords (~13.9 bits of entropy). An attacker who knows the generation scheme can brute-force all possible passwords in milliseconds. These temporary passwords protect Active Directory accounts.
**Fix:**
```python
import secrets

def generate_temp_password() -> str:
    word = secrets.choice(WORDS)
    digits = secrets.randbelow(90) + 10
    symbol = secrets.choice(SYMBOLS)
    return f"{word}{digits}{symbol}"
```
Additionally, expand the word list to at least 100+ words and/or add a second word to increase entropy to 40+ bits minimum. A password protecting an AD account should have at least 30 bits of entropy even for a temporary credential.

### CR-02: No Input Validation on user_dn -- LDAP Injection Risk

**File:** `app/blueprints/search/write_routes.py:37-45`
**Issue:** The `user_dn` parameter is taken directly from form input with only `.strip()` applied, then passed to `ldap_service.unlock_account(user_dn)` which uses it as-is in `conn.modify(user_dn, ...)`. While the DN is used as the target (not in a filter), a malicious admin could supply an arbitrary DN to modify any object in the directory (e.g., a service account or OU). There is no validation that the DN matches a user object, belongs to the expected OU, or matches the `display_name` shown in the confirmation modal.

This applies to all four AD endpoints (unlock, reset-password, enable, disable).
**Fix:**
```python
import re

# Validate DN format and restrict to expected user OU
VALID_USER_DN_PATTERN = re.compile(r"^CN=[^,]+,(?:OU=[^,]+,)*DC=.+$", re.IGNORECASE)

def _validate_user_dn(user_dn: str) -> bool:
    if not user_dn or not VALID_USER_DN_PATTERN.match(user_dn):
        return False
    # Optionally: verify DN exists and is a user object via LDAP search
    return True
```
At minimum, validate that `user_dn` is non-empty and matches an expected DN pattern before passing to LDAP operations.

### CR-03: Graph API URL Path Injection via user_id

**File:** `app/services/graph_service.py:869`
**Issue:** The `user_id` parameter is interpolated directly into the Graph API URL: `f"{self.graph_base_url}/users/{user_id}/assignLicense"`. If `user_id` contains path traversal characters (e.g., `../` or URL-encoded variants), it could alter the API path. While Graph API would likely reject malformed IDs, an attacker-controlled admin could potentially target different API endpoints. The `user_id` comes from form input in `write_routes.py:194` with no format validation.
**Fix:**
```python
import re

# Graph user IDs are GUIDs
GUID_PATTERN = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE)

# In write_routes.py before calling write_ops:
if not GUID_PATTERN.match(user_id):
    return make_response("Invalid user ID format", 400)
```

## Warnings

### WR-01: Swap-License Returns HTTP 200 on Partial Failure (Rollback Success)

**File:** `app/blueprints/search/write_routes.py:287-299`
**Issue:** When a license swap fails but rollback succeeds, the endpoint returns HTTP 200 with a "warning" toast. This is semantically incorrect -- the requested operation (swap) did not succeed. Returning 200 means HTMX considers it "successful" and `htmx:afterRequest` with `evt.detail.successful` will be true, closing the modal. The user sees a brief warning toast but the modal closes as if the action worked. This could lead admins to believe the swap completed.
**Fix:** Return HTTP 422 (Unprocessable Entity) or 409 (Conflict) instead of 200, and handle the non-2xx case in the JS to show a persistent warning rather than closing the modal.

### WR-02: Missing Empty-String Validation on Required Parameters

**File:** `app/blueprints/search/write_routes.py:37-38`
**Issue:** The `user_dn` and `display_name` fields are only stripped, never checked for emptiness. An empty `user_dn` will be passed to `ldap_service.unlock_account("")` which will fail at the LDAP level but waste a connection and produce a confusing error. Same issue for `user_id`, `sku_id` in license endpoints (lines 194-197, 227-230, 260-266). Only `reason` has a minimum-length check.
**Fix:**
```python
if not user_dn:
    return make_response("User DN is required.", 400)
if not display_name:
    return make_response("Display name is required.", 400)
```

### WR-03: XSS Risk in Swap License Modal via License Names

**File:** `app/static/js/write-actions.js:152`
**Issue:** In `_buildSwapLicenseFields`, license display names from `config.currentLicenses` are interpolated directly into HTML via string concatenation: `'<option value="' + lic.skuId + '" data-display-name="' + name + '">' + name + '</option>'`. The `currentLicenses` array comes from `{{ data.get('licenses', []) | tojson }}` in the Jinja template, which is safe for the initial render. However, if a license name contains HTML special characters (e.g., quotes or angle brackets from a malicious tenant SKU name), it would break the HTML structure or enable DOM XSS. The `| tojson` filter escapes for JS string context but not for HTML attribute/content context when later used in innerHTML.
**Fix:** Use DOM APIs or escape HTML entities before interpolation:
```javascript
function _escapeHtml(str) {
    var div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}
// Then: var name = _escapeHtml(lic.displayName || lic.name || lic.skuId);
```

### WR-04: WriteOperationsService Caches Service References Across Requests

**File:** `app/services/write_operations.py:24-45`
**Issue:** `WriteOperationsService` is registered as a singleton in the container (line 155 of `container.py`). Its lazy properties (`ldap_service`, `graph_service`, `audit_logger`) cache service references in instance attributes (`self._ldap_service`, etc.). Since the container itself caches singletons, this is not a correctness bug today. However, if the container ever supports service reload/replacement (e.g., for config changes), the stale cached references in `WriteOperationsService` would not update. This creates a hidden coupling that violates the DI pattern's intent.
**Fix:** Either always resolve from container on each call (remove caching), or document that this service must be recreated if dependencies change.

## Info

### IN-01: Password Banner Exposes Temporary Password in DOM

**File:** `app/templates/search/_password_banner.html:14`
**Issue:** The temporary password is rendered as visible text in the DOM (`{{ password }}`). When "hidden", the JS moves it to a `data-password` attribute (line 366 of write-actions.js), which is still trivially accessible via DevTools. This is acceptable for the stated use case (IT admin reads it to the user), but worth noting that the password persists in the DOM until the banner is manually dismissed. There is no auto-dismiss timeout.
**Fix:** Consider adding an auto-dismiss after a configurable period (e.g., 5 minutes) to reduce exposure window.

---

_Reviewed: 2025-05-17T14:30:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
