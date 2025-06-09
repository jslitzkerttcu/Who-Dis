"""
Unified logging model that consolidates audit, error, and access logging.

This replaces the separate AuditLog, ErrorLog, and AccessAttempt models
with a single, flexible logging system.
"""

import warnings
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.dialects.postgresql import JSONB
from app.database import db
from app.models.base import AuditableModel


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
    action = db.Column(db.String(100), index=True)  # Specific action taken

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

    # User role at time of action
    user_role = db.Column(db.String(50), index=True)

    @classmethod
    def log_search(
        cls,
        user_email: str,
        search_query: str,
        results_count: int,
        services_used: List[str],
        user_role: str = None,
        ip_address: str = None,
        user_agent: str = None,
        session_id: str = None,
        success: bool = True,
        error_message: str = None,
        **kwargs,
    ):
        """Log a search event."""
        return cls(
            event_type="search",
            event_category="user_search",
            action="search_user",
            user_email=user_email,
            search_query=search_query,
            results_count=results_count,
            services_used=services_used,
            user_role=user_role,
            ip_address=ip_address,
            user_agent=user_agent,
            session_id=session_id,
            success=success,
            message=error_message,
            **kwargs,
        ).save()

    @classmethod
    def log_error(
        cls,
        user_email: str,
        error_type: str,
        error_message: str,
        stack_trace: str = None,
        endpoint: str = None,
        request_method: str = None,
        request_data: Dict = None,
        user_role: str = None,
        ip_address: str = None,
        user_agent: str = None,
        session_id: str = None,
        **kwargs,
    ):
        """Log an error event."""
        return cls(
            event_type="error",
            event_category="system_error",
            action="error_occurred",
            user_email=user_email,
            error_type=error_type,
            message=error_message,
            stack_trace=stack_trace,
            request_path=endpoint,
            request_method=request_method,
            request_data=request_data,
            user_role=user_role,
            ip_address=ip_address,
            user_agent=user_agent,
            session_id=session_id,
            success=False,
            **kwargs,
        ).save()

    @classmethod
    def log_access_denied(
        cls,
        user_email: str,
        target_resource: str,
        reason: str = None,
        user_role: str = None,
        ip_address: str = None,
        user_agent: str = None,
        session_id: str = None,
        request_path: str = None,
        request_method: str = None,
        **kwargs,
    ):
        """Log an access denial event."""
        return cls(
            event_type="access",
            event_category="access_denied",
            action="access_denied",
            user_email=user_email,
            target_resource=target_resource,
            message=reason or f"Access denied to {target_resource}",
            user_role=user_role,
            ip_address=ip_address,
            user_agent=user_agent,
            session_id=session_id,
            request_path=request_path,
            request_method=request_method,
            success=False,
            **kwargs,
        ).save()

    @classmethod
    def log_admin_action(
        cls,
        user_email: str,
        action: str,
        target_resource: str,
        user_role: str = None,
        ip_address: str = None,
        user_agent: str = None,
        session_id: str = None,
        success: bool = True,
        message: str = None,
        additional_data: Dict = None,
        **kwargs,
    ):
        """Log an admin action."""
        entry = cls(
            event_type="admin",
            event_category="admin_action",
            action=action,
            user_email=user_email,
            target_resource=target_resource,
            user_role=user_role,
            ip_address=ip_address,
            user_agent=user_agent,
            session_id=session_id,
            success=success,
            message=message or f"Admin action: {action} on {target_resource}",
            **kwargs,
        )

        if additional_data:
            entry.update_data(additional_data)

        return entry.save()

    @classmethod
    def log_config_change(
        cls,
        user_email: str,
        config_key: str,
        old_value: str = None,
        new_value: str = None,
        user_role: str = None,
        ip_address: str = None,
        user_agent: str = None,
        session_id: str = None,
        **kwargs,
    ):
        """Log a configuration change."""
        return cls(
            event_type="config",
            event_category="config_change",
            action="config_update",
            user_email=user_email,
            target_resource=f"config:{config_key}",
            message=f"Configuration changed: {config_key}",
            user_role=user_role,
            ip_address=ip_address,
            user_agent=user_agent,
            session_id=session_id,
            success=True,
            **kwargs,
        ).save()

    # Backward compatibility aliases
    @classmethod
    def log_access(cls, user_email: str, action: str, target_resource: str, success: bool = True, **kwargs):
        """Log an access event (success or failure)."""
        if success:
            return cls(
                event_type="access",
                event_category="access_granted",
                action=action,
                user_email=user_email,
                target_resource=target_resource,
                success=True,
                **kwargs,
            ).save()
        else:
            return cls.log_access_denied(user_email, target_resource, **kwargs)

    @classmethod
    def log_config(
        cls,
        user_email: str,
        config_key: str,
        old_value: str = None,
        new_value: str = None,
        **kwargs,
    ):
        """Backward compatibility alias for log_config_change."""
        return cls.log_config_change(
            user_email, config_key, old_value, new_value, **kwargs
        )

    @classmethod
    def log_event(cls, event_type: str, action: str, user_email: str = None, **kwargs):
        """Generic logging method for backward compatibility."""
        return cls(
            event_type=event_type,
            event_category=kwargs.get("event_category", "general"),
            action=action,
            user_email=user_email or "system",
            **kwargs,
        ).save()

    @classmethod
    def log_auth_event(
        cls,
        user_email: str,
        action: str,
        success: bool = True,
        message: str = None,
        user_role: str = None,
        ip_address: str = None,
        user_agent: str = None,
        session_id: str = None,
        **kwargs,
    ):
        """Log authentication events (login, logout, session events)."""
        return cls(
            event_type="auth",
            event_category="authentication",
            action=action,
            user_email=user_email,
            message=message or f"Authentication event: {action}",
            user_role=user_role,
            ip_address=ip_address,
            user_agent=user_agent,
            session_id=session_id,
            success=success,
            **kwargs,
        ).save()

    @classmethod
    def get_audit_logs(
        cls, limit: int = 50, offset: int = 0, filters: Dict[str, Any] = None
    ):
        """Get audit logs with filtering and pagination."""
        query = cls.query

        if filters:
            if "start_date" in filters:
                query = query.filter(cls.created_at >= filters["start_date"])
            if "end_date" in filters:
                query = query.filter(cls.created_at <= filters["end_date"])
            if "event_type" in filters:
                query = query.filter(cls.event_type == filters["event_type"])
            if "user_email" in filters:
                query = query.filter(cls.user_email.ilike(f"%{filters['user_email']}%"))
            if "search_query" in filters and filters["search_query"]:
                query = query.filter(
                    cls.search_query.ilike(f"%{filters['search_query']}%")
                )
            if "ip_address" in filters:
                query = query.filter(cls.ip_address == filters["ip_address"])
            if "success" in filters:
                query = query.filter(cls.success == filters["success"])

        # Get total count before applying limit/offset
        total = query.count()

        # Apply ordering, limit, and offset
        logs = query.order_by(cls.created_at.desc()).offset(offset).limit(limit).all()

        return logs, total

    @classmethod
    def get_event_types(cls) -> List[str]:
        """Get all distinct event types."""
        result = db.session.query(cls.event_type).distinct().all()
        return [row[0] for row in result if row[0]]

    @classmethod
    def get_users_with_activity(cls) -> List[str]:
        """Get all users who have activity in the logs."""
        result = db.session.query(cls.user_email).distinct().all()
        return [row[0] for row in result if row[0]]

    @classmethod
    def get_search_statistics(
        cls, start_date: datetime = None, end_date: datetime = None
    ) -> Dict[str, Any]:
        """Get search statistics for reporting."""
        query = cls.query.filter(cls.event_type == "search")

        if start_date:
            query = query.filter(cls.created_at >= start_date)
        if end_date:
            query = query.filter(cls.created_at <= end_date)

        total_searches = query.count()
        successful_searches = query.filter(cls.success).count()
        failed_searches = total_searches - successful_searches

        # Get service usage statistics
        service_stats: Dict[str, int] = {}
        for log in query.filter(cls.services_used.isnot(None)).all():
            for service in log.services_used or []:
                service_stats[service] = service_stats.get(service, 0) + 1

        # Get top search terms
        search_terms = (
            db.session.query(
                cls.search_query, db.func.count(cls.search_query).label("count")
            )
            .filter(cls.event_type == "search", cls.search_query.isnot(None))
            .group_by(cls.search_query)
            .order_by(db.func.count(cls.search_query).desc())
            .limit(10)
            .all()
        )

        return {
            "total_searches": total_searches,
            "successful_searches": successful_searches,
            "failed_searches": failed_searches,
            "success_rate": (successful_searches / total_searches * 100)
            if total_searches > 0
            else 0,
            "service_usage": service_stats,
            "top_search_terms": [
                {"term": term, "count": count} for term, count in search_terms
            ],
        }

    @classmethod
    def cleanup_old_logs(cls, days: int = 90) -> int:
        """Clean up logs older than specified days."""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        deleted_count = cls.query.filter(cls.created_at < cutoff_date).delete()
        db.session.commit()
        return deleted_count

    def to_dict(self, exclude: Optional[List[str]] = None) -> Dict[str, Any]:
        """Convert to dictionary with formatted timestamp."""
        result = super().to_dict(exclude=exclude)

        # Format services_used as list if it's not already
        if self.services_used and not isinstance(result.get("services_used"), list):
            result["services_used"] = list(self.services_used)

        return result


def __getattr__(name):
    """Module-level __getattr__ for backward compatibility with deprecation warnings."""
    if name in ["AuditLog", "ErrorLog", "AccessAttempt"]:
        warnings.warn(
            f"{name} is deprecated, use LogEntry instead",
            DeprecationWarning,
            stacklevel=2,
        )
        return LogEntry
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
