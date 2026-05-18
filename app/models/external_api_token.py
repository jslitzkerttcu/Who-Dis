"""ExternalApiToken model for REST API bearer token authentication.

Stores hashed API tokens with usage tracking and revocation support.
Raw tokens are never persisted — only SHA-256 hashes.
"""

import hashlib
import secrets
from datetime import datetime, timezone
from typing import Optional, Tuple

from app.database import db
from app.models.base import BaseModel, TimestampMixin


class ExternalApiToken(BaseModel, TimestampMixin):
    """API token for external REST API access."""

    __tablename__ = "external_api_tokens"

    name = db.Column(db.String(100), nullable=False)
    token_hash = db.Column(db.String(64), unique=True, nullable=False, index=True)
    token_prefix = db.Column(db.String(8), nullable=False)
    created_by = db.Column(db.String(255), nullable=False)

    is_revoked = db.Column(db.Boolean, default=False, nullable=False, index=True)
    revoked_at = db.Column(db.DateTime(timezone=True), nullable=True)
    revoked_by = db.Column(db.String(255), nullable=True)

    last_used_at = db.Column(db.DateTime(timezone=True), nullable=True)
    usage_count = db.Column(db.Integer, default=0, nullable=False)

    @classmethod
    def create_token(
        cls, name: str, created_by: str
    ) -> Tuple["ExternalApiToken", str]:
        """Create a new API token.

        Args:
            name: Human-readable token name.
            created_by: Email of the admin who created the token.

        Returns:
            Tuple of (token model instance, raw token string).
            The raw token is only available at creation time.
        """
        raw_token = secrets.token_hex(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        token_prefix = raw_token[:8]

        token = cls(
            name=name,
            token_hash=token_hash,
            token_prefix=token_prefix,
            created_by=created_by,
        )
        token.save()
        return token, raw_token

    def revoke(self, revoked_by: str) -> None:
        """Revoke this token.

        Args:
            revoked_by: Email of the admin who revoked the token.
        """
        self.is_revoked = True
        self.revoked_at = datetime.now(timezone.utc)
        self.revoked_by = revoked_by
        self.save()

    def record_usage(self) -> None:
        """Record a usage event for this token."""
        db.session.execute(
            db.update(ExternalApiToken)
            .where(ExternalApiToken.id == self.id)
            .values(
                usage_count=ExternalApiToken.usage_count + 1,
                last_used_at=datetime.now(timezone.utc),
            )
        )
        db.session.commit()

    @classmethod
    def find_by_hash(cls, token_hash: str) -> Optional["ExternalApiToken"]:
        """Find an active (non-revoked) token by its hash.

        Args:
            token_hash: SHA-256 hex digest of the raw token.

        Returns:
            The token if found and not revoked, else None.
        """
        return cls.query.filter_by(
            token_hash=token_hash, is_revoked=False
        ).first()

    def __repr__(self) -> str:
        status = "revoked" if self.is_revoked else "active"
        return f"<ExternalApiToken {self.token_prefix}... ({status})>"
