from flask import g, request, render_template, Response
from functools import wraps
import os
import base64
from datetime import datetime
import logging
import random


# Ensure logs directory exists
os.makedirs("logs", exist_ok=True)

# Configure logging for access denied
access_logger = logging.getLogger("access_denied")
access_logger.setLevel(logging.INFO)
handler = logging.FileHandler("logs/access_denied.log")
handler.setFormatter(logging.Formatter("%(message)s"))
access_logger.addHandler(handler)

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
    """Load role lists from environment variables"""
    viewers = os.getenv("VIEWERS", "").split(",")
    editors = os.getenv("EDITORS", "").split(",")
    admins = os.getenv("ADMINS", "").split(",")

    viewers = [email.strip() for email in viewers if email.strip()]
    editors = [email.strip() for email in editors if email.strip()]
    admins = [email.strip() for email in admins if email.strip()]

    return viewers, editors, admins


def get_user_role(email):
    """Determine user role based on email"""
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
            except:
                pass

    if user_email:
        g.user = user_email
        g.role = get_user_role(user_email)

        if g.role is None:
            log_access_denied(user_email, g.role)
            return False
        return True
    else:
        return False


def log_access_denied(user_email=None, user_role=None):
    """Log denied access attempts in the specified format"""
    client_ip = request.remote_addr
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    request_path = request.path

    email_display = user_email if user_email else "unauthenticated"
    role_display = user_role if user_role else "unknown"

    log_message = f"[{timestamp}] DENIED: {email_display} (role: {role_display}) from {client_ip} -> {request_path}"
    access_logger.info(log_message)


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

            return f(*args, **kwargs)

        return decorated_function

    return decorator
