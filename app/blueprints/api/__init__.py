"""REST API blueprint initialization with flask-smorest.

Configures the OpenAPI-documented API with Swagger UI at /api/v1/docs.
Registers API-specific error handlers and sub-blueprints.
"""

import logging

from flask_smorest import Api

from app.blueprints.api.errors import register_api_error_handlers

logger = logging.getLogger(__name__)

# Module-level reference so other modules can import it
api: Api = None  # type: ignore[assignment]


def init_api(app):
    """Initialize the flask-smorest Api and register API blueprints.

    Must be called after limiter.init_app(app) and before regular
    blueprint registration (Pitfall 5).

    Args:
        app: The Flask application instance.

    Returns:
        The initialized Api object.
    """
    global api

    # flask-smorest / OpenAPI configuration
    app.config.update({
        "API_TITLE": "WhoDis API",
        "API_VERSION": "v1",
        "OPENAPI_VERSION": "3.0.3",
        "OPENAPI_URL_PREFIX": "/api/v1",
        "OPENAPI_SWAGGER_UI_PATH": "/docs",
        "OPENAPI_SWAGGER_UI_URL": "https://cdn.jsdelivr.net/npm/swagger-ui-dist/",
    })

    api = Api(app)

    # Register API-scoped error handlers so all /api/v1/* errors
    # return the D-07 JSON envelope instead of HTML.
    register_api_error_handlers(app)

    # Register API resource blueprints
    from app.blueprints.api.search import api_search_bp
    from app.blueprints.api.users import api_users_bp

    api.register_blueprint(api_search_bp, url_prefix="/api/v1")
    api.register_blueprint(api_users_bp, url_prefix="/api/v1")

    logger.info("REST API initialized (flask-smorest) — Swagger UI at /api/v1/docs")

    return api
