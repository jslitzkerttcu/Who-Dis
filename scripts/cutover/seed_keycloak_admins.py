"""Phase 9 cutover — D-07: pre-seed existing Who-Dis admins as Keycloak who-dis admin role.

Idempotent (Pitfall 6). Skips users already mapped; tolerates "user not found"
in Keycloak (legacy admin no longer in Azure AD) with a WARNING.

Usage:
    set -o allexport; source secrets.env; set +o allexport
    python scripts/cutover/seed_keycloak_admins.py [--dry-run] [--include-editors]

By default, ONLY users with users.role='admin' are seeded as Keycloak admin.
With --include-editors, users.role IN ('admin','editor') are seeded as admin
(matches the Plan 03 editor->admin remap default). Recommend running with
--include-editors per the auto-mode editor remap decision.

Required env:
    WHODIS_LIVE_DATABASE_URL — read access to legacy Who-Dis DB
    KEYCLOAK_BASE            — e.g. https://auth.sandcastle.ttcu.com
    KC_REALM                 — sandcastle
    KC_CLIENT                — who-dis
    KC_ADMIN_USER            — Keycloak admin console user
    KC_ADMIN_PASS            — Keycloak admin console password
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from typing import List, Optional

import requests
from sqlalchemy import create_engine, text

logger = logging.getLogger("seed_keycloak_admins")


def get_admin_token(kc_base: str, user: str, password: str) -> str:
    """Obtain a Keycloak admin-cli access token."""
    resp = requests.post(
        f"{kc_base}/realms/master/protocol/openid-connect/token",
        data={
            "grant_type": "password",
            "client_id": "admin-cli",
            "username": user,
            "password": password,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def get_client_uuid(kc_base: str, realm: str, client_id: str, headers: dict) -> str:
    """Look up the internal UUID of a Keycloak client by clientId."""
    resp = requests.get(
        f"{kc_base}/admin/realms/{realm}/clients",
        params={"clientId": client_id},
        headers=headers,
        timeout=30,
    )
    resp.raise_for_status()
    clients = resp.json()
    if not clients:
        raise SystemExit(f"Client '{client_id}' not found in realm '{realm}'")
    return clients[0]["id"]


def get_role_rep(kc_base: str, realm: str, client_uuid: str, role_name: str, headers: dict) -> dict:
    """Fetch the role representation object needed for role-mapping POST body."""
    resp = requests.get(
        f"{kc_base}/admin/realms/{realm}/clients/{client_uuid}/roles/{role_name}",
        headers=headers,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def find_user_id(kc_base: str, realm: str, email: str, headers: dict) -> Optional[str]:
    """Return Keycloak user UUID for the given email, or None if not found."""
    resp = requests.get(
        f"{kc_base}/admin/realms/{realm}/users",
        params={"email": email, "exact": "true"},
        headers=headers,
        timeout=30,
    )
    resp.raise_for_status()
    users = resp.json()
    return users[0]["id"] if users else None


def has_role_already(
    kc_base: str,
    realm: str,
    user_id: str,
    client_uuid: str,
    role_name: str,
    headers: dict,
) -> bool:
    """Return True if the user already has the named client role mapped."""
    resp = requests.get(
        f"{kc_base}/admin/realms/{realm}/users/{user_id}/role-mappings/clients/{client_uuid}",
        headers=headers,
        timeout=30,
    )
    resp.raise_for_status()
    mapped = {r["name"] for r in resp.json()}
    return role_name in mapped


def assign_role(
    kc_base: str,
    realm: str,
    user_id: str,
    client_uuid: str,
    role_rep: dict,
    headers: dict,
) -> None:
    """POST the role-mapping assignment for a single user."""
    resp = requests.post(
        f"{kc_base}/admin/realms/{realm}/users/{user_id}/role-mappings/clients/{client_uuid}",
        headers={**headers, "Content-Type": "application/json"},
        json=[role_rep],
        timeout=30,
    )
    resp.raise_for_status()


def harvest_admin_emails(live_dsn: str, include_editors: bool) -> List[str]:
    """Query legacy Who-Dis DB for active admin (and optionally editor) emails."""
    eng = create_engine(live_dsn)
    if include_editors:
        sql = "SELECT email FROM users WHERE is_active = TRUE AND role IN ('admin', 'editor')"
    else:
        sql = "SELECT email FROM users WHERE is_active = TRUE AND role = 'admin'"
    with eng.connect() as conn:
        rows = conn.execute(text(sql)).all()
    return sorted({str(r[0]).strip().lower() for r in rows if r[0]})


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(
        description="Pre-seed Who-Dis legacy admins as Keycloak who-dis admin role."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Query legacy DB and Keycloak but do not assign roles",
    )
    parser.add_argument(
        "--include-editors",
        action="store_true",
        help=(
            "Also seed users.role='editor' as Keycloak admin "
            "(matches Plan 03 auto-mode editor -> admin remap)"
        ),
    )
    args = parser.parse_args()

    live_dsn = os.environ["WHODIS_LIVE_DATABASE_URL"]
    kc_base = os.environ["KEYCLOAK_BASE"].rstrip("/")
    kc_realm = os.environ.get("KC_REALM", "sandcastle")
    kc_client = os.environ.get("KC_CLIENT", "who-dis")
    kc_user = os.environ["KC_ADMIN_USER"]
    kc_pass = os.environ["KC_ADMIN_PASS"]

    emails = harvest_admin_emails(live_dsn, args.include_editors)
    logger.info(
        "Found %d legacy %s emails: %s",
        len(emails),
        "admin+editor" if args.include_editors else "admin",
        emails,
    )

    if args.dry_run:
        logger.info(
            "--dry-run: not assigning roles. Would attempt to seed %d users.",
            len(emails),
        )
        return 0

    if not emails:
        logger.info("No eligible users found; nothing to do.")
        return 0

    token = get_admin_token(kc_base, kc_user, kc_pass)
    headers = {"Authorization": f"Bearer {token}"}

    client_uuid = get_client_uuid(kc_base, kc_realm, kc_client, headers)
    logger.info("Keycloak client UUID for '%s': %s", kc_client, client_uuid)
    admin_role_rep = get_role_rep(kc_base, kc_realm, client_uuid, "admin", headers)

    seeded, skipped, missing = 0, 0, 0
    for email in emails:
        user_id = find_user_id(kc_base, kc_realm, email, headers)
        if not user_id:
            logger.warning(
                "User not found in Keycloak (skipping): %s — "
                "investigate whether this user is still in Azure AD; "
                "if needed, assign manually in Keycloak admin console post-cutover.",
                email,
            )
            missing += 1
            continue

        if has_role_already(kc_base, kc_realm, user_id, client_uuid, "admin", headers):
            logger.info("Already has %s.admin role (skip): %s", kc_client, email)
            skipped += 1
            continue

        assign_role(kc_base, kc_realm, user_id, client_uuid, admin_role_rep, headers)
        logger.info("Assigned %s.admin to %s", kc_client, email)
        seeded += 1

    logger.info(
        "Done. Seeded=%d  Skipped(already-mapped)=%d  Missing-in-Keycloak=%d",
        seeded,
        skipped,
        missing,
    )
    if missing > 0:
        logger.warning(
            "%d user(s) were not found in Keycloak. "
            "They will NOT have admin access on day 1. "
            "Review and assign manually via Keycloak admin console.",
            missing,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
