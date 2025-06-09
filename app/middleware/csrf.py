from flask import request, make_response, current_app
from functools import wraps
import secrets
import hashlib
import hmac
import time


class DoubleSubmitCSRF:
    """
    Implements double-submit cookie CSRF protection that works with
    header-based authentication (Azure AD).

    This is more suitable for SPAs and AJAX requests than traditional
    session-based CSRF tokens.
    """

    def __init__(self, app=None):
        self.app = app
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        # Load CSRF configuration from database or use defaults
        self._load_csrf_config(app)
        
        # Store instance on app
        app.csrf_double_submit = self
        
    def _load_csrf_config(self, app):
        """Load CSRF configuration from database."""
        from app.services.configuration_service import config_get
        
        # Load configuration from database with defaults
        app.config["CSRF_COOKIE_NAME"] = config_get("csrf.cookie_name") or "_csrf_token"
        app.config["CSRF_COOKIE_SECURE"] = (config_get("csrf.cookie_secure") or "false").lower() == "true"
        # HttpOnly must be false for double-submit cookie pattern - JavaScript needs to read the cookie
        app.config["CSRF_COOKIE_HTTPONLY"] = (config_get("csrf.cookie_httponly") or "false").lower() == "true"
        app.config["CSRF_COOKIE_SAMESITE"] = config_get("csrf.cookie_samesite") or "Lax"
        app.config["CSRF_COOKIE_PATH"] = config_get("csrf.cookie_path") or "/"
        app.config["CSRF_HEADER_NAME"] = config_get("csrf.header_name") or "X-CSRF-Token"
        app.config["CSRF_TOKEN_EXPIRE"] = int(config_get("csrf.token_expire") or "3600")

    def generate_token(self):
        """Generate a new CSRF token with timestamp."""
        # Create token with timestamp
        timestamp = str(int(time.time()))
        random_data = secrets.token_urlsafe(32)

        # Sign the token with app secret key
        secret_key = current_app.config["SECRET_KEY"].encode()
        message = f"{timestamp}:{random_data}".encode()
        signature = hmac.new(secret_key, message, hashlib.sha256).hexdigest()

        return f"{timestamp}:{random_data}:{signature}"

    def validate_token(self, token):
        """Validate a CSRF token."""
        if not token:
            return False

        parts = token.split(":")
        if len(parts) != 3:
            return False

        timestamp, random_data, signature = parts

        # Check timestamp
        try:
            token_time = int(timestamp)
            current_time = int(time.time())
            expire_time = current_app.config["CSRF_TOKEN_EXPIRE"]

            if current_time - token_time > expire_time:
                return False
        except ValueError:
            return False

        # Verify signature
        secret_key = current_app.config["SECRET_KEY"].encode()
        message = f"{timestamp}:{random_data}".encode()
        expected_signature = hmac.new(secret_key, message, hashlib.sha256).hexdigest()

        # Constant-time comparison
        return hmac.compare_digest(signature, expected_signature)

    def set_cookie(self, response):
        """Set CSRF cookie on response."""
        token = self.generate_token()
        
        response.set_cookie(
            current_app.config["CSRF_COOKIE_NAME"],
            value=token,
            secure=current_app.config["CSRF_COOKIE_SECURE"],
            httponly=current_app.config["CSRF_COOKIE_HTTPONLY"],
            samesite=current_app.config["CSRF_COOKIE_SAMESITE"],
            path=current_app.config["CSRF_COOKIE_PATH"],
            max_age=current_app.config["CSRF_TOKEN_EXPIRE"],
        )
        return response

    def get_cookie_token(self):
        """Get CSRF token from cookie."""
        return request.cookies.get(current_app.config["CSRF_COOKIE_NAME"])

    def get_header_token(self):
        """Get CSRF token from header."""
        return request.headers.get(current_app.config["CSRF_HEADER_NAME"])

    def protect(self, f):
        """Decorator to protect endpoints with CSRF."""

        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Skip CSRF for safe methods
            if request.method in ("GET", "HEAD", "OPTIONS"):
                return f(*args, **kwargs)

            # Get tokens
            cookie_token = self.get_cookie_token()
            header_token = self.get_header_token()

            # Validate
            if not cookie_token or not header_token:
                return {"error": "CSRF token missing"}, 403

            if cookie_token != header_token:
                return {"error": "CSRF token mismatch"}, 403

            if not self.validate_token(cookie_token):
                return {"error": "CSRF token invalid or expired"}, 403

            return f(*args, **kwargs)

        return decorated_function

    def exempt(self, f):
        """Mark a view as CSRF exempt."""
        f._csrf_exempt = True
        return f


# Global instance
csrf_double_submit = DoubleSubmitCSRF()


def ensure_csrf_cookie(f):
    """Decorator to ensure CSRF cookie is set on responses."""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        response = make_response(f(*args, **kwargs))

        # Check if cookie needs to be set/refreshed
        current_token = csrf_double_submit.get_cookie_token()

        if not current_token or not csrf_double_submit.validate_token(current_token):
            # Set new cookie
            csrf_double_submit.set_cookie(response)

        return response

    return decorated_function
