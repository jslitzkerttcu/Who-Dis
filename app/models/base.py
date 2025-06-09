"""
Base model classes implementing DRY/SOLID/KISS principles.

This module provides common mixins and base classes to reduce code duplication
and ensure consistent patterns across all models.
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import event
from app.database import db


class TimestampMixin:
    """Mixin for models that need created_at and updated_at timestamps."""

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class UserTrackingMixin:
    """Mixin for models that track user activity."""

    user_email = db.Column(db.String(255), nullable=False, index=True)
    user_agent = db.Column(db.Text)
    ip_address = db.Column(db.String(45), index=True)  # IPv6 compatible
    session_id = db.Column(db.String(255), index=True)


class ExpirableMixin:
    """Mixin for models with expiration functionality."""

    expires_at = db.Column(db.DateTime(timezone=True), nullable=False, index=True)

    def is_expired(self) -> bool:
        """Check if this record has expired."""
        now = datetime.now(timezone.utc)
        expires_at = self.expires_at

        # Handle timezone-naive vs timezone-aware comparison
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        elif now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)

        return now > expires_at

    @classmethod
    def cleanup_expired(cls, commit=True):
        """Remove all expired records for this model.

        Args:
            commit: Whether to commit the transaction. Default True.

        Returns:
            Number of expired records deleted.
        """
        # This method should only be called on actual model classes
        if not hasattr(cls, "query"):
            raise AttributeError(
                f"{cls.__name__} is a mixin and cannot be queried directly"
            )

        # Use consistent timezone handling
        now = datetime.now(timezone.utc)
        expired_count = cls.query.filter(  # type: ignore[attr-defined]
            cls.expires_at < now
        ).delete()
        if commit:
            db.session.commit()
        return expired_count

    def extend_expiration(self, seconds: int, commit=True):
        """Extend expiration by specified seconds.

        Args:
            seconds: Number of seconds to extend expiration.
            commit: Whether to commit the transaction immediately. Default True.
        """
        self.expires_at = datetime.now(timezone.utc) + timedelta(seconds=seconds)
        if commit:
            db.session.commit()
        return self


class SerializableMixin:
    """Mixin for models that need JSON serialization."""

    def to_dict(self, exclude: Optional[List[str]] = None) -> Dict[str, Any]:
        """Convert model instance to dictionary."""
        exclude = exclude or []
        result = {}

        # Only access __table__ if this is actually a model instance
        if hasattr(self, "__table__"):
            for column in self.__table__.columns:
                if column.name in exclude:
                    continue

                value = getattr(self, column.name)
                if isinstance(value, datetime):
                    result[column.name] = value.isoformat()
                elif hasattr(value, "__dict__"):  # Handle relationship objects
                    result[column.name] = str(value)
                else:
                    result[column.name] = value
        return result

    def to_json_safe(self) -> Dict[str, Any]:
        """Convert to JSON-safe dictionary (excludes sensitive fields)."""
        if not hasattr(self, "__table__"):
            return self.to_dict()

        sensitive_fields = ["password", "secret", "token", "key", "hash"]
        exclude = [
            col.name
            for col in self.__table__.columns
            if any(field in col.name.lower() for field in sensitive_fields)
        ]
        return self.to_dict(exclude=exclude)


class JSONDataMixin:
    """Mixin for models that store additional JSON data."""

    additional_data = db.Column(JSONB, default=dict)

    def get_data(self, key: str, default=None):
        """Get value from additional_data."""
        if self.additional_data:
            return self.additional_data.get(key, default)
        return default

    def set_data(self, key: str, value):
        """Set value in additional_data."""
        if self.additional_data is None:
            self.additional_data = {}

        # Create a new dict to trigger SQLAlchemy change detection
        new_data = dict(self.additional_data)
        new_data[key] = value
        self.additional_data = new_data

        # Mark as modified for SQLAlchemy
        db.session.merge(self)

    def update_data(self, data_dict: Dict[str, Any]):
        """Update multiple values in additional_data."""
        if self.additional_data is None:
            self.additional_data = {}

        new_data = dict(self.additional_data)
        new_data.update(data_dict)
        self.additional_data = new_data
        db.session.merge(self)


class BaseModel(db.Model, SerializableMixin):  # type: ignore
    """Base model class with common functionality."""

    __abstract__ = True

    id = db.Column(db.Integer, primary_key=True)

    @classmethod
    def get_by_id(cls, id_value):
        """Get record by ID."""
        return cls.query.get(id_value)

    @classmethod
    def get_or_create(cls, **kwargs):
        """Get existing record or create new one."""
        instance = cls.query.filter_by(**kwargs).first()
        if instance:
            return instance, False
        else:
            instance = cls(**kwargs)
            return instance.save(), True

    def save(self, commit=True):
        """Save the current instance.

        Args:
            commit: Whether to commit the transaction immediately. Default True.
                    Set to False to batch multiple operations in a single transaction.
        """
        try:
            db.session.add(self)
            if commit:
                db.session.commit()
            return self
        except Exception:
            db.session.rollback()
            raise

    def delete(self, commit=True):
        """Delete the current instance.

        Args:
            commit: Whether to commit the transaction immediately. Default True.
        """
        db.session.delete(self)
        if commit:
            db.session.commit()

    def update(self, commit=True, **kwargs):
        """Update instance with provided values.

        Args:
            commit: Whether to commit the transaction immediately. Default True.
            **kwargs: Field values to update.
        """
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        return self.save(commit=commit)


class AuditableModel(BaseModel, TimestampMixin, UserTrackingMixin, JSONDataMixin):
    """Base model for auditable entities."""

    __abstract__ = True

    success = db.Column(db.Boolean, nullable=False, default=True, index=True)
    message = db.Column(db.Text)


class CacheableModel(BaseModel, TimestampMixin, ExpirableMixin):
    """Base model for cacheable entities."""

    __abstract__ = True

    @classmethod
    def get_valid_cache(cls, **filters):
        """Get non-expired cache entries matching filters."""
        now = datetime.now(timezone.utc)
        query = cls.query.filter(cls.expires_at > now)
        for key, value in filters.items():
            if hasattr(cls, key):
                query = query.filter(getattr(cls, key) == value)
        return query.all()

    @classmethod
    def cleanup_and_get_stats(cls):
        """Cleanup expired entries and return statistics."""
        total_count = cls.query.count()
        expired_count = cls.cleanup_expired()
        valid_count = total_count - expired_count

        return {
            "total": total_count,
            "expired_removed": expired_count,
            "valid_remaining": valid_count,
        }


class ServiceDataModel(BaseModel, TimestampMixin, JSONDataMixin):
    """Base model for external service data."""

    __abstract__ = True

    service_id = db.Column(db.String(255), nullable=False, index=True)
    service_name = db.Column(db.String(100), nullable=False, index=True)
    raw_data = db.Column(JSONB, default=dict)
    is_active = db.Column(db.Boolean, default=True, index=True)

    def update_from_service(self, data: Dict[str, Any], commit=True):
        """Update model with fresh data from external service.

        Args:
            data: Data from the external service.
            commit: Whether to commit the transaction. Default True.

        Returns:
            The updated instance.
        """
        self.raw_data = data
        self.updated_at = datetime.now(timezone.utc)

        # Extract common fields from raw data if they exist
        if "name" in data and hasattr(self, "name"):
            self.name = data["name"]
        if "active" in data:
            self.is_active = bool(data.get("active", True))
        if "enabled" in data:
            self.is_active = bool(data.get("enabled", True))

        return self.save(commit=commit)

    @classmethod
    def sync_from_service_data(
        cls, service_name: str, service_data: List[Dict[str, Any]], commit=True
    ):
        """Sync multiple records from service data.

        Args:
            service_name: Name of the external service.
            service_data: List of data items from the service.
            commit: Whether to commit after all updates. Default True.

        Returns:
            Dictionary with created and updated counts.
        """
        updated_count = 0
        created_count = 0

        for item in service_data:
            service_id = item.get("id")
            if not service_id:
                continue

            instance, created = cls.get_or_create(
                service_name=service_name, service_id=service_id
            )
            # Don't commit individual updates when doing batch sync
            instance.update_from_service(item, commit=False)

            if created:
                created_count += 1
            else:
                updated_count += 1

        if commit:
            db.session.commit()

        return {"created": created_count, "updated": updated_count}


# Utility functions for common model operations
def bulk_cleanup_expired(*model_classes):
    """Clean up expired records from multiple model classes."""
    results = {}
    for model_class in model_classes:
        if hasattr(model_class, "cleanup_expired"):
            results[model_class.__name__] = model_class.cleanup_expired()
    return results


def get_model_stats(*model_classes):
    """Get record counts for multiple models."""
    stats = {}
    for model_class in model_classes:
        total = model_class.query.count()
        active = None

        # Get active count if model has is_active field
        if hasattr(model_class, "is_active"):
            active = model_class.query.filter_by(is_active=True).count()

        stats[model_class.__name__] = {"total": total, "active": active}
    return stats


def bulk_update_timestamps(*model_classes, commit=True):
    """Update timestamps for all records in specified models (for migration).

    Args:
        *model_classes: Model classes to update.
        commit: Whether to commit after all updates. Default True.

    Returns:
        Dictionary mapping model names to update counts.
    """
    results = {}
    current_time = datetime.now(timezone.utc)

    for model_class in model_classes:
        if hasattr(model_class, "updated_at"):
            count = model_class.query.update({model_class.updated_at: current_time})
            results[model_class.__name__] = count

    if commit:
        db.session.commit()

    return results


# Event listeners for automatic maintenance
@event.listens_for(db.session, "before_commit")
def before_commit(session):
    """Auto-update timestamps before commit."""
    current_time = datetime.now(timezone.utc)

    for obj in session.new:
        if hasattr(obj, "created_at") and obj.created_at is None:
            obj.created_at = current_time
        if hasattr(obj, "updated_at"):
            obj.updated_at = current_time

    for obj in session.dirty:
        if hasattr(obj, "updated_at"):
            obj.updated_at = current_time
