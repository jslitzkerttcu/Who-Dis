from flask import Blueprint, jsonify, request, session, g
from datetime import datetime, timezone
from app.models.session import UserSession
from app.models import AuditLog
from app.services.configuration_service import config_get
from app.utils.error_handler import handle_errors

session_bp = Blueprint("session", __name__)


@session_bp.route("/check_timeout")
@handle_errors
def check_timeout():
    """Legacy endpoint - now returns empty to avoid authentication loops."""
    # This endpoint was causing authentication loops when called via HTMX
    # Session management is now handled client-side via HTMX error events
    return ""


@session_bp.route("/session/extend", methods=["POST"])
@handle_errors
def extend_session_htmx():
    """Extend session via Htmx."""
    from app.middleware.auth import authenticate

    if not authenticate():
        return '<div class="text-red-600">Authentication required</div>', 401

    session_id = session.get("session_id")
    if not session_id:
        return '<div class="text-red-600">No session found</div>', 401

    user_session = UserSession.query.get(session_id)
    if not user_session or not user_session.is_active:
        return '<div class="text-red-600">Session not found</div>', 401

    # Get timeout configuration
    timeout_minutes = int(config_get("session.timeout_minutes", 15))

    # Extend the session
    user_session.extend_session(timeout_minutes)

    # Log the extension
    AuditLog.log_access(
        user_email=g.user,
        action="session_extended",
        target_resource="/session/extend",
        ip_address=request.remote_addr,
        success=True,
        additional_data={
            "session_id": session_id,
            "extended_for_minutes": timeout_minutes,
        },
    )

    # Return success message and close modal
    return """
    <div class="text-center p-4">
        <i class="fas fa-check-circle text-green-500 text-5xl mb-4"></i>
        <p class="text-lg font-semibold">Session extended!</p>
        <p class="text-gray-600">Your session has been extended for another {} minutes.</p>
    </div>
    <script>
        setTimeout(() => {{
            document.getElementById('sessionModal').innerHTML = '';
        }}, 2000);
    </script>
    """.format(timeout_minutes)


def _render_session_expired_modal():
    """Render session expired modal."""
    return """
    <div class="fixed inset-0 z-50 overflow-y-auto">
        <div class="flex items-center justify-center min-h-screen px-4 pt-4 pb-20 text-center sm:block sm:p-0">
            <div class="fixed inset-0 transition-opacity">
                <div class="absolute inset-0 bg-gray-500 opacity-75"></div>
            </div>
            <div class="inline-block align-bottom bg-white rounded-lg text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-sm sm:w-full">
                <div class="bg-white px-4 pt-5 pb-4 sm:p-6 sm:pb-4">
                    <div class="sm:flex sm:items-start">
                        <div class="mx-auto flex-shrink-0 flex items-center justify-center h-12 w-12 rounded-full bg-red-100 sm:mx-0 sm:h-10 sm:w-10">
                            <i class="fas fa-clock text-red-600"></i>
                        </div>
                        <div class="mt-3 text-center sm:mt-0 sm:ml-4 sm:text-left">
                            <h3 class="text-lg leading-6 font-medium text-gray-900">Session Expired</h3>
                            <div class="mt-2">
                                <p class="text-sm text-gray-500">
                                    Your session has expired due to inactivity. Please log in again to continue.
                                </p>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="bg-gray-50 px-4 py-3 sm:px-6 sm:flex sm:flex-row-reverse">
                    <a href="/login?reason=session_expired" 
                       class="w-full inline-flex justify-center rounded-md border border-transparent shadow-sm px-4 py-2 bg-ttcu-green text-base font-medium text-white hover:bg-green-700 focus:outline-none sm:ml-3 sm:w-auto sm:text-sm">
                        Log In Again
                    </a>
                </div>
            </div>
        </div>
    </div>
    """


def _render_session_warning_modal(minutes_remaining):
    """Render session warning modal."""
    seconds_remaining = int(minutes_remaining * 60)
    return """
    <div class="fixed inset-0 z-50 overflow-y-auto">
        <div class="flex items-center justify-center min-h-screen px-4 pt-4 pb-20 text-center sm:block sm:p-0">
            <div class="fixed inset-0 transition-opacity">
                <div class="absolute inset-0 bg-gray-500 opacity-75"></div>
            </div>
            <div class="inline-block align-bottom bg-white rounded-lg text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-sm sm:w-full">
                <div class="bg-white px-4 pt-5 pb-4 sm:p-6 sm:pb-4">
                    <div class="sm:flex sm:items-start">
                        <div class="mx-auto flex-shrink-0 flex items-center justify-center h-12 w-12 rounded-full bg-yellow-100 sm:mx-0 sm:h-10 sm:w-10">
                            <i class="fas fa-exclamation-triangle text-yellow-600"></i>
                        </div>
                        <div class="mt-3 text-center sm:mt-0 sm:ml-4 sm:text-left">
                            <h3 class="text-lg leading-6 font-medium text-gray-900">Session Expiring Soon</h3>
                            <div class="mt-2">
                                <p class="text-sm text-gray-500">
                                    Your session will expire in <span id="countdown" class="font-bold">{}</span>.
                                    Would you like to extend your session?
                                </p>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="bg-gray-50 px-4 py-3 sm:px-6 sm:flex sm:flex-row-reverse">
                    <button hx-post="/session/extend"
                            hx-target="#sessionModal"
                            hx-swap="innerHTML"
                            class="w-full inline-flex justify-center rounded-md border border-transparent shadow-sm px-4 py-2 bg-ttcu-green text-base font-medium text-white hover:bg-green-700 focus:outline-none sm:ml-3 sm:w-auto sm:text-sm">
                        Extend Session
                    </button>
                    <button onclick="document.getElementById('sessionModal').innerHTML=''"
                            class="mt-3 w-full inline-flex justify-center rounded-md border border-gray-300 shadow-sm px-4 py-2 bg-white text-base font-medium text-gray-700 hover:bg-gray-50 focus:outline-none sm:mt-0 sm:ml-3 sm:w-auto sm:text-sm">
                        Cancel
                    </button>
                </div>
            </div>
        </div>
    </div>
    <script>
        // Countdown timer
        let seconds = {};
        const countdownEl = document.getElementById('countdown');
        
        function updateCountdown() {{
            if (seconds <= 0) {{
                window.location.href = '/login?reason=session_timeout';
                return;
            }}
            
            const minutes = Math.floor(seconds / 60);
            const secs = seconds % 60;
            countdownEl.textContent = minutes + ':' + String(secs).padStart(2, '0');
            seconds--;
            setTimeout(updateCountdown, 1000);
        }}
        
        updateCountdown();
    </script>
    """.format(_format_time(seconds_remaining), seconds_remaining)


def _format_time(seconds):
    """Format seconds as MM:SS."""
    minutes = seconds // 60
    secs = seconds % 60
    return f"{minutes}:{secs:02d}"


@session_bp.route("/api/session/config", methods=["GET"])
@handle_errors(json_response=True)
def get_session_config():
    """Get session configuration"""
    config = {
        "timeout_minutes": int(config_get("session.timeout_minutes", 15)),
        "warning_minutes": int(config_get("session.warning_minutes", 2)),
        "check_interval_seconds": int(config_get("session.check_interval_seconds", 30)),
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
    AuditLog.log_access(
        user_email=g.user,
        action="session_extended",
        target_resource="/api/session/extend",
        ip_address=request.remote_addr,
        success=True,
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
    AuditLog.log_access(
        user_email=g.user,
        action="logout",
        target_resource="/api/session/logout",
        ip_address=request.remote_addr,
        success=True,
        additional_data={"session_id": session_id},
    )

    return jsonify({"success": True}), 200
