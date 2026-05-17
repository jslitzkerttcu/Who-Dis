"""
SandCastle Job API endpoints.

Provides the manifest, trigger, and status endpoints consumed by
the SandCastle scheduler portal for background job orchestration.
"""

import logging
from typing import Any, Callable, Dict

from flask import current_app, g, jsonify, request

from app.auth.portal_auth import admin_or_portal_required

logger = logging.getLogger(__name__)

JOB_REGISTRY = [
    {
        "name": "compliance_check",
        "display_name": "Compliance Check",
        "description": "Run bulk job-role compliance check",
        "endpoint": "/api/admin/jobs/compliance_check",
        "default_cron": "0 6 * * 1",
        "timeout_seconds": 600,
        "method": "POST",
        "dependencies": ["warehouse_sync"],
    },
    {
        "name": "warehouse_sync",
        "display_name": "Warehouse Sync",
        "description": "Sync job roles from warehouse",
        "endpoint": "/api/admin/jobs/warehouse_sync",
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


@admin_or_portal_required
def get_manifest():
    """Return the job manifest for the SandCastle scheduler."""
    return jsonify({"jobs": JOB_REGISTRY})


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


@admin_or_portal_required
def get_job_status(name: str, run_id: str):
    """Get the status of a specific job run."""
    if name not in _JOBS_BY_NAME:
        return jsonify({"error": f"Unknown job: {name}"}), 404

    job_manager = current_app.container.get("job_manager")
    status = job_manager.get_status(run_id)

    if status is None:
        return jsonify({"error": f"Run not found: {run_id}"}), 404

    return jsonify(status)
