"""
Job Role Compliance Data Warehouse Service

This service integrates with the data warehouse to pull job codes, roles,
and employee assignments for compliance checking.
"""

import logging
from typing import Dict, Any, List
from datetime import datetime, timezone

try:
    import pyodbc  # type: ignore[import-not-found]
except ImportError:
    pyodbc = None

from app.database import db
from app.services.base import BaseAPIService
from app.utils.error_handler import handle_service_errors
from app.models.job_role_compliance import (
    JobCode,
    SystemRole,
    EmployeeRoleAssignment,
)

logger = logging.getLogger(__name__)


class JobRoleWarehouseService(BaseAPIService):
    """Service for syncing job role compliance data from the data warehouse."""

    def __init__(self):
        super().__init__(config_prefix="data_warehouse")
        if pyodbc is None:
            logger.warning(
                "pyodbc not available - job role warehouse functionality disabled"
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
        if pyodbc is None:
            logger.error("pyodbc not available")
            return False

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
                cursor.execute("SELECT 1 as test")
                result = cursor.fetchone()

                if result and result[0] == 1:
                    logger.debug("Job role warehouse connection test successful")
                    return True
                else:
                    logger.error("Test query returned unexpected result")
                    return False

        except pyodbc.Error as e:
            logger.error(f"ODBC error testing connection: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Error testing connection: {str(e)}")
            return False

    @handle_service_errors(raise_errors=True)
    def sync_job_codes(self) -> Dict[str, int]:
        """
        Sync job codes from the data warehouse to PostgreSQL.

        Returns:
            Dictionary with sync statistics
        """
        if pyodbc is None:
            raise RuntimeError("pyodbc not available")

        query = """
        SELECT DISTINCT
            emp.JobCode,
            emp.Position,
            emp.Department,
            emp.EmployeeNumber,
            emp.PhysicalLocation,
            CASE
                WHEN emp.EmploymentStatus IN ('Active', 'On Leave') THEN 1
                ELSE 0
            END as IsActive
        FROM [CUFX].[EMPLOYEE] emp
        WHERE emp.JobCode IS NOT NULL
        ORDER BY emp.JobCode
        """

        try:
            connection_string = self._get_connection_string()

            with pyodbc.connect(
                connection_string, timeout=self.connection_timeout
            ) as conn:
                cursor = conn.cursor()
                cursor.execute(query)

                created_count = 0
                updated_count = 0
                sync_time = datetime.now(timezone.utc)

                for row in cursor.fetchall():
                    job_code = row[0]
                    if not job_code:
                        continue

                    # Find or create job code
                    job_code_obj = JobCode.query.filter_by(job_code=job_code).first()

                    if job_code_obj:
                        # Update existing
                        job_code_obj.job_title = (
                            row[1] or job_code_obj.job_title
                        )  # Position
                        job_code_obj.department = row[2]  # Department
                        job_code_obj.job_family = row[
                            3
                        ]  # EmployeeNumber (stored in job_family)
                        job_code_obj.job_level = row[
                            4
                        ]  # PhysicalLocation (stored in job_level)
                        job_code_obj.description = (
                            f"Employee: {row[3]}, Location: {row[4]}"  # Combine info
                        )
                        job_code_obj.is_active = bool(row[5])  # IsActive
                        job_code_obj.synced_at = sync_time
                        updated_count += 1
                    else:
                        # Create new
                        job_code_obj = JobCode(
                            job_code=job_code,
                            job_title=row[1] or f"Job Code {job_code}",  # Position
                            department=row[2],  # Department
                            job_family=row[3],  # EmployeeNumber (stored in job_family)
                            job_level=row[4],  # PhysicalLocation (stored in job_level)
                            description=f"Employee: {row[3]}, Location: {row[4]}",  # Combine info
                            is_active=bool(row[5]),  # IsActive
                            synced_at=sync_time,
                        )
                        job_code_obj.save(commit=False)
                        created_count += 1

                # Commit all changes
                db.session.commit()

                logger.info(
                    f"Job code sync completed: {created_count} created, {updated_count} updated"
                )
                return {"created": created_count, "updated": updated_count}

        except pyodbc.Error as e:
            logger.error(f"ODBC error syncing job codes: {str(e)}")
            db.session.rollback()
            raise
        except Exception as e:
            logger.error(f"Error syncing job codes: {str(e)}")
            db.session.rollback()
            raise

    @handle_service_errors(raise_errors=True)
    def sync_keystone_roles(self) -> Dict[str, int]:
        """
        Sync Keystone roles from the data warehouse to PostgreSQL.

        Returns:
            Dictionary with sync statistics
        """
        if pyodbc is None:
            raise RuntimeError("pyodbc not available")

        query = """
        SELECT DISTINCT
            role.SERIAL as RoleId,
            role.DESCRIPTION as RoleName
        FROM [STAGING].[S1_KEY_ROLE] role
        WHERE role.DESCRIPTION IS NOT NULL
        ORDER BY role.DESCRIPTION
        """

        try:
            connection_string = self._get_connection_string()

            with pyodbc.connect(
                connection_string, timeout=self.connection_timeout
            ) as conn:
                cursor = conn.cursor()
                cursor.execute(query)

                created_count = 0
                updated_count = 0
                sync_time = datetime.now(timezone.utc)

                for row in cursor.fetchall():
                    role_name = row[1]
                    if not role_name:
                        continue

                    # Find or create system role
                    role_obj, created = SystemRole.find_or_create(
                        role_name=role_name,
                        system_name="keystone",
                        role_type="application",
                        synced_at=sync_time,
                    )

                    if created:
                        created_count += 1
                    else:
                        # Update existing
                        role_obj.synced_at = sync_time
                        role_obj.save(commit=False)
                        updated_count += 1

                # Commit all changes
                db.session.commit()

                logger.info(
                    f"Keystone role sync completed: {created_count} created, {updated_count} updated"
                )
                return {"created": created_count, "updated": updated_count}

        except pyodbc.Error as e:
            logger.error(f"ODBC error syncing Keystone roles: {str(e)}")
            db.session.rollback()
            raise
        except Exception as e:
            logger.error(f"Error syncing Keystone roles: {str(e)}")
            db.session.rollback()
            raise

    @handle_service_errors(raise_errors=True)
    def sync_employee_keystone_assignments(self) -> Dict[str, int]:
        """
        Sync current Keystone role assignments for all employees.

        Returns:
            Dictionary with sync statistics
        """
        if pyodbc is None:
            raise RuntimeError("pyodbc not available")

        query = """
        SELECT 
            emp.UPN,
            LiveRole.DESCRIPTION as LiveRoleName,
            TestRole.DESCRIPTION as TestRoleName,
            emp.JobCode,
            user_data.LAST_LOGIN_TIME,
            user_data.LOGIN_LOCK
        FROM [CUFX].[EMPLOYEE] emp
        LEFT JOIN [STAGING].[S1_KEY_USER] user_data 
            ON user_data.USERNAME = emp.SAMAccountName
        LEFT JOIN [STAGING].[S1_KEY_ROLE] LiveRole 
            ON user_data.ROLE_SERIAL = LiveRole.SERIAL
        LEFT JOIN [STAGING].[S1_KEY_ROLE] TestRole 
            ON user_data.TEST_ROLE_SERIAL = TestRole.SERIAL
        WHERE emp.EmploymentStatus IN ('Active', 'On Leave')
        AND emp.UPN IS NOT NULL
        ORDER BY emp.UPN
        """

        try:
            connection_string = self._get_connection_string()

            with pyodbc.connect(
                connection_string, timeout=self.connection_timeout
            ) as conn:
                cursor = conn.cursor()
                cursor.execute(query)

                total_employees = 0
                updated_assignments = 0

                for row in cursor.fetchall():
                    employee_upn = row[0]
                    live_role = row[1]
                    test_role = row[2]

                    if not employee_upn:
                        continue

                    total_employees += 1

                    # Collect current roles for this employee
                    current_roles = []

                    if live_role:
                        current_roles.append(
                            {
                                "role_name": live_role,
                                "assignment_type": "direct",
                                "assignment_source": "live_role",
                            }
                        )

                    if test_role and test_role != live_role:
                        current_roles.append(
                            {
                                "role_name": test_role,
                                "assignment_type": "direct",
                                "assignment_source": "test_role",
                            }
                        )

                    # Sync role assignments for this employee
                    if current_roles:
                        result = EmployeeRoleAssignment.sync_employee_roles(
                            employee_upn=employee_upn,
                            system_name="keystone",
                            current_roles=current_roles,
                            commit=False,
                        )
                        updated_assignments += result["created"] + result["updated"]

                # Commit all changes
                db.session.commit()

                logger.info(
                    f"Keystone assignment sync completed: {total_employees} employees processed, {updated_assignments} assignments updated"
                )
                return {
                    "employees_processed": total_employees,
                    "assignments_updated": updated_assignments,
                }

        except pyodbc.Error as e:
            logger.error(f"ODBC error syncing Keystone assignments: {str(e)}")
            db.session.rollback()
            raise
        except Exception as e:
            logger.error(f"Error syncing Keystone assignments: {str(e)}")
            db.session.rollback()
            raise

    @handle_service_errors(raise_errors=True)
    def get_expected_roles_mapping(self) -> Dict[str, List[str]]:
        """
        Get the expected Keystone roles for each job code based on the data warehouse logic.

        Returns:
            Dictionary mapping job codes to expected role names
        """
        if pyodbc is None:
            raise RuntimeError("pyodbc not available")

        # This is the same CASE statement logic from the existing data warehouse service
        query = """
        SELECT DISTINCT
            emp.JobCode,
            CASE 
                WHEN emp.JobCode IN ('81015','81014','81004','81030','81003') THEN 'Accounting Mgmt'
                WHEN emp.JobCode IN ('80008','78004','780010','76012','88016','78006','78008','78016','76013','76008','74033','90006','78030','78013','78010','76011','74047','74036','74046','74039','74038','74034','74048','74045','74037','74042','74041','74049','74040','74043','74044','76002','74032','74035','76004') THEN 'Inquiry'
                WHEN emp.JobCode IN ('1111') THEN 'Branch Head Teller'
                WHEN emp.JobCode IN ('3102','7103','1101','11005','11006','11007','11008') THEN 'Branch Management/Lead CUA'
                WHEN emp.JobCode IN ('73008','73006','73001','73003') THEN 'Branch Ops Upper Mgmt'
                WHEN emp.JobCode IN ('1115','87001','90007','83009','85031','78003','9999') THEN 'Not Determined'
                WHEN emp.JobCode IN ('1112') THEN 'Branch CUA 1'
                WHEN emp.JobCode IN ('1116','11001') THEN 'CUA 1'
                WHEN emp.JobCode IN ('5110','11003') THEN 'Branch Supervisor/Branch CUA 3'
                WHEN emp.JobCode IN ('77009','77015','77011','77014','71011','71010','77012','88004','90002','72030','77010','72010','77008','77007','77006','88008','88007','88006','70001','84030','77016','77003') THEN 'Inquiry-Audit'
                WHEN emp.JobCode IN ('78012','9999INT','8','13','15','16','76014','76005','76003','76007','76006','77013','1','74001','84012','3','3117','76010','10','4','6','11','10001','9999EXT') THEN 'No Access Granted'
                WHEN emp.JobCode IN ('86010','86007') THEN 'Payment Solutions Sr Rep'
                WHEN emp.JobCode IN ('79012','79015') THEN 'Consumer Credit Card Rep'
                WHEN emp.JobCode IN ('79005','79011','80015','80025','73015','80009','80007') THEN 'Consumer Mgmt 1'
                WHEN emp.JobCode IN ('79009','79010') THEN 'Consumer Rep 1'
                WHEN emp.JobCode IN ('79008','80050','80011','73014') THEN 'Consumer Rep 2'
                WHEN emp.JobCode IN ('79007','80010','73016') THEN 'Consumer Rep 3'
                WHEN emp.JobCode IN ('79030','80002','80020','79031','80004') THEN 'Consumer Mgmt 2'
                WHEN emp.JobCode IN ('1118','11002') THEN 'Branch CUA 2'
                WHEN emp.JobCode IN ('11004') THEN 'VRC CUA 4'
                WHEN emp.JobCode IN ('89153','89154','89132','89152') THEN 'E-Services Supervisor'
                WHEN emp.JobCode IN ('84006','84033','84031','84032') THEN 'IT Security'
                WHEN emp.JobCode IN ('84040','84009','84008','84015','84035') THEN 'IT System Admin'
                WHEN emp.JobCode IN ('84025','84028') THEN 'IT Developer'
                WHEN emp.JobCode IN ('84018','84021','84022','84020') THEN 'IT Business Analyst'
                WHEN emp.JobCode IN ('84005','84010','84014') THEN 'IT Service Desk'
                WHEN emp.JobCode IN ('79032','85003') THEN 'Mortgage Mgmt 2'
                WHEN emp.JobCode IN ('11007') THEN 'Branch Management/Lead CUA OR VRC Upper Management'
                WHEN emp.JobCode IN ('83004') THEN 'MRC Manager'
                WHEN emp.JobCode IN ('86004','86006','86005') THEN 'Payment Solutions Supervisor'
                WHEN emp.JobCode IN ('86009','86008') THEN 'Payment Solutions Rep'
                WHEN emp.JobCode IN ('73005') THEN 'Branch District Management'
                WHEN emp.JobCode IN ('87020','87003','87006','87002','870010','87021') THEN 'Loss Mitigation Supervisor'
                WHEN emp.JobCode IN ('87017','87019') THEN 'Loss Mitigation Member Advocate/Rep'
                WHEN emp.JobCode IN ('87014','87011','87018') THEN 'Loss Mitigation - Specialized'
                WHEN emp.JobCode IN ('90008') THEN 'Strat-Mgmt'
                WHEN emp.JobCode IN ('89120','83030') THEN 'E-Services Rep'
                WHEN emp.JobCode IN ('83007','83011') THEN 'MRC I'
                WHEN emp.JobCode IN ('83008') THEN 'MRC II'
                WHEN emp.JobCode IN ('83006','83025') THEN 'MRC Supervisor'
                WHEN emp.JobCode IN ('85008','85041','85022','85006','85007','85012','85018','85019','85002','85032') THEN 'Mortgage Rep 3'
                WHEN emp.JobCode IN ('85020','85024','85013','85016','85017','85011','85036') THEN 'Mortgage Rep 2'
                WHEN emp.JobCode IN ('85010','85030') THEN 'Mortgage Rep 1'
                WHEN emp.JobCode IN ('85025') THEN 'Mortgage Mgmt 1'
                WHEN emp.JobCode IN ('79040') THEN 'Senior Lending Management'
                WHEN emp.JobCode IN ('117') THEN 'VRC Teller'
                WHEN emp.JobCode IN ('73009') THEN 'VRC Upper Management'
                WHEN emp.JobCode IN ('83010') THEN 'MRC Supervisor'
                ELSE NULL
            END AS ExpectedRole
        FROM [CUFX].[EMPLOYEE] emp
        WHERE emp.EmploymentStatus IN ('Active', 'On Leave')
        AND emp.JobCode IS NOT NULL
        ORDER BY emp.JobCode
        """

        try:
            connection_string = self._get_connection_string()

            with pyodbc.connect(
                connection_string, timeout=self.connection_timeout
            ) as conn:
                cursor = conn.cursor()
                cursor.execute(query)

                expected_roles: Dict[str, List[str]] = {}
                for row in cursor.fetchall():
                    job_code = row[0]
                    expected_role = row[1]

                    if job_code and expected_role:
                        if job_code not in expected_roles:
                            expected_roles[job_code] = []
                        if expected_role not in expected_roles[job_code]:
                            expected_roles[job_code].append(expected_role)

                logger.info(
                    f"Retrieved expected roles for {len(expected_roles)} job codes"
                )
                return expected_roles

        except pyodbc.Error as e:
            logger.error(f"ODBC error getting expected roles mapping: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error getting expected roles mapping: {str(e)}")
            raise

    def sync_system_roles(self) -> Dict[str, int]:
        """
        Sync system roles (currently just Keystone roles).

        Returns:
            Dictionary with sync statistics
        """
        return self.sync_keystone_roles()  # type: ignore[no-any-return]

    def sync_all_compliance_data(self) -> Dict[str, Any]:
        """
        Sync all job role compliance data from the data warehouse.

        Returns:
            Dictionary with comprehensive sync statistics
        """
        logger.info("Starting full job role compliance data sync")
        start_time = datetime.now(timezone.utc)

        try:
            results = {}

            # Sync job codes
            logger.info("Syncing job codes...")
            results["job_codes"] = self.sync_job_codes()

            # Sync Keystone roles
            logger.info("Syncing Keystone roles...")
            results["keystone_roles"] = self.sync_keystone_roles()

            # Sync employee assignments
            logger.info("Syncing employee Keystone assignments...")
            results["keystone_assignments"] = self.sync_employee_keystone_assignments()

            # Calculate total duration
            end_time = datetime.now(timezone.utc)
            duration = int((end_time - start_time).total_seconds())

            results["sync_completed_at"] = end_time.isoformat()
            results["duration_seconds"] = duration
            results["status"] = "success"

            logger.info(
                f"Full job role compliance data sync completed in {duration} seconds"
            )
            return results

        except Exception as e:
            logger.error(f"Error during full sync: {str(e)}")
            results["status"] = "error"
            results["error"] = str(e)
            return results


# Create singleton instance
job_role_warehouse_service = JobRoleWarehouseService()
