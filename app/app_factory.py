"""
Application factory with separated concerns.
Each initialization step is isolated into its own function.
"""

from flask import Flask, g, request
import os
import logging
import secrets


def configure_logging():
    """Configure application logging."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Suppress debug logging from noisy libraries
    logging.getLogger("app.services.simple_config").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("msal").setLevel(logging.WARNING)


def configure_session(app):
    """Configure Flask session settings."""
    # Get secret key from database configuration, generate if not available
    from app.services.simple_config import config_get, config_set

    secret_key = config_get("flask.secret_key")
    if not secret_key:
        secret_key = secrets.token_hex(32)
        # Store the generated key in database for consistency
        config_set("flask.secret_key", secret_key, "system")
    app.config["SECRET_KEY"] = secret_key
    app.config["SESSION_COOKIE_SECURE"] = False  # Set to True in production with HTTPS
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_NAME"] = "whodis_session"
    app.config["SESSION_COOKIE_PATH"] = "/"
    app.config["PERMANENT_SESSION_LIFETIME"] = 86400  # 24 hours


def initialize_database(app):
    """Initialize database connection. Fail fast on errors."""
    from app.database import init_db

    try:
        init_db(app)
        app.logger.info(
            f"Database initialized: {app.config.get('SQLALCHEMY_DATABASE_URI', 'Not configured')}"
        )
    except Exception as e:
        app.logger.error(f"FATAL: Database initialization failed: {str(e)}")
        app.logger.error(
            "Please check your PostgreSQL connection settings in .env file"
        )
        raise  # Fail fast - don't continue with broken database


def load_configuration(app):
    """Load configuration from database."""
    from app.services.simple_config import config_get, config_clear_cache

    # Clear cache to ensure fresh config on startup
    config_clear_cache()

    # Override Flask config with database values
    app.config["FLASK_HOST"] = config_get("flask.host", "0.0.0.0")
    app.config["FLASK_PORT"] = config_get("flask.port", 5000)
    app.config["FLASK_DEBUG"] = config_get("flask.debug", False)

    # Load encrypted Flask secret key
    secret_key = config_get("flask.secret_key")
    if secret_key:
        app.config["SECRET_KEY"] = secret_key


def initialize_services(app):
    """Initialize background services and API tokens."""
    if os.environ.get("WERKZEUG_RUN_MAIN") != "true" and app.debug:
        return  # Skip in reloader process

    from app.services.audit_service_postgres import audit_service

    audit_service.init_app(app)

    with app.app_context():
        # Initialize and refresh API tokens using container if available
        if hasattr(app, "container"):
            # Use container-based initialization (preferred)
            from app.interfaces.token_service import ITokenService

            app.logger.info("Checking and refreshing API tokens at startup...")

            # Get all token services from container and refresh them
            token_services = app.container.get_all_by_interface(ITokenService)
            for service in token_services:
                try:
                    service_name = getattr(service, "token_service_name", "unknown")
                    if service.refresh_token_if_needed():
                        app.logger.info(f"{service_name} token is valid")
                    else:
                        app.logger.warning(
                            f"Failed to refresh {service_name} token at startup"
                        )
                except Exception as e:
                    app.logger.warning(f"Error checking {service_name} token: {e}")

            # Start background token refresh service with container
            token_refresh = app.container.get("token_refresh")
            token_refresh.app = app
            token_refresh.container = app.container
            token_refresh.start()
            app.logger.info("Token refresh background service started with container")
        else:
            # Fallback to direct service initialization
            from app.services.genesys_service import genesys_service
            from app.services.graph_service import graph_service

            app.logger.info("Checking and refreshing API tokens at startup...")

            try:
                if not genesys_service.refresh_token_if_needed():
                    app.logger.warning("Failed to refresh Genesys token at startup")
            except Exception as e:
                app.logger.warning(f"Error checking Genesys token: {e}")

            try:
                if not graph_service.refresh_token_if_needed():
                    app.logger.warning("Failed to refresh Graph API token at startup")
            except Exception as e:
                app.logger.warning(f"Error checking Graph API token: {e}")

            # Start token refresh service without container
            from app.services.token_refresh_service import token_refresh_service

            token_refresh_service.init_app(app)
            token_refresh_service.start()
            app.logger.info("Token refresh background service started (legacy mode)")

        # Initialize Genesys cache
        try:
            from app.services.genesys_cache_db import genesys_cache_db

            if genesys_cache_db.needs_refresh():
                app.logger.info("Initializing Genesys cache on startup...")
                results = genesys_cache_db.refresh_all_caches()
                app.logger.info(f"Genesys cache initialization results: {results}")
        except Exception as e:
            app.logger.error(f"Error initializing Genesys cache: {str(e)}")

        # Clean up expired sessions
        try:
            from app.models.session import UserSession

            UserSession.cleanup_expired()
            app.logger.info("Expired sessions cleaned up")
        except Exception as e:
            app.logger.error(f"Error cleaning up sessions: {str(e)}")


def register_middleware(app):
    """Register middleware components."""
    # CSRF protection
    from app.middleware.csrf import csrf_double_submit

    csrf_double_submit.init_app(app)

    # Security headers
    from app.middleware.security_headers import init_security_headers

    init_security_headers(app)

    @app.before_request
    def before_request():
        # Block OPTIONS requests
        if request.method == "OPTIONS":
            return "Method Not Allowed", 405

        g.user = None
        g.role = None

    @app.context_processor
    def inject_user():
        return dict(g=g)


def register_blueprints(app):
    """Register application blueprints."""
    from app.blueprints.home import home_bp
    from app.blueprints.search import search_bp
    from app.blueprints.admin import admin_bp
    from app.blueprints.session import session_bp

    app.register_blueprint(home_bp)
    app.register_blueprint(search_bp, url_prefix="/employee-search")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(session_bp)


def register_error_handlers(app):
    """Register global error handlers."""
    import traceback

    @app.errorhandler(Exception)
    def handle_exception(e):
        # Log the error to audit log
        try:
            from app.services.audit_service_postgres import audit_service
            from app.utils.ip_utils import format_ip_info, get_all_ips

            user_email = request.headers.get(
                "X-MS-CLIENT-PRINCIPAL-NAME", request.remote_user
            )
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
            app.logger.error(f"Failed to log error: {log_error}")

        app.logger.error(f"Unhandled exception: {e}", exc_info=True)

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


def create_app():
    """Create and configure the Flask application."""
    app = Flask(__name__)

    # Configure logging first
    configure_logging()

    # Configure session
    configure_session(app)

    # Initialize database - fail fast if it doesn't work
    initialize_database(app)

    # Initialize dependency injection container
    from app.container import inject_dependencies

    inject_dependencies(app)

    # Load configuration from database
    try:
        load_configuration(app)
    except Exception as e:
        app.logger.warning(f"Failed to load configuration: {e}")
        app.logger.warning("Using default configuration")

    # Register middleware
    register_middleware(app)

    # Register blueprints
    register_blueprints(app)

    # Register error handlers
    register_error_handlers(app)

    # Initialize services (tokens, cache, etc)
    try:
        initialize_services(app)
    except Exception as e:
        app.logger.error(f"Error initializing services: {str(e)}")

    return app
