"""Authentication handler — Phase 9 SandCastle (D-04, WD-AUTH-01, WD-AUTH-08).

Identity now comes from the Flask session populated by the Authlib OIDC
callback (see app/auth/oidc.py). All Easy-Auth / Azure App Service header
reading and the legacy dev-bypass env-var are deleted — Keycloak is the only
auth path (D-04). See WD-AUTH-08 and the Phase 9 audit trail for removed code.
"""
import logging
from typing import Optional

from flask import g, session

logger = logging.getLogger(__name__)


class AuthenticationHandler:
    """Reads identity from the OIDC-populated Flask session (D-04, WD-AUTH-01)."""

    def authenticate_user(self) -> Optional[str]:
        """Return the lower-cased email of the authenticated user, or None."""
        user = session.get("user")
        if user and user.get("email"):
            return str(user["email"]).strip().lower()
        return None

    def is_authenticated(self) -> bool:
        return self.authenticate_user() is not None

    def set_user_context(self, email: str, role: str) -> None:
        """Set per-request identity context for downstream code (g.user, g.role)."""
        g.user = email
        g.role = role
