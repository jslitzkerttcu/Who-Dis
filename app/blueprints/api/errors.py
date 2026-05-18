"""API-specific error handlers returning D-07 envelope format.

All API errors are returned as JSON with a consistent structure:
  {"error": {"code": "ERROR_CODE", "message": "...", "details": {...}}}
"""

import logging

from flask import jsonify

logger = logging.getLogger(__name__)

# Error code constants
BAD_REQUEST = "BAD_REQUEST"
INVALID_TOKEN = "INVALID_TOKEN"
FORBIDDEN = "FORBIDDEN"
NOT_FOUND = "NOT_FOUND"
VALIDATION_ERROR = "VALIDATION_ERROR"
RATE_LIMITED = "RATE_LIMITED"
INTERNAL_ERROR = "INTERNAL_ERROR"


def _error_response(code: str, message: str, status: int, details: dict = None):
    """Build a D-07 error envelope response."""
    error = {"code": code, "message": message}
    if details:
        error["details"] = details
    return jsonify({"error": error}), status


def register_api_error_handlers(app_or_bp):
    """Register JSON error handlers for API routes.

    Args:
        app_or_bp: Flask app or blueprint to register handlers on.
    """

    @app_or_bp.errorhandler(400)
    def handle_400(e):
        return _error_response(
            BAD_REQUEST,
            getattr(e, "description", "Bad request."),
            400,
        )

    @app_or_bp.errorhandler(401)
    def handle_401(e):
        return _error_response(
            INVALID_TOKEN,
            getattr(e, "description", "Authentication required."),
            401,
        )

    @app_or_bp.errorhandler(403)
    def handle_403(e):
        return _error_response(
            FORBIDDEN,
            getattr(e, "description", "You do not have permission to access this resource."),
            403,
        )

    @app_or_bp.errorhandler(404)
    def handle_404(e):
        return _error_response(
            NOT_FOUND,
            getattr(e, "description", "The requested resource was not found."),
            404,
        )

    @app_or_bp.errorhandler(422)
    def handle_422(e):
        # flask-smorest/webargs sends validation errors as 422
        details = {}
        if hasattr(e, "data") and "messages" in getattr(e, "data", {}):
            details = e.data["messages"]
        return _error_response(
            VALIDATION_ERROR,
            "Request validation failed.",
            422,
            details=details or None,
        )

    @app_or_bp.errorhandler(429)
    def handle_429(e):
        # API-05: include Retry-After header
        response, status = _error_response(
            RATE_LIMITED,
            "Rate limit exceeded. Please retry after the indicated period.",
            429,
        )
        # Flask-Limiter sets Retry-After on the original response;
        # copy it if available, otherwise default to 60s.
        retry_after = None
        if hasattr(e, "response") and e.response is not None:
            retry_after = e.response.headers.get("Retry-After")
        if retry_after is None:
            retry_after = getattr(e, "description", None)
            if retry_after and not str(retry_after).isdigit():
                retry_after = "60"
        response.headers["Retry-After"] = str(retry_after or "60")
        return response, status

    @app_or_bp.errorhandler(500)
    def handle_500(e):
        # T-10-03: never expose stack traces
        logger.error(
            f"API internal error: {e}",
            exc_info=True,
        )
        return _error_response(
            INTERNAL_ERROR,
            "An unexpected error occurred. Please try again later.",
            500,
        )
