from datetime import datetime, timezone, timedelta
from sqlalchemy import Column, String, LargeBinary, DateTime, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session
from typing import Optional, TYPE_CHECKING
import logging

if TYPE_CHECKING:
    from sqlalchemy.ext.declarative import DeclarativeMeta

Base: "DeclarativeMeta" = declarative_base()
logger = logging.getLogger(__name__)


class GraphPhoto(Base):  # type: ignore[valid-type,misc]
    __tablename__ = "graph_photos"

    user_id = Column(String(255), primary_key=True, nullable=False)
    user_principal_name = Column(String(255), nullable=True)
    photo_data = Column(LargeBinary, nullable=False)  # Base64 encoded image data
    content_type = Column(String(50), default="image/jpeg", nullable=False)
    fetched_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        Index("idx_graph_photos_upn", "user_principal_name"),
        Index("idx_graph_photos_updated", "updated_at"),
    )

    @classmethod
    def get_photo(
        cls, db: Session, user_id: str, user_principal_name: Optional[str] = None
    ) -> Optional["GraphPhoto"]:
        """Get cached photo by user ID or UPN."""
        photo = db.query(cls).filter_by(user_id=user_id).first()
        if not photo and user_principal_name:
            photo = (
                db.query(cls).filter_by(user_principal_name=user_principal_name).first()
            )
        return photo

    @classmethod
    def upsert_photo(
        cls,
        db: Session,
        user_id: str,
        photo_data: bytes,
        user_principal_name: Optional[str] = None,
        content_type: str = "image/jpeg",
    ) -> "GraphPhoto":
        """Insert or update a photo."""
        photo = cls.get_photo(db, user_id, user_principal_name)

        if photo:
            photo.photo_data = photo_data  # type: ignore[assignment]
            photo.content_type = content_type  # type: ignore[assignment]
            photo.updated_at = datetime.now(timezone.utc)  # type: ignore[assignment]
            if user_principal_name:
                photo.user_principal_name = user_principal_name  # type: ignore[assignment]
            logger.info(f"Updated cached photo for user {user_id}")
        else:
            photo = cls(
                user_id=user_id,
                user_principal_name=user_principal_name,
                photo_data=photo_data,
                content_type=content_type,
            )
            db.add(photo)
            logger.info(f"Created new cached photo for user {user_id}")

        db.commit()
        return photo

    @classmethod
    def is_stale(cls, photo: "GraphPhoto", hours: int = 24) -> bool:
        """Check if a photo is older than the specified hours."""
        if not photo:
            return True
        age = datetime.now(timezone.utc) - photo.updated_at
        return age.total_seconds() > (hours * 3600)

    @classmethod
    def cleanup_old_photos(cls, db: Session, days: int = 30) -> int:
        """Remove photos older than specified days."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        count = db.query(cls).filter(cls.updated_at < cutoff).delete()
        db.commit()
        logger.info(f"Cleaned up {count} old cached photos")
        return count
