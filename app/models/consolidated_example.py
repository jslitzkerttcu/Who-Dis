"""
Example of how existing models could be consolidated using base classes.

This demonstrates the application of DRY/SOLID/KISS principles to reduce
code duplication and improve maintainability.
"""

from datetime import datetime, timezone, timedelta
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
from app.database import db
from app.models.base import (
    BaseModel,
    AuditableModel,
    CacheableModel,
    ServiceDataModel,
    TimestampMixin,
    ExpirableMixin,
)


# CONSOLIDATED LOGGING MODELS
class LogEntry(AuditableModel):
    """Unified logging model for all system events."""

    __tablename__ = "log_entries"

    # Event categorization
    event_type = db.Column(
        db.String(50), nullable=False, index=True
    )  # 'audit', 'error', 'access'
    event_category = db.Column(
        db.String(50), index=True
    )  # 'search', 'admin', 'auth', etc.

    # Error-specific fields
    error_type = db.Column(db.String(100), index=True)
    stack_trace = db.Column(db.Text)

    # Search-specific fields
    search_query = db.Column(db.String(500), index=True)
    results_count = db.Column(db.Integer)
    services_used = db.Column(JSONB, default=list)  # ['ldap', 'genesys', 'graph']

    # Request details
    request_path = db.Column(db.String(500))
    request_method = db.Column(db.String(10))
    request_data = db.Column(JSONB)

    # Target resource for admin actions
    target_resource = db.Column(db.String(255), index=True)

    @classmethod
    def log_search(
        cls, user_email, search_query, results_count, services_used, **kwargs
    ):
        """Log a search event."""
        return cls(
            event_type="search",
            event_category="user_search",
            user_email=user_email,
            search_query=search_query,
            results_count=results_count,
            services_used=services_used,
            **kwargs,
        ).save()

    @classmethod
    def log_error(cls, user_email, error_type, error_message, stack_trace, **kwargs):
        """Log an error event."""
        return cls(
            event_type="error",
            event_category="system_error",
            user_email=user_email,
            error_type=error_type,
            message=error_message,
            stack_trace=stack_trace,
            success=False,
            **kwargs,
        ).save()

    @classmethod
    def log_access_denied(cls, user_email, target_resource, **kwargs):
        """Log an access denial event."""
        return cls(
            event_type="access",
            event_category="access_denied",
            user_email=user_email,
            target_resource=target_resource,
            success=False,
            **kwargs,
        ).save()

    @classmethod
    def log_admin_action(cls, user_email, action, target_resource, **kwargs):
        """Log an admin action."""
        return cls(
            event_type="admin",
            event_category=action,
            user_email=user_email,
            target_resource=target_resource,
            **kwargs,
        ).save()


# CONSOLIDATED CACHE MODEL
class CacheEntry(CacheableModel):
    """Unified caching model for all cached data."""

    __tablename__ = "cache_entries"

    # Cache identification
    cache_type = db.Column(
        db.String(50), nullable=False, index=True
    )  # 'search', 'api_token', 'photo'
    cache_key = db.Column(db.String(500), nullable=False, index=True)

    # Cache data
    data = db.Column(JSONB, nullable=False)

    # Metadata
    hit_count = db.Column(db.Integer, default=0)
    last_accessed = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    @classmethod
    def get_cached_data(cls, cache_type: str, cache_key: str):
        """Get cached data if not expired."""
        entry = (
            cls.query.filter_by(cache_type=cache_type, cache_key=cache_key)
            .filter(cls.expires_at > datetime.now(timezone.utc))
            .first()
        )

        if entry:
            entry.hit_count += 1
            entry.last_accessed = datetime.now(timezone.utc)
            db.session.commit()
            return entry.data
        return None

    @classmethod
    def set_cached_data(
        cls, cache_type: str, cache_key: str, data, expires_in_seconds: int = 3600
    ):
        """Set cached data with expiration."""
        expires_at = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(
            seconds=expires_in_seconds
        )

        # Update existing or create new
        entry = cls.query.filter_by(cache_type=cache_type, cache_key=cache_key).first()
        if entry:
            entry.data = data
            entry.expires_at = expires_at
            entry.updated_at = datetime.now(timezone.utc)
        else:
            entry = cls(
                cache_type=cache_type,
                cache_key=cache_key,
                data=data,
                expires_at=expires_at,
            )

        return entry.save()


# CONSOLIDATED EXTERNAL SERVICE MODEL
class ExternalServiceData(ServiceDataModel):
    """Unified model for external service data (Genesys, Graph, etc.)."""

    __tablename__ = "external_service_data"

    # Data type (group, skill, location, user, etc.)
    data_type = db.Column(db.String(50), nullable=False, index=True)

    # Human-readable name/title
    name = db.Column(db.String(255), index=True)

    # Status/state
    is_active = db.Column(db.Boolean, default=True, index=True)

    @classmethod
    def get_service_data(
        cls, service_name: str, data_type: str, service_id: str = None
    ):
        """Get data from specific service."""
        query = cls.query.filter_by(service_name=service_name, data_type=data_type)
        if service_id:
            query = query.filter_by(service_id=service_id)
        return query.all()

    @classmethod
    def update_service_data(
        cls,
        service_name: str,
        data_type: str,
        service_id: str,
        name: str,
        raw_data: dict,
    ):
        """Update or create service data."""
        entry = cls.query.filter_by(
            service_name=service_name, data_type=data_type, service_id=service_id
        ).first()

        if entry:
            entry.name = name
            entry.raw_data = raw_data
            entry.updated_at = datetime.now(timezone.utc)
        else:
            entry = cls(
                service_name=service_name,
                data_type=data_type,
                service_id=service_id,
                name=name,
                raw_data=raw_data,
            )

        return entry.save()


# ENHANCED USER MODEL WITH RELATIONSHIPS
class User(BaseModel, TimestampMixin):
    """Enhanced user model with proper relationships."""

    __tablename__ = "users"

    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    role = db.Column(db.String(50), nullable=False, default="viewer", index=True)
    is_active = db.Column(db.Boolean, default=True, index=True)
    last_login = db.Column(db.DateTime, index=True)
    created_by = db.Column(db.String(255))

    # Relationships
    sessions = relationship(
        "UserSession", back_populates="user", cascade="all, delete-orphan"
    )
    notes = relationship(
        "UserNote", back_populates="user", cascade="all, delete-orphan"
    )

    @classmethod
    def get_by_email(cls, email: str):
        """Get user by email address."""
        return cls.query.filter_by(email=email.lower()).first()

    @classmethod
    def get_by_role(cls, role: str):
        """Get all users with specific role."""
        return cls.query.filter_by(role=role, is_active=True).all()

    def update_last_login(self):
        """Update last login timestamp."""
        self.last_login = datetime.now(timezone.utc)
        return self.save()


# SESSION MODEL WITH USER RELATIONSHIP
class UserSession(BaseModel, TimestampMixin, ExpirableMixin):
    """User session model with proper relationships."""

    __tablename__ = "user_sessions"

    # Override ID to use string (session token)
    id = db.Column(db.String(255), primary_key=True)

    user_id = db.Column(
        db.Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    user_email = db.Column(db.String(255), nullable=False, index=True)
    ip_address = db.Column(db.String(45), index=True)
    user_agent = db.Column(db.Text)

    is_active = db.Column(db.Boolean, default=True, index=True)
    last_activity = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    warning_shown = db.Column(db.Boolean, default=False)

    # Relationships
    user = relationship("User", back_populates="sessions")

    def update_activity(self):
        """Update last activity timestamp."""
        self.last_activity = datetime.now(timezone.utc)
        return self.save()

    def deactivate(self):
        """Deactivate the session."""
        self.is_active = False
        return self.save()


# USER NOTES WITH RELATIONSHIP
class UserNote(BaseModel, TimestampMixin):
    """User notes with proper relationships."""

    __tablename__ = "user_notes"

    user_id = db.Column(
        db.Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    created_by = db.Column(db.String(255), nullable=False)
    note_text = db.Column(db.Text, nullable=False)
    is_active = db.Column(db.Boolean, default=True, index=True)

    # Relationships
    user = relationship("User", back_populates="notes")


# MIGRATION UTILITIES
def migrate_existing_models():
    """Utility function to migrate existing models to consolidated structure."""

    # Example migration for audit logs
    from app.models.audit import AuditLog as OldAuditLog

    old_logs = OldAuditLog.query.all()
    for old_log in old_logs:
        new_log = LogEntry(
            event_type="audit",
            event_category=old_log.action,
            user_email=old_log.user_email,
            message=old_log.message,
            success=old_log.success,
            created_at=old_log.timestamp,
            ip_address=old_log.ip_address,
            user_agent=old_log.user_agent,
            search_query=old_log.search_query,
            results_count=old_log.results_count,
            services_used=old_log.services_used or [],
            additional_data=old_log.additional_data or {},
        )
        new_log.save()

    print(f"Migrated {len(old_logs)} audit log entries")


# Usage examples
def example_usage():
    """Examples of how to use the consolidated models."""

    # Log a search
    LogEntry.log_search(
        user_email="user@example.com",
        search_query="john doe",
        results_count=5,
        services_used=["ldap", "genesys"],
        ip_address="192.168.1.1",
    )

    # Cache search results
    CacheEntry.set_cached_data(
        cache_type="search",
        cache_key="john_doe_search",
        data={"results": ["user1", "user2"]},
        expires_in_seconds=1800,
    )

    # Store Genesys group data
    ExternalServiceData.update_service_data(
        service_name="genesys",
        data_type="group",
        service_id="group123",
        name="Customer Service",
        raw_data={"id": "group123", "description": "CS Team"},
    )

    # Get cached data
    cached_results = CacheEntry.get_cached_data("search", "john_doe_search")
    if cached_results:
        print("Using cached search results")

    # Clean up expired entries
    from app.models.base import bulk_cleanup_expired

    cleanup_results = bulk_cleanup_expired(CacheEntry, UserSession)
    print(f"Cleanup results: {cleanup_results}")
