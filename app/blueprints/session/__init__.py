from flask import Blueprint, jsonify, request, session, g
from datetime import datetime, timezone
from app.models.session import UserSession
from app.models.unified_log import LogEntry
from app.services.configuration_service import config_get
from app.utils.error_handler import handle_errors

session_bp = Blueprint("session", __name__, url_prefix="/api/session")


@session_bp.route("/config", methods=["GET"])
@handle_errors(json_response=True)
def get_session_config():
    """Get session configuration"""
    config = {
        "timeout_minutes": int(config_get("session.timeout_minutes", 15)),
        "warning_minutes": int(config_get("session.warning_minutes", 2)),
        "check_interval_seconds": int(
            config_get("session.check_interval_seconds", 30)
        ),
    }
    return jsonify(config), 200


@session_bp.route("/check", methods=["POST"])
@handle_errors(json_response=True)
def check_session():
    """Check session status and update activity"""
    # Manual authentication to avoid HTML responses
    from app.middleware.auth import authenticate

    if not authenticate():
        return jsonify(
            {"error": "Authentication required", "authenticated": False}
        ), 401

    data = request.get_json()
    last_activity_timestamp = data.get("last_activity")

    # Ensure we have current user info from authentication
    if not g.user:
        return jsonify({"error": "No authenticated user"}), 401

    # Get current session ID from Flask session
    session_id = session.get("session_id")
    if not session_id:
        return jsonify(
            {
                "error": "No session found",
                "debug": {
                    "flask_session_keys": list(session.keys()),
                    "user": g.user,
                    "role": g.role,
                },
            }
        ), 401

    # Get session from database
    user_session = UserSession.query.get(session_id)
    if not user_session or not user_session.is_active:
        return jsonify({"error": "Session not found or inactive"}), 401

    # Check if session is expired
    if user_session.is_expired():
        user_session.deactivate()
        session.clear()

        # Try to create a new session for the current user
        from app.models.user import User
        import secrets

        user = User.get_by_email(g.user)
        if user:
            timeout_minutes = int(config_get("session.timeout_minutes", 15))
            new_session_id = secrets.token_urlsafe(32)
            new_user_session = UserSession.create_session(
                session_id=new_session_id,
                user_id=user.id,
                user_email=g.user,
                timeout_minutes=timeout_minutes,
                ip_address=request.headers.get("X-Forwarded-For", request.remote_addr),
                user_agent=request.headers.get("User-Agent"),
            )
            session["session_id"] = new_user_session.id

            # Return success with new session info
            return jsonify(
                {
                    "session_valid": True,
                    "new_session_created": True,
                    "expires_in_minutes": timeout_minutes,
                    "should_show_warning": False,
                    "warning_shown": False,
                    "timeout_minutes": timeout_minutes,
                    "warning_minutes": int(config_get("session.warning_minutes", 2)),
                }
            ), 200

        # If we can't create a new session, return expired error
        return jsonify({"error": "Session expired - unable to create new session"}), 401

    # Get configuration
    timeout_minutes = int(config_get("session.timeout_minutes", 15))
    warning_minutes = int(config_get("session.warning_minutes", 2))

    # Update last activity if there was recent activity
    if last_activity_timestamp:
        client_activity = datetime.fromtimestamp(
            last_activity_timestamp, tz=timezone.utc
        )
        # Ensure user_session.last_activity is timezone-aware for comparison
        last_activity = user_session.last_activity
        if last_activity.tzinfo is None:
            last_activity = last_activity.replace(tzinfo=timezone.utc)
        if client_activity > last_activity:
            user_session.update_activity()
            user_session.extend_session(timeout_minutes)

    # Calculate time until expiration with proper timezone handling
    now = datetime.now(timezone.utc)
    expires_at = user_session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    time_until_expiry = (expires_at - now).total_seconds()
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


@session_bp.route("/extend", methods=["POST"])
@handle_errors(json_response=True)
def extend_session():
    """Extend the current session"""
    # Manual authentication to avoid HTML responses
    from app.middleware.auth import authenticate

    if not authenticate():
        return jsonify(
            {"error": "Authentication required", "authenticated": False}
        ), 401

    # Check role
    if g.role not in ["viewer", "editor", "admin"]:
        return jsonify({"error": "Insufficient permissions"}), 403

    session_id = session.get("session_id")
    if not session_id:
        return jsonify({"error": "No session found"}), 401

    user_session = UserSession.query.get(session_id)
    if not user_session or not user_session.is_active:
        return jsonify({"error": "Session not found or inactive"}), 401

    # Get timeout configuration
    timeout_minutes = int(config_get("session.timeout_minutes", 15))

    # Extend the session
    user_session.extend_session(timeout_minutes)

    # Log the session extension
    LogEntry.log_event(
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


@session_bp.route("/logout", methods=["POST"])
@handle_errors(json_response=True)
def logout():
    """Logout and deactivate session"""
    # Manual authentication to avoid HTML responses
    from app.middleware.auth import authenticate

    if not authenticate():
        return jsonify(
            {"error": "Authentication required", "authenticated": False}
        ), 401

    # Check role
    if g.role not in ["viewer", "editor", "admin"]:
        return jsonify({"error": "Insufficient permissions"}), 403

    session_id = session.get("session_id")
    if session_id:
        user_session = UserSession.query.get(session_id)
        if user_session:
            user_session.deactivate()

    # Clear Flask session
    session.clear()

    # Log the logout
    LogEntry.log_event(
        event_type="auth",
        action="logout",
        user_email=g.user,
        ip_address=request.remote_addr,
        additional_data={"session_id": session_id},
    )

    return jsonify({"success": True}), 200
