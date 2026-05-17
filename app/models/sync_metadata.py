"""
Sync Metadata Model

Tracks synchronization state for various data sync operations.
"""

from app.database import db
from app.models.base import BaseModel, TimestampMixin


class SyncMetadata(BaseModel, TimestampMixin):
    """Model for tracking synchronization metadata across sync types."""

    __tablename__ = "sync_metadata"

    sync_type = db.Column(db.String(50), unique=True, nullable=False, index=True)
    last_success_at = db.Column(db.DateTime(timezone=True), nullable=True)
    last_error_at = db.Column(db.DateTime(timezone=True), nullable=True)
    last_error_message = db.Column(db.Text, nullable=True)
    last_error_category = db.Column(db.String(100), nullable=True)
    total_records_synced = db.Column(db.Integer, default=0)
    duration_seconds = db.Column(db.Integer, nullable=True)

    def __repr__(self):
        return f"<SyncMetadata {self.sync_type}>"
