"""
SandCastle Job API endpoints.

Provides the manifest, trigger, and status endpoints consumed by
the SandCastle scheduler portal for background job orchestration.

Mounted as a separate blueprint at /api/v2/admin/jobs to match the
paths SandCastle expects (avoids double-prefixing under admin_bp).
"""

import logging
from typing import Any, Callable, Dict

from flask import Blueprint, current_app, g, jsonify, request

from app.auth.portal_auth import admin_or_portal_required

logger = logging.getLogger(__name__)

jobs_api_bp = Blueprint("jobs_api", __name__)

JOB_REGISTRY = [
    {
        "name": "compliance_check",
        "display_name": "Compliance Check",
        "description": "Run bulk job-role compliance check",
        "endpoint": "/api/v2/admin/jobs/compliance_check",
        "default_cron": "0 6 * * 1",
        "timeout_seconds": 600,
        "method": "POST",
        "dependencies": ["warehouse_sync"],
    },
    {
        "name": "warehouse_sync",
        "display_name": "Warehouse Sync",
        "description": "Sync job roles from warehouse",
        "endpoint": "/api/v2/admin/jobs/warehouse_sync",
        "default_cron": "0 5 * * *",
        "timeout_seconds": 300,
        "method": "POST",
        "dependencies": [],
    },
]

_JOBS_BY_NAME: Dict[str, Dict[str, Any]] = {job["name"]: job for job in JOB_REGISTRY}

_JOB_RUNNERS: Dict[str, Callable] = {}


def _run_compliance_check(run_id: str) -> None:
    """Runner function for compliance check job."""
    service = current_app.container.get("compliance_checking_service")
    service.run_compliance_check(
        scope="all",
        started_by="sandcastle-scheduler",
        run_type="scheduled",
    )


def _run_warehouse_sync(run_id: str) -> None:
    """Runner function for warehouse sync job."""
    service = current_app.container.get("job_role_warehouse_service")
    service.sync_all_compliance_data()


_JOB_RUNNERS = {
    "compliance_check": _run_compliance_check,
    "warehouse_sync": _run_warehouse_sync,
}


@jobs_api_bp.route("/manifest", methods=["GET"])
@admin_or_portal_required
def get_manifest():
    """Return the job manifest for the SandCastle scheduler."""
    return jsonify({"jobs": JOB_REGISTRY})


@jobs_api_bp.route("/<name>", methods=["POST"])
@admin_or_portal_required
def trigger_job(name: str):
    """Trigger a named job and return 202 with run_id."""
    if name not in _JOBS_BY_NAME:
        return jsonify({"error": f"Unknown job: {name}"}), 404

    runner_fn = _JOB_RUNNERS.get(name)
    if not runner_fn:
        return jsonify({"error": f"No runner configured for job: {name}"}), 500

    from app.services.job_manager_service import ConflictError

    job_manager = current_app.container.get("job_manager")

    try:
        run_id = job_manager.start_job(
            job_name=name,
            runner_fn=runner_fn,
            triggered_by=g.user,
        )
        return jsonify({"status": "started", "run_id": run_id}), 202
    except ConflictError as e:
        return jsonify({"error": str(e), "run_id": e.run_id}), 409


@jobs_api_bp.route("/<name>/status/<run_id>", methods=["GET"])
@admin_or_portal_required
def get_job_status(name: str, run_id: str):
    """Get the status of a specific job run."""
    from flask import render_template

    if name not in _JOBS_BY_NAME:
        return jsonify({"error": f"Unknown job: {name}"}), 404

    job_manager = current_app.container.get("job_manager")
    status = job_manager.get_status(run_id)

    if status is None:
        return jsonify({"error": f"Run not found: {run_id}"}), 404

    # Return HTMX partials for browser polling
    if request.headers.get("HX-Request"):
        if name == "compliance_check":
            from app.models.job_role_compliance import ComplianceCheckRun, ComplianceCheck

            check_run = ComplianceCheckRun.query.filter_by(run_id=run_id).first()

            if status["status"] == "completed" and check_run:
                # Fetch violations for the completed run
                violations = ComplianceCheck.query.filter(
                    ComplianceCheck.check_run_id == run_id,
                    ComplianceCheck.compliance_status != "compliant",
                ).all()

                violation_data = []
                for v in violations:
                    violation_data.append({
                        "id": v.id,
                        "employee_id": v.employee_upn,
                        "job_code": v.job_code,
                        "system_name": v.system_name,
                        "violation_type": v.compliance_status,
                        "severity": v.violation_severity,
                        "status": "open",
                        "detected_at": v.created_at.isoformat() if v.created_at else None,
                        "details": v.notes,
                        "recommended_action": v.remediation_action,
                    })

                return render_template(
                    "admin/partials/_compliance_progress.html",
                    status="completed",
                    run_id=run_id,
                    checked_count=check_run.checked_count or check_run.total_employees or 0,
                    total_employees=check_run.total_employees or 0,
                    percent=100,
                    error_count=check_run.error_count or 0,
                    data={"violations": violation_data, "run_id": run_id},
                )

            elif status["status"] == "failed":
                return render_template(
                    "admin/partials/_compliance_progress.html",
                    status="failed",
                    run_id=run_id,
                    checked_count=check_run.checked_count if check_run else 0,
                    total_employees=check_run.total_employees if check_run else 0,
                    percent=_calc_percent(check_run),
                    error_count=check_run.error_count if check_run else 0,
                    error_message=status.get("error", "Unknown error"),
                )

            else:
                # Running state
                return render_template(
                    "admin/partials/_compliance_progress.html",
                    status="running",
                    run_id=run_id,
                    checked_count=check_run.checked_count if check_run else 0,
                    total_employees=check_run.total_employees if check_run else 0,
                    percent=_calc_percent(check_run),
                    error_count=check_run.error_count if check_run else 0,
                )

        elif name == "warehouse_sync":
            from app.models.sync_metadata import SyncMetadata
            from datetime import datetime, timezone

            metadata = SyncMetadata.query.filter_by(sync_type="warehouse_sync").first()
            last_success_at_relative = ""
            if metadata and metadata.last_success_at:
                delta = datetime.now(timezone.utc) - metadata.last_success_at
                if delta.days > 0:
                    last_success_at_relative = f"{delta.days} day{'s' if delta.days > 1 else ''} ago"
                elif delta.seconds >= 3600:
                    hours = delta.seconds // 3600
                    last_success_at_relative = f"{hours} hour{'s' if hours > 1 else ''} ago"
                else:
                    minutes = max(1, delta.seconds // 60)
                    last_success_at_relative = f"{minutes} minute{'s' if minutes > 1 else ''} ago"

            return render_template(
                "admin/partials/_warehouse_sync_status.html",
                syncing=(status["status"] == "running"),
                last_success_at=metadata.last_success_at.isoformat() if metadata and metadata.last_success_at else None,
                last_success_at_relative=last_success_at_relative,
                last_error_message=metadata.last_error_message if metadata else None,
                last_error_category=metadata.last_error_category if metadata else None,
            )

    return jsonify(status)


def _calc_percent(check_run) -> int:
    """Calculate progress percentage for a compliance check run."""
    if not check_run or not check_run.total_employees:
        return 0
    checked = check_run.checked_count or 0
    return min(100, int((checked / check_run.total_employees) * 100))
