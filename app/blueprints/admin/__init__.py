"""
Admin blueprint for WhoDis application.
Refactored to follow Single Responsibility Principle with separate modules.
"""

from flask import Blueprint, render_template
from app.middleware.auth import require_role

# Import all module functions
from . import users, database, config, cache, audit

admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/")
@require_role("admin")
def index():
    return render_template("admin/index.html")


# User management routes
admin_bp.route("/users", endpoint="users")(users.manage_users)
admin_bp.route("/api/users")(users.api_users)
admin_bp.route("/users/add", methods=["POST"])(users.add_user)
admin_bp.route("/users/update", methods=["POST"])(users.update_user)
admin_bp.route("/users/delete", methods=["POST"])(users.delete_user)
admin_bp.route("/api/users/<int:user_id>/notes", methods=["GET"])(users.get_user_notes)
admin_bp.route("/api/users/<int:user_id>/notes", methods=["POST"])(users.add_user_note)
admin_bp.route("/api/users/notes/<int:note_id>", methods=["PUT"])(
    users.update_user_note
)
admin_bp.route("/api/users/notes/<int:note_id>", methods=["DELETE"])(
    users.delete_user_note
)
admin_bp.route("/api/users/by-email/<email>/notes", methods=["GET"])(
    users.get_user_notes_by_email
)
admin_bp.route("/api/users/by-email/<email>/notes", methods=["POST"])(
    users.add_user_note_by_email
)
# Htmx routes for user management
admin_bp.route("/api/users/<int:user_id>/edit", methods=["GET"])(users.edit_user_modal)
admin_bp.route("/users/edit/<int:user_id>", methods=["GET"])(users.edit_user_modal)
admin_bp.route("/api/users/<int:user_id>/update", methods=["POST"])(
    users.update_user_htmx
)
admin_bp.route("/users/toggle/<int:user_id>", methods=["POST"])(
    users.toggle_user_status
)

# Database management routes
admin_bp.route("/database")(database.database)
admin_bp.route("/api/database/health")(database.database_health)
admin_bp.route("/api/database/tables")(database.database_tables)
admin_bp.route("/api/database/errors/stats")(database.error_stats)
admin_bp.route("/api/sessions/stats")(database.session_stats)
admin_bp.route("/api/database/optimize", methods=["POST"])(database.optimize_database)
admin_bp.route("/api/database/export/audit-logs")(database.export_audit_logs)
admin_bp.route("/error-logs")(database.error_logs)
admin_bp.route("/api/error-logs")(database.api_error_logs)
admin_bp.route("/api/error-logs/<int:error_id>")(database.api_error_detail)
admin_bp.route("/sessions")(database.sessions)
admin_bp.route("/api/sessions")(database.api_sessions)
admin_bp.route("/api/sessions/<session_id>/terminate", methods=["POST"])(
    database.terminate_session
)
admin_bp.route("/api/tokens/status")(database.tokens_status)
admin_bp.route("/api/tokens/refresh/<service_name>", methods=["POST"])(
    database.refresh_token
)

# Cache management routes (from database module)
admin_bp.route("/api/cache/status", endpoint="api_cache_status")(database.cache_status)
admin_bp.route(
    "/api/cache/refresh/<cache_type>", endpoint="api_cache_refresh", methods=["POST"]
)(database.refresh_cache)
admin_bp.route(
    "/api/cache/clear-all", endpoint="api_cache_clear-all", methods=["POST"]
)(database.clear_all_caches)
admin_bp.route(
    "/api/cache/clear/<cache_type>", endpoint="api_cache_clear", methods=["POST"]
)(database.api_cache_clear)
admin_bp.route(
    "/database/cache-section/<section_type>", endpoint="database_cache_section"
)(database.database_cache_section)
admin_bp.route("/api/tokens/status/<api_type>", endpoint="api_token_status")(
    database.api_token_status
)
admin_bp.route(
    "/api/tokens/refresh-all", endpoint="refresh_api_tokens", methods=["POST"]
)(database.refresh_api_tokens)
admin_bp.route("/api/tokens/service-status", endpoint="token_refresh_service_status")(
    database.token_refresh_service_status
)
admin_bp.route("/api/cache/search/stats-html", endpoint="search_cache_stats_html")(
    database.search_cache_stats_html
)
admin_bp.route("/api/cache/genesys/stats-html", endpoint="genesys_cache_stats_html")(
    database.genesys_cache_stats_html
)
admin_bp.route(
    "/api/cache/data-warehouse/stats-html", endpoint="data_warehouse_cache_stats_html"
)(database.data_warehouse_cache_stats_html)
admin_bp.route("/api/cache/performance-metrics", endpoint="cache_performance_metrics")(
    database.cache_performance_metrics
)
admin_bp.route(
    "/api/data-warehouse/connection-status", endpoint="data_warehouse_connection_status"
)(database.data_warehouse_connection_status)
admin_bp.route(
    "/api/cache/clear-single/<cache_type>",
    endpoint="clear_single_cache",
    methods=["POST"],
)(database.clear_single_cache)
admin_bp.route(
    "/api/tokens/refresh-single/<service>",
    endpoint="refresh_single_token",
    methods=["POST"],
)(database.refresh_single_token)

# Cache management routes (from cache module)
admin_bp.route("/cache-status")(cache.cache_status)
admin_bp.route("/api/cache/search/status")(cache.search_cache_status)
admin_bp.route("/api/cache/clear", methods=["POST"])(cache.clear_caches)
admin_bp.route("/api/genesys/cache/status", endpoint="genesys_cache_status_view")(
    cache.genesys_cache_status
)
admin_bp.route("/api/genesys/cache/config", methods=["GET", "POST"])(
    cache.genesys_cache_config
)
admin_bp.route(
    "/api/genesys/cache-status",
    endpoint="get_genesys_cache_status_api",
    methods=["GET"],
)(cache.get_genesys_cache_status)
admin_bp.route("/api/genesys/refresh-cache", methods=["POST"])(
    cache.refresh_genesys_cache
)
admin_bp.route("/api/data-warehouse/cache-status", methods=["GET"])(
    cache.data_warehouse_cache_status
)
admin_bp.route("/api/data-warehouse/refresh-cache", methods=["POST"])(
    cache.refresh_data_warehouse_cache
)
admin_bp.route("/api/data-warehouse/clear-cache", methods=["POST"])(
    cache.clear_data_warehouse_cache
)

# Audit logging routes
admin_bp.route("/audit-logs")(audit.audit_logs)
admin_bp.route("/api/audit-logs")(audit.api_audit_logs)
admin_bp.route("/api/audit-metadata")(audit.api_audit_metadata)

# Configuration management routes
admin_bp.route("/configuration")(config.configuration)
admin_bp.route("/api/configuration", methods=["GET", "POST"])(config.api_configuration)
admin_bp.route("/api/test/ldap", methods=["GET", "POST"])(config.test_ldap_connection)
admin_bp.route("/api/test/graph", methods=["GET", "POST"])(config.test_graph_connection)
admin_bp.route("/api/test/genesys", methods=["GET", "POST"])(
    config.test_genesys_connection
)
admin_bp.route("/api/test/data_warehouse", methods=["GET", "POST"])(
    config.test_data_warehouse_connection
)
