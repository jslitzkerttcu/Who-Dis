"""REST API user profile endpoint.

Provides GET /api/v1/user/<email> with full merged profile in D-04
JSON envelope, per-token rate limiting, and audit logging.
"""

import logging
from typing import Any, Dict

from flask import g, jsonify
from flask.views import MethodView
from flask_smorest import Blueprint

from app import limiter
from app.blueprints.api.auth import require_api_token
from app.blueprints.api.schemas import ProfileResponseSchema
from app.blueprints.api.search import API_RATE_LIMIT, _api_token_rate_key

logger = logging.getLogger(__name__)

api_users_bp = Blueprint(
    "api_v1_users",
    __name__,
    description="User profile lookup",
)


def _sanitize_profile(profile: Dict[str, Any]) -> Dict[str, Any]:
    """Remove binary photo data from profile and add photo_available flag.

    T-10-08: Omit base64 photo data from JSON responses to keep
    response sizes manageable and prevent information disclosure.
    """
    sanitized = dict(profile)

    # Check for photo data under common keys
    photo_keys = ["photo", "photo_base64", "profilePhoto", "thumbnail_photo"]
    photo_found = False
    for key in photo_keys:
        if key in sanitized and sanitized[key]:
            photo_found = True
            del sanitized[key]

    sanitized["photo_available"] = photo_found
    return sanitized


@api_users_bp.route("/user/<string:email>")
class UserProfileResource(MethodView):
    """Retrieve a full merged profile for a single user by email."""

    @api_users_bp.response(200, ProfileResponseSchema)
    @require_api_token
    @limiter.limit(lambda: API_RATE_LIMIT, key_func=_api_token_rate_key)
    def get(self, email: str) -> Any:
        """Look up a user profile by email address.

        Args:
            email: The email address of the user to look up.

        Returns:
            D-04 envelope with the full merged profile, or 404 if not found.
        """
        # Normalize email input
        email = email.strip().lower()

        from app.services.search_orchestrator import SearchOrchestrator
        from app.services.result_merger import ResultMerger

        orchestrator = SearchOrchestrator()
        merger = ResultMerger()

        # Use email as search term for direct lookup
        ldap_result, genesys_result, graph_result = (
            orchestrator.execute_concurrent_search(email)
        )

        # Merge Azure AD (LDAP + Graph) results
        azure_ad_result, azure_ad_error, azure_ad_multiple = (
            merger.merge_azure_ad_results(ldap_result, genesys_result, graph_result)
        )

        # Build the merged profile
        merged_profile = None

        if azure_ad_result is not None:
            if azure_ad_multiple and isinstance(azure_ad_result, dict):
                # Multiple results returned; try to find exact email match
                multiple_items = azure_ad_result.get("multiple_results", [])
                if multiple_items:
                    for item in multiple_items:
                        item_email = (item.get("email") or item.get("mail") or "").lower()
                        if item_email == email:
                            merged_profile = item
                            break
                    if merged_profile is None:
                        # Take first result as best match
                        merged_profile = multiple_items[0]
                else:
                    merged_profile = azure_ad_result
            else:
                merged_profile = azure_ad_result

        # Include Genesys data if available and not already merged
        genesys_data = genesys_result.get("result") if isinstance(genesys_result, dict) else None
        if genesys_data and merged_profile:
            # Add Genesys-specific fields to the profile
            for key in ["genesys_presence", "genesys_queues", "genesys_skills",
                        "genesys_status", "genesys_id"]:
                if key in genesys_data:
                    merged_profile[key] = genesys_data[key]

        # T-10-07: Return 404 (not 403) to prevent email enumeration
        if merged_profile is None:
            return jsonify({
                "error": {
                    "code": "USER_NOT_FOUND",
                    "message": "The requested user was not found.",
                }
            }), 404

        # T-10-08: Sanitize photo data from response
        sanitized_profile = _sanitize_profile(merged_profile)

        # Audit the profile lookup (API-04: every call audited)
        try:
            from flask import current_app

            audit_service = current_app.container.get("audit_service")
            audit_service.log_access(
                user_email=g.user,
                action="api_profile_lookup",
                target_resource=email,
            )
        except Exception as e:
            logger.error(f"Failed to audit API profile lookup: {e}", exc_info=True)

        return {
            "data": sanitized_profile,
            "meta": {
                "page": 1,
                "page_size": 1,
                "total": 1,
            },
            "errors": None,
        }
