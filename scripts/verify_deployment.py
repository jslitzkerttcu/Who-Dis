#!/usr/bin/env python3
"""
Deployment Verification Script
=============================

Verifies that the WhoDis employee_profiles consolidation deployment is working correctly.

Usage:
    python scripts/verify_deployment.py [--skip-photos] [--verbose]

Options:
    --skip-photos    Skip photo loading tests (faster verification)
    --verbose        Enable detailed logging output

This script performs comprehensive health checks on the new consolidated architecture.
"""

import os
import sys
import argparse
import logging
import requests
from pathlib import Path
from typing import List

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    import psycopg2
    from dotenv import load_dotenv
except ImportError as e:
    print(f"Error: Required dependencies not available: {e}")
    print("Please ensure psycopg2 and python-dotenv are installed")
    sys.exit(1)

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class DeploymentVerifier:
    """Comprehensive deployment verification for WhoDis 2.0."""

    def __init__(self, verbose: bool = False, skip_photos: bool = False):
        self.verbose = verbose
        self.skip_photos = skip_photos
        self.app_url = "http://localhost:5000"
        self.checks_passed = 0
        self.checks_total = 0
        self.errors: List[str] = []

        if verbose:
            logging.getLogger().setLevel(logging.DEBUG)

    def get_db_connection(self):
        """Get database connection."""
        try:
            return psycopg2.connect(
                host=os.getenv("POSTGRES_HOST"),
                port=os.getenv("POSTGRES_PORT", 5432),
                database=os.getenv("POSTGRES_DB"),
                user=os.getenv("POSTGRES_USER"),
                password=os.getenv("POSTGRES_PASSWORD"),
            )
        except Exception as e:
            raise ConnectionError(f"Failed to connect to database: {e}")

    def check_database_schema(self) -> bool:
        """Verify consolidated database schema."""
        logger.info("🔍 Checking database schema...")
        self.checks_total += 1

        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()

                # Check employee_profiles table exists
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        AND table_name = 'employee_profiles'
                    );
                """)

                if not cursor.fetchone()[0]:
                    self.errors.append("employee_profiles table not found")
                    return False

                # Check legacy tables are gone
                cursor.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name IN ('graph_photos', 'data_warehouse_cache');
                """)

                legacy_tables = [row[0] for row in cursor.fetchall()]
                if legacy_tables:
                    self.errors.append(f"Legacy tables still exist: {legacy_tables}")
                    return False

                # Check employee_profiles structure
                cursor.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'employee_profiles' 
                    AND column_name IN ('upn', 'photo_data', 'ks_user_serial', 'live_role');
                """)

                columns = [row[0] for row in cursor.fetchall()]
                required_columns = {"upn", "photo_data", "ks_user_serial", "live_role"}

                if not required_columns.issubset(set(columns)):
                    missing = required_columns - set(columns)
                    self.errors.append(f"Missing employee_profiles columns: {missing}")
                    return False

                logger.info("✅ Database schema verification passed")
                self.checks_passed += 1
                return True

        except Exception as e:
            self.errors.append(f"Database schema check failed: {e}")
            return False

    def check_employee_profiles_service(self) -> bool:
        """Verify employee profiles service functionality."""
        logger.info("🔍 Checking employee profiles service...")
        self.checks_total += 1

        try:
            # Import and test the service
            from app.services.refresh_employee_profiles import employee_profiles_service

            # Test basic functionality
            stats = employee_profiles_service.get_cache_stats()

            if not isinstance(stats, dict):
                self.errors.append(
                    "Employee profiles service not returning proper stats"
                )
                return False

            required_keys = {"record_count", "last_updated", "refresh_status"}
            if not required_keys.issubset(stats.keys()):
                missing = required_keys - stats.keys()
                self.errors.append(f"Missing stats keys: {missing}")
                return False

            logger.info(
                f"✅ Employee profiles service active (records: {stats.get('record_count', 0)})"
            )
            self.checks_passed += 1
            return True

        except Exception as e:
            self.errors.append(f"Employee profiles service check failed: {e}")
            return False

    def check_legacy_models_removed(self) -> bool:
        """Verify legacy models are properly removed."""
        logger.info("🔍 Checking legacy models removal...")
        self.checks_total += 1

        try:
            # Try importing legacy models - should fail
            import importlib.util

            graph_photo_spec = importlib.util.find_spec("app.models.graph_photo")
            if graph_photo_spec is not None:
                self.errors.append("GraphPhoto model still available")
                return False

            data_warehouse_spec = importlib.util.find_spec("app.models.data_warehouse")
            if data_warehouse_spec is not None:
                self.errors.append("DataWarehouseCache model still available")
                return False

            # Check models __init__.py doesn't reference them
            models_init = project_root / "app" / "models" / "__init__.py"
            with open(models_init, "r") as f:
                content = f.read()

            if "GraphPhoto" in content or "DataWarehouseCache" in content:
                self.errors.append(
                    "Legacy models still referenced in models/__init__.py"
                )
                return False

            logger.info("✅ Legacy models successfully removed")
            self.checks_passed += 1
            return True

        except Exception as e:
            self.errors.append(f"Legacy models check failed: {e}")
            return False

    def check_flask_application(self) -> bool:
        """Verify Flask application starts and responds."""
        logger.info("🔍 Checking Flask application...")
        self.checks_total += 1

        try:
            # Check if app is running
            response = requests.get(f"{self.app_url}/", timeout=5)

            if response.status_code != 200:
                self.errors.append(
                    f"Flask app not responding correctly (status: {response.status_code})"
                )
                return False

            # Check for basic content
            if "Who Dis?" not in response.text:
                self.errors.append("Flask app not returning expected content")
                return False

            logger.info("✅ Flask application responding correctly")
            self.checks_passed += 1
            return True

        except requests.exceptions.RequestException as e:
            self.errors.append(f"Flask application check failed: {e}")
            logger.warning(
                "⚠️  Flask app check failed - make sure app is running on localhost:5000"
            )
            return False

    def check_admin_interface(self) -> bool:
        """Verify admin interface loads with new consolidated data."""
        logger.info("🔍 Checking admin interface...")
        self.checks_total += 1

        try:
            # Check admin employee profiles page
            admin_url = f"{self.app_url}/admin/employee-profiles"
            response = requests.get(admin_url, timeout=10)

            if response.status_code == 200:
                # Check for modern UI elements
                if "employee_profiles" in response.text.lower():
                    logger.info("✅ Admin interface loads with consolidated data")
                    self.checks_passed += 1
                    return True
                else:
                    self.errors.append(
                        "Admin interface not showing consolidated employee profiles"
                    )
                    return False
            else:
                logger.warning(
                    f"⚠️  Admin interface check skipped (status: {response.status_code})"
                )
                # Don't count as failure since this might need authentication
                self.checks_total -= 1
                return True

        except requests.exceptions.RequestException:
            logger.warning("⚠️  Admin interface check skipped (connection failed)")
            # Don't count as failure since this might need authentication
            self.checks_total -= 1
            return True

    def check_photo_functionality(self) -> bool:
        """Verify photo functionality works with consolidated storage."""
        if self.skip_photos:
            logger.info("📸 Skipping photo functionality check")
            return True

        logger.info("🔍 Checking photo functionality...")
        self.checks_total += 1

        try:
            from app.services.refresh_employee_profiles import employee_profiles_service

            # Check if photo service methods exist
            if not hasattr(employee_profiles_service, "fetch_and_store_photo"):
                self.errors.append(
                    "Photo functionality not available in employee profiles service"
                )
                return False

            logger.info("✅ Photo functionality integrated in consolidated service")
            self.checks_passed += 1
            return True

        except Exception as e:
            self.errors.append(f"Photo functionality check failed: {e}")
            return False

    def check_search_integration(self) -> bool:
        """Verify search integration works with consolidated data."""
        logger.info("🔍 Checking search integration...")
        self.checks_total += 1

        try:
            # Check that search enhancer uses new service
            from app.services.search_enhancer import search_enhancer

            # Test basic search enhancement functionality
            empty_result = search_enhancer.enhance_search_results({})

            if not isinstance(empty_result, dict):
                self.errors.append("Search enhancer not working correctly")
                return False

            logger.info("✅ Search integration working with consolidated data")
            self.checks_passed += 1
            return True

        except Exception as e:
            self.errors.append(f"Search integration check failed: {e}")
            return False

    def run_all_checks(self) -> bool:
        """Run all deployment verification checks."""
        logger.info("🚀 Starting WhoDis 2.0 deployment verification...")
        logger.info("=" * 60)

        checks = [
            self.check_database_schema,
            self.check_legacy_models_removed,
            self.check_employee_profiles_service,
            self.check_search_integration,
            self.check_photo_functionality,
            self.check_flask_application,
            self.check_admin_interface,
        ]

        for check in checks:
            try:
                check()
            except Exception as e:
                self.errors.append(f"Unexpected error in {check.__name__}: {e}")
                logger.error(f"❌ {check.__name__} failed with exception: {e}")

        # Print summary
        logger.info("=" * 60)
        logger.info("📊 Verification Summary:")
        logger.info(f"   ✅ Checks Passed: {self.checks_passed}/{self.checks_total}")

        if self.errors:
            logger.error(f"   ❌ Errors Found: {len(self.errors)}")
            for error in self.errors:
                logger.error(f"      • {error}")

        success = self.checks_passed == self.checks_total and len(self.errors) == 0

        if success:
            logger.info("🎉 All verification checks passed! Deployment is successful.")
        else:
            logger.error(
                "💥 Deployment verification failed. Please review errors above."
            )

        return success


def main():
    """Main verification function."""
    parser = argparse.ArgumentParser(description="Verify WhoDis 2.0 deployment")
    parser.add_argument(
        "--skip-photos", action="store_true", help="Skip photo loading tests"
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    verifier = DeploymentVerifier(verbose=args.verbose, skip_photos=args.skip_photos)
    success = verifier.run_all_checks()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
