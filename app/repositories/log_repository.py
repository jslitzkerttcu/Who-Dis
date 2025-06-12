"""Log repository implementation."""

from typing import Optional, Dict, Any, List
from datetime import datetime
from app.interfaces.log_repository import ILogRepository
from app.models import AuditLog, ErrorLog, AccessAttempt


class LogRepository(ILogRepository):
    """SQLAlchemy implementation of log repository."""

    def log_search(
        self,
        user_email: str,
        search_query: str,
        results_count: int,
        services: List[str],
        **kwargs,
    ) -> None:
        """Log a search event."""
        AuditLog.log_search(user_email, search_query, results_count, services, **kwargs)

    def log_access(
        self,
        user_email: str,
        action: str,
        target_resource: str,
        success: bool = True,
        **kwargs,
    ) -> None:
        """Log an access event."""
        AuditLog.log_access(
            user_email, action, target_resource, success=success, **kwargs
        )

    def log_admin_action(
        self,
        user_email: str,
        action: str,
        target_resource: str,
        additional_data: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> None:
        """Log an administrative action."""
        AuditLog.log_admin_action(user_email, action, target_resource, **kwargs)

    def log_error(
        self,
        error_type: str,
        error_message: str,
        stack_trace: Optional[str] = None,
        **kwargs,
    ) -> None:
        """Log an error event."""
        ErrorLog.log_error(
            error_type, error_message, stack_trace=stack_trace or "", **kwargs
        )

    def query_logs(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        event_type: Optional[str] = None,
        user_email: Optional[str] = None,
        search_query: Optional[str] = None,
        ip_address: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Query log entries with filters across all log tables."""
        all_logs = []

        # Query AuditLog table
        audit_query = AuditLog.query
        if start_date:
            audit_query = audit_query.filter(AuditLog.created_at >= start_date)
        if end_date:
            audit_query = audit_query.filter(AuditLog.created_at <= end_date)
        if event_type:
            audit_query = audit_query.filter(AuditLog.event_type == event_type)
        if user_email:
            audit_query = audit_query.filter(
                AuditLog.user_email.ilike(f"%{user_email}%")
            )
        if search_query:
            audit_query = audit_query.filter(
                AuditLog.search_query.ilike(f"%{search_query}%")
            )
        if ip_address:
            audit_query = audit_query.filter(
                AuditLog.ip_address.ilike(f"%{ip_address}%")
            )

        for log in audit_query.all():
            log_dict = log.to_dict()
            log_dict["log_type"] = "audit"
            all_logs.append(log_dict)

        # Query ErrorLog table (if no specific event_type or event_type is 'error')
        if not event_type or event_type == "error":
            error_query = ErrorLog.query
            if start_date:
                error_query = error_query.filter(ErrorLog.created_at >= start_date)
            if end_date:
                error_query = error_query.filter(ErrorLog.created_at <= end_date)
            if user_email:
                error_query = error_query.filter(
                    ErrorLog.user_email.ilike(f"%{user_email}%")
                )
            if ip_address:
                error_query = error_query.filter(
                    ErrorLog.ip_address.ilike(f"%{ip_address}%")
                )

            for log in error_query.all():
                log_dict = log.to_dict()
                log_dict["log_type"] = "error"
                log_dict["event_type"] = "error"  # Add event_type for consistency
                all_logs.append(log_dict)

        # Query AccessAttempt table (if no specific event_type or event_type is 'access')
        if not event_type or event_type == "access":
            access_query = AccessAttempt.query
            if start_date:
                access_query = access_query.filter(
                    AccessAttempt.created_at >= start_date
                )
            if end_date:
                access_query = access_query.filter(AccessAttempt.created_at <= end_date)
            if user_email:
                access_query = access_query.filter(
                    AccessAttempt.user_email.ilike(f"%{user_email}%")
                )
            if ip_address:
                access_query = access_query.filter(
                    AccessAttempt.ip_address.ilike(f"%{ip_address}%")
                )

            for log in access_query.all():
                log_dict = log.to_dict()
                log_dict["log_type"] = "access"
                log_dict["event_type"] = "access"  # Add event_type for consistency
                all_logs.append(log_dict)

        # Sort by timestamp (created_at) descending
        all_logs.sort(key=lambda x: x.get("created_at", datetime.min), reverse=True)

        # Apply pagination
        return all_logs[offset : offset + limit]

    def count_logs(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        event_type: Optional[str] = None,
        user_email: Optional[str] = None,
        search_query: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> int:
        """Count log entries with filters across all log tables."""
        total_count = 0

        # Count AuditLog entries
        audit_query = AuditLog.query
        if start_date:
            audit_query = audit_query.filter(AuditLog.created_at >= start_date)
        if end_date:
            audit_query = audit_query.filter(AuditLog.created_at <= end_date)
        if event_type:
            audit_query = audit_query.filter(AuditLog.event_type == event_type)
        if user_email:
            audit_query = audit_query.filter(
                AuditLog.user_email.ilike(f"%{user_email}%")
            )
        if search_query:
            audit_query = audit_query.filter(
                AuditLog.search_query.ilike(f"%{search_query}%")
            )
        if ip_address:
            audit_query = audit_query.filter(
                AuditLog.ip_address.ilike(f"%{ip_address}%")
            )

        total_count += int(audit_query.count())

        # Count ErrorLog entries (if no specific event_type or event_type is 'error')
        if not event_type or event_type == "error":
            error_query = ErrorLog.query
            if start_date:
                error_query = error_query.filter(ErrorLog.created_at >= start_date)
            if end_date:
                error_query = error_query.filter(ErrorLog.created_at <= end_date)
            if user_email:
                error_query = error_query.filter(
                    ErrorLog.user_email.ilike(f"%{user_email}%")
                )
            if ip_address:
                error_query = error_query.filter(
                    ErrorLog.ip_address.ilike(f"%{ip_address}%")
                )

            total_count += int(error_query.count())

        # Count AccessAttempt entries (if no specific event_type or event_type is 'access')
        if not event_type or event_type == "access":
            access_query = AccessAttempt.query
            if start_date:
                access_query = access_query.filter(
                    AccessAttempt.created_at >= start_date
                )
            if end_date:
                access_query = access_query.filter(AccessAttempt.created_at <= end_date)
            if user_email:
                access_query = access_query.filter(
                    AccessAttempt.user_email.ilike(f"%{user_email}%")
                )
            if ip_address:
                access_query = access_query.filter(
                    AccessAttempt.ip_address.ilike(f"%{ip_address}%")
                )

            total_count += int(access_query.count())

        return total_count
