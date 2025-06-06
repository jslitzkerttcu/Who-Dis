from datetime import datetime
from app.database import db
from sqlalchemy.dialects.postgresql import JSONB


class SearchCache(db.Model):  # type: ignore
    """Cache for search results"""

    __tablename__ = "search_cache"

    id = db.Column(db.Integer, primary_key=True)
    search_query = db.Column(db.String(500), nullable=False, index=True)
    search_type = db.Column(db.String(50), nullable=False, index=True)
    result_data = db.Column(JSONB, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)

    def __repr__(self):
        return f"<SearchCache {self.search_query} ({self.search_type})>"

    def is_expired(self):
        """Check if cache entry is expired"""
        return datetime.utcnow() > self.expires_at

    @classmethod
    def cleanup_expired(cls):
        """Remove expired cache entries"""
        cls.query.filter(cls.expires_at < datetime.utcnow()).delete()
        db.session.commit()
