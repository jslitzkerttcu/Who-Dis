from datetime import datetime
from app.database import db
from sqlalchemy.dialects.postgresql import JSONB


class ErrorLog(db.Model):  # type: ignore
    """Error log model for tracking application errors"""

    __tablename__ = "error_log"

    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, index=True
    )
    error_type = db.Column(db.String(100), nullable=False, index=True)
    error_message = db.Column(db.Text, nullable=False)
    stack_trace = db.Column(db.Text)
    user_email = db.Column(db.String(255))
    request_path = db.Column(db.String(500))
    request_method = db.Column(db.String(10))
    request_data = db.Column(JSONB)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.Text)
    severity = db.Column(db.String(20), default="ERROR", index=True)

    def __repr__(self):
        return f"<ErrorLog {self.id}: {self.error_type} at {self.timestamp}>"

    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "stack_trace": self.stack_trace,
            "user_email": self.user_email,
            "request_path": self.request_path,
            "request_method": self.request_method,
            "request_data": self.request_data,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "severity": self.severity,
        }

    @classmethod
    def log_error(cls, error_type, error_message, **kwargs):
        """Log an error"""
        log = cls(
            error_type=error_type,
            error_message=error_message,
            stack_trace=kwargs.get("stack_trace"),
            user_email=kwargs.get("user_email"),
            request_path=kwargs.get("request_path"),
            request_method=kwargs.get("request_method"),
            request_data=kwargs.get("request_data"),
            ip_address=kwargs.get("ip_address"),
            user_agent=kwargs.get("user_agent"),
            severity=kwargs.get("severity", "ERROR"),
        )
        db.session.add(log)
        db.session.commit()
        return log
