from flask import g, request, render_template
from functools import wraps
import random

from .authentication_handler import AuthenticationHandler
from .session_manager import SessionManager
from .role_resolver import RoleResolver
from .user_provisioner import UserProvisioner
from .audit_logger import AuditLogger

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

# Initialize service instances
auth_handler = AuthenticationHandler()
session_manager = SessionManager()
role_resolver = RoleResolver()
user_provisioner = UserProvisioner()
audit_logger = AuditLogger()


def load_role_lists():
    """Load role lists from database (fallback to env for migration) - DEPRECATED"""
    # This function is kept for backward compatibility
    # Use RoleResolver class instead
    return role_resolver._load_role_lists()


def get_user_role(email):
    """Determine user role based on email - DEPRECATED"""
    # This function is kept for backward compatibility
    # Use RoleResolver class instead
    return role_resolver.get_user_role(email)


def authenticate():
    """Authenticate user and set g.user and g.role"""
    from app.services.configuration_service import config_get

    # Step 1: Authenticate user
    user_email = auth_handler.authenticate_user()
    if not user_email:
        return False

    # Step 2: Determine role
    user_role = role_resolver.get_user_role(user_email)
    if user_role is None:
        audit_logger.log_access_denied(user_email, user_role)
        return False

    # Step 3: Set user context
    auth_handler.set_user_context(user_email, user_role)

    # Step 4: Get or create user record
    user = user_provisioner.get_or_create_user(user_email, user_role)

    # Step 5: Manage session
    timeout_minutes = int(config_get("session.timeout_minutes", 15))
    session_manager.get_or_create_session(user.id, user_email, timeout_minutes)

    # Step 6: Log successful authentication
    audit_logger.log_authentication_success(user_email, user_role)

    return True


def log_access_denied(user_email=None, user_role=None):
    """Log denied access attempts to audit database - DEPRECATED"""
    # This function is kept for backward compatibility
    # Use AuditLogger class instead
    audit_logger.log_access_denied(user_email, user_role)


def auth_required(f):
    """Decorator to require authentication"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not authenticate():
            if not hasattr(g, "user") or g.user is None:
                log_access_denied()  # Log unauthenticated access

                # Check if this is an HTMX request
                if request.headers.get("HX-Request"):
                    # For HTMX requests, return a 401 response that triggers a full page reload
                    from flask import make_response

                    response = make_response("Authentication required", 401)
                    # Tell HTMX to redirect to login page
                    response.headers["HX-Redirect"] = "/login?reason=session_expired"
                    return response

                # Redirect to login page for regular requests
                from flask import redirect, url_for

                return redirect(url_for("home.login", reason="auth_required"))
            else:
                return render_template(
                    "nope.html", denial_reason=random.choice(DENIAL_REASONS)
                ), 401
        # Set user_role on request for use in view functions
        request.user_role = g.role  # type: ignore[attr-defined]
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

                    # Check if this is an HTMX request
                    if request.headers.get("HX-Request"):
                        # For HTMX requests, return a 401 response that triggers a full page reload
                        from flask import make_response

                        response = make_response("Authentication required", 401)
                        # Tell HTMX to redirect to login page
                        response.headers["HX-Redirect"] = (
                            "/login?reason=session_expired"
                        )
                        return response

                    # Redirect to login page for regular requests
                    from flask import redirect, url_for

                    return redirect(url_for("home.login", reason="auth_required"))
                else:
                    return render_template(
                        "nope.html", denial_reason=random.choice(DENIAL_REASONS)
                    ), 401

            if not role_resolver.is_valid_role(g.role):
                return render_template(
                    "nope.html", denial_reason=random.choice(DENIAL_REASONS)
                ), 401

            if not role_resolver.has_minimum_role(g.role, minimum_role):
                audit_logger.log_access_denied(g.user, g.role)
                return render_template(
                    "nope.html", denial_reason=random.choice(DENIAL_REASONS)
                ), 401

            # Set user_role on request for use in view functions
            request.user_role = g.role  # type: ignore[attr-defined]
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


def require_role_json(minimum_role):
    """Decorator to require a minimum role level (returns JSON for API endpoints)"""

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not authenticate():
                return {"error": "Authentication required"}, 401

            if not role_resolver.is_valid_role(g.role):
                return {"error": "Invalid role"}, 403

            if not role_resolver.has_minimum_role(g.role, minimum_role):
                audit_logger.log_access_denied(g.user, g.role)
                return {"error": "Insufficient permissions"}, 403

            # Set user_role on request for use in view functions
            request.user_role = g.role  # type: ignore[attr-defined]
            return f(*args, **kwargs)

        return decorated_function

    return decorator
