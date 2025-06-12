"""
DEPRECATED: Data warehouse service for Azure SQL Server integration.

This module is deprecated. The core functionality for employee profile management
has been consolidated into `app.services.refresh_employee_profiles.py`.

Use `EmployeeProfilesRefreshService.load_keystone_employee_data()` instead of
`DataWarehouseService.execute_keystone_query()` for new code.

The `employee_profiles_service` now owns all logic to construct complete
employee profiles from multiple data sources.
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

try:
    import pyodbc  # type: ignore[import-not-found]
except ImportError:
    pyodbc = None
from app.services.base import BaseCacheService
from app.utils.error_handler import handle_service_errors

logger = logging.getLogger(__name__)


class DataWarehouseService(BaseCacheService):
    """Service for connecting to Azure SQL Server data warehouse."""

    def __init__(self):
        super().__init__(config_prefix="data_warehouse")
        if pyodbc is None:
            logger.warning(
                "pyodbc not available - data warehouse functionality disabled"
            )

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

    @property
    def cache_refresh_period(self) -> int:
        """Override base class to use hours configuration."""
        return int(self.cache_refresh_hours * 3600)  # Convert hours to seconds

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

        try:
            connection_string = self._get_connection_string()

            with pyodbc.connect(
                connection_string, timeout=self.connection_timeout
            ) as conn:
                cursor = conn.cursor()
                # Simple test query
                cursor.execute("SELECT 1 as test")
                result = cursor.fetchone()

                if result and result[0] == 1:
                    logger.debug("Data warehouse connection test successful")
                    return True
                else:
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

                # Get column names
                columns = [column[0] for column in cursor.description]

                # Fetch all results and convert to list of dictionaries
                results = []
                for row in cursor.fetchall():
                    row_dict = {}
                    for i, value in enumerate(row):
                        column_name = columns[i]
                        # Convert datetime objects to ISO format strings
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

    def refresh_cache(self) -> Dict[str, int]:
        """
        Refresh the data warehouse cache.

        Returns:
            Dictionary with refresh statistics
        """
        try:
            # Execute the query to get fresh data
            results = self.execute_keystone_query()

            # Legacy cache functionality removed - use employee_profiles service instead
            try:
                from app.services.refresh_employee_profiles import (
                    employee_profiles_service,
                )

                refresh_stats = employee_profiles_service.refresh_all_profiles()
                stored_count = refresh_stats.get("success", 0)
            except ImportError:
                logger.warning("Employee profiles service not available")
                stored_count = 0

            logger.info(f"Cached {stored_count} data warehouse records")

            return {"total_records": len(results), "cached_records": stored_count}

        except Exception as e:
            logger.error(f"Error refreshing data warehouse cache: {str(e)}")
            raise

    def get_user_data(self, upn: str) -> Optional[Dict[str, Any]]:
        """
        Get cached user data by UPN from PostgreSQL cache.
        This method does not require SQL Server connectivity.

        Args:
            upn: The UPN to look up

        Returns:
            User data dictionary or None if not found
        """
        try:
            # Use consolidated employee profiles service
            from app.services.refresh_employee_profiles import employee_profiles_service

            profile = employee_profiles_service.get_employee_profile(upn)
            if profile:
                return profile

            logger.debug(f"No employee profile found for UPN: {upn}")
            return None

        except Exception as e:
            logger.error(
                f"Error getting cached data warehouse user data for {upn}: {str(e)}"
            )
            return None

    def get_cache_status(self) -> Dict[str, Any]:
        """
        Get current cache status.

        Returns:
            Dictionary with cache statistics
        """
        try:
            # Use consolidated employee profiles service
            from app.services.refresh_employee_profiles import employee_profiles_service

            stats = employee_profiles_service.get_cache_stats()
            last_updated_str = stats.get("last_updated")

            # Parse datetime string if needed
            last_updated = None
            if last_updated_str:
                try:
                    from datetime import datetime

                    last_updated = datetime.fromisoformat(
                        last_updated_str.replace("Z", "+00:00")
                    )
                except (ValueError, AttributeError):
                    last_updated = None

            # Handle None or naive datetime
            needs_refresh = True
            if last_updated:
                if last_updated.tzinfo is None:
                    # Make it timezone aware
                    last_updated = last_updated.replace(tzinfo=timezone.utc)
                # Check if cache is older than refresh interval
                refresh_hours = float(self._get_config("cache_refresh_hours", "6"))
                age = datetime.now(timezone.utc) - last_updated
                needs_refresh = age.total_seconds() > (refresh_hours * 3600)

            return {
                "total_records": stats.get("total_records", 0),
                "last_updated": last_updated.isoformat() if last_updated else None,
                "record_count": stats.get(
                    "total_records", 0
                ),  # Add for frontend compatibility
                "refresh_status": "needs_refresh" if needs_refresh else "ready",
            }

        except Exception as e:
            logger.error(f"Error getting data warehouse cache status: {str(e)}")
            return {
                "total_records": 0,
                "record_count": 0,
                "last_updated": None,
                "refresh_status": "error",
                "error": str(e),
            }


# Create singleton instance
data_warehouse_service = DataWarehouseService()
