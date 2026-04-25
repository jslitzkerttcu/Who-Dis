"""Boundary tests for ComplianceCheckingService (Plan 02-05 gap closure).

202 missed statements at start; this module targets ~50% coverage via 7 pure-helper
tests + DB-driven tests against the testcontainers Postgres. Pure helpers are the
cheap wins (no DB); the run/check methods exercise the full ORM round-trip.
"""
from datetime import datetime, timezone, timedelta

import pytest

from app.database import db
from app.models.employee_profiles import EmployeeProfiles
from app.models.job_role_compliance import (
    ComplianceCheck,
    ComplianceCheckRun,
    EmployeeRoleAssignment,
)
from app.services.compliance_checking_service import ComplianceCheckingService
from tests.factories.job_code import JobCodeFactory
from tests.factories.system_role import SystemRoleFactory
from tests.factories.job_role_mapping import JobRoleMappingFactory

pytestmark = pytest.mark.unit


@pytest.fixture
def svc(app, db_session):
    return ComplianceCheckingService()


# --- Pure helpers (no DB) -----------------------------------------------------


def test_determine_violation_severity_compliant_returns_low(svc):
    assert svc._determine_violation_severity("required", "compliant", priority=5) == "low"


def test_determine_violation_severity_prohibited_priority_3_returns_critical(svc):
    assert svc._determine_violation_severity("required", "has_prohibited", priority=3) == "critical"


def test_determine_violation_severity_prohibited_priority_1_returns_high(svc):
    assert svc._determine_violation_severity("required", "has_prohibited", priority=1) == "high"


def test_determine_violation_severity_missing_required_priority_5_returns_critical(svc):
    assert svc._determine_violation_severity("required", "missing_required", priority=5) == "critical"


def test_determine_violation_severity_missing_required_priority_3_returns_high(svc):
    assert svc._determine_violation_severity("required", "missing_required", priority=3) == "high"


def test_determine_violation_severity_missing_required_priority_1_returns_medium(svc):
    assert svc._determine_violation_severity("required", "missing_required", priority=1) == "medium"


def test_determine_violation_severity_unexpected_role_priority_3_returns_medium(svc):
    assert svc._determine_violation_severity("unexpected", "unexpected_role", priority=3) == "medium"


def test_determine_violation_severity_unexpected_role_low_priority(svc):
    assert svc._determine_violation_severity("unexpected", "unexpected_role", priority=1) == "low"


def test_determine_violation_severity_unknown_status_returns_medium(svc):
    assert svc._determine_violation_severity("required", "unknown_status", priority=1) == "medium"


def test_determine_remediation_action_compliant(svc):
    assert svc._determine_remediation_action("compliant") == "no_action"


def test_determine_remediation_action_missing_required(svc):
    assert svc._determine_remediation_action("missing_required") == "add_role"


def test_determine_remediation_action_has_prohibited(svc):
    assert svc._determine_remediation_action("has_prohibited") == "remove_role"


def test_determine_remediation_action_unexpected_role(svc):
    assert svc._determine_remediation_action("unexpected_role") == "manual_review"


def test_determine_remediation_action_default(svc):
    assert svc._determine_remediation_action("anything_else") == "manual_review"


# --- DB-driven paths ----------------------------------------------------------


def _seed_employee(upn: str, job_code: str) -> EmployeeProfiles:
    emp = EmployeeProfiles(upn=upn, ukg_job_code=job_code)
    db.session.add(emp)
    db.session.commit()
    return emp


def test_check_employee_compliance_no_mappings_returns_empty(svc, db_session):
    JobCodeFactory(job_code="NO-MAP")
    db.session.commit()
    _seed_employee("nobody@test.local", "NO-MAP")

    # Need a run row so the FK on ComplianceCheck.check_run_id is satisfied if any are created
    run = ComplianceCheckRun(run_id="r-empty", started_by="test", status="running")
    run.save()

    checks = svc.check_employee_compliance("nobody@test.local", "NO-MAP", "r-empty")
    assert checks == []


def test_check_employee_compliance_missing_required_role_creates_violation(svc, db_session):
    jc = JobCodeFactory(job_code="ENG-MR")
    sr = SystemRoleFactory(role_name="Admin", system_name="ad_groups", role_type="security_group")
    JobRoleMappingFactory(job_code=jc, system_role=sr, mapping_type="required", priority=3)
    db.session.commit()

    _seed_employee("alice@test.local", "ENG-MR")
    run = ComplianceCheckRun(run_id="r-mr", started_by="test", status="running")
    run.save()

    checks = svc.check_employee_compliance("alice@test.local", "ENG-MR", "r-mr")
    assert len(checks) == 1
    assert checks[0].compliance_status == "missing_required"
    assert checks[0].actual_assignment is False
    assert checks[0].violation_severity == "high"  # priority=3 → high
    assert checks[0].remediation_action == "add_role"


def test_check_employee_compliance_compliant_when_assignment_present(svc, db_session):
    jc = JobCodeFactory(job_code="ENG-OK")
    sr = SystemRoleFactory(role_name="Reader", system_name="ad_groups", role_type="security_group")
    JobRoleMappingFactory(job_code=jc, system_role=sr, mapping_type="required", priority=1)
    db.session.commit()

    _seed_employee("bob@test.local", "ENG-OK")
    # Pre-seed the role assignment
    EmployeeRoleAssignment(
        employee_upn="bob@test.local", system_name="ad_groups", role_name="Reader"
    ).save()

    run = ComplianceCheckRun(run_id="r-ok", started_by="test", status="running")
    run.save()

    checks = svc.check_employee_compliance("bob@test.local", "ENG-OK", "r-ok")
    assert len(checks) == 1
    assert checks[0].compliance_status == "compliant"


def test_check_employee_compliance_unexpected_role_flagged(svc, db_session):
    jc = JobCodeFactory(job_code="ENG-UR")
    sr_expected = SystemRoleFactory(role_name="Expected", system_name="ad_groups", role_type="security_group")
    JobRoleMappingFactory(job_code=jc, system_role=sr_expected, mapping_type="required", priority=1)
    db.session.commit()

    _seed_employee("eve@test.local", "ENG-UR")
    # Eve has the expected role + a rogue role
    EmployeeRoleAssignment(
        employee_upn="eve@test.local", system_name="ad_groups", role_name="Expected"
    ).save()
    EmployeeRoleAssignment(
        employee_upn="eve@test.local", system_name="ad_groups", role_name="Rogue"
    ).save()

    run = ComplianceCheckRun(run_id="r-ur", started_by="test", status="running")
    run.save()

    checks = svc.check_employee_compliance("eve@test.local", "ENG-UR", "r-ur")
    statuses = {c.compliance_status for c in checks}
    assert "compliant" in statuses
    assert "unexpected_role" in statuses


def test_run_compliance_check_creates_run_row(svc, db_session):
    # Empty scope (no employees). run_compliance_check should still create a run.
    run = svc.run_compliance_check(scope="all", started_by="test-runner")

    assert run.run_id.startswith("compliance_")
    assert run.status == "completed"
    assert run.started_by == "test-runner"
    persisted = ComplianceCheckRun.query.filter_by(run_id=run.run_id).first()
    assert persisted is not None
    assert persisted.completed_at is not None


def test_get_compliance_summary_with_run_id(svc, db_session):
    # Seed a completed run with 2 checks
    run = ComplianceCheckRun(
        run_id="r-summary",
        started_by="test",
        status="completed",
        total_employees=1,
    )
    run.completed_at = datetime.now(timezone.utc)
    run.save()
    ComplianceCheck(
        check_run_id="r-summary",
        employee_upn="x@test.local",
        job_code="JC1",
        system_name="ad_groups",
        role_name="r1",
        actual_assignment=True,
        compliance_status="compliant",
    ).save()
    ComplianceCheck(
        check_run_id="r-summary",
        employee_upn="x@test.local",
        job_code="JC1",
        system_name="ad_groups",
        role_name="r2",
        actual_assignment=False,
        compliance_status="missing_required",
        violation_severity="high",
    ).save()

    summary = svc.get_compliance_summary(run_id="r-summary")
    assert summary["run_info"]["run_id"] == "r-summary"
    assert summary["summary"]["total_checks"] == 2
    assert summary["summary"]["compliant_checks"] == 1
    assert summary["summary"]["violation_checks"] == 1
    assert summary["violations"]["by_type"]["missing_required"] == 1


def test_get_compliance_summary_unknown_run_id_raises(svc, db_session):
    with pytest.raises(ValueError, match="not found"):
        svc.get_compliance_summary(run_id="does-not-exist")


def test_get_compliance_summary_no_completed_runs_returns_error_dict(svc, db_session):
    result = svc.get_compliance_summary()
    assert "error" in result


def test_cleanup_old_compliance_data_deletes_old_rows(svc, db_session):
    # Old run (101 days ago)
    old_run = ComplianceCheckRun(run_id="r-old", started_by="test", status="completed")
    old_run.save()
    old_completed = datetime.now(timezone.utc) - timedelta(days=101)
    old_run.completed_at = old_completed
    db.session.commit()

    # Recent run
    recent_run = ComplianceCheckRun(run_id="r-recent", started_by="test", status="completed")
    recent_run.save()
    recent_run.completed_at = datetime.now(timezone.utc)
    db.session.commit()

    # An old check
    old_check = ComplianceCheck(
        check_run_id="r-old",
        employee_upn="z@test.local",
        job_code="JC",
        system_name="ad_groups",
        role_name="r",
        actual_assignment=True,
        compliance_status="compliant",
    )
    old_check.save()
    db.session.execute(
        db.text("UPDATE compliance_checks SET created_at = :ts WHERE id = :id"),
        {"ts": datetime.now(timezone.utc) - timedelta(days=101), "id": old_check.id},
    )
    db.session.commit()

    result = svc.cleanup_old_compliance_data(days_to_keep=90)
    assert result["deleted_runs"] >= 1
    assert result["deleted_checks"] >= 1
    # Recent run still present
    assert ComplianceCheckRun.query.filter_by(run_id="r-recent").first() is not None
