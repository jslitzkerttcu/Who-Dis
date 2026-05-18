"""
External API token management for admin blueprint.
Handles token CRUD operations: create, list, and revoke.
"""

import json
import logging

from flask import current_app, g, jsonify, render_template, request
from app.middleware.auth import require_role
from app.services.audit_service_postgres import audit_service

logger = logging.getLogger(__name__)


@require_role("admin")
def manage_api_tokens():
    """Display the external API tokens management section."""
    token_service = current_app.container.get("external_api_token_service")
    tokens = token_service.list_tokens()
    return render_template("admin/_external_api_tokens.html", tokens=tokens)


@require_role("admin")
def create_api_token():
    """Create a new external API token.

    Expects form data with 'name' field (2-100 characters).
    Returns JSON with HX-Trigger containing the raw token for reveal modal.
    """
    token_service = current_app.container.get("external_api_token_service")

    name = request.form.get("name", "").strip()

    # Validate name
    if not name or len(name) < 2:
        return jsonify({
            "success": False,
            "error": "Token name must be at least 2 characters."
        }), 400

    if len(name) > 100:
        return jsonify({
            "success": False,
            "error": "Token name must be 100 characters or fewer."
        }), 400

    try:
        model, raw_token = token_service.create_token(
            name=name, created_by=g.user
        )

        # Audit log
        admin_role = getattr(request, "user_role", None)
        user_ip = request.headers.get("X-Forwarded-For", request.remote_addr)

        audit_service.log_admin_action(
            user_email=g.user,
            action="api_token_created",
            target=name,
            details={
                "token_id": model.id,
                "token_prefix": model.token_prefix,
            },
            user_role=admin_role,
            ip_address=user_ip,
            user_agent=request.headers.get("User-Agent"),
        )

        response = jsonify({"success": True})
        response.headers["HX-Trigger"] = json.dumps({
            "tokenCreated": {
                "token": raw_token,
                "name": name,
            }
        })
        return response

    except Exception as e:
        logger.error(f"Token creation failed: {str(e)}", exc_info=True)
        return jsonify({
            "success": False,
            "error": "Token creation failed. Please try again."
        }), 500


@require_role("admin")
def revoke_api_token(token_id):
    """Revoke an external API token.

    Args:
        token_id: Database ID of the token to revoke.
    """
    token_service = current_app.container.get("external_api_token_service")

    token = token_service.revoke_token(
        token_id=token_id, revoked_by=g.user
    )

    if token is None:
        return jsonify({
            "success": False,
            "error": "Token not found."
        }), 404

    # Audit log
    admin_role = getattr(request, "user_role", None)
    user_ip = request.headers.get("X-Forwarded-For", request.remote_addr)

    audit_service.log_admin_action(
        user_email=g.user,
        action="api_token_revoked",
        target=token.name,
        details={"token_id": token.id},
        user_role=admin_role,
        ip_address=user_ip,
        user_agent=request.headers.get("User-Agent"),
    )

    response = jsonify({
        "success": True,
        "message": f'Token "{token.name}" has been revoked',
    })
    response.headers["HX-Trigger"] = "tokenRevoked"
    return response


@require_role("admin")
def api_token_list():
    """Return the token list partial for HTMX refresh after create/revoke."""
    token_service = current_app.container.get("external_api_token_service")
    tokens = token_service.list_tokens()
    return render_template("admin/_external_api_tokens.html", tokens=tokens)
