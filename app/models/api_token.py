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

    def is_expired(self) -> bool:
        """
        Override base class is_expired to provide more robust timezone handling.

        Returns:
            True if token has expired, False otherwise
        """
        import pytz

        now = datetime.now(timezone.utc)
        expires_at = self.expires_at

        # Handle timezone-naive datetime which might be in local server time
        if expires_at.tzinfo is None:
            # Microsoft Graph API tokens might be stored in local server time
            # Try treating as Central Daylight Time (CDT) since server is in CDT
            try:
                cdt = pytz.timezone("US/Central")
                # Assume it's CDT and convert to UTC
                expires_at_cdt = cdt.localize(expires_at, is_dst=True).astimezone(
                    timezone.utc
                )

                # If treating as CDT makes it a future time, use that interpretation
                if expires_at_cdt > now:
                    expires_at = expires_at_cdt
                else:
                    # Otherwise treat as UTC (fallback)
                    expires_at = expires_at.replace(tzinfo=timezone.utc)

            except Exception:
                # Fallback: treat as UTC
                expires_at = expires_at.replace(tzinfo=timezone.utc)
        else:
            # Convert to UTC if it's in a different timezone
            expires_at = expires_at.astimezone(timezone.utc)

        # Add a small buffer (30 seconds) to account for clock skew and processing time
        buffer = timedelta(seconds=30)
        return now > (expires_at - buffer)

    @property
    def time_until_expiry(self):
        """Get time remaining until token expires."""
        import pytz

        now = datetime.now(timezone.utc)
        expires_at = self.expires_at

        # Handle timezone-naive datetime which might be in local server time
        # Use the same logic as is_expired method for consistency
        if expires_at.tzinfo is None:
            # Microsoft Graph API tokens might be stored in local server time
            # Try treating as Central Daylight Time (CDT) since server is in CDT
            try:
                cdt = pytz.timezone("US/Central")
                # Assume it's CDT and convert to UTC
                expires_at_cdt = cdt.localize(expires_at, is_dst=True).astimezone(
                    timezone.utc
                )

                # If treating as CDT makes it a future time, use that interpretation
                if expires_at_cdt > now:
                    expires_at = expires_at_cdt
                else:
                    # Otherwise treat as UTC (fallback)
                    expires_at = expires_at.replace(tzinfo=timezone.utc)

            except Exception:
                # Fallback: treat as UTC
                expires_at = expires_at.replace(tzinfo=timezone.utc)
        else:
            # Convert to UTC if it's in a different timezone
            expires_at = expires_at.astimezone(timezone.utc)

        delta = expires_at - now
        return delta if delta.total_seconds() > 0 else timedelta(0)

    @classmethod
    def get_token(cls, service_name):
        """Get token for a service if it exists and is valid."""
        import logging

        logger = logging.getLogger(__name__)

        try:
            token = cls.query.filter_by(service_name=service_name).first()
            if token:
                logger.debug(
                    f"Found token for {service_name}, expires_at: {token.expires_at}, is_expired: {token.is_expired}"
                )
                if not token.is_expired:
                    logger.debug(f"Returning valid token for {service_name}")
                    return token
                else:
                    logger.debug(
                        f"Token for {service_name} is expired, time_until_expiry: {token.time_until_expiry}"
                    )
            else:
                logger.debug(f"No token found for {service_name}")
        except Exception as e:
            logger.error(f"Error retrieving token for {service_name}: {e}")
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
        """Get status of all stored tokens with detailed debugging information."""
        tokens = cls.query.all()
        status = []
        now = datetime.now(timezone.utc)

        for token in tokens:
            # Calculate time differences for debugging
            expires_at = token.expires_at
            if expires_at.tzinfo is None:
                expires_at_utc = expires_at.replace(tzinfo=timezone.utc)
            else:
                expires_at_utc = expires_at.astimezone(timezone.utc)

            time_diff = expires_at_utc - now

            status.append(
                {
                    "service": token.service_name,
                    "expires_at": token.expires_at.isoformat(),
                    "expires_at_utc": expires_at_utc.isoformat(),
                    "current_time_utc": now.isoformat(),
                    "is_expired": token.is_expired(),
                    "time_until_expiry": str(token.time_until_expiry),
                    "time_diff_seconds": time_diff.total_seconds(),
                    "last_refreshed": token.last_refreshed.isoformat()
                    if token.last_refreshed
                    else None,
                    "timezone_info": str(token.expires_at.tzinfo)
                    if token.expires_at.tzinfo
                    else "naive",
                }
            )
        return status
