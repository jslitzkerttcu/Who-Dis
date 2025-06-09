"""
Audit logging functionality for admin blueprint.
Handles audit log viewing, querying, and metadata retrieval.
"""

from flask import render_template, jsonify, request
from app.middleware.auth import require_role


@require_role("admin")
def audit_logs():
    """Display audit logs viewer."""
    return render_template("admin/audit_logs.html")


@require_role("admin")
def api_audit_logs():
    """API endpoint for querying audit logs."""
    from app.services.audit_service_postgres import audit_service

    # Get query parameters
    event_type = request.args.get("event_type")
    user_email = request.args.get("user_email")
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    search_query = request.args.get("search_query")
    ip_address = request.args.get("ip_address")
    success = request.args.get("success")
    limit = int(request.args.get("limit", 100))
    offset = int(request.args.get("offset", 0))

    # Convert success parameter
    if success is not None:
        success = success.lower() == "true"

    # Query logs
    results = audit_service.query_logs(
        event_type=event_type,
        user_email=user_email,
        start_date=start_date,
        end_date=end_date,
        search_query=search_query,
        ip_address=ip_address,
        success=success,
        limit=limit,
        offset=offset,
    )

    return jsonify(results)


@require_role("admin")
def api_audit_metadata():
    """Get metadata for audit log filtering."""
    from app.services.audit_service_postgres import audit_service

    return jsonify(
        {
            "event_types": audit_service.get_event_types(),
            "users": audit_service.get_users_with_activity(),
        }
    )
