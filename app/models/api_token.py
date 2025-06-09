from app.database import db
from datetime import datetime, timezone, timedelta
from .base import CacheableModel, JSONDataMixin


class ApiToken(CacheableModel, JSONDataMixin):
    """Store API tokens for various services with automatic refresh."""

    __tablename__ = "api_tokens"

    # CacheableModel provides: id, created_at, updated_at, expires_at, is_expired(),
    # cleanup_expired(), extend_expiration()
    # JSONDataMixin provides: additional_data, get_data(), set_data(), update_data()

    service_name = db.Column(db.String(50), unique=True, nullable=False, index=True)
    access_token = db.Column(db.Text, nullable=False)
    token_type = db.Column(db.String(20), default="Bearer")
    refresh_token = db.Column(db.Text)  # Some services provide refresh tokens
    last_refreshed = db.Column(
        db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    def __repr__(self):
        return f"<ApiToken {self.service_name}>"

    @property
    def time_until_expiry(self):
        """Get time remaining until token expires."""
        now = datetime.now(timezone.utc)
        expires_at = self.expires_at

        # Handle timezone-naive vs timezone-aware comparison
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        elif now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)

        delta = expires_at - now
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
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in_seconds)

        token = cls.query.filter_by(service_name=service_name).first()
        if token:
            # Use base class update method
            token.update(
                access_token=access_token,
                expires_at=expires_at,
                token_type=token_type,
                refresh_token=refresh_token,
                last_refreshed=datetime.now(timezone.utc),
            )
            # Use JSONDataMixin method for additional_data
            if additional_data:
                token.update_data(additional_data)
        else:
            token = cls(
                service_name=service_name,
                access_token=access_token,
                expires_at=expires_at,
                token_type=token_type,
                refresh_token=refresh_token,
                additional_data=additional_data,
            )
            token.save()

        return token

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
