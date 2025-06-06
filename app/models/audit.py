from datetime import datetime
from app.database import db
from sqlalchemy.dialects.postgresql import JSONB
import json


class AuditLog(db.Model):  # type: ignore
    """Audit log model for tracking all system activities"""

    __tablename__ = "audit_log"

    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, index=True
    )
    event_type = db.Column(db.String(50), nullable=False, index=True)
    user_email = db.Column(db.String(255), nullable=False, index=True)
    user_role = db.Column(db.String(50))
    ip_address = db.Column(db.String(45), index=True)
    action = db.Column(db.String(100), nullable=False)
    target_resource = db.Column(db.String(500))
    search_query = db.Column(db.String(500), index=True)
    search_results_count = db.Column(db.Integer)
    search_services = db.Column(db.Text)  # JSON array as text
    success = db.Column(db.Boolean, default=True, index=True)
    error_message = db.Column(db.Text)
    additional_data = db.Column(JSONB)
    session_id = db.Column(db.String(255))
    user_agent = db.Column(db.Text)

    def __repr__(self):
        return f"<AuditLog {self.id}: {self.event_type} by {self.user_email}>"

    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "event_type": self.event_type,
            "user_email": self.user_email,
            "user_role": self.user_role,
            "ip_address": self.ip_address,
            "action": self.action,
            "target_resource": self.target_resource,
            "search_query": self.search_query,
            "search_results_count": self.search_results_count,
            "search_services": json.loads(self.search_services)
            if self.search_services
            else None,
            "success": self.success,
            "error_message": self.error_message,
            "additional_data": self.additional_data,
            "session_id": self.session_id,
            "user_agent": self.user_agent,
        }

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
            error_message=kwargs.get("error_message"),
            additional_data=kwargs.get("additional_data"),
            session_id=kwargs.get("session_id"),
            user_agent=kwargs.get("user_agent"),
        )
        db.session.add(log)
        db.session.commit()
        return log

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
            error_message=kwargs.get("error_message"),
            additional_data=kwargs.get("additional_data"),
            session_id=kwargs.get("session_id"),
            user_agent=kwargs.get("user_agent"),
        )
        db.session.add(log)
        db.session.commit()
        return log

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
            error_message=kwargs.get("error_message"),
            additional_data=kwargs.get("additional_data"),
            session_id=kwargs.get("session_id"),
            user_agent=kwargs.get("user_agent"),
        )
        db.session.add(log)
        db.session.commit()
        return log

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
            error_message=kwargs.get("error_message"),
            additional_data=additional_data,
            session_id=kwargs.get("session_id"),
            user_agent=kwargs.get("user_agent"),
        )
        db.session.add(log)
        db.session.commit()
        return log
