---
phase: 01-foundation
plan: 05
type: execute
wave: 2
depends_on: [01]
files_modified:
  - app/services/config_validator.py
  - app/__init__.py
autonomous: true
requirements: [OPS-03]
must_haves:
  truths:
    - "Application refuses to start when any required configuration key is missing, raising a clear error listing every missing key"
    - "When all required keys are present, validator runs to completion and create_app() returns normally"
  artifacts:
    - path: "app/services/config_validator.py"
      provides: "ConfigurationError exception + validate_required_config() function"
      contains: "class ConfigurationError"
  key_links:
    - from: "app/__init__.py:create_app"
      to: "app/services/config_validator.py"
      via: "validate_required_config() called after configuration_service init, before blueprint registration"
      pattern: "validate_required_config"
---

<objective>
Add a startup validator that aborts boot with a clear error message when required encrypted-config values are missing. Satisfies OPS-03.

Purpose: Misconfigured deployments currently surface as runtime 500s scattered across services. Failing fast at boot points operators directly at the missing keys.
Output: New `config_validator.py` service, called from `create_app()` after configuration service is initialized.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/01-foundation/01-CONTEXT.md
@.planning/phases/01-foundation/01-PATTERNS.md
@CLAUDE.md
@app/services/encryption_service.py
@app/services/configuration_service.py
@app/__init__.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: ConfigurationError + validate_required_config()</name>
  <read_first>
    - app/services/encryption_service.py lines 21–27 (constructor-raises analog per PATTERNS.md)
    - app/services/configuration_service.py (confirm config_get signature + decryption path)
    - app/__init__.py (find the line where configuration_service is initialized, ~ around line 76 per PATTERNS.md, to insert validator call after)
  </read_first>
  <action>
    Per OPS-03 Claude's Discretion + PATTERNS.md "config_validator.py":

    1. Create `app/services/config_validator.py`:
       ```python
       import logging
       from typing import List, Tuple
       from app.services.configuration_service import config_get

       logger = logging.getLogger(__name__)

       class ConfigurationError(Exception):
           """Raised at startup when required configuration is missing."""

       # (category.key, human_label) — keep keys aligned with config_get categories used today
       REQUIRED_KEYS: List[Tuple[str, str]] = [
           ("ldap.server", "LDAP server hostname"),
           ("ldap.bind_dn", "LDAP bind DN"),
           ("graph.tenant_id", "Microsoft Graph tenant ID"),
           ("graph.client_id", "Microsoft Graph client ID"),
           ("graph.client_secret", "Microsoft Graph client secret"),
           ("genesys.client_id", "Genesys Cloud client ID"),
           ("genesys.client_secret", "Genesys Cloud client secret"),
       ]

       def validate_required_config() -> None:
           missing: List[str] = []
           for key, label in REQUIRED_KEYS:
               value = config_get(key, None)
               if value is None or (isinstance(value, str) and not value.strip()):
                   missing.append(f"{key} ({label})")
           if missing:
               msg = (
                   "Application cannot start — required configuration is missing:\n  - "
                   + "\n  - ".join(missing)
                   + "\nUse the admin config UI or scripts/import_config.py to set these values."
               )
               logger.error(msg)
               raise ConfigurationError(msg)
           logger.info("Configuration validation passed: %d required keys present", len(REQUIRED_KEYS))
       ```
    2. In `app/__init__.py:create_app()`, after the configuration service is initialized (PATTERNS.md says ~ line 76, AFTER configuration_service init) and BEFORE blueprint registration, call:
       ```python
       from app.services.config_validator import validate_required_config
       validate_required_config()  # raises ConfigurationError on missing keys → boot aborts
       ```
    3. Do NOT catch `ConfigurationError` — it must propagate and abort `create_app()` per CONTEXT "failure aborts app boot".
  </action>
  <verify>
    <automated>grep -q 'class ConfigurationError' app/services/config_validator.py &amp;&amp; grep -q 'validate_required_config' app/__init__.py &amp;&amp; grep -q 'REQUIRED_KEYS' app/services/config_validator.py &amp;&amp; python -c 'from app.services.config_validator import REQUIRED_KEYS; assert len(REQUIRED_KEYS) >= 7'</automated>
  </verify>
  <acceptance_criteria>
    - `app/services/config_validator.py` exists with `class ConfigurationError(Exception)` and `def validate_required_config`
    - `REQUIRED_KEYS` list contains at least 7 entries (LDAP server + bind DN, Graph tenant + client_id + client_secret, Genesys client_id + client_secret)
    - `grep -n "validate_required_config" app/__init__.py` matches
    - When all required keys are set in DB config, `python -c "from app import create_app; create_app()"` exits 0
    - When a required key is missing, calling `create_app()` raises `ConfigurationError` whose message lists the missing key(s) by category.key name AND human label
  </acceptance_criteria>
  <done>Boot fails fast with a clear message when required config is missing; passes silently when present.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| operator → deployment | Misconfiguration at deploy time should fail loud not silent |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-01-05-01 | Information Disclosure | Error message | mitigate | Error lists only the *names* of missing keys (e.g. `graph.client_secret (Microsoft Graph client secret)`), never the present values. No decrypted secrets included in the message. |
| T-01-05-02 | Denial of Service | Boot abort | accept | Failing boot is the desired behavior; partial-config startup leads to runtime 500s which are worse. |
| T-01-05-03 | Tampering | REQUIRED_KEYS list | mitigate | List is in code (read-only at deploy time), not in DB config — operators cannot tamper their way around the gate without code change |
</threat_model>

<verification>
- With full config: `python -c "from app import create_app; create_app()"` exits 0 and logs "Configuration validation passed: 7 required keys present"
- With one key missing in DB: same command raises `ConfigurationError` with that key's name in the message
- The error message text is human-readable and points at remediation
</verification>

<success_criteria>
OPS-03 acceptance criterion satisfied: app validates required configuration at startup with clear error messages.
</success_criteria>

<output>
After completion, create `.planning/phases/01-foundation/01-05-SUMMARY.md`.
</output>
