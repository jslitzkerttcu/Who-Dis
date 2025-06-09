"""Admin configuration management routes."""

import logging
from flask import render_template, request, jsonify, session
from app.middleware.auth import require_role
from app.utils.error_handler import handle_errors
from app.blueprints.admin import admin_bp
from sqlalchemy import text
from app.database import db

logger = logging.getLogger(__name__)


@admin_bp.route("/config")
@require_role("admin")
@handle_errors()
def configuration():
    """Display polished configuration page."""
    return render_template("admin/configuration.html")


@admin_bp.route("/api/config", methods=["GET"])
@require_role("admin")
@handle_errors(json_response=True)
def api_get_config():
    """Get all configuration values."""
    from app.services.configuration_service import config_get_all

    config_data = config_get_all()

    # Get metadata about which fields have encrypted values
    encrypted_fields = []
    try:
        # Query database directly to find fields with encrypted values
        result = db.session.execute(
            text("""
                SELECT category, setting_key 
                FROM configuration 
                WHERE is_sensitive = true AND encrypted_value IS NOT NULL
            """)
        )

        for row in result:
            key = f"{row.category}.{row.setting_key}"
            encrypted_fields.append(key)
    except Exception as e:
        logger.error(f"Error checking encrypted fields: {e}")

    return jsonify({"config": config_data, "encrypted_fields": encrypted_fields})


@admin_bp.route("/api/config", methods=["POST"])
@require_role("admin")
@handle_errors(json_response=True)
def api_set_config():
    """Set a configuration value."""
    from app.services.configuration_service import config_set, config_clear_cache
    from app.services.audit_service_postgres import audit_service

    data = request.get_json()
    key = data.get("key")
    value = data.get("value")

    if not key:
        return jsonify({"error": "Key is required"}), 400

    user_email = session.get("user_email", "system")
    success = config_set(key, value, user_email)

    if success:
        # Clear configuration cache so services get fresh values
        config_clear_cache()

        # Log the configuration change
        audit_service.log_config(
            user_email=user_email,
            config_key=key,
            old_value="(not logged)",  # Don't log actual values for security
            new_value="(not logged)",
            ip_address=request.remote_addr,
        )

        return jsonify({"success": True})
    else:
        return jsonify({"error": "Failed to set configuration"}), 500


@admin_bp.route("/api/config/<key>", methods=["DELETE"])
@require_role("admin")
@handle_errors(json_response=True)
def api_delete_config(key: str):
    """Delete a configuration value."""
    from app.services.configuration_service import config_delete
    from app.services.audit_service_postgres import audit_service

    user_email = session.get("user_email", "system")
    success = config_delete(key)

    if success:
        # Log the configuration deletion
        audit_service.log_config(
            user_email=user_email,
            config_key=key,
            old_value="(deleted)",
            new_value=None,
            ip_address=request.remote_addr,
        )

        return jsonify({"success": True})
    else:
        return jsonify({"error": "Failed to delete configuration"}), 500
