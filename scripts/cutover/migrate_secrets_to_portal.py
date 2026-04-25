"""Phase 9 cutover — D-12: migrate Who-Dis encrypted-config secrets to the portal env-var store.

Idempotent (Pitfall 6 in 09-RESEARCH.md). Re-running this script does NOT
duplicate env vars; it diffs against existing portal env vars and POSTs only
the missing/changed keys.

Usage (operator runs ONCE, before the encrypted-config tables are dropped and
before the new container is deployed):

    set -o allexport; source secrets.env; set +o allexport
    python scripts/cutover/migrate_secrets_to_portal.py [--dry-run] [--force]

Required env:
    WHODIS_LIVE_DATABASE_URL — DSN for the legacy Who-Dis DB (read access)
    WHODIS_ENCRYPTION_KEY    — Fernet key for the legacy encryption service
    PORTAL_BASE              — e.g. https://sandcastle.ttcu.com
    PORTAL_TOKEN             — admin OIDC bearer token for portal API
    WHODIS_APP_ID            — UUID of the who-dis app from POST /api/apps response
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from typing import Dict, List

import requests
from sqlalchemy import create_engine, text

logger = logging.getLogger("migrate_secrets_to_portal")

# Map legacy `configuration` table keys -> portal env var names.
# This list MUST cover every required runtime secret (verify against the live
# configuration table contents during pre-cutover). Non-secret values (server
# hostnames, regions) are also migrated for completeness.
#
# KEY_MAP is keyed by the legacy composite key: "{category}.{setting_key}" as
# stored in the `configuration` table's (category, setting_key) columns.
# Values are the portal env var names that Who-Dis reads from os.environ
# after SandCastle env-var injection.
KEY_MAP: Dict[str, str] = {
    # LDAP / Active Directory
    "ldap.server": "LDAP_SERVER",
    "ldap.host": "LDAP_SERVER",          # alias — some rows use "host" key
    "ldap.bind_dn": "LDAP_BIND_DN",
    "ldap.bind_password": "LDAP_BIND_PASSWORD",
    "ldap.base_dn": "LDAP_BASE_DN",
    "ldap.user_search_base": "LDAP_USER_SEARCH_BASE",
    "ldap.port": "LDAP_PORT",
    "ldap.use_ssl": "LDAP_USE_SSL",
    "ldap.connect_timeout": "LDAP_CONNECT_TIMEOUT",
    "ldap.connection_timeout": "LDAP_CONNECTION_TIMEOUT",
    "ldap.operation_timeout": "LDAP_OPERATION_TIMEOUT",
    # Microsoft Graph
    "graph.tenant_id": "GRAPH_TENANT_ID",
    "graph.client_id": "GRAPH_CLIENT_ID",
    "graph.client_secret": "GRAPH_CLIENT_SECRET",
    "graph.api_timeout": "GRAPH_API_TIMEOUT",
    # Genesys Cloud
    "genesys.client_id": "GENESYS_CLIENT_ID",
    "genesys.client_secret": "GENESYS_CLIENT_SECRET",
    "genesys.region": "GENESYS_REGION",
    "genesys.api_timeout": "GENESYS_API_TIMEOUT",
    "genesys.cache_refresh_hours": "GENESYS_CACHE_REFRESH_HOURS",
    # Data Warehouse
    "data_warehouse.server": "DATA_WAREHOUSE_SERVER",
    "data_warehouse.database": "DATA_WAREHOUSE_DATABASE",
    "data_warehouse.client_id": "DATA_WAREHOUSE_CLIENT_ID",
    "data_warehouse.client_secret": "DATA_WAREHOUSE_CLIENT_SECRET",
    "data_warehouse.connection_timeout": "DATA_WAREHOUSE_CONNECTION_TIMEOUT",
    "data_warehouse.query_timeout": "DATA_WAREHOUSE_QUERY_TIMEOUT",
    "data_warehouse.cache_refresh_hours": "DATA_WAREHOUSE_CACHE_REFRESH_HOURS",
    # Auth / search / audit tunables (non-secret but migrated for completeness)
    "auth.required": "AUTH_REQUIRED",
    "auth.session_timeout_minutes": "AUTH_SESSION_TIMEOUT_MINUTES",
    "search.timeout": "SEARCH_TIMEOUT",
    "search.overall_timeout": "SEARCH_OVERALL_TIMEOUT",
    "search.cache_expiration_hours": "SEARCH_CACHE_EXPIRATION_HOURS",
    "search.lazy_load_photos": "SEARCH_LAZY_LOAD_PHOTOS",
    "audit.retention_days": "AUDIT_RETENTION_DAYS",
    "audit.log_retention_days": "AUDIT_LOG_RETENTION_DAYS",
}

# Keys that are intentionally NOT migrated (bootstrap values stay in .env;
# debug toggle stays in DB per D-13 carve-out).
INTENTIONALLY_SKIPPED: set = {
    "flask.host",
    "flask.port",
    "flask.debug",
    "flask.secret_key",   # Replaced by env SECRET_KEY per .env.sandcastle.example
}


def _decrypt_legacy_value(fernet_key: bytes, ciphertext: str) -> str:
    """Decrypt a value that was encrypted by the legacy SimpleConfig._encrypt().

    SimpleConfig stores values as Fernet token strings (gAAAAAB...) using the
    raw Fernet key (44-char base64 URL-safe key, NOT PBKDF2-derived).
    """
    from cryptography.fernet import Fernet

    f = Fernet(fernet_key)
    return f.decrypt(ciphertext.encode("utf-8")).decode("utf-8")


def harvest_secrets(live_dsn: str, fernet_key: bytes) -> tuple[Dict[str, str], List[str]]:
    """Read+decrypt the legacy `configuration` rows.

    Returns a (mapped, unmapped) tuple:
      - mapped: {portal_env_key: decrypted_or_plain_value} for every row whose
        legacy key has a KEY_MAP entry.
      - unmapped: list of legacy keys that have NO KEY_MAP entry AND are not in
        INTENTIONALLY_SKIPPED. The caller MUST surface these to the operator
        so the operator either extends KEY_MAP or explicitly acknowledges the
        skip before running for real.
    """
    eng = create_engine(live_dsn)
    mapped: Dict[str, str] = {}
    unmapped: List[str] = []

    with eng.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT category, setting_key, setting_value, encrypted_value "
                "FROM configuration ORDER BY category, setting_key"
            )
        ).all()

    for category, setting_key, setting_value, encrypted_value in rows:
        legacy_key = f"{category}.{setting_key}"

        if legacy_key in INTENTIONALLY_SKIPPED:
            logger.debug("Intentionally skipping bootstrap key: %s", legacy_key)
            continue

        portal_key = KEY_MAP.get(legacy_key)
        if not portal_key:
            unmapped.append(legacy_key)
            continue

        # Determine raw value: prefer encrypted_value (decrypt it), else setting_value
        if encrypted_value:
            raw = encrypted_value
            # Handle memoryview objects from PostgreSQL BYTEA columns
            if hasattr(raw, "tobytes"):
                raw = raw.tobytes().decode("utf-8")
            else:
                raw = str(raw)

            if raw.startswith("gAAAAAB"):
                try:
                    value = _decrypt_legacy_value(fernet_key, raw)
                except Exception as exc:
                    logger.error("Failed to decrypt %s: %s", legacy_key, exc)
                    raise SystemExit(2)
            else:
                # Stored in encrypted_value column but not actually encrypted
                value = raw
        elif setting_value is not None:
            value = str(setting_value)
        else:
            logger.debug("Skipping NULL row: %s", legacy_key)
            continue

        mapped[portal_key] = value

    return mapped, unmapped


def fetch_existing_portal_vars(portal_base: str, token: str, app_id: str) -> Dict[str, str]:
    """GET current env vars for the app. Used for diff (Pitfall 6 idempotency)."""
    resp = requests.get(
        f"{portal_base}/api/apps/{app_id}/env-vars",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    resp.raise_for_status()
    payload = resp.json()
    # Portal returns {"env_vars": [{"key": ..., "value": "***"}, ...]} OR similar
    # We only need the keys for diffing — values may be masked.
    items = payload.get("env_vars") or payload.get("items") or []
    return {item["key"]: item.get("value", "") for item in items}


def post_new_vars(portal_base: str, token: str, app_id: str, new_vars: List[Dict[str, str]]) -> None:
    if not new_vars:
        logger.info("No new vars to push (already up to date).")
        return
    resp = requests.post(
        f"{portal_base}/api/apps/{app_id}/env-vars",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        data=json.dumps({"env_vars": new_vars}),
        timeout=60,
    )
    if resp.status_code >= 400:
        logger.error("Portal POST failed: %s %s", resp.status_code, resp.text[:500])
    resp.raise_for_status()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(
        description="Migrate Who-Dis encrypted-config secrets to the portal env-var store."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Decrypt + diff but do not POST; lists unmapped legacy keys",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-POST even if key already exists in portal (overwrite)",
    )
    parser.add_argument(
        "--acknowledge-unmapped",
        action="store_true",
        help=(
            "Required (non-dry-run) when the live configuration table contains "
            "keys not in KEY_MAP. Run --dry-run first to inspect; extend KEY_MAP "
            "or pass this flag to proceed."
        ),
    )
    args = parser.parse_args()

    live_dsn = os.environ["WHODIS_LIVE_DATABASE_URL"]
    fernet_key = os.environ["WHODIS_ENCRYPTION_KEY"].encode("utf-8")
    portal_base = os.environ["PORTAL_BASE"].rstrip("/")
    portal_token = os.environ["PORTAL_TOKEN"]
    app_id = os.environ["WHODIS_APP_ID"]

    logger.info("Harvesting secrets from %s ...", live_dsn.split("@")[-1])
    decrypted, unmapped = harvest_secrets(live_dsn, fernet_key)
    logger.info("Decrypted/read %d mapped keys: %s", len(decrypted), sorted(decrypted))

    if unmapped:
        logger.warning(
            "Found %d UNMAPPED legacy configuration keys (NOT being migrated): %s",
            len(unmapped),
            sorted(unmapped),
        )
        logger.warning(
            "If any of these are required at runtime, extend KEY_MAP in this script "
            "and re-run. Without --acknowledge-unmapped the script aborts in non-dry-run mode."
        )
        if not args.dry_run and not args.acknowledge_unmapped:
            logger.error(
                "Aborting: %d unmapped legacy keys present. Re-run with --dry-run to inspect, "
                "then either extend KEY_MAP or pass --acknowledge-unmapped to proceed.",
                len(unmapped),
            )
            return 3

    logger.info("Fetching existing portal env vars for app %s ...", app_id)
    existing = fetch_existing_portal_vars(portal_base, portal_token, app_id)

    if args.force:
        new_vars = [{"key": k, "value": v} for k, v in decrypted.items()]
    else:
        new_vars = [
            {"key": k, "value": v}
            for k, v in decrypted.items()
            if k not in existing
        ]
    skipped = sorted(set(decrypted) - {v["key"] for v in new_vars})
    logger.info(
        "To POST: %d. Skipped (already present, use --force to overwrite): %s",
        len(new_vars),
        skipped,
    )

    if args.dry_run:
        logger.info(
            "--dry-run: not POSTing. Would push: %s",
            sorted([v["key"] for v in new_vars]),
        )
        return 0

    post_new_vars(portal_base, portal_token, app_id, new_vars)
    logger.info("Done. Verify via portal UI: %s/apps/who-dis/env-vars", portal_base)
    return 0


if __name__ == "__main__":
    sys.exit(main())
