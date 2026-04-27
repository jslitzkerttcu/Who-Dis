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

try:
    import pyodbc  # type: ignore[import-not-found]
except ImportError:
    pyodbc = None

from app.services.base import BaseConfigurableService
from app.services.graph_service import GraphService
from app.models.employee_profiles import EmployeeProfiles
from app.utils.error_handler import handle_service_errors

try:
    from flask import current_app
except ImportError:  # pragma: no cover - Flask is a hard dependency
    current_app = None  # type: ignore[assignment]

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
        if pyodbc is None:
            logger.warning(
                "pyodbc not available - data warehouse functionality disabled"
            )

    # --- Data warehouse configuration (Azure SQL connection) ---

    @property
    def server(self):
        """Get SQL Server hostname."""
        return self._get_config("server")

    @property
    def database(self):
        """Get database name."""
        return self._get_config("database", "CUFX")

    @property
    def client_id(self):
        """Get Azure AD client ID."""
        return self._get_config("client_id")

    @property
    def client_secret(self):
        """Get Azure AD client secret."""
        return self._get_config("client_secret")

    @property
    def connection_timeout(self):
        """Get connection timeout in seconds."""
        return int(self._get_config("connection_timeout", "30"))

    @property
    def query_timeout(self):
        """Get query timeout in seconds."""
        return int(self._get_config("query_timeout", "60"))

    @property
    def cache_refresh_hours(self):
        """Get cache refresh period in hours."""
        return float(self._get_config("cache_refresh_hours", "6.0"))

    def _get_connection_string(self) -> str:
        """Build Azure SQL connection string with AD authentication."""
        driver = "ODBC Driver 18 for SQL Server"

        connection_parts = [
            f"DRIVER={{{driver}}}",
            f"SERVER={self.server}",
            f"DATABASE={self.database}",
            "Encrypt=yes",
            "TrustServerCertificate=no",
            "Connection Timeout=30",
            "Authentication=ActiveDirectoryServicePrincipal",
            f"UID={self.client_id}",
            f"PWD={self.client_secret}",
        ]

        return ";".join(connection_parts)

    @handle_service_errors(raise_errors=True)
    def test_connection(self) -> bool:
        """Test connection to Azure SQL Server."""
        # Clear cache to force reload of configuration
        self._clear_config_cache()

        # Check if credentials are configured
        client_id = self.client_id
        client_secret = self.client_secret
        server = self.server

        if not client_id or not client_secret or not server:
            logger.error("Data warehouse credentials not configured")
            return False

        if pyodbc is None:
            logger.error("pyodbc not available - cannot test data warehouse connection")
            return False

        try:
            connection_string = self._get_connection_string()

            with pyodbc.connect(
                connection_string, timeout=self.connection_timeout
            ) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1 as test")
                result = cursor.fetchone()

                if result and result[0] == 1:
                    logger.debug("Data warehouse connection test successful")
                    return True
                logger.error("Data warehouse test query returned unexpected result")
                return False

        except pyodbc.Error as e:
            logger.error(f"ODBC error testing data warehouse connection: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Error testing data warehouse connection: {str(e)}")
            return False

    @handle_service_errors(raise_errors=True)
    def execute_keystone_query(self) -> List[Dict[str, Any]]:
        """
        Execute the Keystone user query and return results.

        Returns:
            List of user records from the data warehouse
        """
        if pyodbc is None:
            logger.error("pyodbc not available - cannot execute keystone query")
            return []

        query = """
        SELECT
            [User].[SERIAL] AS KS_User_Serial,
            [User].[LAST_LOGIN_TIME] AS KS_Last_Login_Time,
            [User].[LOGIN_LOCK] AS KS_Login_Lock,
            Employee.UPN,
            RoleDesc.[DESCRIPTION] AS Live_Role,
            TestRoleDesc.[DESCRIPTION] AS Test_Role,
            Employee.[JobCode] AS UKG_Job_Code,
            CASE
                WHEN Employee.JobCode IN ('81015','81014','81004','81030','81003') THEN 'Accounting Mgmt'
                WHEN Employee.JobCode IN ('80008','78004','780010','76012','88016','78006','78008','78016','76013','76008','74033','90006','78030','78013','78010','76011','74047','74036','74046','74039','74038','74034','74048','74045','74037','74042','74041','74049','74040','74043','74044','76002','74032','74035','76004') THEN 'Inquiry'
                WHEN Employee.JobCode IN ('1111') THEN 'Branch Head Teller'
                WHEN Employee.JobCode IN ('3102','7103','1101','11005','11006','11007','11008') THEN 'Branch Management/Lead CUA'
                WHEN Employee.JobCode IN ('73008','73006','73001','73003') THEN 'Branch Ops Upper Mgmt'
                WHEN Employee.JobCode IN ('1115','87001','90007','83009','85031','78003','9999') THEN 'Not Determined'
                WHEN Employee.JobCode IN ('1112') THEN 'Branch CUA 1'
                WHEN Employee.JobCode IN ('1116','11001') THEN 'CUA 1'
                WHEN Employee.JobCode IN ('5110','11003') THEN 'Branch Supervisor/Branch CUA 3'
                WHEN Employee.JobCode IN ('77009','77015','77011','77014','71011','71010','77012','88004','90002','72030','77010','72010','77008','77007','77006','88008','88007','88006','70001','84030','77016','77003') THEN 'Inquiry-Audit'
                WHEN Employee.JobCode IN ('78012','9999INT','8','13','15','16','76014','76005','76003','76007','76006','77013','1','74001','84012','3','3117','76010','10','4','6','11','10001','9999EXT') THEN 'No Access Granted'
                WHEN Employee.JobCode IN ('86010','86007') THEN 'Payment Solutions Sr Rep'
                WHEN Employee.JobCode IN ('79012','79015') THEN 'Consumer Credit Card Rep'
                WHEN Employee.JobCode IN ('79005','79011','80015','80025','73015','80009','80007') THEN 'Consumer Mgmt 1'
                WHEN Employee.JobCode IN ('79009','79010') THEN 'Consumer Rep 1'
                WHEN Employee.JobCode IN ('79008','80050','80011','73014') THEN 'Consumer Rep 2'
                WHEN Employee.JobCode IN ('79007','80010','73016') THEN 'Consumer Rep 3'
                WHEN Employee.JobCode IN ('79030','80002','80020','79031','80004') THEN 'Consumer Mgmt 2'
                WHEN Employee.JobCode IN ('1118','11002') THEN 'Branch CUA 2'
                WHEN Employee.JobCode IN ('11004') THEN 'VRC CUA 4'
                WHEN Employee.JobCode IN ('89153','89154','89132','89152') THEN 'E-Services Supervisor'
                WHEN Employee.JobCode IN ('84006','84033','84031','84032') THEN 'IT Security'
                WHEN Employee.JobCode IN ('84040','84009','84008','84015','84035') THEN 'IT System Admin'
                WHEN Employee.JobCode IN ('84025','84028') THEN 'IT Developer'
                WHEN Employee.JobCode IN ('84018','84021','84022','84020') THEN 'IT Business Analyst'
                WHEN Employee.JobCode IN ('84005','84010','84014') THEN 'IT Service Desk'
                WHEN Employee.JobCode IN ('79032','85003') THEN 'Mortgage Mgmt 2'
                WHEN Employee.JobCode IN ('11007') THEN 'Branch Management/Lead CUA OR VRC Upper Management'
                WHEN Employee.JobCode IN ('83004') THEN 'MRC Manager'
                WHEN Employee.JobCode IN ('86004','86006','86005') THEN 'Payment Solutions Supervisor'
                WHEN Employee.JobCode IN ('86009','86008') THEN 'Payment Solutions Rep'
                WHEN Employee.JobCode IN ('73005') THEN 'Branch District Management'
                WHEN Employee.JobCode IN ('87020','87003','87006','87002','870010','87021') THEN 'Loss Mitigation Supervisor'
                WHEN Employee.JobCode IN ('87017','87019') THEN 'Loss Mitigation Member Advocate/Rep'
                WHEN Employee.JobCode IN ('87014','87011','87018') THEN 'Loss Mitigation - Specialized'
                WHEN Employee.JobCode IN ('90008') THEN 'Strat-Mgmt'
                WHEN Employee.JobCode IN ('89120','83030') THEN 'E-Services Rep'
                WHEN Employee.JobCode IN ('83007','83011') THEN 'MRC I'
                WHEN Employee.JobCode IN ('83008') THEN 'MRC II'
                WHEN Employee.JobCode IN ('83006','83025') THEN 'MRC Supervisor'
                WHEN Employee.JobCode IN ('85008','85041','85022','85006','85007','85012','85018','85019','85002','85032') THEN 'Mortgage Rep 3'
                WHEN Employee.JobCode IN ('85020','85024','85013','85016','85017','85011','85036') THEN 'Mortgage Rep 2'
                WHEN Employee.JobCode IN ('85010','85030') THEN 'Mortgage Rep 1'
                WHEN Employee.JobCode IN ('85025') THEN 'Mortgage Mgmt 1'
                WHEN Employee.JobCode IN ('79040') THEN 'Senior Lending Management'
                WHEN Employee.JobCode IN ('117') THEN 'VRC Teller'
                WHEN Employee.JobCode IN ('73009') THEN 'VRC Upper Management'
                WHEN Employee.JobCode IN ('83010') THEN 'MRC Supervisor'
                ELSE NULL
            END AS [Keystone_Expected_Role_For_Job_Title]
        FROM
            [STAGING].[S1_KEY_USER] AS [User]
        LEFT JOIN
            [STAGING].[S1_KEY_ROLE] AS RoleDesc
            ON [User].[ROLE_SERIAL] = RoleDesc.[SERIAL]
        LEFT JOIN
            [STAGING].[S1_KEY_ROLE] AS TestRoleDesc
            ON [User].[TEST_ROLE_SERIAL] = TestRoleDesc.[SERIAL]
        LEFT JOIN
            [CUFX].[EMPLOYEE] AS Employee
            ON Employee.[SAMAccountName] = [User].[USERNAME]
        WHERE
            Employee.[EmploymentStatus] IN ('Active', 'On Leave')
        """

        try:
            connection_string = self._get_connection_string()

            with pyodbc.connect(
                connection_string, timeout=self.connection_timeout
            ) as conn:
                cursor = conn.cursor()
                cursor.execute(query)

                columns = [column[0] for column in cursor.description]

                results = []
                for row in cursor.fetchall():
                    row_dict = {}
                    for i, value in enumerate(row):
                        column_name = columns[i]
                        if isinstance(value, datetime):
                            row_dict[column_name] = value.isoformat()
                        else:
                            row_dict[column_name] = value
                    results.append(row_dict)

                logger.info(f"Retrieved {len(results)} records from data warehouse")
                return results

        except pyodbc.Error as e:
            logger.error(f"ODBC error executing keystone query: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error executing keystone query: {str(e)}")
            raise

    # --- Employee profile loading ---

    def load_keystone_employee_data(self) -> List[Dict[str, Any]]:
        """
        Load employee data from Azure SQL Server data warehouse.

        Returns:
            List of employee records from Azure SQL Server
        """
        logger.info("Loading employee data from Azure SQL Server")

        try:
            # Execute the Keystone query directly against Azure SQL
            raw_records = self.execute_keystone_query()

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
            # Detect whether we are inside a running event loop. asyncio.run()
            # cannot be called from within one, so we fall back to sync
            # processing in that case.
            try:
                asyncio.get_running_loop()
                # We're already in an async context — sync fallback
                logger.info("Running in existing event loop, using sync processing")
                return self._refresh_profiles_sync(employee_records)
            except RuntimeError:
                # No running loop in current thread — safe to call asyncio.run()
                return asyncio.run(self._refresh_profiles_async(employee_records))

        except Exception as e:
            logger.error(f"Error during employee profiles refresh: {str(e)}")
            raise
        finally:
            # Phase 06 D-04 / D-07: piggyback the daily SKU catalog refresh on
            # the existing employee-profiles refresh cycle. Reuses the existing
            # 24h schedule — no new thread, no new TTL layer. Wrapped in
            # try/except so a SKU-cache failure cannot crash the parent job.
            try:
                if current_app is not None:
                    sku_catalog = current_app.container.get("sku_catalog")
                    if sku_catalog.needs_refresh():
                        sku_catalog.refresh()
            except Exception as e:
                logger.error(
                    f"SKU catalog refresh failed: {str(e)}", exc_info=True
                )

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

        Returns:
            Dictionary with connection test results
        """
        try:
            success = self.test_connection()
            return {
                "success": success,
                "message": "Connection successful"
                if success
                else "Connection failed - check logs and credentials",
                "connection_available": success,
            }
        except Exception as e:
            logger.error(f"Error testing data warehouse connection: {str(e)}")
            return {
                "success": False,
                "message": f"Connection test failed: {str(e)}",
                "connection_available": False,
            }

    # --- Cache compatibility wrappers for admin cache UI ---

    def get_cache_status(self) -> Dict[str, Any]:
        """
        Get cache status in the shape expected by the admin cache UI.

        Returns:
            Dictionary with cache statistics matching the interface used
            by app/blueprints/admin/cache.py.
        """
        stats = self.get_cache_stats()
        return {
            "total_records": stats.get("total_records", 0),
            "record_count": stats.get("record_count", 0),
            "last_updated": stats.get("last_updated"),
            "refresh_status": stats.get("refresh_status", "unknown"),
        }

    def refresh_cache(self) -> Dict[str, int]:
        """
        Refresh data warehouse / employee profiles cache.

        Returns:
            Dictionary with refresh statistics: total_records, cached_records.
        """
        try:
            results = self.execute_keystone_query()
            refresh_stats = self.refresh_all_profiles()
            stored_count = refresh_stats.get("success", 0)
            logger.info(f"Cached {stored_count} data warehouse records")
            return {"total_records": len(results), "cached_records": stored_count}
        except Exception as e:
            logger.error(f"Error refreshing data warehouse cache: {str(e)}")
            raise

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
