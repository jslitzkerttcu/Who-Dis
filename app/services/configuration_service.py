"""Configuration service — Phase 9 SandCastle (D-13 carve-out only).

The encrypted-config layer (D-11) was removed in Phase 9. Secrets now live in
the portal env-var store and are read via os.environ. The ONLY surviving
capability is the WD-CFG-04 debug-mode DB toggle — a non-secret operational
flag toggled from the admin DB or directly to enable Flask debug at runtime.

All secret-bearing functions and the SimpleConfig/EncryptionService imports
have been removed. The legacy `configuration` table will be dropped from the
live DB after the Plan 06 post-cutover verification (per
`scripts/cutover/README.md`); until then it remains for forensics but is not
read by the running app except for the debug toggle.
"""
import logging
import os
from typing import Optional

from sqlalchemy import text

logger = logging.getLogger(__name__)


# Phase 9 env-var bridge.
#
# Pre-Phase-9 services call config_get("category.key") to read encrypted
# settings out of the (now-retired) configuration table. Plan 05 left
# config_get as a no-op shim, which silently broke every call site —
# LDAP/Graph/Genesys all received None for their credentials. This map
# translates the legacy dotted keys to the portal env-var names that
# .env.sandcastle.example documents and that scripts/cutover/migrate_secrets_to_portal.py
# writes into the portal store.
#
# Only the keys whose env-var name does NOT match the AUTO_UPPER fallback need
# to live in this map. Everything else (graph.client_id -> GRAPH_CLIENT_ID,
# genesys.region -> GENESYS_REGION, etc.) is handled by the
# `key.replace(".", "_").upper()` rule in config_get below.
#
# Per the canonical mapping in scripts/cutover/migrate_secrets_to_portal.py,
# `ldap.host` is the lone exception — the portal env-var is LDAP_SERVER, not
# LDAP_HOST. If you add a new exception, also update the migration script.
ENV_BRIDGE = {
    "ldap.host": "LDAP_SERVER",
}


def get_debug_mode() -> bool:
    """Return the runtime debug toggle (WD-CFG-04 / D-13).

    Reads the non-encrypted 'flask.debug' row from the legacy `configuration`
    table. Returns False if the table does not exist or the row is absent
    (safe default for production).
    """
    try:
        from app.database import db

        with db.engine.connect() as conn:
            result = conn.execute(
                text(
                    "SELECT setting_value FROM configuration "
                    "WHERE category = 'flask' AND setting_key = 'debug'"
                )
            ).first()

        if result and result[0] is not None:
            return str(result[0]).lower() in ("true", "1", "yes")
        return False
    except Exception as exc:
        logger.debug("Could not read debug toggle from DB (returning False): %s", exc)
        return False


def set_debug_mode(value: bool) -> bool:
    """Persist the runtime debug toggle (admin write path, WD-CFG-04 / D-13).

    Uses an upsert so the row is created if absent. Returns True on success.
    """
    try:
        from datetime import datetime
        from app.database import db

        with db.engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO configuration
                        (category, setting_key, setting_value, updated_by, updated_at, is_sensitive)
                    VALUES
                        ('flask', 'debug', :val, 'system', :now, FALSE)
                    ON CONFLICT (category, setting_key) DO UPDATE
                        SET setting_value = EXCLUDED.setting_value,
                            updated_by    = EXCLUDED.updated_by,
                            updated_at    = EXCLUDED.updated_at
                """),
                {"val": str(value).lower(), "now": datetime.utcnow()},
            )
        return True
    except Exception as exc:
        logger.error("Failed to set debug toggle: %s", exc)
        return False


def config_get(key: str, default=None):
    """Phase 9 — read from os.environ via the ENV_BRIDGE map (D-11 retirement).

    Pre-Phase-9 services call ``config_get("category.key", default)`` to read
    encrypted settings out of the (now-retired) configuration table. They are
    now backed by the portal env-var store, which the SandCastle deploy injects
    as os.environ keys per .env.sandcastle.example.

    Resolution order:
      1. ENV_BRIDGE explicit map (e.g. ldap.host -> LDAP_SERVER)
      2. AUTO_UPPER fallback (e.g. graph.api_timeout -> GRAPH_API_TIMEOUT)
      3. ``default``

    Tests that rely on ``service._config_cache`` overrides remain unaffected —
    BaseConfigurableService._get_config caches per-instance and reads this
    function only on cache miss (Plan 02-PATTERNS).
    """
    env_key = ENV_BRIDGE.get(key) or key.replace(".", "_").upper()
    val = os.environ.get(env_key)
    return val if val is not None else default


def config_set(key: str, value, *args, **kwargs) -> bool:
    """Phase 9 shim — no-op for compatibility (D-11 retirement)."""
    return False


def config_delete(key: str, *args, **kwargs) -> bool:
    """Phase 9 shim — no-op for compatibility (D-11 retirement)."""
    return False


def config_get_all(*args, **kwargs) -> dict:
    """Phase 9 shim — returns empty dict (D-11 retirement)."""
    return {}


def get_flask_config_from_env() -> dict:
    """Return Flask config values sourced from os.environ (Phase 9 SandCastle pattern).

    Replaces the pre-Phase-9 pattern of reading these from the encrypted
    configuration DB. After D-11 retirement, every secret lives in the portal
    env-var store and is injected as an environment variable at container start.

    Returns a dict suitable for `app.config.update(...)`.
    """
    import os

    return {
        "FLASK_HOST": os.environ.get("FLASK_HOST", "0.0.0.0"),
        "FLASK_PORT": int(os.environ.get("FLASK_PORT", "5000")),
        "FLASK_DEBUG": get_debug_mode(),
    }
