import logging
import os
from typing import Optional

from flask import g, request

from app.services.configuration_service import config_get

logger = logging.getLogger(__name__)


class AuthenticationHandler:
    """Handles user authentication from Azure AD headers"""

    def authenticate_user(self) -> Optional[str]:
        """
        Extract and validate user email from the configured principal header.

        Default header name is ``X-MS-CLIENT-PRINCIPAL-NAME`` (Azure App Service),
        but ``auth.principal_header`` can override for non-Azure reverse proxies
        (nginx, Traefik, etc.).

        Development bypass: when the OS environment variable
        ``DANGEROUS_DEV_AUTH_BYPASS_USER`` is set, every request authenticates
        as that user and a WARNING-level log line is emitted on each call.
        This is env-var-only by design — operators must redeploy with the
        variable set; it cannot be flipped from the admin UI. NEVER set this
        in production.

        Returns:
            str: User email if authenticated, None otherwise
        """
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

        # Basic auth has been disabled for security reasons
        # Only Azure AD authentication (or configured equivalent) is supported
        return None

    def is_authenticated(self) -> bool:
        """Check if current request is authenticated"""
        return self.authenticate_user() is not None

    def set_user_context(self, email: str, role: str) -> None:
        """Set user context in Flask g object"""
        g.user = email
        g.role = role
