"""
Job Run Model

Tracks background job executions with status, timing, and error information.
"""

from datetime import datetime, timezone

from app.database import db
from app.models.base import BaseModel, TimestampMixin


class JobRun(BaseModel, TimestampMixin):
    """Model for tracking background job runs."""

    __tablename__ = "job_runs"

    run_id = db.Column(db.String(100), unique=True, nullable=False, index=True)
    job_name = db.Column(db.String(100), nullable=False, index=True)
    status = db.Column(
        db.String(50), default="running", index=True
    )  # 'running', 'completed', 'failed'
    started_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    completed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    error = db.Column(db.Text, nullable=True)
    triggered_by = db.Column(db.String(255), default="system")

    def __repr__(self):
        return f"<JobRun {self.run_id} ({self.job_name}): {self.status}>"
