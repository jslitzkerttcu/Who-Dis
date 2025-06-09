"""Enhanced UserSession model with base classes and relationships."""

from datetime import datetime, timezone, timedelta
from typing import Optional
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship
from app.database import db
from app.models.base import BaseModel, TimestampMixin, ExpirableMixin


class UserSession(BaseModel, TimestampMixin, ExpirableMixin):
    """User session model with proper relationships."""

    __tablename__ = "user_sessions"

    # Override ID to use string (session token)
    id = db.Column(db.String(255), primary_key=True)

    # Foreign key to users table
    user_id = db.Column(
        db.Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_email = db.Column(db.String(255), nullable=False, index=True)

    # Session details
    ip_address = db.Column(db.String(45), index=True)
    user_agent = db.Column(db.Text)

    # Session state
    is_active = db.Column(db.Boolean, default=True, index=True)
    last_activity = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    warning_shown = db.Column(db.Boolean, default=False)

    # Relationships
    user = relationship("User", back_populates="sessions")

    @classmethod
    def create_session(
        cls,
        session_id: str,
        user_id: int,
        user_email: str,
        ip_address: str = None,
        user_agent: str = None,
        timeout_minutes: int = 15,
    ) -> "UserSession":
        """Create a new session."""
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=timeout_minutes)

        session = cls(
            id=session_id,
            user_id=user_id,
            user_email=user_email.lower().strip(),
            ip_address=ip_address,
            user_agent=user_agent,
            expires_at=expires_at,
            is_active=True,
        )
        return session.save()

    @classmethod
    def get_active_session(cls, session_id: str) -> Optional["UserSession"]:
        """Get active session by ID."""
        return (
            cls.query.filter_by(id=session_id, is_active=True)
            .filter(cls.expires_at > datetime.now(timezone.utc))
            .first()
        )

    @classmethod
    def get_user_sessions(cls, user_id: int, active_only: bool = True):
        """Get all sessions for a user."""
        query = cls.query.filter_by(user_id=user_id)

        if active_only:
            query = query.filter_by(is_active=True).filter(
                cls.expires_at > datetime.now(timezone.utc)
            )

        return query.all()

    def update_activity(self) -> "UserSession":
        """Update last activity timestamp."""
        self.last_activity = datetime.now(timezone.utc)
        return self.save()

    def extend_session(self, timeout_minutes: int) -> "UserSession":
        """Extend session expiration."""
        self.expires_at = datetime.now(timezone.utc) + timedelta(
            minutes=timeout_minutes
        )
        self.warning_shown = False  # Reset warning
        return self.save()

    def deactivate(self) -> "UserSession":
        """Deactivate the session."""
        self.is_active = False
        return self.save()

    def mark_warning_shown(self) -> "UserSession":
        """Mark that timeout warning has been shown."""
        self.warning_shown = True
        return self.save()

    def get_time_until_expiry(self) -> timedelta:
        """Get time remaining until session expires."""
        return self.expires_at - datetime.now(timezone.utc)

    def get_minutes_until_expiry(self) -> float:
        """Get minutes remaining until session expires."""
        return self.get_time_until_expiry().total_seconds() / 60

    def should_show_warning(self, warning_minutes: int = 2) -> bool:
        """Check if warning should be shown."""
        return (
            not self.warning_shown
            and self.get_minutes_until_expiry() <= warning_minutes
            and not self.is_expired()
        )

    def get_session_duration(self) -> timedelta:
        """Get total session duration so far."""
        return self.last_activity - self.created_at

    def to_dict(self, exclude: Optional[list] = None) -> dict:
        """Convert to dictionary with session-specific fields."""
        result = super().to_dict(exclude=exclude)

        # Add computed fields
        result["time_until_expiry_minutes"] = self.get_minutes_until_expiry()
        result["session_duration_minutes"] = (
            self.get_session_duration().total_seconds() / 60
        )
        result["is_expired"] = self.is_expired()

        return result

    def __repr__(self):
        return f"<UserSession {self.id[:8]}... for {self.user_email}>"
