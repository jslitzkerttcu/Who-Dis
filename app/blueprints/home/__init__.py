from flask import Blueprint, render_template, redirect, url_for, session, request, g
from app.middleware.auth import auth_required
from app.models.session import UserSession
from app.models import AccessAttempt
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
    """Phase 9: redirect unauthenticated users to the Keycloak OIDC flow (D-04).

    The legacy login.html form (Azure AD / Easy-Auth) is no longer used.
    Authenticated users are sent directly to the home page. Unauthenticated
    users are forwarded to /auth/login which initiates the Authlib OIDC dance.
    The ?next= and ?reason= query params are forwarded for post-login return
    and session-expired messaging (WD-AUTH-04).
    """
    from app.middleware.auth import authenticate

    if authenticate():
        return redirect(url_for("home.index"))

    # Pass through any ?next= param so /auth/login can stash it for post-callback return.
    next_url = request.args.get("next", "/")
    return redirect(url_for("auth.login", next=next_url))


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
        AccessAttempt.log_attempt(
            ip_address=request.remote_addr,
            access_granted=True,
            user_email=g.user,
            auth_method="logout",
            requested_path=request.path,
        )

    # Clear Flask session
    session.clear()

    return redirect(url_for("home.login"))
