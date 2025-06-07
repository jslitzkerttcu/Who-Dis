from flask import g, request, render_template, Response, session as flask_session
from functools import wraps
import os
import base64
import random

# Snarky denial reasons
DENIAL_REASONS = [
    "Access level: Potato 🥔",
    "Your aura doesn't match the permissions matrix",
    "Mercury is in retrograde",
    "Your vibes are off and the server knows it",
    "You clicked without thinking. Classic.",
    "Permission denied: because reasons.",
    "You're not that guy.",
    "This request has been escalated to the Department of Nope.",
    "Authorization failed. Try bribing someone.",
    "You're trying to do what now? Bold of you.",
    "This page self-destructed just reading your request.",
    "System response: lol no.",
    "You brought a mouse click to a permissions fight.",
    "Nice try, but no cookies for you. 🍪🚫",
    "The server screamed internally and locked the door.",
    "You have the enthusiasm of admin, but the clearance of an intern.",
    "This action requires the wisdom of Gandalf and the rights of root.",
    "You're in the right place... in the wrong multiverse.",
    "This button is guarded by ancient sysadmin magic.",
    "Error 403: Your karma isn't high enough.",
    "Denied: This isn't The Sims. You can't just delete people.",
    "You've tripped a wire. Security is now watching in real time. Wave 👋",
]


def load_role_lists():
    """Load role lists from database (fallback to env for migration)"""
    try:
        from app.models import User

        # Try database first
        viewers = [u.email for u in User.get_by_role(User.ROLE_VIEWER)]
        editors = [u.email for u in User.get_by_role(User.ROLE_EDITOR)]
        admins = [u.email for u in User.get_by_role(User.ROLE_ADMIN)]

        if viewers or editors or admins:
            return viewers, editors, admins
    except Exception:
        # Database not available or table doesn't exist yet
        pass

    # Try configuration service (encrypted values)
    try:
        from app.services.configuration_service import config_get

        viewers_str = config_get("auth", "viewers", "")
        editors_str = config_get("auth", "editors", "")
        admins_str = config_get("auth", "admins", "")

        if viewers_str or editors_str or admins_str:
            viewers = [
                email.strip() for email in viewers_str.split(",") if email.strip()
            ]
            editors = [
                email.strip() for email in editors_str.split(",") if email.strip()
            ]
            admins = [email.strip() for email in admins_str.split(",") if email.strip()]
            return viewers, editors, admins
    except Exception:
        pass

    # Fallback to environment variables
    viewers = os.getenv("VIEWERS", "").split(",")
    editors = os.getenv("EDITORS", "").split(",")
    admins = os.getenv("ADMINS", "").split(",")

    viewers = [email.strip() for email in viewers if email.strip()]
    editors = [email.strip() for email in editors if email.strip()]
    admins = [email.strip() for email in admins if email.strip()]

    return viewers, editors, admins


def get_user_role(email):
    """Determine user role based on email"""
    try:
        from app.models import User

        # Try database first
        user = User.get_by_email(email)
        if user:
            # Update last login
            user.update_last_login()
            return user.role
    except Exception:
        # Database not available, fall back to env
        pass

    # Fallback to environment variables
    viewers, editors, admins = load_role_lists()

    if email in admins:
        return "admin"
    elif email in editors:
        return "editor"
    elif email in viewers:
        return "viewer"
    else:
        return None


def authenticate():
    """Authenticate user and set g.user and g.role"""
    from app.models.session import UserSession
    from app.services.configuration_service import config_get

    user_email = None

    ms_principal = request.headers.get("X-MS-CLIENT-PRINCIPAL-NAME")
    if ms_principal:
        user_email = ms_principal
    else:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Basic "):
            try:
                credentials = base64.b64decode(auth_header[6:]).decode("utf-8")
                username = credentials.split(":")[0]
                user_email = username
            except Exception:
                pass

    if user_email:
        g.user = user_email
        g.role = get_user_role(user_email)

        if g.role is None:
            log_access_denied(user_email, g.role)
            return False

        # Session management
        session_id = flask_session.get("session_id")
        user_session = None

        if session_id:
            # Check existing session
            user_session = UserSession.query.get(session_id)
            if user_session and user_session.user_email == user_email:
                if user_session.is_expired() or not user_session.is_active:
                    # Session expired or inactive
                    user_session.deactivate()
                    flask_session.clear()
                    user_session = None
                else:
                    # Update activity
                    user_session.update_activity()
            else:
                # Session doesn't match user
                flask_session.clear()
                user_session = None

        # Create new session if needed
        if not user_session:
            timeout_minutes = int(config_get("session", "timeout_minutes", 15))
            user_session = UserSession.create_session(
                user_email=user_email,
                timeout_minutes=timeout_minutes,
                ip_address=request.headers.get("X-Forwarded-For", request.remote_addr),
                user_agent=request.headers.get("User-Agent"),
            )
            flask_session["session_id"] = user_session.id
            flask_session.permanent = True

        return True
    else:
        return False


def log_access_denied(user_email=None, user_role=None):
    """Log denied access attempts to audit database"""
    client_ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    request_path = request.path

    email_display = user_email if user_email else "unauthenticated"
    role_display = user_role if user_role else "unknown"

    # Log to audit database
    try:
        from app.services.audit_service_postgres import audit_service
        from app.models import AccessAttempt

        # Log to access attempts table
        AccessAttempt.log_attempt(
            ip_address=client_ip,
            access_granted=False,
            user_email=email_display if email_display != "unauthenticated" else None,
            user_agent=request.headers.get("User-Agent"),
            requested_path=request_path,
            denial_reason="Insufficient permissions"
            if user_email
            else "Not authenticated",
            auth_method="azure_ad"
            if request.headers.get("X-MS-CLIENT-PRINCIPAL-NAME")
            else "basic_auth",
        )

        # Also log to audit log
        audit_service.log_access(
            user_email=email_display,
            action="access_denied",
            target_resource=request_path,
            user_role=role_display,
            ip_address=client_ip,
            user_agent=request.headers.get("User-Agent"),
            success=False,
            error_message="Insufficient permissions",
        )
    except Exception:
        # Don't let audit logging failures break authentication
        pass


def auth_required(f):
    """Decorator to require authentication"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not authenticate():
            if not hasattr(g, "user") or g.user is None:
                log_access_denied()  # Log unauthenticated access
                return Response(
                    "Authentication required",
                    401,
                    {"WWW-Authenticate": 'Basic realm="Who Dis?"'},
                )
            else:
                return render_template(
                    "nope.html", denial_reason=random.choice(DENIAL_REASONS)
                ), 401
        # Set user_role on request for use in view functions
        request.user_role = g.role
        return f(*args, **kwargs)

    return decorated_function


def require_role(minimum_role):
    """Decorator to require a minimum role level"""

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not authenticate():
                if not hasattr(g, "user") or g.user is None:
                    log_access_denied()  # Log unauthenticated access
                    return Response(
                        "Authentication required",
                        401,
                        {"WWW-Authenticate": 'Basic realm="Who Dis?"'},
                    )
                else:
                    return render_template(
                        "nope.html", denial_reason=random.choice(DENIAL_REASONS)
                    ), 401

            role_hierarchy = {"viewer": 1, "editor": 2, "admin": 3}

            if g.role not in role_hierarchy:
                return render_template(
                    "nope.html", denial_reason=random.choice(DENIAL_REASONS)
                ), 401

            if role_hierarchy.get(g.role, 0) < role_hierarchy.get(minimum_role, 0):
                log_access_denied(g.user, g.role)
                return render_template(
                    "nope.html", denial_reason=random.choice(DENIAL_REASONS)
                ), 401

            # Set user_role on request for use in view functions
            request.user_role = g.role
            return f(*args, **kwargs)

        return decorated_function

    return decorator


def login_required(f):
    """Simple decorator to check if user is logged in (for API endpoints)"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not authenticate():
            return {"error": "Authentication required"}, 401
        return f(*args, **kwargs)

    return decorated_function
