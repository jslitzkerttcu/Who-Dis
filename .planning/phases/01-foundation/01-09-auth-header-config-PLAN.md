---
phase: 01-foundation
plan: 09
type: execute
wave: 1
depends_on: []
files_modified:
  - app/middleware/authentication_handler.py
autonomous: true
requirements: [SEC-04]
must_haves:
  truths:
    - "Authentication header name is read from config (auth.principal_header) with default X-MS-CLIENT-PRINCIPAL-NAME — non-Azure deployments can override"
    - "DANGEROUS_DEV_AUTH_BYPASS_USER environment variable, when set, returns the configured user as the authenticated principal and emits a WARNING log"
    - "Production deploys without the env var continue to behave identically to today (zero behavior change in default path)"
  artifacts:
    - path: "app/middleware/authentication_handler.py"
      provides: "authenticate_user() reads header name from config + supports dev bypass"
      contains: "DANGEROUS_DEV_AUTH_BYPASS_USER"
  key_links:
    - from: "app/middleware/authentication_handler.py"
      to: "app/services/configuration_service.py"
      via: "config_get('auth.principal_header', 'X-MS-CLIENT-PRINCIPAL-NAME')"
      pattern: "auth.principal_header"
---

<objective>
Make the authentication header name configurable for non-Azure environments and provide an explicit, loud dev bypass for local testing. Satisfies SEC-04.

Purpose: WhoDis hardcodes Azure App Service's `X-MS-CLIENT-PRINCIPAL-NAME`. Other reverse proxies (nginx, Traefik) inject different header names. A small config knob preserves Azure-default behavior while enabling broader deployment.
Output: Single file change to `authentication_handler.py`; new optional config key documented inline.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/01-foundation/01-CONTEXT.md
@.planning/phases/01-foundation/01-PATTERNS.md
@CLAUDE.md
@app/middleware/authentication_handler.py
@app/middleware/auth.py
@app/services/configuration_service.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Configurable auth header + dev bypass in authentication_handler.py</name>
  <read_first>
    - app/middleware/authentication_handler.py lines 8–22 (current authenticate_user — exact analog per PATTERNS.md)
    - app/services/configuration_service.py (confirm config_get import path + None-default behavior)
    - app/middleware/auth.py (caller site — confirm authenticate_user is called once and its return contract)
  </read_first>
  <action>
    Per SEC-04 Claude's Discretion + PATTERNS.md adaptation:

    1. Modify `app/middleware/authentication_handler.py:authenticate_user()` so the implementation matches:

       ```python
       import os
       import logging
       from flask import request
       from typing import Optional
       from app.services.configuration_service import config_get

       logger = logging.getLogger(__name__)

       class AuthenticationHandler:
           def authenticate_user(self) -> Optional[str]:
               # WARNING: only honored when DANGEROUS_DEV_AUTH_BYPASS_USER is set in the OS env.
               # Never set this in production. Env-var-only by design — cannot be flipped via admin UI.
               bypass_user = os.getenv("DANGEROUS_DEV_AUTH_BYPASS_USER")
               if bypass_user:
                   logger.warning(
                       "AUTH BYPASS ACTIVE — authenticating as %s "
                       "(DANGEROUS_DEV_AUTH_BYPASS_USER set)",
                       bypass_user,
                   )
                   return bypass_user.strip().lower()

               header_name = config_get("auth.principal_header", "X-MS-CLIENT-PRINCIPAL-NAME")
               principal = request.headers.get(header_name)
               if principal:
                   return principal.strip().lower()
               return None
       ```

    2. Default header name MUST remain `X-MS-CLIENT-PRINCIPAL-NAME` so existing Azure deployments are unaffected.
    3. Bypass uses an ENVIRONMENT VARIABLE (not a DB config key). Operators must redeploy with the env var set; cannot be flipped from the admin UI.
    4. Leave the direct `X-MS-CLIENT-PRINCIPAL-NAME` reads in `app/__init__.py` and `app/utils/error_handler.py` AS-IS (those read for logging context, not auth decisions). Note this in the SUMMARY as a known follow-up.
    5. Preserve any other behavior already in `AuthenticationHandler` (e.g. additional methods); only `authenticate_user` is the target.
  </action>
  <verify>
    <automated>grep -q 'DANGEROUS_DEV_AUTH_BYPASS_USER' app/middleware/authentication_handler.py &amp;&amp; grep -q 'auth.principal_header' app/middleware/authentication_handler.py &amp;&amp; grep -q 'X-MS-CLIENT-PRINCIPAL-NAME' app/middleware/authentication_handler.py &amp;&amp; grep -q 'AUTH BYPASS ACTIVE' app/middleware/authentication_handler.py &amp;&amp; python -c 'from app.middleware.authentication_handler import AuthenticationHandler; AuthenticationHandler()'</automated>
  </verify>
  <acceptance_criteria>
    - `grep -n "DANGEROUS_DEV_AUTH_BYPASS_USER" app/middleware/authentication_handler.py` matches at least once
    - `grep -n "auth.principal_header" app/middleware/authentication_handler.py` matches
    - `grep -n "X-MS-CLIENT-PRINCIPAL-NAME" app/middleware/authentication_handler.py` matches (default preserved)
    - `grep -n "logger.warning" app/middleware/authentication_handler.py` matches (bypass emits WARNING)
    - With env var unset, behavior is byte-identical to pre-change for an Azure-headered request
    - With env var set to `dev@example.com`, the WARNING log line fires and `authenticate_user()` returns `"dev@example.com"`
    - App boots: `python -c "from app import create_app; create_app()"` exits 0
  </acceptance_criteria>
  <done>Header name configurable; dev bypass works only when env var set; production behavior unchanged.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| reverse proxy → Flask | Auth principal header arrives from the upstream — name is now config-driven |
| OS env → process | DANGEROUS_DEV_AUTH_BYPASS_USER controls authentication outcome |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-01-09-01 | Spoofing | Configurable header name | mitigate | Header is still proxy-injected; downstream trust model unchanged. Operators are responsible for stripping client-supplied copies of the header at the proxy edge — same as today. |
| T-01-09-02 | Elevation of Privilege | Dev bypass enabled in prod | mitigate | Bypass is env-var-gated (not DB-config), variable name is intentionally loud (`DANGEROUS_*`), every invocation emits WARNING-level log. Operators cannot enable it from the admin UI; deployment-time gate only. |
| T-01-09-03 | Repudiation | Bypass user identity | mitigate | Bypass user is fully audited via the existing audit pipeline — log lines tag the configured email as the actor; the WARNING log line on every request makes accidental enablement immediately obvious. |
</threat_model>

<verification>
- Production-style request with `X-MS-CLIENT-PRINCIPAL-NAME: alice@corp.com` and no env var → returns `alice@corp.com`
- Set `DANGEROUS_DEV_AUTH_BYPASS_USER=dev@example.com`, restart app → every request authenticates as `dev@example.com` and stderr shows `AUTH BYPASS ACTIVE` warnings
- Set DB config `auth.principal_header=X-Forwarded-User`, send request with `X-Forwarded-User: bob@corp.com` (and no env var) → returns `bob@corp.com`
</verification>

<success_criteria>
SEC-04 acceptance criterion satisfied: authentication header validation configurable for non-Azure environments.
</success_criteria>

<output>
After completion, create `.planning/phases/01-foundation/01-09-SUMMARY.md`.
</output>
