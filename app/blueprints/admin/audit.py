"""
Audit logging functionality for admin blueprint.
Handles audit log viewing, querying, and metadata retrieval.
"""

from flask import render_template, jsonify, request
from app.middleware.auth import require_role
from datetime import datetime


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
    from app.services.audit_service_postgres import audit_service

    # Get query parameters - filter out empty strings
    event_type = request.args.get("event_type") or None
    user_email = request.args.get("user_email") or None
    start_date = request.args.get("start_date") or None
    end_date = request.args.get("end_date") or None
    search_query = request.args.get("search_query") or None
    ip_address = request.args.get("ip_address") or None
    success = request.args.get("success") or None
    limit = int(request.args.get("limit", 100))
    offset = int(request.args.get("offset", 0))

    # Convert success parameter - handle empty string
    if success is not None and success != "":
        success = success.lower() == "true"
    else:
        success = None

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

    # Debug logging
    import logging

    logger = logging.getLogger(__name__)
    logger.info(
        f"Audit query results: {results.get('total', 0)} total, {len(results.get('results', []))} returned"
    )

    # Check if this is an Htmx request
    if request.headers.get("HX-Request"):
        return _render_audit_logs_table(results)

    return jsonify(results)


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


# ===== Htmx Helper Functions =====


def _render_audit_logs_table(results):
    """Render audit logs table for Htmx."""
    logs = results.get("results", [])
    total = results.get("total", 0)

    if not logs:
        return """
        <div class="text-center py-8 text-gray-500">
            No audit logs found matching your criteria.
        </div>
        """

    # Build the table
    html = f"""
    <div data-result-count="Showing {len(logs)} of {total} entries">
        <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
                <tr>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Timestamp</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Event Type</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">User</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Action/Query</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Details</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">IP Address</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200">
    """

    for log in logs:
        event_class = _get_event_class(log["event_type"])
        status_class = "text-green-600" if log.get("success", True) else "text-red-600"
        status_icon = "check-circle" if log.get("success", True) else "times-circle"

        # Format timestamp
        try:
            if isinstance(log.get("timestamp"), str):
                timestamp = datetime.fromisoformat(
                    log["timestamp"].replace("Z", "+00:00")
                )
            else:
                timestamp = log.get("timestamp", datetime.now())
            formatted_time = timestamp.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            formatted_time = str(log.get("timestamp", "Unknown"))

        # Get action/query text
        action_text = (
            log.get("search_query") or log.get("action") or log.get("resource", "-")
        )
        if len(action_text) > 50:
            action_text = action_text[:50] + "..."

        # Format details
        details = []
        if log.get("service"):
            details.append(f"Service: {log['service']}")
        if log.get("results_count") is not None:
            details.append(f"Results: {log['results_count']}")
        if log.get("target"):
            details.append(f"Target: {log['target']}")
        details_text = ", ".join(details) if details else "-"

        html += f"""
        <tr class="hover:bg-gray-50">
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{formatted_time}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm">
                <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full {event_class}">
                    {_format_event_type(log["event_type"])}
                </span>
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{log.get("user_email", "Unknown")}</td>
            <td class="px-6 py-4 text-sm text-gray-900">{action_text}</td>
            <td class="px-6 py-4 text-sm text-gray-500">{details_text}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{log.get("ip_address", "-")}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm {status_class}">
                <i class="fas fa-{status_icon}"></i>
            </td>
        </tr>
        """

    html += """
            </tbody>
        </table>
    </div>
    """

    # Add pagination if needed
    if total > len(logs):
        html += """
        <div class="bg-white px-4 py-3 flex items-center justify-between border-t border-gray-200 sm:px-6">
            <div class="flex-1 flex justify-between sm:hidden">
                <button class="relative inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50">
                    Previous
                </button>
                <button class="ml-3 relative inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50">
                    Next
                </button>
            </div>
        </div>
        """

    return html


def _get_event_class(event_type):
    """Get CSS class for event type badge."""
    if event_type == "search":
        return "bg-blue-100 text-blue-800"
    elif event_type == "access":
        return "bg-yellow-100 text-yellow-800"
    elif event_type == "admin":
        return "bg-purple-100 text-purple-800"
    elif event_type == "config":
        return "bg-green-100 text-green-800"
    elif event_type == "error":
        return "bg-red-100 text-red-800"
    else:
        return "bg-gray-100 text-gray-800"


def _format_event_type(event_type):
    """Format event type for display."""
    return event_type.replace("_", " ").title()
