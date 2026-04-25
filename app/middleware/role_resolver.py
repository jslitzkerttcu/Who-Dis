"""Role resolver — Phase 9 SandCastle (D-03, D-05, D-06, WD-AUTH-05).

Role is sourced from session["user"]["roles"] (populated by the OIDC callback
from `resource_access.{KEYCLOAK_CLIENT_ID}.roles` per the Keycloak `client-roles`
protocol mapper added in Plan 01). The legacy users.role DB column is no longer
read for authorization (D-06) — it remains in the DB for audit/legacy purposes.

D-05 collapses the hierarchy from {viewer, editor, admin} to {viewer, admin}.
The pre-existing editor tier is intentionally absent. Plan 05's role-seeding
script promotes existing users.role IN ('admin', 'editor') to Keycloak admin.
Existing routes guarded by @require_role("editor") are remapped in Task 3.
"""
import logging
from typing import List, Optional, Tuple

from flask import session

logger = logging.getLogger(__name__)


class RoleResolver:
    """Determines effective role from the OIDC ID-token cached in the session."""

    # D-05 — two-tier hierarchy. editor is REMOVED.
    ROLE_HIERARCHY = {"viewer": 1, "admin": 2}

    def get_user_role(self, email: str) -> Optional[str]:
        """Return 'admin', 'viewer', or None — sourced from cached ID-token claims (D-03/D-06).

        Note: the `email` argument is retained for API compatibility with the
        existing decorator call site but is intentionally NOT used here — the
        token claim is the authoritative source per D-06.
        """
        user = session.get("user") or {}
        roles = user.get("roles") or []
        if "admin" in roles:
            return "admin"
        if "viewer" in roles:
            return "viewer"
        return None

    def has_minimum_role(self, user_role: str, minimum_role: str) -> bool:
        if user_role not in self.ROLE_HIERARCHY:
            return False
        # Treat the legacy 'editor' minimum as 'admin' for backward-compat
        # while the Task 3 audit migrates explicit decorators.
        if minimum_role == "editor":
            minimum_role = "admin"
        if minimum_role not in self.ROLE_HIERARCHY:
            return False
        return self.ROLE_HIERARCHY[user_role] >= self.ROLE_HIERARCHY[minimum_role]

    def is_valid_role(self, role: str) -> bool:
        return role in self.ROLE_HIERARCHY

    def _load_role_lists(self) -> Tuple[List[str], List[str], List[str]]:
        """Deprecated. Kept as a no-op for any external caller; returns empty lists."""
        return [], [], []
