from flask import Flask, g, request
import os
import logging
import traceback
from app.container import inject_dependencies


def create_app():
    app = Flask(__name__)

    # Generate a secure random key if none is provided
    import secrets

    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY") or secrets.token_hex(32)

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

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

    # Initialize configuration service
    try:
        from app.services.configuration_service import config_get, config_clear_cache

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

        # Initialize CSRF protection after configuration is loaded
        from app.middleware.csrf import DoubleSubmitCSRF

        csrf = DoubleSubmitCSRF()
        csrf.init_app(app)

    except Exception as e:
        app.logger.warning(f"Failed to initialize configuration service: {e}")
        app.logger.warning("Falling back to environment variables")

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
                app.logger.info("Token refresh background service started")

                # Initialize Genesys cache if empty
                try:
                    from app.services.genesys_cache_db import genesys_cache_db

                    if genesys_cache_db.needs_refresh():
                        app.logger.info("Initializing Genesys cache on startup...")
                        results = genesys_cache_db.refresh_all()
                        app.logger.info(
                            f"Genesys cache initialization results: {results}"
                        )
                except Exception as e:
                    app.logger.error(f"Error initializing Genesys cache: {str(e)}")

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
        return dict(g=g)

    from app.blueprints.home import home_bp
    from app.blueprints.search import search_bp
    from app.blueprints.admin import admin_bp
    from app.blueprints.session import session_bp

    app.register_blueprint(home_bp)
    app.register_blueprint(search_bp, url_prefix="/search")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(session_bp)

    # Global error handlers
    @app.errorhandler(Exception)
    def handle_exception(e):
        # Log the error to audit log
        try:
            from app.services.audit_service_postgres import audit_service

            user_email = request.headers.get(
                "X-MS-CLIENT-PRINCIPAL-NAME", request.remote_user
            )
            user_role = getattr(request, "user_role", None)
            user_ip = request.headers.get("X-Forwarded-For", request.remote_addr)

            audit_service.log_error(
                error_type=type(e).__name__,
                error_message=str(e),
                stack_trace=traceback.format_exc(),
                user_email=user_email,
                user_role=user_role,
                ip_address=user_ip,
                request_path=request.path,
                request_method=request.method,
                user_agent=request.headers.get("User-Agent"),
                additional_data={
                    "url": request.url,
                    "args": dict(request.args),
                    "form": dict(request.form) if request.form else None,
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
