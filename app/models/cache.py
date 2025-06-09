from app.database import db
from sqlalchemy.dialects.postgresql import JSONB
from .base import CacheableModel, JSONDataMixin


class SearchCache(CacheableModel, JSONDataMixin):
    """Cache for search results"""

    __tablename__ = "search_cache"

    # CacheableModel provides: id, created_at, updated_at, expires_at, is_expired(),
    # cleanup_expired(), extend_expiration(), get_valid_cache()
    # JSONDataMixin provides: additional_data, get_data(), set_data(), update_data()

    search_query = db.Column(db.String(500), nullable=False, index=True)
    search_type = db.Column(db.String(50), nullable=False, index=True)
    result_data = db.Column(JSONB, nullable=False)

    def __repr__(self):
        return f"<SearchCache {self.search_query} ({self.search_type})>"
