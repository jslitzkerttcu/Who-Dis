"""
Report Cache Model

Stores aggregated report data with tiered TTL and staleness detection.
Used by ReportSyncService to cache expensive Graph API aggregations
(license summaries, MFA stats, sign-in failures) so report tabs render
from pre-computed data instead of live API calls.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional

from app.database import db
from app.models.base import BaseModel, TimestampMixin


class ReportCache(BaseModel, TimestampMixin):
    """Model for cached report data with tiered TTL."""

    __tablename__ = "report_cache"

    report_type = db.Column(db.String(50), nullable=False, index=True)
    cache_key = db.Column(db.String(100), nullable=False, index=True)
    data = db.Column(db.JSON, nullable=False)
    generated_at = db.Column(db.DateTime(timezone=True), nullable=False)
    ttl_hours = db.Column(db.Integer, nullable=False)

    __table_args__ = (
        db.UniqueConstraint("report_type", "cache_key", name="uq_report_cache"),
    )

    @property
    def is_stale(self) -> bool:
        """Check if cached data has exceeded its TTL."""
        if not self.generated_at:
            return True
        generated = self.generated_at
        if generated.tzinfo is None:
            generated = generated.replace(tzinfo=timezone.utc)
        expiry = generated + timedelta(hours=self.ttl_hours)
        return datetime.now(timezone.utc) > expiry

    @property
    def age_display(self) -> str:
        """Human-readable age string for template use."""
        if not self.generated_at:
            return "unknown"
        generated = self.generated_at
        if generated.tzinfo is None:
            generated = generated.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - generated
        total_seconds = int(delta.total_seconds())
        if total_seconds < 60:
            return "just now"
        minutes = total_seconds // 60
        if minutes < 60:
            return f"{minutes} min ago"
        hours = minutes // 60
        if hours < 24:
            return f"{hours} hour{'s' if hours > 1 else ''} ago"
        days = hours // 24
        return f"{days} day{'s' if days > 1 else ''} ago"

    @classmethod
    def store(
        cls,
        report_type: str,
        cache_key: str,
        data: object,
        ttl_hours: int,
    ) -> "ReportCache":
        """Upsert pattern: update existing cache entry or insert new one.

        Args:
            report_type: Category of report (e.g. "license_summary").
            cache_key: Sub-key within report type (e.g. "per_sku").
            data: Aggregated report payload (must be JSON-serializable).
            ttl_hours: Time-to-live in hours before data is considered stale.

        Returns:
            The created or updated ReportCache instance.
        """
        now = datetime.now(timezone.utc)
        existing = cls.query.filter_by(
            report_type=report_type,
            cache_key=cache_key,
        ).first()

        if existing:
            existing.data = data
            existing.generated_at = now
            existing.ttl_hours = ttl_hours
            return existing.save()

        entry = cls(
            report_type=report_type,
            cache_key=cache_key,
            data=data,
            generated_at=now,
            ttl_hours=ttl_hours,
        )
        return entry.save()

    @classmethod
    def get_cached(
        cls, report_type: str, cache_key: str
    ) -> Optional["ReportCache"]:
        """Retrieve a cached report entry by type and key.

        Args:
            report_type: Category of report.
            cache_key: Sub-key within report type.

        Returns:
            ReportCache instance or None if not found.
        """
        return cls.query.filter_by(
            report_type=report_type,
            cache_key=cache_key,
        ).first()

    def __repr__(self) -> str:
        return f"<ReportCache {self.report_type}/{self.cache_key}>"
