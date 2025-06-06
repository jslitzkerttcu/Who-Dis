from flask import Flask, g, request
import os
import logging
import traceback
import psycopg2


def create_app():
    app = Flask(__name__)

    app.config["SECRET_KEY"] = os.getenv(
        "SECRET_KEY", "dev-secret-key-change-in-production"
    )

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

    # Initialize configuration service
    try:
        # Create a separate connection for configuration service
        # Note: We must use os.getenv here because config service needs DB connection first
        db_config = {
            "host": os.getenv("POSTGRES_HOST", "localhost"),
            "port": os.getenv("POSTGRES_PORT", "5432"),
            "database": os.getenv("POSTGRES_DB", "whodis_db"),
            "user": os.getenv("POSTGRES_USER", "whodis_user"),
            "password": os.getenv("POSTGRES_PASSWORD", ""),
        }

        config_conn = psycopg2.connect(**db_config)
        config_conn.autocommit = True  # For configuration updates

        from app.services.configuration_service import get_config_service, config_get

        config_service = get_config_service(config_conn)
        app.config["CONFIG_SERVICE"] = config_service

        # Override Flask config with database values
        app.config["FLASK_HOST"] = config_get("flask", "host", "0.0.0.0")
        app.config["FLASK_PORT"] = config_get("flask", "port", 5000)
        app.config["FLASK_DEBUG"] = config_get("flask", "debug", False)

        # Load encrypted Flask secret key
        secret_key = config_get("flask", "secret_key")
        if secret_key:
            app.config["SECRET_KEY"] = secret_key

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
                from app.services.genesys_service import genesys_service
                from app.services.graph_service import graph_service

                app.logger.info("Checking and refreshing API tokens at startup...")

                # Refresh Genesys token
                try:
                    if genesys_service.refresh_token_if_needed():
                        app.logger.info("Genesys token is valid")
                    else:
                        app.logger.warning("Failed to refresh Genesys token at startup")
                except Exception as e:
                    app.logger.warning(f"Error checking Genesys token: {e}")

                # Refresh Graph API token
                try:
                    if graph_service.refresh_token_if_needed():
                        app.logger.info("Graph API token is valid")
                    else:
                        app.logger.warning(
                            "Failed to refresh Graph API token at startup"
                        )
                except Exception as e:
                    app.logger.warning(f"Error checking Graph API token: {e}")

                # Start background token refresh service
                from app.services.token_refresh_service import token_refresh_service

                token_refresh_service.init_app(app)
                token_refresh_service.start()
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

    app.register_blueprint(home_bp)
    app.register_blueprint(search_bp, url_prefix="/search")
    app.register_blueprint(admin_bp, url_prefix="/admin")

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
