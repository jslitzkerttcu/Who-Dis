from datetime import datetime
from app.database import db
from sqlalchemy.dialects.postgresql import JSONB


class GenesysGroup(db.Model):  # type: ignore
    """Cached Genesys groups"""

    __tablename__ = "genesys_groups"

    id = db.Column(db.String(100), primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    member_count = db.Column(db.Integer)
    date_modified = db.Column(db.DateTime)
    cached_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    raw_data = db.Column(JSONB)

    def __repr__(self):
        return f"<GenesysGroup {self.name}>"

    def to_dict(self):
        """Convert to dictionary"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "memberCount": self.member_count,
            "dateModified": self.date_modified.isoformat()
            if self.date_modified
            else None,
        }


class GenesysLocation(db.Model):  # type: ignore
    """Cached Genesys locations"""

    __tablename__ = "genesys_locations"

    id = db.Column(db.String(100), primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    emergency_number = db.Column(db.String(50))
    address = db.Column(JSONB)
    cached_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    raw_data = db.Column(JSONB)

    def __repr__(self):
        return f"<GenesysLocation {self.name}>"

    def to_dict(self):
        """Convert to dictionary"""
        return {
            "id": self.id,
            "name": self.name,
            "emergencyNumber": self.emergency_number,
            "address": self.address,
        }


class GenesysSkill(db.Model):  # type: ignore
    """Cached Genesys skills"""

    __tablename__ = "genesys_skills"

    id = db.Column(db.String(100), primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    cached_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    raw_data = db.Column(JSONB)

    def __repr__(self):
        return f"<GenesysSkill {self.name}>"

    def to_dict(self):
        """Convert to dictionary"""
        return {"id": self.id, "name": self.name}
