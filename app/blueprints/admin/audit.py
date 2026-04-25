"""
Audit logging functionality for admin blueprint.
Handles audit log viewing, querying, and metadata retrieval.
"""

from datetime import datetime

from flask import jsonify, render_template, request
from sqlalchemy import and_, desc, or_

from app.middleware.auth import require_role
from app.utils.pagination import paginate
from app.utils.timezone import format_timestamp_long


@require_role("admin")
def audit_logs():
    """Display audit logs viewer."""
    # Log the access to audit logs
    from app.services.audit_service_postgres import audit_service

    user_email = request.headers.get(
        "X-MS-CLIENT-PRINCIPAL-NAME", request.remote_user or "unknown"
    )
    user_role = getattr(request, "user_role", None)
    user_ip = request.headers.get("X-Forwarded-For", request.remote_addr)

    audit_service.log_admin_action(
        user_email=user_email,
        action="view_audit_logs",
        target="audit_logs",
        details={},
        user_role=user_role,
        ip_address=user_ip,
        user_agent=request.headers.get("User-Agent"),
        success=True,
    )

    return render_template("admin/audit_logs.html")


@require_role("admin")
def api_audit_logs():
    """API endpoint for querying audit logs."""
    from app.models import AuditLog

    # Get query parameters - filter out empty strings
    event_type = request.args.get("event_type") or None
    user_email = request.args.get("user_email") or None
    start_date = request.args.get("start_date") or None
    end_date = request.args.get("end_date") or None
    search_query = request.args.get("search_query") or None
    ip_address = request.args.get("ip_address") or None
    success_param = request.args.get("success") or None

    # Convert success parameter
    if success_param is not None and success_param != "":
        success_val = success_param.lower() == "true"
    else:
        success_val = None

    query = AuditLog.query
    filters = []
    if event_type:
        filters.append(AuditLog.event_type == event_type)
    if user_email:
        filters.append(AuditLog.user_email.ilike(f"%{user_email}%"))
    if start_date:
        try:
            filters.append(AuditLog.timestamp >= datetime.fromisoformat(start_date))
        except ValueError:
            pass
    if end_date:
        try:
            filters.append(AuditLog.timestamp <= datetime.fromisoformat(end_date))
        except ValueError:
            pass
    if search_query:
        filters.append(
            or_(
                AuditLog.search_query.ilike(f"%{search_query}%"),
                AuditLog.action.ilike(f"%{search_query}%"),
                AuditLog.target_resource.ilike(f"%{search_query}%"),
            )
        )
    if ip_address:
        filters.append(AuditLog.ip_address.ilike(f"%{ip_address}%"))
    if success_val is not None:
        filters.append(AuditLog.success == success_val)

    if filters:
        query = query.filter(and_(*filters))

    query = query.order_by(desc(AuditLog.timestamp))

    page_result = paginate(query)

    # Build template-friendly dicts (decouple template from ORM internals)
    logs = []
    for entry in page_result.items:
        try:
            formatted_ts = format_timestamp_long(entry.timestamp)
        except Exception:
            formatted_ts = str(entry.timestamp)
        logs.append(
            {
                "formatted_timestamp": formatted_ts,
                "event_type": entry.event_type,
                "user_email": entry.user_email,
                "search_query": entry.search_query,
                "action": entry.action,
                "resource": entry.target_resource,
                "service": None,
                "results_count": entry.search_results_count,
                "target": entry.target_resource,
                "ip_address": entry.ip_address,
                "success": entry.success,
            }
        )

    # Htmx fragment vs JSON
    if request.headers.get("HX-Request"):
        return render_template(
            "admin/partials/_audit_logs_table.html",
            pagination=page_result,
            logs=logs,
        )

    # JSON response — preserve legacy "results"/"total" shape
    return jsonify(
        {
            "results": [entry.to_dict() for entry in page_result.items],
            "total": page_result.total,
            "page": page_result.page,
            "per_page": page_result.per_page,
            "pages": page_result.pages,
        }
    )


@require_role("admin")
def api_audit_metadata():
    """Get metadata for audit log filtering."""
    from app.services.audit_service_postgres import audit_service

    # Check if this is for a specific type
    metadata_type = request.args.get("type")

    if request.headers.get("HX-Request"):
        if metadata_type == "users":
            users = audit_service.get_users_with_activity()
            options = ['<option value="">All Users</option>']
            options.extend(
                [f'<option value="{user}">{user}</option>' for user in users]
            )
            return "".join(options)
        else:
            event_types = audit_service.get_event_types()
            options = ['<option value="">All Events</option>']
            options.extend(
                [
                    f'<option value="{et}">{_format_event_type(et)}</option>'
                    for et in event_types
                ]
            )
            return "".join(options)

    return jsonify(
        {
            "event_types": audit_service.get_event_types(),
            "users": audit_service.get_users_with_activity(),
        }
    )


def _format_event_type(event_type):
    """Format event type for display."""
    return event_type.replace("_", " ").title()
