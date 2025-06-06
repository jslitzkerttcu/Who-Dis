from app.database import db
from datetime import datetime, timedelta
from sqlalchemy.dialects.postgresql import JSONB


class ApiToken(db.Model):  # type: ignore[name-defined]
    """Store API tokens for various services with automatic refresh."""

    __tablename__ = "api_tokens"

    id = db.Column(db.Integer, primary_key=True)
    service_name = db.Column(db.String(50), unique=True, nullable=False, index=True)
    access_token = db.Column(db.Text, nullable=False)
    token_type = db.Column(db.String(20), default="Bearer")
    expires_at = db.Column(db.DateTime, nullable=False, index=True)
    refresh_token = db.Column(db.Text)  # Some services provide refresh tokens
    additional_data = db.Column(JSONB)  # Store any extra token data
    last_refreshed = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def __repr__(self):
        return f"<ApiToken {self.service_name}>"

    @property
    def is_expired(self):
        """Check if token is expired or will expire soon (5 minute buffer)."""
        return datetime.utcnow() >= (self.expires_at - timedelta(minutes=5))

    @property
    def time_until_expiry(self):
        """Get time remaining until token expires."""
        delta = self.expires_at - datetime.utcnow()
        return delta if delta.total_seconds() > 0 else timedelta(0)

    @classmethod
    def get_token(cls, service_name):
        """Get token for a service if it exists and is valid."""
        try:
            token = cls.query.filter_by(service_name=service_name).first()
            if token and not token.is_expired:
                return token
        except Exception as e:
            # Handle case where table doesn't exist
            db.session.rollback()
            raise e
        return None

    @classmethod
    def upsert_token(
        cls,
        service_name,
        access_token,
        expires_in_seconds,
        token_type="Bearer",
        refresh_token=None,
        additional_data=None,
    ):
        """Create or update a token for a service."""
        expires_at = datetime.utcnow() + timedelta(seconds=expires_in_seconds)

        token = cls.query.filter_by(service_name=service_name).first()
        if token:
            token.access_token = access_token
            token.expires_at = expires_at
            token.token_type = token_type
            token.refresh_token = refresh_token
            token.additional_data = additional_data
            token.last_refreshed = datetime.utcnow()
            token.updated_at = datetime.utcnow()
        else:
            token = cls(
                service_name=service_name,
                access_token=access_token,
                expires_at=expires_at,
                token_type=token_type,
                refresh_token=refresh_token,
                additional_data=additional_data,
            )
            db.session.add(token)

        try:
            db.session.commit()
            return token
        except Exception as e:
            db.session.rollback()
            raise e

    @classmethod
    def get_all_tokens_status(cls):
        """Get status of all stored tokens."""
        tokens = cls.query.all()
        status = []
        for token in tokens:
            status.append(
                {
                    "service": token.service_name,
                    "expires_at": token.expires_at.isoformat(),
                    "is_expired": token.is_expired,
                    "time_until_expiry": str(token.time_until_expiry),
                    "last_refreshed": token.last_refreshed.isoformat(),
                }
            )
        return status
