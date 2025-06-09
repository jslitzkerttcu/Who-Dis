"""Admin audit log routes."""

from flask import render_template, request, jsonify
from app.middleware.auth import require_role
from app.utils.error_handler import handle_errors
from app.blueprints.admin import admin_bp


@admin_bp.route("/audit-logs")
@require_role("admin")
@handle_errors()
def audit_logs():
    """Display audit logs viewer."""
    return render_template("admin/audit_logs.html")


@admin_bp.route("/api/audit-logs")
@require_role("admin")
@handle_errors(json_response=True)
def api_audit_logs():
    """API endpoint for audit logs with filtering."""
    from app.services.audit_service_postgres import audit_service

    # Get query parameters
    limit = int(request.args.get("limit", 50))
    offset = int(request.args.get("offset", 0))
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    event_type = request.args.get("event_type")
    user_email = request.args.get("user_email")
    search_query = request.args.get("search_query")
    ip_address = request.args.get("ip_address")

    # Get logs
    result = audit_service.query_logs(
        event_type=event_type,
        user_email=user_email,
        start_date=start_date,
        end_date=end_date,
        search_query=search_query,
        ip_address=ip_address,
        limit=limit,
        offset=offset,
    )
    logs = result.get("results", [])
    total = result.get("total", 0)

    # Logs are already formatted as dicts by the audit service
    formatted_logs = logs

    return jsonify({"logs": formatted_logs, "total": total})


@admin_bp.route("/api/audit-metadata")
@require_role("admin")
@handle_errors(json_response=True)
def api_audit_metadata():
    """Get metadata for audit log filtering."""
    from app.services.audit_service_postgres import audit_service

    return jsonify(
        {
            "event_types": audit_service.get_event_types(),
            "users": audit_service.get_users_with_activity(),
        }
    )
