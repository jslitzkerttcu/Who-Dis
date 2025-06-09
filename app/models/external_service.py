"""
Consolidated external service data models.

This replaces the separate Genesys models (GenesysGroup, GenesysLocation, GenesysSkill)
with a single, flexible model for all external service data.
"""

from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from app.database import db
from app.models.base import ServiceDataModel


class ExternalServiceData(ServiceDataModel):
    """Unified model for external service data (Genesys, Graph, etc.)."""

    __tablename__ = "external_service_data"

    # Data type (group, skill, location, user, etc.)
    data_type = db.Column(db.String(50), nullable=False, index=True)

    # Human-readable name/title
    name = db.Column(db.String(255), index=True)

    # Description from the service
    description = db.Column(db.Text)

    # Unique constraint on service_name + data_type + service_id
    __table_args__ = (
        db.UniqueConstraint(
            "service_name", "data_type", "service_id", name="uq_service_type_id"
        ),
    )

    @classmethod
    def get_service_data(
        cls,
        service_name: str,
        data_type: str,
        service_id: str = None,
        active_only: bool = True,
    ) -> List["ExternalServiceData"]:
        """Get data from specific service."""
        query = cls.query.filter_by(service_name=service_name, data_type=data_type)

        if service_id:
            query = query.filter_by(service_id=service_id)

        if active_only:
            query = query.filter_by(is_active=True)

        return query.all()

    @classmethod
    def get_by_service_id(
        cls, service_name: str, data_type: str, service_id: str
    ) -> Optional["ExternalServiceData"]:
        """Get specific data by service ID."""
        return cls.query.filter_by(
            service_name=service_name, data_type=data_type, service_id=service_id
        ).first()

    @classmethod
    def update_service_data(
        cls,
        service_name: str,
        data_type: str,
        service_id: str,
        name: str,
        raw_data: Dict[str, Any],
        description: str = None,
    ) -> "ExternalServiceData":
        """Update or create service data."""
        entry = cls.query.filter_by(
            service_name=service_name, data_type=data_type, service_id=service_id
        ).first()

        if entry:
            entry.name = name
            entry.description = description
            entry.raw_data = raw_data
            entry.updated_at = datetime.now(timezone.utc)

            # Update active status from raw data
            if "active" in raw_data:
                entry.is_active = bool(raw_data.get("active", True))
            elif "enabled" in raw_data:
                entry.is_active = bool(raw_data.get("enabled", True))

        else:
            entry = cls(
                service_name=service_name,
                data_type=data_type,
                service_id=service_id,
                name=name,
                description=description,
                raw_data=raw_data,
                is_active=bool(raw_data.get("active", raw_data.get("enabled", True))),
            )

        return entry.save()

    @classmethod
    def bulk_sync_service_data(
        cls, service_name: str, data_type: str, service_data: List[Dict[str, Any]]
    ) -> Dict[str, int]:
        """Sync multiple records from service data."""
        updated_count = 0
        created_count = 0

        # Get existing records for this service/type
        existing_ids = set()
        for entry in cls.query.filter_by(
            service_name=service_name, data_type=data_type
        ).all():
            existing_ids.add(entry.service_id)

        # Process new/updated data
        processed_ids = set()
        for item in service_data:
            service_id = item.get("id")
            if not service_id:
                continue

            processed_ids.add(service_id)
            name = item.get("name", item.get("displayName", service_id))
            description = item.get("description", item.get("desc"))

            entry, created = cls.get_or_create(
                service_name=service_name, data_type=data_type, service_id=service_id
            )

            entry.name = name
            entry.description = description
            entry.update_from_service(item)

            if created:
                created_count += 1
            else:
                updated_count += 1

        # Mark missing entries as inactive
        missing_ids = existing_ids - processed_ids
        deactivated_count = 0
        if missing_ids:
            deactivated_count = cls.query.filter(
                cls.service_name == service_name,
                cls.data_type == data_type,
                cls.service_id.in_(missing_ids),
            ).update({cls.is_active: False})
            db.session.commit()

        return {
            "created": created_count,
            "updated": updated_count,
            "deactivated": deactivated_count,
        }

    @classmethod
    def get_genesys_groups(cls) -> List["ExternalServiceData"]:
        """Get Genesys groups (backward compatibility)."""
        return cls.get_service_data("genesys", "group")

    @classmethod
    def get_genesys_skills(cls) -> List["ExternalServiceData"]:
        """Get Genesys skills (backward compatibility)."""
        return cls.get_service_data("genesys", "skill")

    @classmethod
    def get_genesys_locations(cls) -> List["ExternalServiceData"]:
        """Get Genesys locations (backward compatibility)."""
        return cls.get_service_data("genesys", "location")

    @classmethod
    def get_name_by_id(
        cls, service_name: str, data_type: str, service_id: str
    ) -> Optional[str]:
        """Get name by service ID (for cache lookups)."""
        entry = cls.get_by_service_id(service_name, data_type, service_id)
        return entry.name if entry else None

    @classmethod
    def get_genesys_group_name(cls, group_id: str) -> Optional[str]:
        """Get Genesys group name by ID (backward compatibility)."""
        return cls.get_name_by_id("genesys", "group", group_id)

    @classmethod
    def get_genesys_skill_name(cls, skill_id: str) -> Optional[str]:
        """Get Genesys skill name by ID (backward compatibility)."""
        return cls.get_name_by_id("genesys", "skill", skill_id)

    @classmethod
    def get_genesys_location_info(cls, location_id: str) -> Optional[Dict[str, Any]]:
        """Get Genesys location info by ID (backward compatibility)."""
        entry = cls.get_by_service_id("genesys", "location", location_id)
        if entry:
            return {
                "id": entry.service_id,
                "name": entry.name,
                "description": entry.description,
                "raw_data": entry.raw_data,
            }
        return None

    @classmethod
    def refresh_genesys_cache(
        cls,
        groups_data: List[Dict] = None,
        skills_data: List[Dict] = None,
        locations_data: List[Dict] = None,
    ) -> Dict[str, Dict[str, int]]:
        """Refresh Genesys cache data (backward compatibility)."""
        results = {}

        if groups_data:
            results["groups"] = cls.bulk_sync_service_data(
                "genesys", "group", groups_data
            )

        if skills_data:
            results["skills"] = cls.bulk_sync_service_data(
                "genesys", "skill", skills_data
            )

        if locations_data:
            results["locations"] = cls.bulk_sync_service_data(
                "genesys", "location", locations_data
            )

        return results

    @classmethod
    def needs_refresh(cls, service_name: str = "genesys", hours: int = 6) -> bool:
        """Check if service data needs refresh."""
        from datetime import timedelta

        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)

        # Check if we have any recent data
        recent_data = cls.query.filter(
            cls.service_name == service_name, cls.updated_at > cutoff_time
        ).first()

        return recent_data is None

    @classmethod
    def get_service_statistics(cls) -> Dict[str, Any]:
        """Get statistics about external service data."""
        # Get counts by service and type
        service_stats: Dict[str, Dict[str, Dict[str, int]]] = {}

        results = (
            db.session.query(
                cls.service_name,
                cls.data_type,
                db.func.count(cls.id).label("count"),
                db.func.sum(db.case([(cls.is_active, 1)], else_=0)).label(
                    "active_count"
                ),
            )
            .group_by(cls.service_name, cls.data_type)
            .all()
        )

        for service_name, data_type, total_count, active_count in results:
            if service_name not in service_stats:
                service_stats[service_name] = {}

            service_stats[service_name][data_type] = {
                "total": total_count,
                "active": active_count,
                "inactive": total_count - active_count,
            }

        # Get overall statistics
        total_records = cls.query.count()
        active_records = cls.query.filter_by(is_active=True).count()

        return {
            "by_service": service_stats,
            "overall": {
                "total": total_records,
                "active": active_records,
                "inactive": total_records - active_records,
            },
        }

    def to_dict(self, exclude: Optional[List[str]] = None) -> Dict[str, Any]:
        """Convert to dictionary with service-specific formatting."""
        result = super().to_dict(exclude=exclude)

        # Add computed fields for backward compatibility
        result["display_name"] = self.name
        result["service_display_name"] = (
            f"{self.service_name.title()} {self.data_type.title()}"
        )

        return result


# Backward compatibility classes for existing code
class GenesysGroup(ExternalServiceData):
    """Backward compatibility class for Genesys groups."""

    def __new__(cls, *args, **kwargs):
        # Redirect to ExternalServiceData with appropriate defaults
        kwargs["service_name"] = "genesys"
        kwargs["data_type"] = "group"
        return ExternalServiceData(*args, **kwargs)

    @classmethod
    def query(cls):
        return ExternalServiceData.query.filter_by(
            service_name="genesys", data_type="group"
        )


class GenesysSkill(ExternalServiceData):
    """Backward compatibility class for Genesys skills."""

    def __new__(cls, *args, **kwargs):
        kwargs["service_name"] = "genesys"
        kwargs["data_type"] = "skill"
        return ExternalServiceData(*args, **kwargs)

    @classmethod
    def query(cls):
        return ExternalServiceData.query.filter_by(
            service_name="genesys", data_type="skill"
        )


class GenesysLocation(ExternalServiceData):
    """Backward compatibility class for Genesys locations."""

    def __new__(cls, *args, **kwargs):
        kwargs["service_name"] = "genesys"
        kwargs["data_type"] = "location"
        return ExternalServiceData(*args, **kwargs)

    @classmethod
    def query(cls):
        return ExternalServiceData.query.filter_by(
            service_name="genesys", data_type="location"
        )


# Migration utilities
class ServiceDataMigrationUtils:
    """Utilities for migrating existing service data."""

    @staticmethod
    def migrate_genesys_data():
        """Migrate existing Genesys models to unified service data."""
        migrated_counts = {"groups": 0, "skills": 0, "locations": 0}

        try:
            # Import original models
            from app.models.genesys import GenesysGroup as OriginalGroup
            from app.models.genesys import GenesysSkill as OriginalSkill
            from app.models.genesys import GenesysLocation as OriginalLocation

            # Migrate groups
            for group in OriginalGroup.query.all():
                ExternalServiceData.update_service_data(
                    service_name="genesys",
                    data_type="group",
                    service_id=group.group_id,
                    name=group.name,
                    raw_data=group.raw_data or {},
                    description=group.raw_data.get("description")
                    if group.raw_data
                    else None,
                )
                migrated_counts["groups"] += 1

            # Migrate skills
            for skill in OriginalSkill.query.all():
                ExternalServiceData.update_service_data(
                    service_name="genesys",
                    data_type="skill",
                    service_id=skill.skill_id,
                    name=skill.name,
                    raw_data=skill.raw_data or {},
                    description=skill.raw_data.get("description")
                    if skill.raw_data
                    else None,
                )
                migrated_counts["skills"] += 1

            # Migrate locations
            for location in OriginalLocation.query.all():
                ExternalServiceData.update_service_data(
                    service_name="genesys",
                    data_type="location",
                    service_id=location.location_id,
                    name=location.name,
                    raw_data=location.raw_data or {},
                    description=location.raw_data.get("description")
                    if location.raw_data
                    else None,
                )
                migrated_counts["locations"] += 1

        except ImportError:
            pass  # Original models don't exist yet

        return migrated_counts
