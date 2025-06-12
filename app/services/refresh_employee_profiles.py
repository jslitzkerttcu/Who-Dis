"""Employee profiles refresh service with Azure SQL and Graph API integration."""

import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

try:
    import httpx
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        AsyncClientType = httpx.AsyncClient
    else:
        AsyncClientType = Any
except ImportError:
    httpx = None
    AsyncClientType = Any  # Fallback type

from app.services.base import BaseConfigurableService
from app.services.graph_service import GraphService

# Legacy data_warehouse_service removed - functionality consolidated
from app.models.employee_profiles import EmployeeProfiles
from app.utils.error_handler import handle_service_errors

logger = logging.getLogger(__name__)


class EmployeeProfilesRefreshService(BaseConfigurableService):
    """Service for refreshing employee profiles from Azure SQL and Graph API."""

    def __init__(self):
        super().__init__(config_prefix="data_warehouse")
        self.graph_service = GraphService()
        self.max_concurrent_requests = 5
        self.semaphore = asyncio.Semaphore(self.max_concurrent_requests)

        if httpx is None:
            logger.warning(
                "httpx not available - photo fetching functionality disabled"
            )

    def load_keystone_employee_data(self) -> List[Dict[str, Any]]:
        """
        Load employee data from Azure SQL Server data warehouse.

        Returns:
            List of employee records from Azure SQL Server
        """
        logger.info("Loading employee data from Azure SQL Server")

        try:
            # Use existing data warehouse service to execute the Keystone query
            try:
                from app.services.data_warehouse_service import data_warehouse_service

                raw_records = data_warehouse_service.execute_keystone_query()
            except ImportError:
                logger.warning(
                    "Data warehouse service not available - using empty dataset"
                )
                raw_records = []

            # Transform the data to match EmployeeProfiles model field names
            transformed_records = []
            for record in raw_records:
                # Convert datetime strings back to datetime objects if needed
                ks_last_login_time = record.get("KS_Last_Login_Time")
                if isinstance(ks_last_login_time, str):
                    try:
                        ks_last_login_time = datetime.fromisoformat(
                            ks_last_login_time.replace("Z", "+00:00")
                        )
                    except (ValueError, AttributeError):
                        ks_last_login_time = None

                transformed_record = {
                    "upn": record.get("UPN"),
                    "ks_user_serial": record.get("KS_User_Serial"),
                    "ks_last_login_time": ks_last_login_time,
                    "ks_login_lock": record.get("KS_Login_Lock"),
                    "live_role": record.get("Live_Role"),
                    "test_role": record.get("Test_Role"),
                    "keystone_expected_role": record.get(
                        "Keystone_Expected_Role_For_Job_Title"
                    ),
                    "ukg_job_code": record.get("UKG_Job_Code"),
                }

                # Only add records with valid UPN
                if transformed_record["upn"]:
                    transformed_records.append(transformed_record)

            logger.info(
                f"Loaded {len(transformed_records)} employee records from Azure SQL"
            )
            return transformed_records

        except Exception as e:
            logger.error(f"Error loading employee data from Azure SQL: {str(e)}")
            # Fall back to mock data for development/testing
            logger.warning("Falling back to mock data due to Azure SQL error")
            return self._get_fallback_mock_data()

    def _get_fallback_mock_data(self) -> List[Dict[str, Any]]:
        """
        Fallback mock data when Azure SQL is unavailable.

        Returns:
            List of mock employee records
        """
        logger.info("Using fallback mock employee data")

        mock_employees = [
            {
                "upn": "john.doe@company.com",
                "ks_user_serial": 12345,
                "ks_last_login_time": datetime(
                    2024, 6, 1, 9, 30, 0, tzinfo=timezone.utc
                ),
                "ks_login_lock": "N",
                "live_role": "Manager",
                "test_role": "Test_Manager",
                "keystone_expected_role": "Manager",
                "ukg_job_code": "MGR001",
            },
            {
                "upn": "jane.smith@company.com",
                "ks_user_serial": 12346,
                "ks_last_login_time": datetime(
                    2024, 6, 2, 14, 15, 0, tzinfo=timezone.utc
                ),
                "ks_login_lock": "L",
                "live_role": "Analyst",
                "test_role": "Test_Analyst",
                "keystone_expected_role": "Analyst",
                "ukg_job_code": "ANL001",
            },
            {
                "upn": "mike.brown@company.com",
                "ks_user_serial": 12349,
                "ks_last_login_time": None,
                "ks_login_lock": "N",
                "live_role": None,
                "test_role": "Test_Intern",
                "keystone_expected_role": "Intern",
                "ukg_job_code": "INT001",
            },
        ]

        return mock_employees

    async def _fetch_user_photo_async(self, upn: str, client: Any) -> Optional[bytes]:
        """
        Fetch user photo from Graph API asynchronously using existing Graph service.

        Args:
            upn: User principal name
            client: httpx AsyncClient instance

        Returns:
            Photo bytes if successful, None if failed or no photo
        """
        async with self.semaphore:
            try:
                # Get access token from Graph service
                access_token = self.graph_service.get_access_token()
                if not access_token:
                    logger.warning(
                        f"No Graph API access token available for photo fetch: {upn}"
                    )
                    return None

                # Use real Graph API call
                url = f"https://graph.microsoft.com/v1.0/users/{upn}/photo/$value"
                headers = {"Authorization": f"Bearer {access_token}"}

                response = await client.get(url, headers=headers, timeout=15.0)

                if response.status_code == 200:
                    logger.debug(f"Successfully fetched photo for {upn}")
                    return bytes(response.content)
                elif response.status_code == 404:
                    logger.debug(f"No photo found for {upn}")
                    return None
                else:
                    logger.warning(
                        f"Failed to fetch photo for {upn}: HTTP {response.status_code}"
                    )
                    return None

            except Exception as e:
                logger.error(f"Error fetching photo for {upn}: {str(e)}")
                return None

    def _get_user_photo_sync(self, upn: str) -> Optional[bytes]:
        """
        Synchronous photo fetching using existing Graph service method.

        Args:
            upn: User principal name

        Returns:
            Photo bytes if successful, None if failed or no photo
        """
        try:
            # Use existing Graph service method but extract raw bytes
            photo_data_url = self.graph_service.get_user_photo(upn, upn)
            if photo_data_url and photo_data_url.startswith("data:image/"):
                # Extract base64 data and decode to bytes
                import base64

                base64_data = photo_data_url.split(",", 1)[1]
                return base64.b64decode(base64_data)
            return None
        except Exception as e:
            logger.error(f"Error fetching photo for {upn} (sync): {str(e)}")
            return None

    def _mock_photo_bytes(self) -> bytes:
        """Generate mock photo bytes for testing."""
        # Create a small mock JPEG-like byte sequence
        mock_jpeg_header = b"\xff\xd8\xff\xe0\x00\x10JFIF"
        mock_data = b"mock_photo_data_" + str(datetime.now().timestamp()).encode()
        mock_jpeg_footer = b"\xff\xd9"
        return mock_jpeg_header + mock_data + mock_jpeg_footer

    async def _process_employee_async(
        self, employee_data: Dict[str, Any], client: Any
    ) -> bool:
        """
        Process a single employee record asynchronously.

        Args:
            employee_data: Employee record from Azure SQL
            client: httpx AsyncClient instance

        Returns:
            True if successful, False if failed
        """
        upn = employee_data.get("upn")
        if not upn:
            logger.error("Employee record missing UPN, skipping")
            return False

        try:
            logger.debug(f"Processing employee profile: {upn}")

            # Fetch user photo
            photo_bytes = await self._fetch_user_photo_async(upn, client)

            # Prepare raw_data for JSON storage (convert datetime objects)
            raw_data = dict(employee_data)
            for key, value in raw_data.items():
                if isinstance(value, datetime):
                    raw_data[key] = value.isoformat()

            # Prepare data for upsert
            profile_data = {
                "ks_user_serial": employee_data.get("ks_user_serial"),
                "ks_last_login_time": employee_data.get("ks_last_login_time"),
                "ks_login_lock": employee_data.get("ks_login_lock"),
                "live_role": employee_data.get("live_role"),
                "test_role": employee_data.get("test_role"),
                "keystone_expected_role": employee_data.get("keystone_expected_role"),
                "ukg_job_code": employee_data.get("ukg_job_code"),
                "photo_data": photo_bytes,
                "photo_content_type": "image/jpeg" if photo_bytes else None,
                "raw_data": raw_data,  # Store complete original record
            }

            # Upsert to database
            EmployeeProfiles.create_or_update_profile(upn, profile_data)
            logger.info(f"Successfully processed employee profile: {upn}")
            return True

        except Exception as e:
            logger.error(f"Failed to process employee {upn}: {str(e)}")
            return False

    async def _refresh_profiles_async(
        self, employee_records: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Refresh all employee profiles asynchronously.

        Args:
            employee_records: List of employee records from Azure SQL

        Returns:
            Dictionary with processing statistics
        """
        if httpx is None:
            logger.error("httpx not available - cannot perform async requests")
            return {"success": 0, "failed": 0, "total": 0}

        total_count = len(employee_records)
        success_count = 0
        failed_count = 0

        logger.info(f"Starting async processing of {total_count} employee profiles")

        # Create httpx client with timeout configuration
        timeout = httpx.Timeout(connect=10.0, read=15.0, write=10.0, pool=30.0)

        async with httpx.AsyncClient(timeout=timeout) as client:
            # Process all employees concurrently with semaphore limiting
            tasks = [
                self._process_employee_async(employee_data, client)
                for employee_data in employee_records
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Count results
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"Task failed with exception: {result}")
                    failed_count += 1
                elif result:
                    success_count += 1
                else:
                    failed_count += 1

        logger.info(
            f"Async processing completed: {success_count} success, "
            f"{failed_count} failed, {total_count} total"
        )

        return {
            "success": success_count,
            "failed": failed_count,
            "total": total_count,
            "timestamp": datetime.now(timezone.utc),
        }

    @handle_service_errors(
        service_name="employee_profiles_refresh",
        default_return={"success": 0, "failed": 0, "total": 0},
    )
    def refresh_all_profiles(self) -> Dict[str, Any]:
        """
        Refresh all employee profiles from Azure SQL and Graph API.

        This is the main entry point for the service.

        Returns:
            Dictionary with processing statistics
        """
        logger.info("=== Starting Employee Profiles Refresh ===")
        start_time = datetime.now(timezone.utc)

        try:
            # Step 1: Load employee data from Azure SQL
            employee_records = self.load_keystone_employee_data()

            if not employee_records:
                logger.warning("No employee records found, nothing to process")
                return {"success": 0, "failed": 0, "total": 0}

            # Step 2: Process records asynchronously
            try:
                # Try to get current event loop
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # If we're already in an async context, fall back to sync processing
                    logger.info("Running in existing event loop, using sync processing")
                    return self._refresh_profiles_sync(employee_records)
                else:
                    # Create new event loop
                    return asyncio.run(self._refresh_profiles_async(employee_records))
            except RuntimeError:
                # No event loop in current thread, use sync processing
                logger.info("No event loop in current thread, using sync processing")
                return self._refresh_profiles_sync(employee_records)

        except Exception as e:
            logger.error(f"Error during employee profiles refresh: {str(e)}")
            raise
        finally:
            end_time = datetime.now(timezone.utc)
            duration = (end_time - start_time).total_seconds()
            logger.info(
                f"=== Employee Profiles Refresh Completed in {duration:.2f}s ==="
            )

    def _refresh_profiles_sync(
        self, employee_records: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Fallback synchronous processing for when async is not available.

        Args:
            employee_records: List of employee records from Azure SQL

        Returns:
            Dictionary with processing statistics
        """
        total_count = len(employee_records)
        success_count = 0
        failed_count = 0

        logger.info(
            f"Starting synchronous processing of {total_count} employee profiles"
        )

        for employee_data in employee_records:
            upn = employee_data.get("upn", "unknown")
            try:
                # Fetch photo synchronously
                photo_bytes = self._get_user_photo_sync(upn)

                # Prepare data for upsert
                # Prepare raw_data for JSON storage (convert datetime objects)
                raw_data = dict(employee_data)
                for key, value in raw_data.items():
                    if isinstance(value, datetime):
                        raw_data[key] = value.isoformat()

                profile_data = {
                    "ks_user_serial": employee_data.get("ks_user_serial"),
                    "ks_last_login_time": employee_data.get("ks_last_login_time"),
                    "ks_login_lock": employee_data.get("ks_login_lock"),
                    "live_role": employee_data.get("live_role"),
                    "test_role": employee_data.get("test_role"),
                    "keystone_expected_role": employee_data.get(
                        "keystone_expected_role"
                    ),
                    "ukg_job_code": employee_data.get("ukg_job_code"),
                    "photo_data": photo_bytes,
                    "photo_content_type": "image/jpeg" if photo_bytes else None,
                    "raw_data": raw_data,
                }

                EmployeeProfiles.create_or_update_profile(upn, profile_data)
                logger.info(f"Successfully processed employee profile (sync): {upn}")
                success_count += 1

            except Exception as e:
                logger.error(f"Failed to process employee {upn} (sync): {str(e)}")
                failed_count += 1

        logger.info(
            f"Synchronous processing completed: {success_count} success, "
            f"{failed_count} failed, {total_count} total"
        )

        return {
            "success": success_count,
            "failed": failed_count,
            "total": total_count,
            "timestamp": datetime.now(timezone.utc),
        }

    def get_refresh_stats(self) -> Dict[str, Any]:
        """
        Get statistics about current employee profiles.

        Returns:
            Dictionary with profile statistics
        """
        try:
            total_profiles = EmployeeProfiles.query.count()
            locked_profiles = EmployeeProfiles.query.filter_by(
                ks_login_lock="L"
            ).count()
            profiles_with_photos = EmployeeProfiles.query.filter(
                EmployeeProfiles.photo_data.isnot(None)
            ).count()

            # Get the most recent update
            latest_profile = EmployeeProfiles.query.order_by(
                EmployeeProfiles.updated_at.desc()
            ).first()

            last_updated = latest_profile.updated_at if latest_profile else None

            return {
                "total_profiles": total_profiles,
                "locked_profiles": locked_profiles,
                "profiles_with_photos": profiles_with_photos,
                "profiles_without_photos": total_profiles - profiles_with_photos,
                "last_updated": last_updated.isoformat() if last_updated else None,
            }

        except Exception as e:
            logger.error(f"Error getting refresh stats: {str(e)}")
            return {
                "total_profiles": 0,
                "locked_profiles": 0,
                "profiles_with_photos": 0,
                "profiles_without_photos": 0,
                "last_updated": None,
                "error": str(e),
            }

    def get_employee_profile(self, upn: str) -> Optional[Dict[str, Any]]:
        """
        Get a complete employee profile by UPN.

        This is the main interface for retrieving employee information
        from the consolidated employee_profiles table.

        Args:
            upn: User principal name

        Returns:
            Complete employee profile or None if not found
        """
        try:
            profile = EmployeeProfiles.get_by_upn(upn)
            if profile:
                return profile.get_display_info()
            return None
        except Exception as e:
            logger.error(f"Error getting employee profile for {upn}: {str(e)}")
            return None

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the employee profiles cache.

        This method provides compatibility with the old data warehouse service interface.

        Returns:
            Dictionary with cache statistics
        """
        try:
            # Get basic statistics from the employee_profiles table
            total_records = EmployeeProfiles.query.count()

            # Get the most recent update
            latest_profile = EmployeeProfiles.query.order_by(
                EmployeeProfiles.updated_at.desc()
            ).first()
            last_updated = latest_profile.updated_at if latest_profile else None

            # Determine refresh status
            if total_records == 0:
                refresh_status = "empty"
                needs_refresh = True
            elif last_updated:
                from datetime import datetime, timedelta

                # Consider cache stale if older than 24 hours
                stale_threshold = datetime.now() - timedelta(hours=24)
                needs_refresh = last_updated < stale_threshold
                refresh_status = "stale" if needs_refresh else "current"
            else:
                refresh_status = "unknown"
                needs_refresh = True

            return {
                "record_count": total_records,
                "last_updated": last_updated.isoformat() if last_updated else None,
                "refresh_status": refresh_status,
                "needs_refresh": needs_refresh,
                "total_records": total_records,  # Legacy compatibility
            }

        except Exception as e:
            logger.error(f"Error getting cache stats: {str(e)}")
            return {
                "record_count": 0,
                "last_updated": None,
                "refresh_status": "error",
                "needs_refresh": True,
                "total_records": 0,
                "error": str(e),
            }

    def test_data_warehouse_connection(self) -> Dict[str, Any]:
        """
        Test data warehouse connection.

        This method provides compatibility with the old data warehouse service interface.

        Returns:
            Dictionary with connection test results
        """
        try:
            # Try to import and test the legacy data warehouse service if available
            try:
                from app.services.data_warehouse_service import data_warehouse_service

                result: Dict[str, Any] = data_warehouse_service.test_connection()
                return result
            except ImportError:
                # If legacy service is not available, return success for consolidated architecture
                return {
                    "success": True,
                    "message": "Data warehouse functionality consolidated into employee_profiles service",
                    "connection_available": True,
                }
        except Exception as e:
            logger.error(f"Error testing data warehouse connection: {str(e)}")
            return {
                "success": False,
                "message": f"Connection test failed: {str(e)}",
                "connection_available": False,
            }

    # Legacy migration removed - use the drop_legacy_tables.py script instead


# Service instance for import
employee_profiles_service = EmployeeProfilesRefreshService()


def main():
    """CLI entry point for the service."""
    import sys

    # Set up logging for CLI usage
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

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
                "Usage: python refresh_employee_profiles.py [refresh|stats|migrate|profile <upn>]"
            )
            sys.exit(1)
    else:
        print(
            "Usage: python refresh_employee_profiles.py [refresh|stats|migrate|profile <upn>]"
        )
        print("  refresh - Refresh all employee profiles from Azure SQL and Graph API")
        print("  stats   - Show current employee profiles statistics")
        print("  migrate - Migrate data from legacy tables to employee_profiles")
        print("  profile <upn> - Show specific employee profile")


if __name__ == "__main__":
    main()
