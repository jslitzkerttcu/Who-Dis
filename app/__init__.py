from datetime import timedelta

from flask import Flask, g, request
from werkzeug.middleware.proxy_fix import ProxyFix
import os
import logging
import traceback

from pythonjsonlogger import jsonlogger
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from app.container import inject_dependencies
from app.middleware.request_id import RequestIdFilter, init_request_id


# Module-level Limiter so route modules can `from app import limiter`.
#
# SEC-03 / WD-NET-01 / WD-CONT-02: per-user rate limiting on search endpoints.
# Storage URI comes from RATELIMIT_STORAGE_URI env var (default: "memory://" for
# local dev and CI). In production (SandCastle), set RATELIMIT_STORAGE_URI to
# redis://redis:6379/0 — the `redis` hostname resolves on the SandCastle internal
# network. Multi-worker gunicorn requires a shared Redis counter store; memory://
# enforces per-worker only and will NOT correctly limit users across workers.
# Phase 1 D-08 deviation closed by Plan 03-01 (2026-04-26).
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=os.environ.get("RATELIMIT_STORAGE_URI", "memory://"),
)


def _configure_json_logging() -> None:
    """Install a JSON formatter on the root logger with request_id injection."""
    _root = logging.getLogger()
    _root.setLevel(logging.INFO)
    # Clear pre-existing handlers to avoid duplicate output under the
    # Flask debug reloader (which imports this module twice).
    for h in list(_root.handlers):
        _root.removeHandler(h)

    handler = logging.StreamHandler()
    handler.setFormatter(
        jsonlogger.JsonFormatter(
            "%(asctime)s %(levelname)s %(name)s %(request_id)s %(message)s",
            rename_fields={
                "asctime": "timestamp",
                "levelname": "level",
                "name": "logger",
            },
        )
    )
    handler.addFilter(RequestIdFilter())
    _root.addHandler(handler)


def create_app():
    app = Flask(__name__)

    # WD-NET-04 — honor X-Forwarded-Proto/Host so url_for(_external=True) emits HTTPS
    # behind Traefik. Hop count is 1 (Traefik only). DO NOT set higher — would trust
    # forged X-Forwarded-* headers from the client (Pitfall 4 in 09-RESEARCH.md).
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=0)

    # Session cookie hardening (Pitfall 7). SameSite=Lax is REQUIRED for OIDC —
    # Strict breaks the Keycloak->Who-Dis redirect-back because it's cross-site.
    app.config.update(
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
    )

    # SECRET_KEY sourced from environment (portal env-var injection, D-16).
    # The pre-Phase-9 pattern of storing it encrypted in the DB is removed (D-11).
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY") or os.urandom(32).hex()

    # Configure JSON-structured logging with per-request correlation IDs.
    _configure_json_logging()

    # Suppress debug logging from noisy libraries (preserved from DEBT-01 migration)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("msal").setLevel(logging.WARNING)

    # Wire request-ID middleware as early as possible so all subsequent
    # before_request handlers (auth, audit, etc.) see g.request_id.
    init_request_id(app)

    # Initialize database
    from app.database import init_db

    try:
        init_db(app)
        app.logger.info(
            f"Database initialized: {app.config.get('SQLALCHEMY_DATABASE_URI', 'Not configured')}"
        )
    except Exception as e:
        app.logger.error(f"Database initialization failed: {str(e)}")
        # Fallback to SQLite if PostgreSQL fails
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///logs/app.db"
        app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
        from app.database import db

        db.init_app(app)
        app.logger.warning("Falling back to SQLite database")

    # Initialize dependency injection container
    inject_dependencies(app)

    # SEC-03: initialize Flask-Limiter against this app. Default in-memory
    # storage; Retry-After/RateLimit-* headers enabled so 429 responses
    # carry actionable backoff data for clients.
    app.config["RATELIMIT_HEADERS_ENABLED"] = True
    limiter.init_app(app)
    # D-G2-02: warn loudly if production mode is using in-memory rate limiting.
    # In-memory storage enforces counters per-worker only — incorrect under
    # multi-worker gunicorn. This warning surfaces in structured docker logs.
    _ratelimit_uri = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")
    if os.environ.get("FLASK_ENV") == "production" and (
        not _ratelimit_uri or _ratelimit_uri == "memory://"
    ):
        app.logger.warning(
            "RATELIMIT_STORAGE_URI is unset or memory:// in production — "
            "rate-limit counters are per-worker and will not enforce correctly "
            "under multi-worker gunicorn. Set RATELIMIT_STORAGE_URI=redis://redis:6379/0 "
            "in the portal env-var store (see .env.sandcastle.example)."
        )

    # Phase 9 D-13 carve-out: read the debug-mode toggle from DB (non-secret flag).
    # All secrets now come from os.environ via portal env-var injection (D-11, D-16).
    try:
        from app.services.configuration_service import get_debug_mode, get_flask_config_from_env

        flask_cfg = get_flask_config_from_env()
        app.config["FLASK_HOST"] = flask_cfg["FLASK_HOST"]
        app.config["FLASK_PORT"] = flask_cfg["FLASK_PORT"]
        app.config["FLASK_DEBUG"] = flask_cfg["FLASK_DEBUG"]

    except Exception as e:
        app.logger.warning(f"Failed to read Flask config from env/DB: {e}")

    # Initialize CSRF protection
    from app.middleware.csrf import DoubleSubmitCSRF

    csrf = DoubleSubmitCSRF()
    csrf.init_app(app)

    # Initialize audit service with Flask app
    # Skip initialization if we're in the reloader process
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true" or not app.debug:
        from app.services.audit_service_postgres import audit_service

        audit_service.init_app(app)

        # Initialize and refresh API tokens at startup
        with app.app_context():
            try:
                from app.interfaces.token_service import ITokenService

                app.logger.info("Checking and refreshing API tokens at startup...")

                # Get all token services from container and refresh them
                # D-06: skip startup token refresh under TESTING; tests use fake services
                # registered after create_app() returns and drive refresh manually.
                token_services = app.container.get_all_by_interface(ITokenService)
                genesys_service = None
                if not (app.config.get("TESTING") or os.environ.get("TESTING")):
                    for service in token_services:
                        service_name = getattr(
                            service, "token_service_name", "unknown"
                        )
                        try:
                            if service.refresh_token_if_needed():
                                app.logger.info(f"{service_name} token is valid")
                                if service_name == "genesys":
                                    genesys_service = service
                            else:
                                app.logger.warning(
                                    f"Failed to refresh {service_name} token at startup"
                                )
                        except Exception as e:
                            app.logger.warning(
                                f"Error checking {service_name} token: {e}"
                            )

                # Start background token refresh service with container
                # D-06: skip background thread under TESTING; tests drive services synchronously.
                if not (app.config.get("TESTING") or os.environ.get("TESTING")):
                    token_refresh = app.container.get("token_refresh")
                    token_refresh.app = app
                    token_refresh.container = app.container
                    token_refresh.start()
                    app.logger.info("Token refresh background service started")

                # DEBT-03: hourly background prune of expired SearchCache rows
                # D-06: skip background thread under TESTING.
                if not (app.config.get("TESTING") or os.environ.get("TESTING")):
                    cache_cleanup = app.container.get("cache_cleanup")
                    cache_cleanup.app = app
                    cache_cleanup.start()
                    app.logger.info("Cache cleanup background service started")

                # Initialize Genesys cache using the validated service
                # D-06: skip Genesys cache warmup under TESTING (avoids real HTTP calls).
                if genesys_service and not (app.config.get("TESTING") or os.environ.get("TESTING")):
                    try:
                        from app.services.genesys_cache_db import genesys_cache_db

                        if genesys_cache_db.needs_refresh():
                            app.logger.info(
                                "Initializing Genesys cache with validated service..."
                            )
                            results = genesys_cache_db.refresh_all_caches(
                                genesys_service
                            )
                            if any(results.values()):
                                app.logger.info(
                                    f"Genesys cache initialization results: {results}"
                                )
                            else:
                                app.logger.warning(
                                    "Genesys cache initialization returned no results"
                                )
                        else:
                            app.logger.info("Genesys cache is up to date")
                    except Exception as e:
                        app.logger.error(f"Error initializing Genesys cache: {str(e)}")
                else:
                    app.logger.info(
                        "Skipping Genesys cache initialization - no valid Genesys service"
                    )

                # Clean up expired sessions on startup
                try:
                    from app.models.session import UserSession

                    UserSession.cleanup_expired()
                    app.logger.info("Expired sessions cleaned up")
                except Exception as e:
                    app.logger.error(f"Error cleaning up sessions: {str(e)}")

            except Exception as e:
                app.logger.error(f"Error refreshing tokens at startup: {str(e)}")

    @app.before_request
    def before_request():
        # Block OPTIONS requests
        if request.method == "OPTIONS":
            return "Method Not Allowed", 405

        g.user = None
        g.role = None

    @app.context_processor
    def inject_user():
        return dict(g=g, min=min, max=max)

    from app.blueprints.home import home_bp
    from app.blueprints.search import search_bp
    from app.blueprints.admin import admin_bp
    from app.blueprints.session import session_bp
    from app.blueprints.utilities import utilities
    from app.blueprints.health import health_bp

    app.register_blueprint(home_bp)
    app.register_blueprint(search_bp, url_prefix="/search")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(session_bp)
    app.register_blueprint(utilities, url_prefix="/utilities")
    # OPS-01: unauthenticated /health and /health/live for external monitors
    app.register_blueprint(health_bp)

    # Phase 9 — Authlib OIDC (D-01..D-04, WD-AUTH-01..07)
    from app.auth import init_oauth, auth_bp
    init_oauth(app)
    app.register_blueprint(auth_bp)

    # Global error handlers
    @app.errorhandler(Exception)
    def handle_exception(e):
        # Log the error to audit log
        try:
            from app.services.audit_service_postgres import audit_service
            from app.utils.ip_utils import format_ip_info, get_all_ips

            from flask import session as _session
            user_email = (_session.get("user") or {}).get("email") or request.remote_user
            user_role = getattr(request, "user_role", None)

            audit_service.log_error(
                error_type=type(e).__name__,
                error_message=str(e),
                stack_trace=traceback.format_exc(),
                user_email=user_email,
                user_role=user_role,
                ip_address=format_ip_info(),
                request_path=request.path,
                request_method=request.method,
                user_agent=request.headers.get("User-Agent"),
                additional_data={
                    "url": request.url,
                    "args": dict(request.args),
                    "form": dict(request.form) if request.form else None,
                    "ip_info": get_all_ips(),
                },
            )
        except Exception as log_error:
            # Don't let logging errors break the app
            app.logger.error(f"Failed to log error: {log_error}")

        # Log to standard logger as well
        app.logger.error(f"Unhandled exception: {e}", exc_info=True)

        # Return generic error to user
        if request.path.startswith("/api/") or request.is_json:
            return {"error": "An internal error occurred"}, 500
        else:
            return "An internal error occurred", 500

    @app.errorhandler(404)
    def handle_404(e):
        if request.path.startswith("/api/") or request.is_json:
            return {"error": "Resource not found"}, 404
        else:
            return "Page not found", 404

    return app
