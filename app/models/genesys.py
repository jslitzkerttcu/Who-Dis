from typing import Optional, List, Dict, Any
from app.database import db
from sqlalchemy.dialects.postgresql import JSONB
from .base import ServiceDataModel


class GenesysGroup(ServiceDataModel):
    """Cached Genesys groups"""

    __tablename__ = "genesys_groups"

    # ServiceDataModel provides: id, created_at, updated_at, service_id, service_name,
    # raw_data, is_active, additional_data, update_from_service(), sync_from_service_data()

    # Override id to use string type for Genesys IDs
    id = db.Column(db.String(100), primary_key=True)

    # Group-specific fields
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    member_count = db.Column(db.Integer)
    date_modified = db.Column(db.DateTime(timezone=True))

    # Keep cached_at for backward compatibility, map to updated_at
    cached_at = db.synonym("updated_at")

    def __repr__(self):
        return f"<GenesysGroup {self.name}>"

    def to_dict(self, exclude: Optional[List[str]] = None) -> Dict[str, Any]:
        """Convert to dictionary"""
        # Use base class to_dict and add custom formatting
        data = super().to_dict(exclude)

        # Add custom field mappings for Genesys API compatibility
        return {
            "id": data.get("id") or data.get("service_id"),
            "name": data.get("name"),
            "description": data.get("description"),
            "memberCount": data.get("member_count"),
            "dateModified": data.get("date_modified"),
        }


class GenesysLocation(ServiceDataModel):
    """Cached Genesys locations"""

    __tablename__ = "genesys_locations"

    # Override id to use string type for Genesys IDs
    id = db.Column(db.String(100), primary_key=True)

    # Location-specific fields
    name = db.Column(db.String(255), nullable=False)
    emergency_number = db.Column(db.String(50))
    address = db.Column(JSONB)

    # Keep cached_at for backward compatibility
    cached_at = db.synonym("updated_at")

    def __repr__(self):
        return f"<GenesysLocation {self.name}>"

    def to_dict(self, exclude: Optional[List[str]] = None) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = super().to_dict(exclude)
        return {
            "id": data.get("id") or data.get("service_id"),
            "name": data.get("name"),
            "emergencyNumber": data.get("emergency_number"),
            "address": data.get("address"),
        }


class GenesysSkill(ServiceDataModel):
    """Cached Genesys skills"""

    __tablename__ = "genesys_skills"

    # Override id to use string type for Genesys IDs
    id = db.Column(db.String(100), primary_key=True)

    # Skill-specific fields
    name = db.Column(db.String(255), nullable=False)

    # Keep cached_at for backward compatibility
    cached_at = db.synonym("updated_at")

    def __repr__(self):
        return f"<GenesysSkill {self.name}>"

    def to_dict(self, exclude: Optional[List[str]] = None) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = super().to_dict(exclude)
        return {
            "id": data.get("id") or data.get("service_id"),
            "name": data.get("name"),
        }
