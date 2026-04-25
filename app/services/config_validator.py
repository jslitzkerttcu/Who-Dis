"""
Startup configuration validator.

Per OPS-03: misconfigured deployments should fail loud at boot, not silent at
runtime. This module is invoked from `create_app()` after the configuration
service is initialized but before blueprints are registered. If any required
encrypted-config key is missing or empty, `validate_required_config()` raises
`ConfigurationError` listing every missing key — boot aborts.

Note: PostgreSQL credentials remain in `.env` (chicken-and-egg bootstrap), so
this validator only covers encrypted-config keys (LDAP, Graph, Genesys, etc.).
"""

import logging
from typing import List, Tuple

from app.services.configuration_service import config_get

logger = logging.getLogger(__name__)


class ConfigurationError(Exception):
    """Raised at startup when required configuration is missing."""


# (category.key, human_label) — keep keys aligned with config_get categories used today.
# This list is intentionally code-resident (not DB-driven) so operators cannot
# tamper their way around the gate without a code change (T-01-05-03).
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
    """Validate that all required encrypted-config keys are present and non-empty.

    Raises:
        ConfigurationError: if any required key is missing/empty. The message
            lists every missing key by `category.key (Human Label)` form. No
            present (decrypted) values are ever included in the message
            (T-01-05-01).
    """
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

    logger.info(
        "Configuration validation passed: %d required keys present",
        len(REQUIRED_KEYS),
    )
