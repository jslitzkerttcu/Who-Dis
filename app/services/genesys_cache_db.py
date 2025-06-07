import os
import requests
from requests.exceptions import Timeout
import logging
from typing import Dict, Optional
from datetime import datetime
from app.models import GenesysGroup, GenesysLocation, GenesysSkill, ApiToken
from app.database import db
from app.services.configuration_service import config_get

logger = logging.getLogger(__name__)


class GenesysCacheDB:
    """Database-backed Genesys cache service with automatic refresh."""

    def __init__(self):
        # Get credentials from config service (encrypted in database)
        self.client_id = config_get(
            "genesys", "client_id", os.getenv("GENESYS_CLIENT_ID")
        )
        self.client_secret = config_get(
            "genesys", "client_secret", os.getenv("GENESYS_CLIENT_SECRET")
        )
        # Region from config service
        self.region = config_get(
            "genesys", "region", os.getenv("GENESYS_REGION", "mypurecloud.com")
        )
        self.base_url = f"https://api.{self.region}"

        # Cache timeout for API calls
        self.cache_timeout = int(
            config_get(
                "genesys", "cache_timeout", os.getenv("GENESYS_CACHE_TIMEOUT", "30")
            )
        )

        # Get cache refresh period from config (default 6 hours)
        self.cache_refresh_period = int(
            config_get("genesys", "cache_refresh_period", 21600)  # 6 hours default
        )

        logger.info(
            f"Genesys cache initialized with {self.cache_refresh_period / 3600} hour refresh period"
        )

    def _get_access_token(self) -> Optional[str]:
        """Get access token from database (managed by GenesysService)."""
        try:
            token_record = ApiToken.get_token("genesys")
            if token_record:
                return str(token_record.access_token)
        except Exception as e:
            logger.error(f"Error getting token from database: {e}")

        logger.error("No valid Genesys token found in database")
        return None

    def needs_refresh(self) -> bool:
        """Check if cache needs refreshing based on configured period."""
        try:
            from flask import has_app_context

            # Check if we're in an application context
            if has_app_context():
                # Check when groups were last cached
                latest_group = GenesysGroup.query.order_by(
                    GenesysGroup.cached_at.desc()
                ).first()
                if not latest_group:
                    return True

                time_since_refresh = datetime.utcnow() - latest_group.cached_at
                return bool(
                    time_since_refresh.total_seconds() > self.cache_refresh_period
                )
        except Exception as e:
            if "application context" not in str(e):
                logger.error(f"Error checking cache refresh status: {e}")
        return False  # Don't refresh if we can't check

    def refresh_groups(self) -> bool:
        """Fetch all groups from Genesys Cloud and store in database."""
        token = self._get_access_token()
        if not token:
            logger.error("Failed to get token for groups cache")
            return False

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        try:
            logger.info("Fetching groups from Genesys Cloud...")

            # Fetch all groups (up to 500)
            response = requests.get(
                f"{self.base_url}/api/v2/groups",
                headers=headers,
                params={"pageSize": 500},
                timeout=self.cache_timeout,
            )

            if response.status_code != 200:
                logger.error(
                    f"Failed to fetch groups: {response.status_code} - {response.text}"
                )
                return False

            data = response.json()
            groups = data.get("entities", [])
            total_count = data.get("total", 0)

            # Clear old cache and insert new data
            GenesysGroup.query.delete()

            for group in groups:
                group_id = group.get("id")
                if group_id:
                    db_group = GenesysGroup(
                        id=group_id,
                        name=group.get("name", "Unknown"),
                        description=group.get("description"),
                        member_count=group.get("memberCount"),
                        date_modified=datetime.fromisoformat(
                            group["dateModified"].replace("Z", "+00:00")
                        )
                        if group.get("dateModified")
                        else None,
                        raw_data=group,
                    )
                    db.session.add(db_group)

            db.session.commit()
            logger.info(
                f"Successfully cached {len(groups)} groups (total in system: {total_count})"
            )
            return True

        except Timeout:
            logger.error(f"Timeout fetching groups after {self.cache_timeout} seconds")
            return False
        except Exception as e:
            logger.error(f"Error fetching groups for cache: {str(e)}")
            db.session.rollback()
            return False

    def refresh_locations(self) -> bool:
        """Fetch all locations from Genesys Cloud and store in database."""
        token = self._get_access_token()
        if not token:
            logger.error("Failed to get token for locations cache")
            return False

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        try:
            logger.info("Fetching locations from Genesys Cloud...")

            # Log the exact URL being called
            url = f"{self.base_url}/api/v2/locations"
            logger.info(f"Calling: {url} with pageSize=400")

            # Fetch all locations (up to 400 as per the requirement)
            response = requests.get(
                url,
                headers=headers,
                params={"pageSize": 400},
                timeout=self.cache_timeout,
            )

            if response.status_code != 200:
                logger.error(
                    f"Failed to fetch locations: {response.status_code} - {response.text}"
                )
                return False

            data = response.json()
            locations = data.get("entities", [])
            total_count = data.get("total", 0)

            logger.info(
                f"Received {len(locations)} locations from API (total: {total_count})"
            )

            # Clear old cache and insert new data
            GenesysLocation.query.delete()

            for location in locations:
                location_id = location.get("id")
                if location_id:
                    # Extract emergency number properly
                    emergency_number = None
                    emergency_obj = location.get("emergencyNumber")
                    if emergency_obj and isinstance(emergency_obj, dict):
                        # Prefer formatted number, fallback to e164
                        emergency_number = emergency_obj.get(
                            "number"
                        ) or emergency_obj.get("e164")

                    db_location = GenesysLocation(
                        id=location_id,
                        name=location.get("name", "Unknown"),
                        emergency_number=emergency_number,
                        address=location.get("address"),
                        raw_data=location,
                    )
                    db.session.add(db_location)

            db.session.commit()
            logger.info(
                f"Successfully cached {len(locations)} locations (total in system: {total_count})"
            )
            return True

        except Timeout:
            logger.error(
                f"Timeout fetching locations after {self.cache_timeout} seconds"
            )
            return False
        except Exception as e:
            logger.error(f"Error fetching locations for cache: {str(e)}")
            db.session.rollback()
            return False

    def refresh_skills(self) -> bool:
        """Fetch all skills from Genesys Cloud and store in database."""
        token = self._get_access_token()
        if not token:
            logger.error("Failed to get token for skills cache")
            return False

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        try:
            logger.info("Fetching skills from Genesys Cloud...")

            # Fetch all skills (up to 500)
            response = requests.get(
                f"{self.base_url}/api/v2/routing/skills",
                headers=headers,
                params={"pageSize": 500},
                timeout=self.cache_timeout,
            )

            if response.status_code != 200:
                logger.error(
                    f"Failed to fetch skills: {response.status_code} - {response.text}"
                )
                return False

            data = response.json()
            skills = data.get("entities", [])
            total_count = data.get("total", 0)

            # Clear old cache and insert new data
            GenesysSkill.query.delete()

            for skill in skills:
                skill_id = skill.get("id")
                if skill_id:
                    db_skill = GenesysSkill(
                        id=skill_id, name=skill.get("name", "Unknown"), raw_data=skill
                    )
                    db.session.add(db_skill)

            db.session.commit()
            logger.info(
                f"Successfully cached {len(skills)} skills (total in system: {total_count})"
            )
            return True

        except Timeout:
            logger.error(f"Timeout fetching skills after {self.cache_timeout} seconds")
            return False
        except Exception as e:
            logger.error(f"Error fetching skills for cache: {str(e)}")
            db.session.rollback()
            return False

    def refresh_all(self) -> Dict[str, bool]:
        """Refresh all cached data."""
        logger.info("Starting full Genesys cache refresh...")
        results = {
            "groups": self.refresh_groups(),
            "locations": self.refresh_locations(),
            "skills": self.refresh_skills(),
        }
        logger.info(f"Genesys cache refresh completed: {results}")
        return results

    def get_group_name(self, group_id: str) -> str:
        """Get group name from database cache."""
        try:
            from flask import has_app_context

            # Check if we're in an application context
            if has_app_context():
                group = GenesysGroup.query.get(group_id)
                return group.name if group else group_id
        except Exception as e:
            # If we're outside the app context or any other error, return the ID
            if "application context" not in str(e):
                logger.warning(f"Error getting group name for {group_id}: {e}")
        return group_id

    def get_location_name(self, location_id: str) -> str:
        """Get location name from database cache."""
        try:
            from flask import has_app_context

            # Check if we're in an application context
            if has_app_context():
                location = GenesysLocation.query.get(location_id)
                if location:
                    logger.debug(f"Found location {location_id}: {location.name}")
                    return location.name
                else:
                    logger.debug(f"Location {location_id} not found in cache")
                    return location_id
        except Exception as e:
            # If we're outside the app context or any other error, return the ID
            if "application context" not in str(e):
                logger.warning(f"Error getting location name for {location_id}: {e}")
        return location_id

    def get_skill_name(self, skill_id: str) -> str:
        """Get skill name from database cache."""
        try:
            from flask import has_app_context

            # Check if we're in an application context
            if has_app_context():
                skill = GenesysSkill.query.get(skill_id)
                return skill.name if skill else skill_id
        except Exception as e:
            # If we're outside the app context or any other error, return the ID
            if "application context" not in str(e):
                logger.warning(f"Error getting skill name for {skill_id}: {e}")
        return skill_id

    def get_cache_status(self) -> Dict:
        """Get cache status information."""
        try:
            from flask import has_app_context

            # Check if we're in an application context
            if has_app_context():
                # Get latest cache times
                latest_group = GenesysGroup.query.order_by(
                    GenesysGroup.cached_at.desc()
                ).first()
                latest_location = GenesysLocation.query.order_by(
                    GenesysLocation.cached_at.desc()
                ).first()
                latest_skill = GenesysSkill.query.order_by(
                    GenesysSkill.cached_at.desc()
                ).first()

                now = datetime.utcnow()

                return {
                    "groups_cached": GenesysGroup.query.count(),
                    "locations_cached": GenesysLocation.query.count(),
                    "skills_cached": GenesysSkill.query.count(),
                    "last_group_update": latest_group.cached_at.isoformat()
                    if latest_group
                    else None,
                    "last_location_update": latest_location.cached_at.isoformat()
                    if latest_location
                    else None,
                    "last_skill_update": latest_skill.cached_at.isoformat()
                    if latest_skill
                    else None,
                    "group_cache_age": str(now - latest_group.cached_at)
                    if latest_group
                    else None,
                    "location_cache_age": str(now - latest_location.cached_at)
                    if latest_location
                    else None,
                    "skill_cache_age": str(now - latest_skill.cached_at)
                    if latest_skill
                    else None,
                    "refresh_period_hours": self.cache_refresh_period / 3600,
                    "needs_refresh": self.needs_refresh(),
                }
        except Exception as e:
            # If we're outside the app context or any other error, return minimal info
            if "application context" not in str(e):
                logger.warning(f"Error getting cache status: {e}")
        return {
            "groups_cached": 0,
            "locations_cached": 0,
            "skills_cached": 0,
            "error": "Cache status unavailable outside application context",
            "refresh_period_hours": self.cache_refresh_period / 3600,
        }

    def clear(self):
        """Clear all cached data."""
        try:
            GenesysGroup.query.delete()
            GenesysLocation.query.delete()
            GenesysSkill.query.delete()
            db.session.commit()
            logger.info("Genesys cache cleared")
        except Exception as e:
            logger.error(f"Error clearing cache: {str(e)}")
            db.session.rollback()


# Global cache instance
genesys_cache_db = GenesysCacheDB()
