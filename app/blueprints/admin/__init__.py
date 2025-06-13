"""
Admin blueprint for WhoDis application.
Refactored to follow Single Responsibility Principle with separate modules.
"""

from flask import Blueprint, render_template, request, jsonify, render_template_string
from app.middleware.auth import require_role

# Import all module functions
from . import (
    users,
    database,
    config,
    cache,
    audit,
    admin_employee_profiles,
    job_role_compliance,
)

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

# Employee Profiles management routes


@admin_bp.route("/employee-profiles")
@require_role("admin")
def employee_profiles():
    """Employee profiles management page."""
    return render_template("admin/employee_profiles.html")


@admin_bp.route("/api/employee-profiles")
@require_role("admin")
def api_employee_profiles():
    """Get employee profiles list with filters and pagination."""
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    filter_role = request.args.get("filter_role", "").strip()
    filter_lock = request.args.get("filter_lock", "").strip()
    filter_expected_role = request.args.get("filter_expected_role", "").strip()

    # Apply filters
    filter_role = filter_role if filter_role else None
    filter_lock = filter_lock if filter_lock else None
    filter_expected_role = filter_expected_role if filter_expected_role else None

    profiles_data = admin_employee_profiles.get_employee_profiles_list(
        page=page,
        per_page=per_page,
        filter_role=filter_role,
        filter_lock=filter_lock,
        filter_expected_role=filter_expected_role,
    )

    # Return HTML for HTMX requests
    if request.headers.get("HX-Request"):
        # Always return full content (table + pagination) to ensure
        # pagination controls update correctly for both filters and navigation
        return admin_employee_profiles.render_employee_profiles_with_pagination(
            profiles_data
        )

    return jsonify(profiles_data)


@admin_bp.route("/api/employee-profiles/stats")
@require_role("admin")
def api_employee_profiles_stats():
    """Get employee profiles statistics."""
    stats = admin_employee_profiles.get_employee_profiles_stats()

    if request.headers.get("HX-Request"):
        # Return single card for cache stats section
        stats_template = """
        <div class="space-y-2 text-sm">
            <div class="flex items-center justify-between">
                <span class="text-gray-600">Total Profiles:</span>
                <span class="font-medium">{{ stats.total_profiles }}</span>
            </div>
            <div class="flex items-center justify-between">
                <span class="text-gray-600">Locked Accounts:</span>
                <span class="font-medium {% if stats.locked_profiles > 0 %}text-red-600{% else %}text-green-600{% endif %}">{{ stats.locked_profiles }}</span>
            </div>
            <div class="flex items-center justify-between">
                <span class="text-gray-600">With Photos:</span>
                <span class="font-medium text-blue-600">{{ stats.profiles_with_photos }}</span>
            </div>
            <div class="flex items-center justify-between">
                <span class="text-gray-600">Last Refresh:</span>
                <span class="font-medium">{{ stats.last_refresh_formatted }}</span>
            </div>
        </div>
        """
        return render_template_string(stats_template, stats=stats)

    return jsonify(stats)


@admin_bp.route("/api/employee-profiles/pagination")
@require_role("admin")
def api_employee_profiles_pagination():
    """Get pagination controls for employee profiles."""
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)

    profiles_data = admin_employee_profiles.get_employee_profiles_list(
        page=page, per_page=per_page
    )

    if request.headers.get("HX-Request"):
        return admin_employee_profiles.render_employee_profiles_pagination(
            profiles_data["pagination"]
        )

    return jsonify(profiles_data["pagination"])


@admin_bp.route("/api/employee-profiles/refresh", methods=["POST"])
@require_role("admin")
def api_employee_profiles_refresh():
    """Trigger refresh of all employee profiles."""
    result = admin_employee_profiles.refresh_all_employee_profiles()
    return jsonify(result)


@admin_bp.route("/api/employee-profile-lookup")
@require_role("admin")
def api_employee_profile_lookup():
    """Look up specific employee profile by UPN."""
    upn = request.args.get("search_upn", "").strip()

    if not upn:
        return jsonify({"error": "UPN required"})

    profile = admin_employee_profiles.get_employee_profile_by_upn(upn)

    if request.headers.get("HX-Request"):
        if profile:
            profile_template = """
            <div class="mt-4 bg-blue-50 border border-blue-200 rounded-lg p-4">
                <div class="flex items-start space-x-4">
                    {% if profile.has_photo %}
                        <div class="relative photo-hover-container">
                            <img src="{{ url_for('admin.api_employee_profile_photo', upn=profile.upn) }}" 
                                 alt="Profile photo" 
                                 class="h-16 w-16 rounded-full object-cover border border-gray-200 cursor-pointer">
                            <!-- Hover overlay with larger image -->
                            <div class="photo-hover-overlay absolute z-50 hidden bg-white rounded-lg shadow-2xl border border-gray-300 p-2" 
                                 style="bottom: 100%; left: 50%; transform: translateX(-50%); margin-bottom: 8px;">
                                <img src="{{ url_for('admin.api_employee_profile_photo', upn=profile.upn) }}" 
                                     alt="Profile photo enlarged" 
                                     class="w-40 h-40 rounded-lg object-cover">
                                <div class="text-xs text-gray-600 text-center mt-2 font-medium">{{ profile.upn }}</div>
                                <!-- Arrow pointing down -->
                                <div class="absolute top-full left-1/2 transform -translate-x-1/2 w-0 h-0 border-l-4 border-r-4 border-t-4 border-transparent border-t-white"></div>
                                <div class="absolute top-full left-1/2 transform -translate-x-1/2 w-0 h-0 border-l-4 border-r-4 border-t-4 border-transparent border-t-gray-300" style="margin-top: 1px;"></div>
                            </div>
                        </div>
                    {% else %}
                        <div class="h-16 w-16 rounded-full bg-gray-200 flex items-center justify-center border border-gray-300">
                            <i class="fas fa-user text-gray-500 text-xl"></i>
                        </div>
                    {% endif %}
                    <div class="flex-1">
                        <h4 class="text-lg font-medium text-gray-900">{{ profile.upn }}</h4>
                        <dl class="mt-2 grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
                            <div>
                                <dt class="font-medium text-gray-500">User Serial:</dt>
                                <dd class="text-gray-900">{{ profile.user_serial or 'N/A' }}</dd>
                            </div>
                            <div>
                                <dt class="font-medium text-gray-500">Live Role:</dt>
                                <dd class="text-gray-900">{{ profile.live_role or 'None' }}</dd>
                            </div>
                            <div>
                                <dt class="font-medium text-gray-500">Expected Role:</dt>
                                <dd class="text-gray-900">{{ profile.expected_role or 'Not mapped' }}</dd>
                            </div>
                            <div>
                                <dt class="font-medium text-gray-500">Lock Status:</dt>
                                <dd class="text-gray-900">{{ profile.lock_status }}</dd>
                            </div>
                            <div>
                                <dt class="font-medium text-gray-500">Job Code:</dt>
                                <dd class="text-gray-900">{{ profile.job_code or 'N/A' }}</dd>
                            </div>
                            <div>
                                <dt class="font-medium text-gray-500">Last Login:</dt>
                                <dd class="text-gray-900">{{ profile.last_login or 'Never' }}</dd>
                            </div>
                        </dl>
                    </div>
                </div>
            </div>
            """
            return render_template_string(profile_template, profile=profile)
        else:
            return """
            <div class="mt-4 bg-yellow-50 border border-yellow-200 rounded-lg p-4">
                <div class="flex items-center">
                    <i class="fas fa-exclamation-triangle text-yellow-600 mr-3"></i>
                    <span class="text-yellow-800">No employee profile found for UPN: {}</span>
                </div>
            </div>
            """.format(upn)

    return jsonify({"profile": profile, "upn": upn})


@admin_bp.route("/api/employee-profiles/<upn>/photo")
@require_role("admin")
def api_employee_profile_photo(upn: str):
    """Get employee profile photo."""
    from app.models.employee_profiles import EmployeeProfiles
    import base64
    from flask import Response

    # Only fetch the photo fields for performance
    profile = EmployeeProfiles.query.filter_by(upn=upn).first()
    if not profile or not profile.photo_data:
        # Return a 1x1 transparent pixel if no photo
        return Response(
            base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
            ),
            mimetype="image/png",
            headers={
                "Cache-Control": "public, max-age=86400",  # Cache for 24 hours
                "Content-Length": "67",  # Size of transparent pixel
            },
        )

    return Response(
        profile.photo_data,
        mimetype=profile.photo_content_type or "image/jpeg",
        headers={
            "Cache-Control": "public, max-age=86400",  # Cache for 24 hours
            "Content-Length": str(len(profile.photo_data)),
        },
    )


# Job Role Compliance management routes
admin_bp.route("/job-role-compliance")(job_role_compliance.job_role_compliance)
admin_bp.route("/api/job-codes")(job_role_compliance.api_job_codes)
admin_bp.route("/api/system-roles")(job_role_compliance.api_system_roles)
admin_bp.route("/api/job-role-matrix")(job_role_compliance.api_job_role_matrix)
admin_bp.route("/api/job-role-mapping", methods=["POST"])(
    job_role_compliance.api_create_job_role_mapping
)
admin_bp.route("/api/job-role-mapping/delete", methods=["POST"])(
    job_role_compliance.api_delete_job_role_mapping
)
admin_bp.route("/api/sync-job-codes", methods=["POST"])(
    job_role_compliance.api_sync_job_codes
)
admin_bp.route("/api/sync-system-roles", methods=["POST"])(
    job_role_compliance.api_sync_system_roles
)

# Compliance Dashboard routes
admin_bp.route("/compliance-dashboard")(job_role_compliance.compliance_dashboard)
admin_bp.route("/api/compliance-overview")(job_role_compliance.api_compliance_overview)
admin_bp.route("/api/compliance-violations")(
    job_role_compliance.api_compliance_violations
)
admin_bp.route("/api/run-compliance-check", methods=["POST"])(
    job_role_compliance.api_run_compliance_check
)


# Compliance Violations Management routes
@admin_bp.route("/compliance-violations")
@require_role("admin")
def compliance_violations():
    """Compliance violations management page."""
    return render_template("admin/compliance_violations.html")
