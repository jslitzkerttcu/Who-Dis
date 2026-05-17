"""
Portal authentication decorator for SandCastle job API.

Allows either admin session (via existing auth) or M2M Bearer token
from the SandCastle scheduler service account validated against Keycloak JWKS.
"""

import logging
import os
from functools import wraps
from typing import Optional

import jwt
from jwt import PyJWKClient

from flask import abort, current_app, g, request

logger = logging.getLogger(__name__)

PORTAL_SERVICE_ACCOUNT = "sandcastle-scheduler"

_jwks_client: Optional[PyJWKClient] = None


def _get_jwks_client() -> PyJWKClient:
    """Get or create a cached PyJWKClient for Keycloak token validation."""
    global _jwks_client
    if _jwks_client is None:
        issuer = os.environ.get("KEYCLOAK_ISSUER", "")
        if not issuer:
            logger.error("KEYCLOAK_ISSUER environment variable not set")
            raise ValueError("KEYCLOAK_ISSUER environment variable not set")
        jwks_url = f"{issuer}/protocol/openid-connect/certs"
        _jwks_client = PyJWKClient(jwks_url)
    return _jwks_client


def admin_or_portal_required(f):
    """
    Decorator that allows access for:
    1. Admin session users (g.user set and g.role == 'admin')
    2. SandCastle scheduler M2M Bearer tokens validated via Keycloak JWKS
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check for existing admin session
        if g.get("user") and g.get("role") == "admin":
            return f(*args, **kwargs)

        # Check for Bearer token from portal
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            logger.warning("admin_or_portal_required: no admin session and no Bearer token")
            abort(403)

        token = auth_header[7:]  # Strip "Bearer " prefix

        try:
            # Peek at unverified claims to check azp
            unverified = jwt.decode(
                token, options={"verify_signature": False}, algorithms=["RS256"]
            )
            azp = unverified.get("azp", "")
            if azp != PORTAL_SERVICE_ACCOUNT:
                logger.warning(
                    f"admin_or_portal_required: azp '{azp}' does not match expected "
                    f"'{PORTAL_SERVICE_ACCOUNT}'"
                )
                abort(403)

            # Full RS256 verification via JWKS
            jwks_client = _get_jwks_client()
            signing_key = jwks_client.get_signing_key_from_jwt(token)

            issuer = os.environ.get("KEYCLOAK_ISSUER", "")
            jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                issuer=issuer,
                options={"verify_aud": False},
            )

            # Token validated - set service account identity
            g.user = PORTAL_SERVICE_ACCOUNT
            return f(*args, **kwargs)

        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, Exception) as e:
            logger.warning(f"admin_or_portal_required: token validation failed: {e}")
            abort(403)

    return decorated_function
