#!/usr/bin/env python3
"""
Check Genesys cache status and refresh if needed
"""

import os
import sys

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.services.genesys_cache_db import genesys_cache_db
from app.models import GenesysGroup, GenesysLocation, GenesysSkill


def check_cache_status():
    """Check the status of Genesys cache"""
    app = create_app()

    with app.app_context():
        print("=== Genesys Cache Status ===")
        print()

        # Get counts
        groups_count = GenesysGroup.query.count()
        locations_count = GenesysLocation.query.count()
        skills_count = GenesysSkill.query.count()

        print(f"Groups cached: {groups_count}")
        print(f"Locations cached: {locations_count}")
        print(f"Skills cached: {skills_count}")
        print()

        # Check cache status
        needs_refresh = genesys_cache_db.needs_refresh()
        print(f"Needs refresh: {needs_refresh}")

        # Try to get last update from the database
        try:
            latest_location = GenesysLocation.query.order_by(
                GenesysLocation.updated_at.desc()
            ).first()
            if latest_location:
                print(f"Last location update: {latest_location.updated_at}")
            else:
                print("No location cache data found!")
        except Exception as e:
            print(f"Error checking cache timestamps: {e}")

        print()

        # If no locations, try to refresh
        if locations_count == 0:
            print("No locations found in cache. Attempting to refresh...")
            try:
                results = genesys_cache_db.refresh_all_caches()
                location_count = results.get("locations", 0)
                if location_count > 0:
                    print(f"✓ Successfully cached {location_count} locations")
                else:
                    print("✗ Failed to refresh locations cache")
            except Exception as e:
                print(f"✗ Error refreshing cache: {e}")

        # Show sample locations
        if locations_count > 0:
            print("\nSample locations:")
            locations = GenesysLocation.query.limit(5).all()
            for loc in locations:
                print(f"  - {loc.name} (ID: {loc.id})")


if __name__ == "__main__":
    check_cache_status()
