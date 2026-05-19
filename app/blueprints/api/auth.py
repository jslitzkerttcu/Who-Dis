"""Bearer token authentication decorator for the REST API.

Validates API tokens from the Authorization header and sets
g.api_token and g.user for downstream handlers.
"""

import logging
from functools import wraps
from typing import Any, Callable

from flask import current_app, g, jsonify, request

logger = logging.getLogger(__name__)


def require_api_token(f: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator that requires a valid bearer token.

    Extracts the token from the Authorization header, validates it
    against the database, and sets g.api_token and g.user on success.

    On failure, returns a D-07 envelope error response.
    """

    @wraps(f)
    def decorated_function(*args: Any, **kwargs: Any) -> Any:
        auth_header = request.headers.get("Authorization", "")

        # Check for Bearer scheme
        if not auth_header.startswith("Bearer "):
            return jsonify({
                "error": {
                    "code": "MISSING_TOKEN",
                    "message": "Authorization header with Bearer token is required.",
                }
            }), 401

        raw_token = auth_header[7:].strip()
        if not raw_token:
            return jsonify({
                "error": {
                    "code": "MISSING_TOKEN",
                    "message": "Authorization header with Bearer token is required.",
                }
            }), 401

        # Validate via service layer — never log the raw token (T-10-02)
        token_service = current_app.container.get("external_api_token_service")  # type: ignore[attr-defined]
        token = token_service.validate_token(raw_token)

        if token is None:
            logger.warning("API auth failed: invalid or revoked token")
            return jsonify({
                "error": {
                    "code": "INVALID_TOKEN",
                    "message": "The provided API token is invalid or has been revoked.",
                }
            }), 401

        # Record usage and set request context
        token.record_usage()
        g.api_token = token
        # Pitfall 4: set g.user for audit trail compatibility
        g.user = f"api:{token.name}"

        return f(*args, **kwargs)

    return decorated_function
