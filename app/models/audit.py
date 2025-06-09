from typing import Optional, List, Dict, Any
from app.database import db
import json
from .base import AuditableModel


class AuditLog(AuditableModel):
    """Audit log model for tracking all system activities"""

    __tablename__ = "audit_log"

    # AuditableModel provides: id, created_at, updated_at, user_email, user_agent,
    # ip_address, session_id, success, message, additional_data

    # Keep timestamp for backward compatibility, map to created_at
    timestamp = db.synonym("created_at")

    # Additional audit-specific fields
    event_type = db.Column(db.String(50), nullable=False, index=True)
    user_role = db.Column(db.String(50))
    action = db.Column(db.String(100), nullable=False)
    target_resource = db.Column(db.String(500))
    search_query = db.Column(db.String(500), index=True)
    search_results_count = db.Column(db.Integer)
    search_services = db.Column(db.Text)  # JSON array as text
    error_message = db.synonym("message")  # Map to base class field

    def __repr__(self):
        return f"<AuditLog {self.id}: {self.event_type} by {self.user_email}>"

    def to_dict(self, exclude: Optional[List[str]] = None) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        # Use base class to_dict and add custom handling for search_services
        data = super().to_dict(exclude)

        # Parse search_services JSON if present
        if self.search_services:
            data["search_services"] = json.loads(self.search_services)

        # Ensure timestamp alias is included
        data["timestamp"] = data.get("created_at")

        return data

    @classmethod
    def log_search(cls, user_email, search_query, results_count, services, **kwargs):
        """Log a search event"""
        log = cls(
            event_type="search",
            user_email=user_email,
            action="identity_search",
            search_query=search_query,
            search_results_count=results_count,
            search_services=json.dumps(services),
            user_role=kwargs.get("user_role"),
            ip_address=kwargs.get("ip_address"),
            success=kwargs.get("success", True),
            message=kwargs.get("error_message"),
            additional_data=kwargs.get("additional_data"),
            session_id=kwargs.get("session_id"),
            user_agent=kwargs.get("user_agent"),
        )
        return log.save()

    @classmethod
    def log_access(cls, user_email, action, target_resource, **kwargs):
        """Log an access event"""
        log = cls(
            event_type="access",
            user_email=user_email,
            action=action,
            target_resource=target_resource,
            user_role=kwargs.get("user_role"),
            ip_address=kwargs.get("ip_address"),
            success=kwargs.get("success", True),
            message=kwargs.get("error_message"),
            additional_data=kwargs.get("additional_data"),
            session_id=kwargs.get("session_id"),
            user_agent=kwargs.get("user_agent"),
        )
        return log.save()

    @classmethod
    def log_admin_action(cls, user_email, action, target_resource, **kwargs):
        """Log an admin action"""
        log = cls(
            event_type="admin",
            user_email=user_email,
            action=action,
            target_resource=target_resource,
            user_role=kwargs.get("user_role"),
            ip_address=kwargs.get("ip_address"),
            success=kwargs.get("success", True),
            message=kwargs.get("error_message"),
            additional_data=kwargs.get("additional_data"),
            session_id=kwargs.get("session_id"),
            user_agent=kwargs.get("user_agent"),
        )
        return log.save()

    @classmethod
    def log_config_change(cls, user_email, action, config_key, **kwargs):
        """Log a configuration change"""
        additional_data = kwargs.get("additional_data", {})
        additional_data.update(
            {
                "config_key": config_key,
                "old_value": kwargs.get("old_value"),
                "new_value": kwargs.get("new_value"),
            }
        )

        log = cls(
            event_type="config",
            user_email=user_email,
            action=action,
            target_resource=config_key,
            user_role=kwargs.get("user_role"),
            ip_address=kwargs.get("ip_address"),
            success=kwargs.get("success", True),
            message=kwargs.get("error_message"),
            additional_data=additional_data,
            session_id=kwargs.get("session_id"),
            user_agent=kwargs.get("user_agent"),
        )
        return log.save()
