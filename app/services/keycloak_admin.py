"""Keycloak Admin REST client for service-account operations.

Phase 9 follow-up — auto-grants the `who-dis` client role to a user on their
first federated login so federated users don't hit the "logged in but
unauthorized" loop documented in 09-RESEARCH.md.

Uses the confidential `who-dis` client's service account (client_credentials
grant) — no separate admin password is plumbed into this app. Prerequisites
on the Keycloak side (one-time):

  - Client `who-dis` has serviceAccountsEnabled=true
  - Its service account holds realm-management roles `view-users` and
    `manage-users` (composites pull in `query-users`, `query-groups`)

Issuer/realm/client config is read from the same env vars Authlib already
consumes (KEYCLOAK_ISSUER, KEYCLOAK_CLIENT_ID, KEYCLOAK_CLIENT_SECRET) — no
new secrets to provision.
"""

import logging
import os
import threading
import time
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import requests

logger = logging.getLogger(__name__)

_TOKEN_REFRESH_LEEWAY_SECONDS = 30


class KeycloakAdminError(Exception):
    """Raised when an admin REST call fails."""


class KeycloakAdminClient:
    """Minimal Keycloak Admin REST client. Public methods are idempotent."""

    def __init__(
        self,
        issuer: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        admin_base_url: Optional[str] = None,
        timeout: float = 10.0,
        session: Optional[requests.Session] = None,
    ):
        self._issuer = issuer or os.environ["KEYCLOAK_ISSUER"]
        self._client_id = client_id or os.environ["KEYCLOAK_CLIENT_ID"]
        self._client_secret = client_secret or os.environ["KEYCLOAK_CLIENT_SECRET"]
        parsed = urlparse(self._issuer)
        # Issuer URL is .../realms/<realm>; realm is the last path segment.
        self._realm = parsed.path.rstrip("/").rsplit("/", 1)[-1]
        self._admin_base = (
            admin_base_url
            or f"{parsed.scheme}://{parsed.netloc}/admin/realms/{self._realm}"
        )
        self._timeout = timeout
        self._session = session or requests.Session()

        self._token: Optional[str] = None
        self._token_expires_at: float = 0.0
        self._token_lock = threading.Lock()
        self._client_uuid_cache: Dict[str, str] = {}

    def _fetch_token(self) -> None:
        url = f"{self._issuer.rstrip('/')}/protocol/openid-connect/token"
        resp = self._session.post(
            url,
            data={
                "grant_type": "client_credentials",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
            },
            timeout=self._timeout,
        )
        if resp.status_code != 200:
            raise KeycloakAdminError(
                f"client_credentials token request failed: {resp.status_code} {resp.text[:200]}"
            )
        body = resp.json()
        self._token = body["access_token"]
        expires_in = int(body.get("expires_in", 60))
        self._token_expires_at = time.monotonic() + max(
            expires_in - _TOKEN_REFRESH_LEEWAY_SECONDS, 5
        )

    def _ensure_token(self) -> str:
        with self._token_lock:
            if not self._token or time.monotonic() >= self._token_expires_at:
                self._fetch_token()
            assert self._token is not None
            return self._token

    def _admin_request(
        self,
        method: str,
        path: str,
        *,
        json_body: Optional[Any] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> requests.Response:
        token = self._ensure_token()
        url = f"{self._admin_base}{path}"
        for attempt in (0, 1):
            resp = self._session.request(
                method,
                url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json",
                },
                json=json_body,
                params=params,
                timeout=self._timeout,
            )
            if resp.status_code == 401 and attempt == 0:
                # Token may have been revoked or rotated; refresh once and retry.
                with self._token_lock:
                    self._token = None
                token = self._ensure_token()
                continue
            return resp
        raise KeycloakAdminError("unreachable")  # pragma: no cover

    def find_user_id_by_email(self, email: str) -> Optional[str]:
        """Return the Keycloak user UUID for `email`, or None if unknown."""
        resp = self._admin_request(
            "GET", "/users", params={"email": email, "exact": "true"}
        )
        if resp.status_code != 200:
            raise KeycloakAdminError(
                f"GET /users failed: {resp.status_code} {resp.text[:200]}"
            )
        users = resp.json()
        if not users:
            return None
        return users[0]["id"]

    def get_client_uuid(self, client_id: str) -> str:
        if client_id in self._client_uuid_cache:
            return self._client_uuid_cache[client_id]
        resp = self._admin_request("GET", "/clients", params={"clientId": client_id})
        if resp.status_code != 200:
            raise KeycloakAdminError(
                f"GET /clients failed: {resp.status_code} {resp.text[:200]}"
            )
        clients = resp.json()
        if not clients:
            raise KeycloakAdminError(f"no client with clientId={client_id!r}")
        uuid = clients[0]["id"]
        self._client_uuid_cache[client_id] = uuid
        return uuid

    def assign_client_role(
        self, *, user_id: str, client_id: str, role_name: str
    ) -> bool:
        """Assign the named client role. Returns True if newly assigned, False if already present."""
        client_uuid = self.get_client_uuid(client_id)
        existing = self._admin_request(
            "GET", f"/users/{user_id}/role-mappings/clients/{client_uuid}"
        )
        if existing.status_code != 200:
            raise KeycloakAdminError(
                f"GET role-mappings failed: {existing.status_code} {existing.text[:200]}"
            )
        if any(r.get("name") == role_name for r in existing.json()):
            return False

        role_resp = self._admin_request(
            "GET", f"/clients/{client_uuid}/roles/{role_name}"
        )
        if role_resp.status_code != 200:
            raise KeycloakAdminError(
                f"GET client role {role_name!r} failed: {role_resp.status_code} {role_resp.text[:200]}"
            )
        role_repr = role_resp.json()

        post_resp = self._admin_request(
            "POST",
            f"/users/{user_id}/role-mappings/clients/{client_uuid}",
            json_body=[{"id": role_repr["id"], "name": role_repr["name"]}],
        )
        if post_resp.status_code not in (201, 204):
            raise KeycloakAdminError(
                f"POST role-mappings failed: {post_resp.status_code} {post_resp.text[:200]}"
            )
        return True
