from flask import request, g
from typing import Optional


class AuthenticationHandler:
    """Handles user authentication from Azure AD headers"""

    def authenticate_user(self) -> Optional[str]:
        """
        Extract and validate user email from Azure AD headers

        Returns:
            str: User email if authenticated, None otherwise
        """
        # Check for Azure AD principal header
        ms_principal = request.headers.get("X-MS-CLIENT-PRINCIPAL-NAME")
        if ms_principal:
            return ms_principal

        # Basic auth has been disabled for security reasons
        # Only Azure AD authentication is supported
        return None

    def is_authenticated(self) -> bool:
        """Check if current request is authenticated"""
        return self.authenticate_user() is not None

    def set_user_context(self, email: str, role: str) -> None:
        """Set user context in Flask g object"""
        g.user = email
        g.role = role
