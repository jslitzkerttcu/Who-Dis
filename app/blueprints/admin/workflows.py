"""
Workflow Automation Admin Module

Onboarding and offboarding checklist management with completion tracking.
Provides dashboard with KPI cards, workflow creation from job role mappings,
detail view with item completion/skip interactions, and CSV export.
"""

import csv
import io
import logging
from typing import Dict, List

from flask import (
    abort,
    current_app,
    g,
    redirect,
    render_template,
    request,
    Response,
    url_for,
)

from app.middleware.auth import require_role
from app.middleware.csrf import csrf_double_submit
from app.models.workflow import StandardOffboardingItem
from app.models.job_role_compliance import JobCode, JobRoleMapping

logger = logging.getLogger(__name__)


@require_role("admin")
def workflows_dashboard():
    """Main workflows dashboard with KPI cards and Active/Completed tabs."""
    tab = request.args.get("tab", "active")
    if request.headers.get("HX-Request"):
        return _render_tab(tab)

    workflow_service = current_app.container.get("workflow_service")
    stats = workflow_service.get_dashboard_stats()
    tab_content = _render_tab(tab)

    return render_template(
        "admin/workflows.html",
        stats=stats,
        active_tab=tab,
        tab_content=tab_content,
    )


def _render_tab(tab: str) -> str:
    """Dispatch tab rendering to the appropriate handler.

    Args:
        tab: Tab identifier string ("active" or "completed").

    Returns:
        Rendered HTML partial for the requested tab.
    """
    tab_handlers = {
        "active": _render_active_tab,
        "completed": _render_completed_tab,
    }
    handler = tab_handlers.get(tab)
    if handler is None:
        abort(404)
    return handler()


def _render_active_tab() -> str:
    """Render the active workflows table partial."""
    workflow_service = current_app.container.get("workflow_service")
    workflows = workflow_service.get_active_workflows()
    return render_template(
        "admin/partials/_workflow_active_table.html",
        workflows=workflows,
    )


def _render_completed_tab() -> str:
    """Render the completed workflows table partial with pagination."""
    page = request.args.get("page", 1, type=int)
    workflow_service = current_app.container.get("workflow_service")
    pagination = workflow_service.get_completed_workflows(page=page)
    return render_template(
        "admin/partials/_workflow_completed_table.html",
        pagination=pagination,
    )


@require_role("admin")
def create_workflow():
    """Create a new workflow. GET renders form, POST processes creation."""
    if request.method == "GET":
        job_codes = JobCode.get_active_job_codes()
        error = request.args.get("error")
        return render_template(
            "admin/workflow_create.html",
            job_codes=job_codes,
            error=error,
        )

    # POST: create the workflow
    employee_name = request.form.get("employee_name", "").strip()
    employee_email = request.form.get("employee_email", "").strip() or None
    job_code = request.form.get("job_code", "").strip()
    workflow_type = request.form.get("workflow_type", "").strip()

    # Validate
    if not employee_name:
        job_codes = JobCode.get_active_job_codes()
        return render_template(
            "admin/workflow_create.html",
            job_codes=job_codes,
            error="Employee name is required.",
        )

    if not job_code:
        job_codes = JobCode.get_active_job_codes()
        return render_template(
            "admin/workflow_create.html",
            job_codes=job_codes,
            error="Job code is required.",
        )

    if workflow_type not in ("onboarding", "offboarding"):
        job_codes = JobCode.get_active_job_codes()
        return render_template(
            "admin/workflow_create.html",
            job_codes=job_codes,
            error="Invalid workflow type.",
        )

    workflow_service = current_app.container.get("workflow_service")

    try:
        if workflow_type == "onboarding":
            workflow = workflow_service.generate_onboarding(
                employee_name=employee_name,
                employee_email=employee_email,
                job_code=job_code,
                created_by=g.user,
            )
        else:
            workflow = workflow_service.generate_offboarding(
                employee_name=employee_name,
                employee_email=employee_email,
                job_code=job_code,
                created_by=g.user,
            )

        # Audit log
        admin_role = getattr(request, "user_role", None)
        user_ip = request.headers.get("X-Forwarded-For", request.remote_addr)

        current_app.container.get("audit_logger").log_admin_action(
            user_email=g.user,
            action="workflow_created",
            target=f"{employee_name} ({workflow_type})",
            details={
                "workflow_id": workflow.id,
                "job_code": job_code,
                "item_count": len(workflow.items),
                "employee_email": employee_email,
            },
            user_role=admin_role,
            ip_address=user_ip,
            user_agent=request.headers.get("User-Agent"),
        )

        return redirect(
            url_for("admin.workflow_detail", workflow_id=workflow.id)
        )

    except ValueError as e:
        job_codes = JobCode.get_active_job_codes()
        return render_template(
            "admin/workflow_create.html",
            job_codes=job_codes,
            error=str(e),
        )


@require_role("admin")
def preview_checklist():
    """HTMX endpoint: preview checklist items before creation.

    Returns an HTML fragment showing items that will be generated
    for the selected job code and workflow type.
    """
    job_code = request.args.get("job_code", "").strip()
    workflow_type = request.args.get("workflow_type", "onboarding").strip()

    if not job_code:
        return '<div class="text-sm text-gray-500 italic">Select a job code to preview checklist items.</div>'

    mappings = JobRoleMapping.get_active_mappings_for_job_code(job_code)
    if not mappings:
        return (
            '<div class="bg-yellow-50 border border-yellow-200 rounded-md p-4">'
            '<p class="text-sm text-yellow-800">'
            "No active role mappings found for this job code."
            "</p></div>"
        )

    items: List[Dict[str, str]] = []

    for mapping in mappings:
        if mapping.mapping_type == "prohibited":
            continue

        system_name = mapping.system_role.system_name
        role_name = mapping.system_role.role_name

        if workflow_type == "onboarding":
            if mapping.mapping_type == "required":
                text = f"Assign: {role_name} ({system_name})"
            else:
                text = f"Consider assigning: {role_name} ({system_name})"
        else:
            text = f"Remove: {role_name} ({system_name})"

        items.append({"text": text, "source": "From role mapping"})

    # Add standard offboarding items for offboarding
    if workflow_type == "offboarding":
        standard_items = StandardOffboardingItem.get_all_active()
        for std_item in standard_items:
            items.append({
                "text": std_item.item_text,
                "source": "Standard offboarding item",
            })

    if not items:
        return '<div class="text-sm text-gray-500 italic">No checklist items would be generated.</div>'

    # Build preview HTML
    html_parts = [
        '<div class="space-y-2">',
        f'<p class="text-sm font-medium text-gray-700">{len(items)} items will be generated:</p>',
        '<ul class="space-y-1">',
    ]
    for item in items:
        html_parts.append(
            '<li class="flex items-start gap-2 text-sm">'
            '<i class="fas fa-circle text-gray-300 text-xs mt-1"></i>'
            "<div>"
            f'<span class="text-gray-900">{item["text"]}</span>'
            f'<span class="text-xs text-gray-500 ml-1">({item["source"]})</span>'
            "</div>"
            "</li>"
        )
    html_parts.append("</ul></div>")

    return "".join(html_parts)


@require_role("admin")
def workflow_detail(workflow_id: int):
    """Display workflow detail with checklist items."""
    workflow_service = current_app.container.get("workflow_service")
    workflow = workflow_service.get_workflow(workflow_id)
    if workflow is None:
        abort(404)

    return render_template(
        "admin/workflow_detail.html",
        workflow=workflow,
    )


@require_role("admin")
@csrf_double_submit.protect
def complete_item(item_id: int):
    """Mark a workflow item as completed. HTMX endpoint."""
    workflow_service = current_app.container.get("workflow_service")

    try:
        item = workflow_service.complete_item(item_id, g.user)
    except ValueError as e:
        return (
            f'<div class="bg-red-50 border border-red-200 rounded-md p-4">'
            f'<p class="text-sm text-red-800">{e}</p></div>'
        ), 400

    # Audit log
    admin_role = getattr(request, "user_role", None)
    user_ip = request.headers.get("X-Forwarded-For", request.remote_addr)

    current_app.container.get("audit_logger").log_admin_action(
        user_email=g.user,
        action="workflow_item_completed",
        target=item.item_text,
        details={
            "item_id": item.id,
            "workflow_id": item.workflow_id,
        },
        user_role=admin_role,
        ip_address=user_ip,
        user_agent=request.headers.get("User-Agent"),
    )

    return render_template(
        "admin/partials/_workflow_item.html",
        item=item,
    )


@require_role("admin")
@csrf_double_submit.protect
def skip_item(item_id: int):
    """Mark a workflow item as skipped with a reason. HTMX endpoint."""
    reason = request.form.get("skip_reason", "").strip()

    workflow_service = current_app.container.get("workflow_service")

    try:
        item = workflow_service.skip_item(item_id, g.user, reason)
    except ValueError as e:
        return (
            f'<div class="bg-red-50 border border-red-200 rounded-md p-4">'
            f'<p class="text-sm text-red-800">{e}</p></div>'
        ), 400

    # Audit log
    admin_role = getattr(request, "user_role", None)
    user_ip = request.headers.get("X-Forwarded-For", request.remote_addr)

    current_app.container.get("audit_logger").log_admin_action(
        user_email=g.user,
        action="workflow_item_skipped",
        target=item.item_text,
        details={
            "item_id": item.id,
            "workflow_id": item.workflow_id,
            "reason": reason,
        },
        user_role=admin_role,
        ip_address=user_ip,
        user_agent=request.headers.get("User-Agent"),
    )

    return render_template(
        "admin/partials/_workflow_item.html",
        item=item,
    )


@require_role("admin")
@csrf_double_submit.protect
def cancel_workflow(workflow_id: int):
    """Cancel an active workflow."""
    workflow_service = current_app.container.get("workflow_service")

    try:
        workflow = workflow_service.cancel_workflow(workflow_id)
    except ValueError:
        abort(404)

    # Audit log
    admin_role = getattr(request, "user_role", None)
    user_ip = request.headers.get("X-Forwarded-For", request.remote_addr)

    current_app.container.get("audit_logger").log_admin_action(
        user_email=g.user,
        action="workflow_cancelled",
        target=f"{workflow.employee_name} ({workflow.workflow_type})",
        details={
            "workflow_id": workflow.id,
        },
        user_role=admin_role,
        ip_address=user_ip,
        user_agent=request.headers.get("User-Agent"),
    )

    return redirect(url_for("admin.workflows_dashboard"))


@require_role("admin")
def export_workflow_csv(workflow_id: int):
    """Export workflow checklist as CSV."""
    workflow_service = current_app.container.get("workflow_service")
    workflow = workflow_service.get_workflow(workflow_id)
    if workflow is None:
        abort(404)

    output = io.StringIO()
    writer = csv.writer(output)

    # Metadata rows
    writer.writerow([
        f"Workflow: {workflow.workflow_type.title()} - {workflow.employee_name}"
    ])
    writer.writerow([
        f"Job Code: {workflow.job_code} - {workflow.job_title or 'N/A'}"
    ])
    writer.writerow([f"Status: {workflow.status.title()}"])
    writer.writerow([
        f"Created: {workflow.created_at.strftime('%Y-%m-%d %H:%M:%S') if workflow.created_at else 'N/A'}"
    ])
    writer.writerow([])

    # Header row
    writer.writerow([
        "Item",
        "Source",
        "Status",
        "Completed By",
        "Completed At",
        "Skip Reason",
        "Due Date",
    ])

    # Data rows
    for item in workflow.items:
        writer.writerow([
            item.item_text,
            item.item_source,
            item.status.title(),
            item.completed_by or "",
            item.completed_at.strftime("%Y-%m-%d %H:%M:%S") if item.completed_at else "",
            item.skip_reason or "",
            item.due_date.strftime("%Y-%m-%d") if item.due_date else "",
        ])

    csv_content = output.getvalue()
    output.close()

    safe_name = workflow.employee_name.replace(" ", "_")
    filename = f"workflow_{workflow.id}_{workflow.workflow_type}_{safe_name}.csv"

    return Response(
        csv_content,
        mimetype="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        },
    )


@require_role("admin")
def employee_search():
    """HTMX typeahead endpoint for employee search during workflow creation.

    Returns HTML fragment with clickable result rows containing
    employee name, email, and job code data attributes.
    """
    q = request.args.get("q", "").strip()
    if len(q) < 2:
        return ""

    try:
        search_orchestrator = current_app.container.get("search_orchestrator")
        results = search_orchestrator.search(q)
    except Exception as e:
        logger.error(f"Employee search failed: {e}", exc_info=True)
        return '<div class="text-sm text-red-600 p-2">Search failed. Please try again.</div>'

    if not results:
        return '<div class="text-sm text-gray-500 p-2">No results found.</div>'

    html_parts = [
        '<div class="border border-gray-200 rounded-md bg-white shadow-sm max-h-60 overflow-y-auto">'
    ]

    for result in results[:10]:
        name = result.get("displayName", result.get("name", ""))
        email = result.get(
            "mail", result.get("email", result.get("userPrincipalName", ""))
        )
        job_code = result.get("ukg_job_code", result.get("jobTitle", ""))

        html_parts.append(
            '<div class="px-3 py-2 hover:bg-blue-50 cursor-pointer border-b border-gray-100 last:border-0"'
            ' onclick="selectEmployee(this)"'
            f' data-name="{name}"'
            f' data-email="{email}"'
            f' data-job-code="{job_code}">'
            f'<div class="text-sm font-medium text-gray-900">{name}</div>'
            f'<div class="text-xs text-gray-500">{email}</div>'
            "</div>"
        )

    html_parts.append("</div>")
    return "".join(html_parts)
