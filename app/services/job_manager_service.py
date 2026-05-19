"""
Job Manager Service

Provides background job execution with conflict detection, status tracking,
and Flask app context propagation.
"""

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional
from uuid import uuid4

from flask import current_app

from app.database import db
from app.models.job_run import JobRun

logger = logging.getLogger(__name__)


class ConflictError(Exception):
    """Raised when a job is already running."""

    def __init__(self, message: str, run_id: str):
        super().__init__(message)
        self.run_id = run_id


class JobManagerService:
    """Service for managing background job execution with conflict detection."""

    def __init__(self):
        self._executor = ThreadPoolExecutor(max_workers=1)
        self._lock = threading.Lock()

    def start_job(
        self,
        job_name: str,
        runner_fn: Callable,
        triggered_by: str = "system",
        app=None,
    ) -> str:
        """
        Start a background job with conflict detection.

        Args:
            job_name: Name of the job to run
            runner_fn: Callable that performs the job work (receives run_id kwarg)
            triggered_by: Who triggered the job
            app: Flask app instance (defaults to current_app)

        Returns:
            run_id of the started job

        Raises:
            ConflictError: If a job with the same name is already running
        """
        with self._lock:
            existing = (
                JobRun.query.filter_by(job_name=job_name, status="running").first()
            )
            if existing:
                raise ConflictError(
                    f"Job '{job_name}' is already running", existing.run_id
                )

            run_id = uuid4().hex
            job_run = JobRun(
                run_id=run_id,
                job_name=job_name,
                status="running",
                triggered_by=triggered_by,
            )
            db.session.add(job_run)
            db.session.commit()

        app = app or current_app._get_current_object()  # type: ignore[attr-defined]
        self._executor.submit(self._run_with_context, app, run_id, runner_fn)
        return run_id

    def _run_with_context(self, app: Any, run_id: str, fn: Callable) -> None:
        """Execute job function within Flask app context."""
        with app.app_context():
            try:
                fn(run_id=run_id)
                job_run = JobRun.query.filter_by(run_id=run_id).first()
                if job_run:
                    job_run.status = "completed"
                    job_run.completed_at = datetime.now(timezone.utc)
                    db.session.commit()
            except Exception as e:
                logger.error(f"Job {run_id} failed: {str(e)}", exc_info=True)
                job_run = JobRun.query.filter_by(run_id=run_id).first()
                if job_run:
                    job_run.status = "failed"
                    job_run.completed_at = datetime.now(timezone.utc)
                    job_run.error = str(e)[:500]
                    db.session.commit()

    def get_status(self, run_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the status of a job run.

        Args:
            run_id: The unique run identifier

        Returns:
            Dict with job status info, or None if not found
        """
        job_run = JobRun.query.filter_by(run_id=run_id).first()
        if not job_run:
            return None

        return {
            "run_id": job_run.run_id,
            "job_name": job_run.job_name,
            "status": job_run.status,
            "started_at": job_run.started_at.isoformat() if job_run.started_at else None,
            "completed_at": (
                job_run.completed_at.isoformat() if job_run.completed_at else None
            ),
            "error": job_run.error,
        }

    def is_running(self, job_name: str) -> bool:
        """
        Check if a job with the given name is currently running.

        Args:
            job_name: Name of the job to check

        Returns:
            True if a job with that name has status 'running'
        """
        return (
            JobRun.query.filter_by(job_name=job_name, status="running").first()
            is not None
        )
