import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from sqlalchemy import and_, or_, desc, func
from app.models.audit import AuditLog
from app.models.error import ErrorLog
from app.database import db
from app.interfaces.audit_service import IAuditLogger, IAuditQueryService

logger = logging.getLogger(__name__)


class PostgresAuditService(IAuditLogger, IAuditQueryService):
    """PostgreSQL-based audit service using SQLAlchemy models"""

    def __init__(self):
        logger.info("PostgreSQL audit service initialized")

    def init_app(self, app):
        """Flask compatibility method"""
        pass

    # Public logging methods

    def log_search(
        self,
        user_email: str,
        search_query: str,
        results_count: int,
        services: List[str],
        **kwargs,
    ):
        try:
            AuditLog.log_search(
                user_email, search_query, results_count, services, **kwargs
            )
        except Exception as e:
            logger.error(f"Failed to log search: {e}")
            try:
                db.session.rollback()
            except Exception:
                pass

    def log_access(self, user_email: str, action: str, target_resource: str, **kwargs):
        try:
            AuditLog.log_access(user_email, action, target_resource, **kwargs)
        except Exception as e:
            logger.error(f"Failed to log access: {e}")
            # Ensure session is rolled back on error
            try:
                db.session.rollback()
            except Exception:
                pass

    def log_access_denial(
        self, user_email: str, requested_resource: str, reason: str, **kwargs
    ) -> None:
        """Log an access denial event."""
        try:
            AuditLog.log_access(
                user_email=user_email,
                action="access_denied",
                target_resource=requested_resource,
                success=False,
                message=reason,
                **kwargs,
            )
        except Exception as e:
            logger.error(f"Failed to log access denial: {e}")

    def log_admin_action(
        self,
        user_email: str,
        action: str,
        target: str,
        details: Dict[str, Any],
        **kwargs,
    ) -> None:
        """Log an administrative action."""
        try:
            AuditLog.log_admin_action(
                user_email=user_email,
                action=action,
                target_resource=target,
                additional_data=details,
                **kwargs,
            )
        except Exception as e:
            logger.error(f"Failed to log admin action: {e}")
            try:
                db.session.rollback()
            except Exception:
                pass

    def log_config_change(self, user_email: str, config_key: str, **kwargs):
        try:
            AuditLog.log_config_change(user_email, config_key, **kwargs)
        except Exception as e:
            logger.error(f"Failed to log config change: {e}")
            try:
                db.session.rollback()
            except Exception:
                pass

    def log_config(
        self,
        user_email: str,
        config_key: str,
        old_value: Optional[str] = None,
        new_value: Optional[str] = None,
        **kwargs,
    ):
        """Log configuration changes (backward compatibility alias)."""
        try:
            # Add old_value and new_value to kwargs for the actual method
            kwargs["old_value"] = old_value
            kwargs["new_value"] = new_value
            AuditLog.log_config_change(
                user_email, "config_change", config_key, **kwargs
            )
        except Exception as e:
            logger.error(f"Failed to log config: {e}")

    def log_error(
        self,
        error_type: str,
        error_message: str,
        stack_trace: Optional[str] = None,
        **kwargs,
    ) -> None:
        try:
            # Log to audit log
            audit_log = AuditLog(
                event_type="error",
                user_email=kwargs.get("user_email", "system"),
                action=error_type,
                target_resource=kwargs.get("request_path"),
                user_role=kwargs.get("user_role"),
                ip_address=kwargs.get("ip_address"),
                success=False,
                message=error_message,
                additional_data={
                    "error_type": error_type,
                    "stack_trace": stack_trace,
                    "request_method": kwargs.get("request_method"),
                },
                session_id=kwargs.get("session_id"),
                user_agent=kwargs.get("user_agent"),
            )
            audit_log.save()

            # Also log to dedicated error log
            ErrorLog.log_error(
                error_type=error_type,
                error_message=error_message,
                user_email=kwargs.get("user_email", "system"),
                stack_trace=stack_trace,
                request_path=kwargs.get("request_path"),
                request_method=kwargs.get("request_method"),
                request_data=kwargs.get("additional_data", {}).get("form"),
                ip_address=kwargs.get("ip_address"),
                user_agent=kwargs.get("user_agent"),
            )
        except Exception as e:
            logger.error(f"Failed to log error: {e}")

    # Query methods

    def get_recent_logs(
        self,
        limit: int = 100,
        event_type: Optional[str] = None,
        user_email: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Get recent audit logs with optional filters."""
        try:
            query = AuditLog.query

            # Apply filters
            filters = []
            if event_type:
                filters.append(AuditLog.event_type == event_type)
            if user_email:
                filters.append(AuditLog.user_email.ilike(f"%{user_email}%"))
            if start_date:
                filters.append(AuditLog.timestamp >= start_date)
            if end_date:
                filters.append(AuditLog.timestamp <= end_date)

            if filters:
                query = query.filter(and_(*filters))

            results = query.order_by(desc(AuditLog.timestamp)).limit(limit).all()
            return [log.to_dict() for log in results]
        except Exception as e:
            logger.error(f"Failed to get recent logs: {e}")
            return []

    def query_logs(
        self,
        event_type: Optional[str] = None,
        user_email: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        search_query: Optional[str] = None,
        ip_address: Optional[str] = None,
        success: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        try:
            query = AuditLog.query

            # Apply filters
            filters = []
            if event_type:
                filters.append(AuditLog.event_type == event_type)
            if user_email:
                filters.append(AuditLog.user_email.ilike(f"%{user_email}%"))
            if start_date:
                filters.append(AuditLog.timestamp >= datetime.fromisoformat(start_date))
            if end_date:
                filters.append(AuditLog.timestamp <= datetime.fromisoformat(end_date))
            if search_query:
                filters.append(
                    or_(
                        AuditLog.search_query.ilike(f"%{search_query}%"),
                        AuditLog.action.ilike(f"%{search_query}%"),
                        AuditLog.target_resource.ilike(f"%{search_query}%"),
                    )
                )
            if ip_address:
                filters.append(AuditLog.ip_address.ilike(f"%{ip_address}%"))
            if success is not None:
                filters.append(AuditLog.success == success)

            if filters:
                query = query.filter(and_(*filters))

            # Get total count
            total = query.count()

            # Get paginated results
            results = (
                query.order_by(desc(AuditLog.timestamp))
                .limit(limit)
                .offset(offset)
                .all()
            )

            return {
                "results": [log.to_dict() for log in results],
                "total": total,
                "limit": limit,
                "offset": offset,
            }
        except Exception as e:
            logger.error(f"Failed to query logs: {e}")
            return {
                "results": [],
                "total": 0,
                "limit": limit,
                "offset": offset,
            }

    def get_recent_searches(self, limit: int = 100) -> List[Dict[str, Any]]:
        try:
            results = (
                AuditLog.query.filter_by(event_type="search")
                .order_by(desc(AuditLog.timestamp))
                .limit(limit)
                .all()
            )
            return [log.to_dict() for log in results]
        except Exception as e:
            logger.error(f"Failed to get recent searches: {e}")
            return []

    def get_event_types(self) -> List[str]:
        try:
            results = (
                db.session.query(AuditLog.event_type)
                .distinct()
                .order_by(AuditLog.event_type)
                .all()
            )
            return [r[0] for r in results]
        except Exception as e:
            logger.error(f"Failed to get event types: {e}")
            return []

    def get_users_with_activity(self) -> List[str]:
        try:
            results = (
                db.session.query(AuditLog.user_email)
                .filter(AuditLog.user_email != "system")
                .distinct()
                .order_by(AuditLog.user_email)
                .all()
            )
            return [r[0] for r in results]
        except Exception as e:
            logger.error(f"Failed to get users: {e}")
            return []

    def get_user_activity(
        self, user_email: str, days: int = 30
    ) -> List[Dict[str, Any]]:
        try:
            cutoff = datetime.utcnow() - timedelta(days=days)

            results = (
                AuditLog.query.filter(AuditLog.user_email == user_email)
                .filter(AuditLog.timestamp >= cutoff)
                .order_by(desc(AuditLog.timestamp))
                .all()
            )
            return [log.to_dict() for log in results]
        except Exception as e:
            logger.error(f"Failed to get user activity: {e}")
            return []

    def get_search_statistics(self, days: int = 30) -> Dict[str, Any]:
        try:
            cutoff = datetime.utcnow() - timedelta(days=days)

            # Base query for searches
            search_query = AuditLog.query.filter(
                AuditLog.event_type == "search"
            ).filter(AuditLog.timestamp >= cutoff)

            # Get basic stats
            total_searches = search_query.count()
            unique_users = (
                db.session.query(func.count(func.distinct(AuditLog.user_email)))
                .filter(AuditLog.event_type == "search")
                .filter(AuditLog.timestamp >= cutoff)
                .scalar()
            )
            unique_queries = (
                db.session.query(func.count(func.distinct(AuditLog.search_query)))
                .filter(AuditLog.event_type == "search")
                .filter(AuditLog.timestamp >= cutoff)
                .scalar()
            )
            avg_results = (
                db.session.query(func.avg(AuditLog.search_results_count))
                .filter(AuditLog.event_type == "search")
                .filter(AuditLog.timestamp >= cutoff)
                .scalar()
                or 0
            )
            failed_searches = search_query.filter(AuditLog.success.is_(False)).count()

            # Get top searches
            top_searches = (
                db.session.query(
                    AuditLog.search_query,
                    func.count(AuditLog.search_query).label("count"),
                )
                .filter(AuditLog.event_type == "search")
                .filter(AuditLog.timestamp >= cutoff)
                .group_by(AuditLog.search_query)
                .order_by(desc("count"))
                .limit(10)
                .all()
            )

            return {
                "total_searches": total_searches,
                "unique_users": unique_users,
                "unique_queries": unique_queries,
                "avg_results": float(avg_results),
                "failed_searches": failed_searches,
                "top_searches": [
                    {"search_query": q, "count": c} for q, c in top_searches
                ],
            }
        except Exception as e:
            logger.error(f"Failed to get search statistics: {e}")
            return {
                "total_searches": 0,
                "unique_users": 0,
                "unique_queries": 0,
                "avg_results": 0,
                "failed_searches": 0,
                "top_searches": [],
            }

    def get_config_changes(self, days: int = 30) -> List[Dict[str, Any]]:
        try:
            cutoff = datetime.utcnow() - timedelta(days=days)

            results = (
                AuditLog.query.filter(AuditLog.event_type == "config")
                .filter(AuditLog.timestamp >= cutoff)
                .order_by(desc(AuditLog.timestamp))
                .all()
            )
            return [log.to_dict() for log in results]
        except Exception as e:
            logger.error(f"Failed to get config changes: {e}")
            return []

    def get_errors(self, days: int = 7) -> List[Dict[str, Any]]:
        try:
            cutoff = datetime.utcnow() - timedelta(days=days)

            results = (
                ErrorLog.query.filter(ErrorLog.timestamp >= cutoff)
                .order_by(desc(ErrorLog.timestamp))
                .all()
            )
            return [log.to_dict() for log in results]
        except Exception as e:
            logger.error(f"Failed to get errors: {e}")
            return []

    def get_error_statistics(self, days: int = 7) -> Dict[str, Any]:
        try:
            cutoff = datetime.utcnow() - timedelta(days=days)

            # Base query for errors
            error_query = ErrorLog.query.filter(ErrorLog.timestamp >= cutoff)

            # Get basic stats
            total_errors = error_query.count()
            unique_error_types = (
                db.session.query(func.count(func.distinct(ErrorLog.error_type)))
                .filter(ErrorLog.timestamp >= cutoff)
                .scalar()
            )
            affected_users = (
                db.session.query(func.count(func.distinct(ErrorLog.user_email)))
                .filter(ErrorLog.timestamp >= cutoff)
                .filter(ErrorLog.user_email.isnot(None))
                .scalar()
            )
            affected_paths = (
                db.session.query(func.count(func.distinct(ErrorLog.request_path)))
                .filter(ErrorLog.timestamp >= cutoff)
                .filter(ErrorLog.request_path.isnot(None))
                .scalar()
            )

            # Get top errors
            top_errors = (
                db.session.query(
                    ErrorLog.error_type, func.count(ErrorLog.error_type).label("count")
                )
                .filter(ErrorLog.timestamp >= cutoff)
                .group_by(ErrorLog.error_type)
                .order_by(desc("count"))
                .limit(10)
                .all()
            )

            return {
                "total_errors": total_errors,
                "unique_error_types": unique_error_types,
                "affected_users": affected_users,
                "affected_paths": affected_paths,
                "top_errors": [{"error_type": t, "count": c} for t, c in top_errors],
            }
        except Exception as e:
            logger.error(f"Failed to get error statistics: {e}")
            return {
                "total_errors": 0,
                "unique_error_types": 0,
                "affected_users": 0,
                "affected_paths": 0,
                "top_errors": [],
            }

    def stop(self):
        """Compatibility method - no cleanup needed for PostgreSQL"""
        pass


# Create a module-level instance
audit_service = PostgresAuditService()


# For backward compatibility
def get_audit_service():
    """Get singleton instance of AuditService"""
    return audit_service
