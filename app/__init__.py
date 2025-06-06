from flask import Flask, g, request
import os
import logging
import traceback


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

    # Initialize audit service with Flask app
    from app.services.audit_service import audit_service

    audit_service.init_app(app)

    @app.before_request
    def before_request():
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
            from app.services.audit_service import audit_service

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
