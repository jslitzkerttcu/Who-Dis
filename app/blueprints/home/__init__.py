from flask import Blueprint, render_template, redirect, url_for, session, request, g
from app.middleware.auth import auth_required
from app.models.session import UserSession
from app.models.audit import AuditLog

home_bp = Blueprint("home", __name__)


@home_bp.route("/")
@auth_required
def index():
    return render_template("home/index.html")


@home_bp.route("/login")
def login():
    """Login page (redirects to home if already authenticated)"""
    from app.middleware.auth import authenticate

    if authenticate():
        return redirect(url_for("home.index"))

    # Show login reason if provided
    reason = request.args.get("reason", "")
    return render_template("home/login.html", reason=reason)


@home_bp.route("/logout", methods=["POST"])
def logout():
    """Logout endpoint"""
    try:
        session_id = session.get("session_id")
        if session_id:
            user_session = UserSession.query.get(session_id)
            if user_session:
                user_session.deactivate()

        # Log the logout
        if hasattr(g, "user") and g.user:
            AuditLog.log_event(
                event_type="auth",
                action="logout",
                user_email=g.user,
                ip_address=request.remote_addr,
                additional_data={"session_id": session_id},
            )

        # Clear Flask session
        session.clear()

    except Exception:
        # Don't let logout failures prevent clearing session
        pass

    return redirect(url_for("home.login"))
