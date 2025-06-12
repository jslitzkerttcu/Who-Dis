#!/usr/bin/env python3
"""
CLI script for refreshing employee profiles.
This script can be run from the project root directory.
"""

import sys
from pathlib import Path

# Add the parent directory to Python path to import from app
sys.path.append(str(Path(__file__).parent.parent))


def main():
    """CLI entry point for the service."""
    import logging
    from app.services.refresh_employee_profiles import employee_profiles_service

    # Set up logging for CLI usage
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    logger = logging.getLogger(__name__)
    logger.info("Employee Profiles Refresh Service - CLI Mode")

    if len(sys.argv) > 1:
        command = sys.argv[1].lower()

        if command == "refresh":
            logger.info("Starting employee profiles refresh...")
            result = employee_profiles_service.refresh_all_profiles()
            print(f"Refresh completed: {result}")

        elif command == "stats":
            logger.info("Getting employee profiles statistics...")
            stats = employee_profiles_service.get_refresh_stats()
            print("Employee Profiles Statistics:")
            for key, value in stats.items():
                print(f"  {key}: {value}")

        elif command == "migrate":
            logger.info("Migrating legacy data...")
            result = employee_profiles_service.migrate_legacy_data()
            print(f"Migration completed: {result}")

        elif command == "profile" and len(sys.argv) > 2:
            upn = sys.argv[2]
            logger.info(f"Getting profile for {upn}...")
            profile = employee_profiles_service.get_employee_profile(upn)
            if profile:
                print(f"Profile for {upn}:")
                for key, value in profile.items():
                    print(f"  {key}: {value}")
            else:
                print(f"No profile found for {upn}")

        else:
            print(
                "Usage: python scripts/refresh_employee_profiles.py [refresh|stats|migrate|profile <upn>]"
            )
            sys.exit(1)
    else:
        print(
            "Usage: python scripts/refresh_employee_profiles.py [refresh|stats|migrate|profile <upn>]"
        )
        print("  refresh - Refresh all employee profiles from Azure SQL and Graph API")
        print("  stats   - Show current employee profiles statistics")
        print("  migrate - Migrate data from legacy tables to employee_profiles")
        print("  profile <upn> - Show specific employee profile")


if __name__ == "__main__":
    main()
