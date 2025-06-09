from flask import Blueprint, render_template, redirect, url_for, session, request, g
from app.middleware.auth import auth_required
from app.models.session import UserSession
from app.models.unified_log import LogEntry
from app.utils.error_handler import handle_errors

home_bp = Blueprint("home", __name__)


@home_bp.route("/")
@auth_required
@handle_errors
def index():
    from app.middleware.csrf import ensure_csrf_cookie

    @ensure_csrf_cookie
    def render():
        return render_template("home/index.html")

    return render()


@home_bp.route("/login")
@handle_errors
def login():
    """Login page (redirects to home if already authenticated)"""
    from app.middleware.auth import authenticate

    if authenticate():
        return redirect(url_for("home.index"))

    # Show login reason if provided
    reason = request.args.get("reason", "")
    return render_template("home/login.html", reason=reason)


@home_bp.route("/logout", methods=["POST"])
@handle_errors
def logout():
    """Logout endpoint"""
    session_id = session.get("session_id")
    if session_id:
        user_session = UserSession.query.get(session_id)
        if user_session:
            user_session.deactivate()

    # Log the logout
    if hasattr(g, "user") and g.user:
        LogEntry.log_event(
            event_type="auth",
            action="logout",
            user_email=g.user,
            ip_address=request.remote_addr,
            additional_data={"session_id": session_id},
        )

    # Clear Flask session
    session.clear()

    return redirect(url_for("home.login"))
