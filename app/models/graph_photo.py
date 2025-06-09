from datetime import datetime, timezone, timedelta
from app.database import db
from typing import Optional
import logging
from .base import CacheableModel

logger = logging.getLogger(__name__)


class GraphPhoto(CacheableModel):
    __tablename__ = "graph_photos"

    # CacheableModel provides: id, created_at, updated_at, expires_at, is_expired(),
    # cleanup_expired(), extend_expiration()

    # Override id to use user_id as primary key
    id = None  # Remove base class id
    user_id = db.Column(db.String(255), primary_key=True, nullable=False)
    user_principal_name = db.Column(db.String(255), nullable=True, index=True)
    photo_data = db.Column(db.LargeBinary, nullable=False)  # Base64 encoded image data
    content_type = db.Column(db.String(50), default="image/jpeg", nullable=False)

    # Keep fetched_at for backward compatibility, map to created_at
    fetched_at = db.synonym("created_at")

    @classmethod
    def get_photo(
        cls, db_session, user_id: str, user_principal_name: Optional[str] = None
    ) -> Optional["GraphPhoto"]:
        """Get cached photo by user ID or UPN."""
        photo = cls.query.filter_by(user_id=user_id).first()
        if not photo and user_principal_name:
            photo = cls.query.filter_by(user_principal_name=user_principal_name).first()
        return photo

    @classmethod
    def upsert_photo(
        cls,
        db_session,
        user_id: str,
        photo_data: bytes,
        user_principal_name: Optional[str] = None,
        content_type: str = "image/jpeg",
    ) -> "GraphPhoto":
        """Insert or update a photo."""
        photo = cls.get_photo(db_session, user_id, user_principal_name)

        if photo:
            # Use base class update method
            photo.update(
                photo_data=photo_data,
                content_type=content_type,
                user_principal_name=user_principal_name,
            )
            logger.info(f"Updated cached photo for user {user_id}")
        else:
            # Set expires_at to 30 days from now
            expires_at = datetime.now(timezone.utc) + timedelta(days=30)
            photo = cls(
                user_id=user_id,
                user_principal_name=user_principal_name,
                photo_data=photo_data,
                content_type=content_type,
                expires_at=expires_at,
            )
            photo.save()
            logger.info(f"Created new cached photo for user {user_id}")

        return photo

    @classmethod
    def is_stale(cls, photo: "GraphPhoto", hours: int = 24) -> bool:
        """Check if a photo is older than the specified hours."""
        if not photo:
            return True
        # Handle timezone-aware datetime
        now = datetime.now(timezone.utc)
        updated_at = photo.updated_at

        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)
        elif now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)

        age = now - updated_at
        return age.total_seconds() > (hours * 3600)

    @classmethod
    def cleanup_old_photos(cls, db_session=None, days: int = 30) -> int:
        """Remove photos older than specified days."""
        # Use base class cleanup_expired method
        count = cls.cleanup_expired()
        logger.info(f"Cleaned up {count} old cached photos")
        return count
