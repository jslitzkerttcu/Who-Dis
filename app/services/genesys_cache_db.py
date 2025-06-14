"""Genesys cache service with simplified configuration."""

import requests
import logging
from typing import Dict, Optional, Any
from datetime import datetime
from app.database import db
from app.services.base import BaseCacheService
from app.models.api_token import ApiToken
from app.models.external_service import ExternalServiceData

logger = logging.getLogger(__name__)


class GenesysCacheDB(BaseCacheService):
    """Database-backed Genesys cache service with automatic refresh."""

    def __init__(self):
        super().__init__(config_prefix="genesys")

    @property
    def client_id(self):
        return self._get_config("client_id")

    @property
    def client_secret(self):
        return self._get_config("client_secret")

    @property
    def region(self):
        return self._get_config("region", "mypurecloud.com")

    @property
    def base_url(self):
        return f"https://api.{self.region}"

    @property
    def cache_timeout(self):
        return int(self._get_config("cache_timeout", "30"))

    @property
    def cache_refresh_period(self):
        return int(self._get_config("cache_refresh_period", "21600"))  # 6 hours

    def _get_access_token(self) -> Optional[str]:
        """
        Legacy database token lookup (fallback only).

        Note: This method is only used as a final fallback. The preferred approach
        is to pass the GenesysService instance directly to refresh_all_caches().
        """
        try:
            token_record = ApiToken.get_token("genesys")
            if token_record:
                # Check if token is expired
                if token_record.is_expired():
                    logger.debug("Genesys token is expired")
                    return None

                # Get the access token
                if hasattr(token_record, "access_token") and token_record.access_token:
                    logger.debug("Retrieved Genesys token from database (legacy path)")
                    return str(token_record.access_token)
                else:
                    logger.error("Genesys token record exists but has no access_token")
            else:
                logger.debug("No Genesys token found in database")
        except Exception as e:
            logger.error(f"Error getting Genesys token from database: {e}")
        return None

    def needs_refresh(self, last_update: Optional[datetime] = None) -> bool:
        """Check if cache needs refresh based on last update time."""
        try:
            if last_update is None:
                # Check external service data table for last update
                from sqlalchemy import text
                from datetime import timezone

                result = db.session.execute(
                    text(
                        "SELECT MAX(updated_at) FROM external_service_data WHERE service_name = 'genesys' AND data_type = 'group'"
                    )
                ).scalar()

                if not result:
                    return True  # No data, needs refresh

                last_update = result

            # Ensure timezone consistency
            now = datetime.now(timezone.utc)
            if last_update.tzinfo is None:
                last_update = last_update.replace(tzinfo=timezone.utc)

            hours_since_update = (now - last_update).total_seconds() / 3600

            needs_update = hours_since_update >= (self.cache_refresh_period / 3600)
            logger.info(
                f"Cache last updated {hours_since_update:.1f} hours ago. "
                f"Needs refresh: {needs_update}"
            )
            return bool(needs_update)

        except Exception as e:
            logger.error(f"Error checking cache refresh status: {e}")
            return True

    def refresh_all_caches(self, genesys_service=None) -> Dict[str, int]:
        """
        Refresh all Genesys caches.

        Args:
            genesys_service: Optional GenesysService instance. If provided, uses it directly.
                           If not provided, attempts to get service from container.
        """
        results = {
            "groups": 0,
            "skills": 0,
            "locations": 0,
        }

        # Get token from GenesysService (preferred) or fallback to database
        token = None
        if genesys_service:
            try:
                token = genesys_service.get_access_token()
                if token:
                    logger.debug("Using provided GenesysService for cache refresh")
            except Exception as e:
                logger.error(f"Error getting token from provided GenesysService: {e}")

        if not token:
            # Fallback: try to get service from container
            try:
                from flask import current_app

                if current_app and hasattr(current_app, "container"):
                    service = current_app.container.get("genesys_service")
                    token = service.get_access_token()
                    if token:
                        logger.debug(
                            "Using GenesysService from container for cache refresh"
                        )
            except Exception as e:
                logger.debug(f"Could not get GenesysService from container: {e}")

        if not token:
            # Final fallback: direct database lookup (legacy path)
            token = self._get_access_token()
            if token:
                logger.debug("Using direct database lookup for cache refresh")

        if not token:
            logger.error("No valid token available for cache refresh")
            return results

        # Refresh each cache type
        results["groups"] = self._refresh_groups(token)
        results["skills"] = self._refresh_skills(token)
        results["locations"] = self._refresh_locations(token)

        logger.info(f"Cache refresh completed: {results}")
        return results

    def _refresh_groups(self, token: str) -> int:
        """Refresh groups cache."""
        try:
            headers = {"Authorization": f"Bearer {token}"}
            count = 0
            page_number = 1
            page_size = 100

            while True:
                response = requests.get(
                    f"{self.base_url}/api/v2/groups",
                    headers=headers,
                    params={"pageSize": page_size, "pageNumber": page_number},
                    timeout=self.cache_timeout,
                )

                if response.status_code != 200:
                    logger.error(f"Error fetching groups: {response.status_code}")
                    break

                data = response.json()
                entities = data.get("entities", [])

                if not entities:
                    break

                # Clear old data on first page
                if page_number == 1:
                    ExternalServiceData.query.filter_by(
                        service_name="genesys", data_type="group"
                    ).delete()

                # Insert new data
                for group in entities:
                    ExternalServiceData.update_service_data(
                        service_name="genesys",
                        data_type="group",
                        service_id=group.get("id"),
                        name=group.get("name"),
                        description=group.get("description"),
                        raw_data=group,
                    )
                    count += 1

                db.session.commit()

                # Check if more pages
                if data.get("pageCount", 0) <= page_number:
                    break

                page_number += 1

            logger.info(f"Refreshed {count} groups")
            return count

        except Exception as e:
            logger.error(f"Error refreshing groups: {e}")
            db.session.rollback()
            return 0

    def _refresh_skills(self, token: str) -> int:
        """Refresh skills cache."""
        try:
            headers = {"Authorization": f"Bearer {token}"}
            count = 0
            page_number = 1
            page_size = 100

            while True:
                response = requests.get(
                    f"{self.base_url}/api/v2/routing/skills",
                    headers=headers,
                    params={"pageSize": page_size, "pageNumber": page_number},
                    timeout=self.cache_timeout,
                )

                if response.status_code != 200:
                    logger.error(f"Error fetching skills: {response.status_code}")
                    break

                data = response.json()
                entities = data.get("entities", [])

                if not entities:
                    break

                # Clear old data on first page
                if page_number == 1:
                    ExternalServiceData.query.filter_by(
                        service_name="genesys", data_type="skill"
                    ).delete()

                # Insert new data
                for skill in entities:
                    ExternalServiceData.update_service_data(
                        service_name="genesys",
                        data_type="skill",
                        service_id=skill.get("id"),
                        name=skill.get("name"),
                        raw_data=skill,
                    )
                    count += 1

                db.session.commit()

                # Check if more pages
                if data.get("pageCount", 0) <= page_number:
                    break

                page_number += 1

            logger.info(f"Refreshed {count} skills")
            return count

        except Exception as e:
            logger.error(f"Error refreshing skills: {e}")
            db.session.rollback()
            return 0

    def _refresh_locations(self, token: str) -> int:
        """Refresh locations cache."""
        try:
            headers = {"Authorization": f"Bearer {token}"}
            count = 0
            page_number = 1
            page_size = 100

            while True:
                response = requests.get(
                    f"{self.base_url}/api/v2/locations",
                    headers=headers,
                    params={"pageSize": page_size, "pageNumber": page_number},
                    timeout=self.cache_timeout,
                )

                if response.status_code != 200:
                    logger.error(f"Error fetching locations: {response.status_code}")
                    break

                data = response.json()
                entities = data.get("entities", [])

                if not entities:
                    break

                # Clear old data on first page
                if page_number == 1:
                    ExternalServiceData.query.filter_by(
                        service_name="genesys", data_type="location"
                    ).delete()

                # Insert new data
                for location in entities:
                    # Build address string
                    address_parts = []
                    if location.get("address"):
                        addr = location["address"]
                        if addr.get("street1"):
                            address_parts.append(addr["street1"])
                        if addr.get("city"):
                            address_parts.append(addr["city"])
                        if addr.get("state"):
                            address_parts.append(addr["state"])

                    address_str = ", ".join(address_parts) if address_parts else None
                    ExternalServiceData.update_service_data(
                        service_name="genesys",
                        data_type="location",
                        service_id=location.get("id"),
                        name=location.get("name"),
                        description=address_str,
                        raw_data=location,
                    )
                    count += 1

                db.session.commit()

                # Check if more pages
                if data.get("pageCount", 0) <= page_number:
                    break

                page_number += 1

            logger.info(f"Refreshed {count} locations")
            return count

        except Exception as e:
            logger.error(f"Error refreshing locations: {e}")
            db.session.rollback()
            return 0

    # Lookup methods
    def get_group_name(self, group_id: str) -> Optional[str]:
        """Get group name from cache."""
        try:
            group = ExternalServiceData.query.filter_by(
                service_name="genesys", data_type="group", service_id=group_id
            ).first()
            return group.name if group else None
        except Exception:
            return None

    def get_skill_name(self, skill_id: str) -> Optional[str]:
        """Get skill name from cache."""
        try:
            skill = ExternalServiceData.query.filter_by(
                service_name="genesys", data_type="skill", service_id=skill_id
            ).first()
            return skill.name if skill else None
        except Exception:
            return None

    def get_location_info(self, location_id: str) -> Optional[Dict[str, str]]:
        """Get location info from cache."""
        try:
            location = ExternalServiceData.query.filter_by(
                service_name="genesys", data_type="location", service_id=location_id
            ).first()
            if location:
                return {
                    "id": location.service_id,
                    "name": location.name,
                    "address": location.description,
                }
            return None
        except Exception:
            return None

    def get_cache_status(self) -> Dict[str, Any]:
        """Get cache status with counts and age information."""
        try:
            # Use the existing Genesys tables instead of external_service_data
            from sqlalchemy import text
            from datetime import timezone

            # Get counts from existing tables
            groups_count = (
                db.session.execute(text("SELECT COUNT(*) FROM genesys_groups")).scalar()
                or 0
            )
            skills_count = (
                db.session.execute(text("SELECT COUNT(*) FROM genesys_skills")).scalar()
                or 0
            )
            locations_count = (
                db.session.execute(
                    text("SELECT COUNT(*) FROM genesys_locations")
                ).scalar()
                or 0
            )

            # Get cache age information from groups table
            result = db.session.execute(
                text("SELECT MAX(updated_at) FROM genesys_groups")
            ).scalar()

            cache_age = None
            needs_refresh = True

            if result:
                now = datetime.now(timezone.utc)
                last_update = result
                if last_update.tzinfo is None:
                    last_update = last_update.replace(tzinfo=timezone.utc)

                time_diff = now - last_update
                hours_since_update = time_diff.total_seconds() / 3600

                # Format as HH:MM:SS
                cache_age = f"{int(hours_since_update):02d}:{int((hours_since_update % 1) * 60):02d}:00"
                needs_refresh = hours_since_update >= (self.cache_refresh_period / 3600)

            return {
                "groups_cached": groups_count,
                "skills_cached": skills_count,
                "locations_cached": locations_count,
                "group_cache_age": cache_age,
                "needs_refresh": needs_refresh,
            }
        except Exception as e:
            logger.error(f"Error getting cache status: {e}")
            return {
                "groups_cached": 0,
                "skills_cached": 0,
                "locations_cached": 0,
                "group_cache_age": None,
                "needs_refresh": True,
            }

    def clear(self):
        """Clear all cached data."""
        try:
            ExternalServiceData.query.filter_by(service_name="genesys").delete()
            db.session.commit()
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
            db.session.rollback()

    def refresh_all(self) -> Dict[str, int]:
        """Alias for refresh_all_caches for backward compatibility."""
        return self.refresh_all_caches()

    def refresh_groups(self) -> int:
        """Refresh groups cache."""
        token = self._get_access_token()
        if token:
            return self._refresh_groups(token)
        return 0

    def refresh_skills(self) -> int:
        """Refresh skills cache."""
        token = self._get_access_token()
        if token:
            return self._refresh_skills(token)
        return 0

    def refresh_locations(self) -> int:
        """Refresh locations cache."""
        token = self._get_access_token()
        if token:
            return self._refresh_locations(token)
        return 0

    def refresh_cache(self) -> Dict[str, Any]:
        """Refresh cache - implementation of abstract method."""
        return self.refresh_all_caches()


genesys_cache_db = GenesysCacheDB()
