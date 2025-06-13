"""
Compliance Checking Service

This service performs compliance checks by comparing expected role mappings
against actual role assignments across all systems.
"""

import logging
from typing import Dict, Any, List, Optional, Set
from datetime import datetime, timezone, timedelta
import uuid

from app.database import db
from app.services.base import BaseConfigurableService
from app.utils.error_handler import handle_service_errors
from app.models.job_role_compliance import (
    JobCode,
    JobRoleMapping,
    ComplianceCheck,
    ComplianceCheckRun,
    EmployeeRoleAssignment,
)
from app.models.employee_profiles import EmployeeProfiles

logger = logging.getLogger(__name__)


class ComplianceCheckingService(BaseConfigurableService):
    """Service for performing job role compliance checks."""

    def __init__(self):
        super().__init__(config_prefix="job_role_compliance")

    def _determine_violation_severity(
        self, mapping_type: str, compliance_status: str, priority: int = 1
    ) -> str:
        """
        Determine the severity level of a compliance violation.

        Args:
            mapping_type: The type of mapping (required, optional, prohibited)
            compliance_status: The compliance status
            priority: The mapping priority

        Returns:
            Severity level (low, medium, high, critical)
        """
        if compliance_status == "compliant":
            return "low"  # Not actually a violation

        # High severity violations
        if compliance_status == "has_prohibited":
            return "critical" if priority >= 3 else "high"

        if compliance_status == "missing_required":
            if priority >= 5:
                return "critical"
            elif priority >= 3:
                return "high"
            else:
                return "medium"

        # Unexpected roles are generally medium severity
        if compliance_status == "unexpected_role":
            return "medium" if priority >= 3 else "low"

        return "medium"  # Default

    def _determine_remediation_action(
        self, compliance_status: str, mapping_type: Optional[str] = None
    ) -> str:
        """
        Determine the recommended remediation action.

        Args:
            compliance_status: The compliance status
            mapping_type: The mapping type if applicable

        Returns:
            Remediation action string
        """
        if compliance_status == "compliant":
            return "no_action"

        if compliance_status == "missing_required":
            return "add_role"

        if compliance_status == "has_prohibited":
            return "remove_role"

        if compliance_status == "unexpected_role":
            return "manual_review"

        return "manual_review"

    @handle_service_errors(raise_errors=True)
    def check_employee_compliance(
        self, employee_upn: str, job_code: str, run_id: str, commit: bool = True
    ) -> List[ComplianceCheck]:
        """
        Check compliance for a single employee against their job code mappings.

        Args:
            employee_upn: Employee UPN
            job_code: Employee's job code
            run_id: The compliance check run ID
            commit: Whether to commit results immediately

        Returns:
            List of ComplianceCheck instances
        """
        compliance_checks: List[ComplianceCheck] = []

        # Get expected mappings for this job code
        expected_mappings = JobRoleMapping.get_active_mappings_for_job_code(job_code)
        if not expected_mappings:
            logger.debug(f"No role mappings found for job code {job_code}")
            return compliance_checks

        # Get actual role assignments for this employee
        actual_assignments = EmployeeRoleAssignment.get_roles_for_employee(employee_upn)

        # Group assignments by system for easier lookup
        assignments_by_system: Dict[str, Set[str]] = {}
        for assignment in actual_assignments:
            system = assignment.system_name
            if system not in assignments_by_system:
                assignments_by_system[system] = set()
            assignments_by_system[system].add(assignment.role_name)

        # Check each expected mapping
        for mapping in expected_mappings:
            system_name = mapping.system_role.system_name
            role_name = mapping.system_role.role_name
            mapping_type = mapping.mapping_type

            # Check if employee has this role
            has_role = (
                system_name in assignments_by_system
                and role_name in assignments_by_system[system_name]
            )

            # Determine compliance status
            if mapping_type == "required":
                compliance_status = "compliant" if has_role else "missing_required"
            elif mapping_type == "prohibited":
                compliance_status = "has_prohibited" if has_role else "compliant"
            elif mapping_type == "optional":
                compliance_status = "compliant"  # Optional roles are always compliant
            else:
                compliance_status = "unknown"

            # Create compliance check record
            check = ComplianceCheck(
                check_run_id=run_id,
                employee_upn=employee_upn,
                job_code=job_code,
                system_name=system_name,
                role_name=role_name,
                expected_mapping_type=mapping_type,
                actual_assignment=has_role,
                compliance_status=compliance_status,
                violation_severity=self._determine_violation_severity(
                    mapping_type, compliance_status, mapping.priority
                ),
                remediation_action=self._determine_remediation_action(
                    compliance_status, mapping_type
                ),
                notes=f"Priority: {mapping.priority}, Mapping ID: {mapping.id}",
            )

            check.save(commit=False)
            compliance_checks.append(check)

        # Check for unexpected roles (roles not in any mapping)
        expected_roles_by_system: Dict[str, Set[str]] = {}
        for mapping in expected_mappings:
            system = mapping.system_role.system_name
            if system not in expected_roles_by_system:
                expected_roles_by_system[system] = set()
            expected_roles_by_system[system].add(mapping.system_role.role_name)

        # Find unexpected roles
        for system_name, assigned_roles in assignments_by_system.items():
            expected_roles = expected_roles_by_system.get(system_name, set())
            unexpected_roles = assigned_roles - expected_roles

            for role_name in unexpected_roles:
                check = ComplianceCheck(
                    check_run_id=run_id,
                    employee_upn=employee_upn,
                    job_code=job_code,
                    system_name=system_name,
                    role_name=role_name,
                    expected_mapping_type=None,
                    actual_assignment=True,
                    compliance_status="unexpected_role",
                    violation_severity=self._determine_violation_severity(
                        "unexpected", "unexpected_role"
                    ),
                    remediation_action=self._determine_remediation_action(
                        "unexpected_role"
                    ),
                    notes="Role not defined in any job code mapping",
                )

                check.save(commit=False)
                compliance_checks.append(check)

        if commit:
            db.session.commit()

        return compliance_checks

    @handle_service_errors(raise_errors=True)
    def run_compliance_check(
        self,
        scope: str = "all",
        scope_filter: Optional[str] = None,
        started_by: str = "system",
        run_type: str = "manual",
    ) -> ComplianceCheckRun:
        """
        Run a compliance check across specified scope.

        Args:
            scope: Scope of the check (all, department, job_code, individual)
            scope_filter: Additional filter criteria
            started_by: User starting the check
            run_type: Type of run (manual, scheduled, triggered)

        Returns:
            ComplianceCheckRun instance
        """
        # Generate unique run ID
        run_id = f"compliance_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

        # Create the run record
        check_run = ComplianceCheckRun(
            run_id=run_id,
            run_type=run_type,
            scope=scope,
            scope_filter=scope_filter,
            started_by=started_by,
            status="running",
        )
        check_run.save()

        try:
            # Get employees to check based on scope
            employees_to_check = self._get_employees_for_scope(scope, scope_filter)

            check_run.total_employees = len(employees_to_check)
            check_run.save()

            logger.info(
                f"Starting compliance check {run_id} for {len(employees_to_check)} employees"
            )

            # Process employees in batches for better performance
            batch_size = 50
            total_checks = 0
            error_count = 0

            for i in range(0, len(employees_to_check), batch_size):
                batch = employees_to_check[i : i + batch_size]

                try:
                    # Process batch
                    for employee_data in batch:
                        employee_upn = employee_data["upn"]
                        job_code = employee_data["job_code"]

                        try:
                            checks = self.check_employee_compliance(
                                employee_upn=employee_upn,
                                job_code=job_code,
                                run_id=run_id,
                                commit=False,
                            )
                            total_checks += len(checks)
                        except Exception as e:
                            logger.error(
                                f"Error checking compliance for {employee_upn}: {str(e)}"
                            )
                            error_count += 1

                    # Commit batch
                    db.session.commit()
                    logger.debug(
                        f"Processed batch {i // batch_size + 1}, total checks: {total_checks}"
                    )

                except Exception as e:
                    logger.error(
                        f"Error processing batch {i // batch_size + 1}: {str(e)}"
                    )
                    db.session.rollback()
                    error_count += len(batch)

            # Update run statistics
            check_run.total_checks = total_checks
            check_run.error_count = error_count
            check_run.update_stats(commit=False)
            check_run.mark_completed()

            logger.info(
                f"Compliance check {run_id} completed: {total_checks} checks, {error_count} errors"
            )

        except Exception as e:
            logger.error(f"Error during compliance check {run_id}: {str(e)}")
            check_run.mark_failed(str(e))
            raise

        return check_run

    def _get_employees_for_scope(
        self, scope: str, scope_filter: Optional[str] = None
    ) -> List[Dict[str, str]]:
        """
        Get list of employees to check based on scope.

        Args:
            scope: Scope type
            scope_filter: Filter criteria

        Returns:
            List of employee dictionaries with upn and job_code
        """
        query = EmployeeProfiles.query.filter(EmployeeProfiles.ukg_job_code.isnot(None))

        if scope == "department" and scope_filter:
            # Filter by department - need to join with job codes table
            query = query.join(
                JobCode, EmployeeProfiles.ukg_job_code == JobCode.job_code
            ).filter(JobCode.department == scope_filter)

        elif scope == "job_code" and scope_filter:
            query = query.filter(EmployeeProfiles.ukg_job_code == scope_filter)

        elif scope == "individual" and scope_filter:
            query = query.filter(EmployeeProfiles.upn == scope_filter)

        # Get results
        employees = query.all()

        return [
            {"upn": emp.upn, "job_code": emp.ukg_job_code}
            for emp in employees
            if emp.upn and emp.ukg_job_code
        ]

    def get_compliance_summary(self, run_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get compliance summary statistics.

        Args:
            run_id: Specific run ID or None for latest

        Returns:
            Dictionary with summary statistics
        """
        # Get the run to summarize
        if run_id:
            check_run = ComplianceCheckRun.query.filter_by(run_id=run_id).first()
            if not check_run:
                raise ValueError(f"Compliance check run {run_id} not found")
        else:
            # Get latest completed run
            check_run = (
                ComplianceCheckRun.query.filter_by(status="completed")
                .order_by(ComplianceCheckRun.completed_at.desc())
                .first()
            )
            if not check_run:
                return {"error": "No completed compliance runs found"}

        # Get compliance checks for this run
        checks = ComplianceCheck.query.filter_by(check_run_id=check_run.run_id).all()

        # Calculate statistics
        total_checks = len(checks)
        compliant_checks = sum(1 for c in checks if c.compliance_status == "compliant")
        violation_checks = total_checks - compliant_checks

        # Group violations by type
        violation_types: Dict[str, int] = {}
        severity_counts: Dict[str, int] = {}
        system_violations: Dict[str, int] = {}

        for check in checks:
            if check.compliance_status != "compliant":
                # Count by violation type
                status = check.compliance_status
                violation_types[status] = violation_types.get(status, 0) + 1

                # Count by severity
                severity = check.violation_severity
                severity_counts[severity] = severity_counts.get(severity, 0) + 1

                # Count by system
                system = check.system_name
                system_violations[system] = system_violations.get(system, 0) + 1

        # Get top violating job codes
        job_code_violations = (
            db.session.query(
                ComplianceCheck.job_code, db.func.count(ComplianceCheck.id)
            )
            .filter(
                ComplianceCheck.check_run_id == check_run.run_id,
                ComplianceCheck.compliance_status != "compliant",
            )
            .group_by(ComplianceCheck.job_code)
            .order_by(db.func.count(ComplianceCheck.id).desc())
            .limit(10)
            .all()
        )

        return {
            "run_info": {
                "run_id": check_run.run_id,
                "started_at": check_run.started_at.isoformat(),
                "completed_at": check_run.completed_at.isoformat()
                if check_run.completed_at
                else None,
                "duration_seconds": check_run.duration_seconds,
                "started_by": check_run.started_by,
                "scope": check_run.scope,
                "scope_filter": check_run.scope_filter,
            },
            "summary": {
                "total_employees": check_run.total_employees,
                "total_checks": total_checks,
                "compliant_checks": compliant_checks,
                "violation_checks": violation_checks,
                "compliance_percentage": round(
                    (compliant_checks / total_checks * 100) if total_checks > 0 else 0,
                    2,
                ),
            },
            "violations": {
                "by_type": violation_types,
                "by_severity": severity_counts,
                "by_system": system_violations,
                "top_job_codes": dict(job_code_violations),
            },
        }

    def get_employee_compliance_report(self, employee_upn: str) -> Dict[str, Any]:
        """
        Get detailed compliance report for a specific employee.

        Args:
            employee_upn: Employee UPN

        Returns:
            Dictionary with employee compliance details
        """
        # Get employee profile
        profile = EmployeeProfiles.query.filter_by(upn=employee_upn).first()
        if not profile:
            raise ValueError(f"Employee profile not found for {employee_upn}")

        # Get latest compliance checks for this employee
        latest_checks = (
            ComplianceCheck.query.filter_by(employee_upn=employee_upn)
            .order_by(ComplianceCheck.created_at.desc())
            .limit(100)
            .all()
        )

        # Group by system and role
        checks_by_system: Dict[str, List[Dict[str, Any]]] = {}
        violations = []
        compliance_score = 0

        for check in latest_checks:
            system = check.system_name
            if system not in checks_by_system:
                checks_by_system[system] = []

            check_data = check.to_dict_with_employee_info()
            checks_by_system[system].append(check_data)

            if check.compliance_status == "compliant":
                compliance_score += 1
            else:
                violations.append(check_data)

        # Calculate compliance percentage
        total_checks = len(latest_checks)
        compliance_percentage = (
            round((compliance_score / total_checks * 100), 2)
            if total_checks > 0
            else 100
        )

        return {
            "employee": {
                "upn": employee_upn,
                "job_code": profile.ukg_job_code,
                "live_role": profile.live_role,
                "test_role": profile.test_role,
            },
            "compliance": {
                "total_checks": total_checks,
                "compliant_checks": compliance_score,
                "violation_count": len(violations),
                "compliance_percentage": compliance_percentage,
            },
            "checks_by_system": checks_by_system,
            "violations": violations,
        }

    @handle_service_errors(raise_errors=True)
    def schedule_compliance_check(
        self,
        scope: str = "all",
        scope_filter: Optional[str] = None,
        delay_seconds: int = 0,
    ) -> str:
        """
        Schedule a compliance check to run in the background.

        Args:
            scope: Scope of the check
            scope_filter: Filter criteria
            delay_seconds: Delay before running

        Returns:
            Run ID of the scheduled check
        """
        # For now, just run immediately in a background thread
        # In a production environment, this would use Celery or similar
        import threading

        def run_check():
            if delay_seconds > 0:
                import time

                time.sleep(delay_seconds)

            try:
                self.run_compliance_check(
                    scope=scope,
                    scope_filter=scope_filter,
                    run_type="scheduled",
                    started_by="scheduler",
                )
            except Exception as e:
                logger.error(f"Error in scheduled compliance check: {str(e)}")

        # Generate run ID for tracking
        run_id = f"scheduled_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

        # Start background thread
        thread = threading.Thread(target=run_check, daemon=True)
        thread.start()

        logger.info(f"Scheduled compliance check {run_id} with {delay_seconds}s delay")
        return run_id

    def cleanup_old_compliance_data(self, days_to_keep: int = 90) -> Dict[str, int]:
        """
        Clean up old compliance check data.

        Args:
            days_to_keep: Number of days of data to keep

        Returns:
            Dictionary with cleanup statistics
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_to_keep)

        # Delete old compliance checks
        deleted_checks = ComplianceCheck.query.filter(
            ComplianceCheck.created_at < cutoff_date
        ).delete()

        # Delete old completed runs
        deleted_runs = ComplianceCheckRun.query.filter(
            ComplianceCheckRun.completed_at < cutoff_date,
            ComplianceCheckRun.status == "completed",
        ).delete()

        db.session.commit()

        logger.info(
            f"Cleaned up {deleted_checks} old compliance checks and {deleted_runs} old runs"
        )
        return {"deleted_checks": deleted_checks, "deleted_runs": deleted_runs}


# Create singleton instance
compliance_checking_service = ComplianceCheckingService()
