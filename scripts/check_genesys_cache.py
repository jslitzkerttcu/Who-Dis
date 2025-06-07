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

        # Get cache status
        status = genesys_cache_db.get_cache_status()
        print(f"Needs refresh: {status.get('needs_refresh', 'Unknown')}")
        print(f"Refresh period: {status.get('refresh_period_hours', 'Unknown')} hours")

        if status.get("last_location_update"):
            print(f"Last location update: {status['last_location_update']}")
            print(f"Location cache age: {status.get('location_cache_age', 'Unknown')}")
        else:
            print("No location cache data found!")

        print()

        # If no locations, try to refresh
        if locations_count == 0:
            print("No locations found in cache. Attempting to refresh...")
            success = genesys_cache_db.refresh_locations()
            if success:
                new_count = GenesysLocation.query.count()
                print(f"✓ Successfully cached {new_count} locations")
            else:
                print("✗ Failed to refresh locations cache")

        # Show sample locations
        if locations_count > 0:
            print("\nSample locations:")
            locations = GenesysLocation.query.limit(5).all()
            for loc in locations:
                print(f"  - {loc.name} (ID: {loc.id})")


if __name__ == "__main__":
    check_cache_status()
