"""Unit tests for WorkflowService (Phase 11, Plan 01).

Covers onboarding/offboarding generation, item completion/skip,
auto-completion, dashboard stats, and cancellation.
"""

from datetime import datetime, timezone, timedelta, date

import pytest

from app.database import db
from app.services.workflow_service import WorkflowService
from tests.factories.job_code import JobCodeFactory
from tests.factories.system_role import SystemRoleFactory
from tests.factories.job_role_mapping import JobRoleMappingFactory
from tests.factories.workflow import (
    WorkflowFactory,
    WorkflowItemFactory,
    StandardOffboardingItemFactory,
)

pytestmark = pytest.mark.unit


@pytest.fixture
def svc(app, db_session):
    """Return a fresh WorkflowService instance."""
    return WorkflowService()


# --- generate_onboarding ---------------------------------------------------


def test_generate_onboarding(svc):
    """Onboarding creates items for required/optional mappings, excludes prohibited."""
    jc = JobCodeFactory(job_code="OB001", job_title="Teller")
    sr_req1 = SystemRoleFactory(role_name="TellerRole", system_name="keystone")
    sr_req2 = SystemRoleFactory(role_name="CashAccess", system_name="ad_groups")
    sr_opt = SystemRoleFactory(role_name="OptionalTool", system_name="genesys")
    sr_prohib = SystemRoleFactory(role_name="AdminOnly", system_name="keystone")

    JobRoleMappingFactory(
        job_code=jc, system_role=sr_req1, mapping_type="required"
    )
    JobRoleMappingFactory(
        job_code=jc, system_role=sr_req2, mapping_type="required"
    )
    JobRoleMappingFactory(
        job_code=jc, system_role=sr_opt, mapping_type="optional"
    )
    JobRoleMappingFactory(
        job_code=jc, system_role=sr_prohib, mapping_type="prohibited"
    )

    wf = svc.generate_onboarding(
        employee_name="Jane Doe",
        employee_email="jane@test.com",
        job_code="OB001",
        created_by="admin@test.com",
    )

    assert wf.workflow_type == "onboarding"
    assert wf.status == "active"
    assert wf.job_title == "Teller"
    assert len(wf.items) == 3  # prohibited excluded

    # Required items use "Assign:" prefix
    required_items = [i for i in wf.items if "Assign:" in i.item_text]
    assert len(required_items) == 2

    # Optional items use "Consider assigning:" prefix
    optional_items = [
        i for i in wf.items if "Consider assigning:" in i.item_text
    ]
    assert len(optional_items) == 1

    # All items should be "add" action type
    assert all(i.action_type == "add" for i in wf.items)
    assert all(i.item_source == "role_mapping" for i in wf.items)


def test_generate_onboarding_no_mappings(svc):
    """Raises ValueError when no active mappings exist for the job code."""
    with pytest.raises(ValueError, match="No active role mappings found"):
        svc.generate_onboarding(
            employee_name="No One",
            employee_email=None,
            job_code="NONEXISTENT",
            created_by="admin@test.com",
        )


def test_generate_onboarding_nullable_email(svc):
    """Employee email can be None for net-new hires (D-03)."""
    jc = JobCodeFactory(job_code="OB002", job_title="New Hire Role")
    sr = SystemRoleFactory(
        role_name="BasicAccess", system_name="ad_groups",
        role_type="security_group",
    )
    JobRoleMappingFactory(job_code=jc, system_role=sr, mapping_type="required")

    wf = svc.generate_onboarding(
        employee_name="New Hire",
        employee_email=None,
        job_code="OB002",
        created_by="admin@test.com",
    )
    assert wf.employee_email is None
    assert len(wf.items) == 1


# --- generate_offboarding ---------------------------------------------------


def test_generate_offboarding(svc):
    """Offboarding creates role removal items plus standard offboarding items."""
    jc = JobCodeFactory(job_code="OFF01", job_title="Departing Role")
    sr1 = SystemRoleFactory(
        role_name="RoleA", system_name="keystone", role_type="application"
    )
    sr2 = SystemRoleFactory(
        role_name="RoleB", system_name="ad_groups", role_type="security_group"
    )
    JobRoleMappingFactory(job_code=jc, system_role=sr1, mapping_type="required")
    JobRoleMappingFactory(job_code=jc, system_role=sr2, mapping_type="optional")

    # Create standard offboarding items
    StandardOffboardingItemFactory(item_text="Collect badge", sort_order=0)
    StandardOffboardingItemFactory(item_text="Disable VPN", sort_order=1)

    wf = svc.generate_offboarding(
        employee_name="Leaving Employee",
        employee_email="leaving@test.com",
        job_code="OFF01",
        created_by="admin@test.com",
    )

    assert wf.workflow_type == "offboarding"
    assert len(wf.items) == 4  # 2 role removals + 2 standard

    role_items = [i for i in wf.items if i.item_source == "role_mapping"]
    std_items = [i for i in wf.items if i.item_source == "standard_offboarding"]

    assert len(role_items) == 2
    assert len(std_items) == 2
    assert all("Remove:" in i.item_text for i in role_items)
    assert all(i.action_type == "remove" for i in role_items)
    assert all(i.action_type == "action" for i in std_items)


# --- complete_item -----------------------------------------------------------


def test_complete_item(svc):
    """Completing a pending item sets status, completed_by, and completed_at."""
    wf = WorkflowFactory()
    item = WorkflowItemFactory(workflow=wf, status="pending")

    result = svc.complete_item(item.id, completed_by="user@test.com")

    assert result.status == "completed"
    assert result.completed_by == "user@test.com"
    assert result.completed_at is not None


def test_complete_item_already_completed(svc):
    """Completing an already-completed item raises ValueError."""
    wf = WorkflowFactory()
    item = WorkflowItemFactory(workflow=wf, status="pending")

    svc.complete_item(item.id, completed_by="user@test.com")

    with pytest.raises(ValueError, match="already 'completed'"):
        svc.complete_item(item.id, completed_by="user@test.com")


def test_complete_item_not_found(svc):
    """Completing a nonexistent item raises ValueError."""
    with pytest.raises(ValueError, match="not found"):
        svc.complete_item(999999, completed_by="user@test.com")


# --- skip_item ---------------------------------------------------------------


def test_skip_item(svc):
    """Skipping a pending item with a reason sets status, skip_reason, completed_by."""
    wf = WorkflowFactory()
    item = WorkflowItemFactory(workflow=wf, status="pending")

    result = svc.skip_item(
        item.id, completed_by="user@test.com", reason="Not applicable"
    )

    assert result.status == "skipped"
    assert result.skip_reason == "Not applicable"
    assert result.completed_by == "user@test.com"
    assert result.completed_at is not None


def test_skip_item_requires_reason(svc):
    """Skipping without a reason raises ValueError (D-06)."""
    wf = WorkflowFactory()
    item = WorkflowItemFactory(workflow=wf, status="pending")

    with pytest.raises(ValueError, match="reason is required"):
        svc.skip_item(item.id, completed_by="user@test.com", reason="")

    with pytest.raises(ValueError, match="reason is required"):
        svc.skip_item(item.id, completed_by="user@test.com", reason="   ")


# --- auto-complete workflow --------------------------------------------------


def test_auto_complete_workflow(svc):
    """Workflow auto-completes when all items are completed or skipped."""
    wf = WorkflowFactory()
    item1 = WorkflowItemFactory(workflow=wf, item_text="Item 1", status="pending")
    item2 = WorkflowItemFactory(workflow=wf, item_text="Item 2", status="pending")

    svc.complete_item(item1.id, completed_by="user@test.com")
    assert wf.status == "active"  # still active after first item

    svc.skip_item(
        item2.id, completed_by="user@test.com", reason="Not needed"
    )
    # Refresh workflow from session
    db.session.refresh(wf)
    assert wf.status == "completed"
    assert wf.completed_at is not None


# --- cancel_workflow ---------------------------------------------------------


def test_cancel_workflow(svc):
    """Cancelling sets status to cancelled and records completed_at."""
    wf = WorkflowFactory()

    result = svc.cancel_workflow(wf.id)

    assert result.status == "cancelled"
    assert result.completed_at is not None


# --- get_dashboard_stats -----------------------------------------------------


def test_dashboard_stats(svc):
    """Dashboard stats return correct counts for active, overdue, completed."""
    # 2 active workflows
    wf1 = WorkflowFactory(status="active")
    WorkflowFactory(status="active")

    # 1 completed workflow (completed this month)
    wf3 = WorkflowFactory(status="completed")
    wf3.completed_at = datetime.now(timezone.utc)
    wf3.save()

    # 1 overdue item on active workflow
    WorkflowItemFactory(
        workflow=wf1,
        status="pending",
        due_date=date.today() - timedelta(days=3),
    )

    stats = svc.get_dashboard_stats()

    assert stats["active"] == 2
    assert stats["overdue"] == 1
    assert stats["completed_this_month"] == 1
    assert isinstance(stats["avg_completion_days"], (int, float))


# --- get_workflow / get_active_workflows / get_completed_workflows -----------


def test_get_workflow(svc):
    """get_workflow returns the workflow by ID."""
    wf = WorkflowFactory()
    result = svc.get_workflow(wf.id)
    assert result is not None
    assert result.id == wf.id


def test_get_active_workflows(svc):
    """get_active_workflows returns only active workflows."""
    WorkflowFactory(status="active")
    WorkflowFactory(status="completed")

    result = svc.get_active_workflows()
    assert all(w.status == "active" for w in result)
