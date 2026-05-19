"""Service for managing external API tokens.

Provides CRUD operations for API token lifecycle: creation,
validation, revocation, and listing.
"""

import hashlib
import logging
from typing import List, Optional, Tuple

from app.models.external_api_token import ExternalApiToken

logger = logging.getLogger(__name__)


class ExternalApiTokenService:
    """Manages external API token lifecycle."""

    def create_token(
        self, name: str, created_by: str
    ) -> Tuple[ExternalApiToken, str]:
        """Create a new API token.

        Args:
            name: Human-readable token name.
            created_by: Email of the admin creating the token.

        Returns:
            Tuple of (token model, raw token string shown once).
        """
        token, raw = ExternalApiToken.create_token(name, created_by)
        logger.info(
            f"API token created: prefix={token.token_prefix}... "
            f"name='{name}' by={created_by}"
        )
        return token, raw

    def validate_token(self, raw_token: str) -> Optional[ExternalApiToken]:
        """Validate a raw token string.

        Args:
            raw_token: The bearer token from the Authorization header.

        Returns:
            The token model if valid and active, else None.
        """
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        return ExternalApiToken.find_by_hash(token_hash)

    def revoke_token(
        self, token_id: int, revoked_by: str
    ) -> Optional[ExternalApiToken]:
        """Revoke a token by ID.

        Args:
            token_id: Database ID of the token to revoke.
            revoked_by: Email of the admin revoking the token.

        Returns:
            The revoked token model, or None if not found.
        """
        token = ExternalApiToken.get_by_id(token_id)
        if token is None:
            logger.warning(f"Token revocation failed: id={token_id} not found")
            return None
        token.revoke(revoked_by)
        logger.info(
            f"API token revoked: prefix={token.token_prefix}... "
            f"id={token_id} by={revoked_by}"
        )
        return token  # type: ignore[no-any-return]

    def list_tokens(self) -> List[ExternalApiToken]:
        """List all tokens ordered by creation date (newest first).

        Returns both active and revoked tokens for the admin view.
        """
        return ExternalApiToken.query.order_by(  # type: ignore[no-any-return]
            ExternalApiToken.created_at.desc()
        ).all()

    def get_token_by_id(self, token_id: int) -> Optional[ExternalApiToken]:
        """Get a token by its database ID.

        Args:
            token_id: Database ID of the token.

        Returns:
            The token model, or None if not found.
        """
        return ExternalApiToken.get_by_id(token_id)  # type: ignore[no-any-return]
