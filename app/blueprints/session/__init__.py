from flask import Blueprint, jsonify, request, session, g
from datetime import datetime
from app.models.session import UserSession
from app.models.audit import AuditLog
from app.services.configuration_service import config_get
from app.middleware.auth import require_role

session_bp = Blueprint("session", __name__, url_prefix="/api/session")


@session_bp.route("/config", methods=["GET"])
@require_role("viewer")
def get_session_config():
    """Get session configuration"""
    try:
        config = {
            "timeout_minutes": int(config_get("session", "timeout_minutes", 15)),
            "warning_minutes": int(config_get("session", "warning_minutes", 2)),
            "check_interval_seconds": int(
                config_get("session", "check_interval_seconds", 30)
            ),
        }
        return jsonify(config), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@session_bp.route("/check", methods=["POST"])
@require_role("viewer")
def check_session():
    """Check session status and update activity"""
    try:
        data = request.get_json()
        last_activity_timestamp = data.get("last_activity")

        # Get current session ID from Flask session
        session_id = session.get("session_id")
        if not session_id:
            return jsonify({"error": "No session found"}), 401

        # Get session from database
        user_session = UserSession.query.get(session_id)
        if not user_session or not user_session.is_active:
            return jsonify({"error": "Session not found or inactive"}), 401

        # Check if session is expired
        if user_session.is_expired():
            user_session.deactivate()
            session.clear()
            return jsonify({"error": "Session expired"}), 401

        # Get configuration
        timeout_minutes = int(config_get("session", "timeout_minutes", 15))
        warning_minutes = int(config_get("session", "warning_minutes", 2))

        # Update last activity if there was recent activity
        if last_activity_timestamp:
            client_activity = datetime.fromtimestamp(last_activity_timestamp)
            if client_activity > user_session.last_activity:
                user_session.update_activity()
                user_session.extend_session(timeout_minutes)

        # Calculate time until expiration
        time_until_expiry = (
            user_session.expires_at - datetime.utcnow()
        ).total_seconds()
        minutes_until_expiry = time_until_expiry / 60

        # Check if we should show warning
        should_show_warning = minutes_until_expiry <= warning_minutes

        response = {
            "session_valid": True,
            "expires_in_minutes": minutes_until_expiry,
            "should_show_warning": should_show_warning,
            "warning_shown": user_session.warning_shown,
            "timeout_minutes": timeout_minutes,
            "warning_minutes": warning_minutes,
        }

        # Mark warning as shown if needed
        if should_show_warning and not user_session.warning_shown:
            user_session.mark_warning_shown()

        return jsonify(response), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@session_bp.route("/extend", methods=["POST"])
@require_role("viewer")
def extend_session():
    """Extend the current session"""
    try:
        session_id = session.get("session_id")
        if not session_id:
            return jsonify({"error": "No session found"}), 401

        user_session = UserSession.query.get(session_id)
        if not user_session or not user_session.is_active:
            return jsonify({"error": "Session not found or inactive"}), 401

        # Get timeout configuration
        timeout_minutes = int(config_get("session", "timeout_minutes", 15))

        # Extend the session
        user_session.extend_session(timeout_minutes)

        # Log the session extension
        AuditLog.log_event(
            event_type="session",
            action="session_extended",
            user_email=g.user,
            ip_address=request.remote_addr,
            additional_data={
                "session_id": session_id,
                "extended_for_minutes": timeout_minutes,
            },
        )

        return jsonify(
            {
                "success": True,
                "new_expiry": user_session.expires_at.isoformat(),
                "timeout_minutes": timeout_minutes,
            }
        ), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@session_bp.route("/logout", methods=["POST"])
@require_role("viewer")
def logout():
    """Logout and deactivate session"""
    try:
        session_id = session.get("session_id")
        if session_id:
            user_session = UserSession.query.get(session_id)
            if user_session:
                user_session.deactivate()

        # Clear Flask session
        session.clear()

        # Log the logout
        AuditLog.log_event(
            event_type="auth",
            action="logout",
            user_email=g.user,
            ip_address=request.remote_addr,
            additional_data={"session_id": session_id},
        )

        return jsonify({"success": True}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
