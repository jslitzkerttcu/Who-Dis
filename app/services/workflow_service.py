"""
Workflow Service

This service handles workflow checklist generation from job role mappings,
item completion/skip tracking, auto-completion logic, and dashboard statistics.
"""

import logging
from datetime import datetime, timezone, date
from typing import Dict, Any, List, Optional

from sqlalchemy import func

from app.database import db
from app.services.base import BaseConfigurableService
from app.utils.error_handler import handle_service_errors
from app.models.workflow import Workflow, WorkflowItem, StandardOffboardingItem
from app.models.job_role_compliance import JobCode, JobRoleMapping

logger = logging.getLogger(__name__)


class WorkflowService(BaseConfigurableService):
    """Service for managing onboarding/offboarding workflow checklists."""

    def __init__(self) -> None:
        super().__init__(config_prefix="workflow")

    @handle_service_errors(raise_errors=True)
    def generate_onboarding(
        self,
        employee_name: str,
        employee_email: Optional[str],
        job_code: str,
        created_by: str,
    ) -> Workflow:
        """Generate an onboarding workflow from job role mappings.

        Args:
            employee_name: Full name of the employee.
            employee_email: Email address (nullable for net-new hires per D-03).
            job_code: Job code string to look up mappings.
            created_by: Email of the admin creating the workflow.

        Returns:
            The created Workflow with populated items.

        Raises:
            ValueError: If no active mappings exist for the job code.
        """
        mappings = JobRoleMapping.get_active_mappings_for_job_code(job_code)
        if not mappings:
            raise ValueError(
                f"No active role mappings found for job code '{job_code}'"
            )

        job_code_obj = JobCode.get_by_job_code(job_code)
        job_title = job_code_obj.job_title if job_code_obj else None

        workflow = Workflow(
            workflow_type="onboarding",
            status="active",
            employee_name=employee_name,
            employee_email=employee_email,
            job_code=job_code,
            job_title=job_title,
            created_by=created_by,
        )
        workflow.save(commit=False)

        sort_index = 0
        for mapping in mappings:
            if mapping.mapping_type == "prohibited":
                continue

            system_name = mapping.system_role.system_name
            role_name = mapping.system_role.role_name

            if mapping.mapping_type == "required":
                item_text = f"Assign: {role_name} ({system_name})"
            else:
                item_text = f"Consider assigning: {role_name} ({system_name})"

            item = WorkflowItem(
                workflow_id=workflow.id,
                item_text=item_text,
                item_source="role_mapping",
                source_detail=f"{system_name}.{role_name} ({mapping.mapping_type})",
                action_type="add",
                system_name=system_name,
                role_name=role_name,
                sort_order=sort_index,
                status="pending",
            )
            item.save(commit=False)
            sort_index += 1

        db.session.commit()
        logger.info(
            f"Generated onboarding workflow for {employee_name} "
            f"(job_code={job_code}, items={sort_index})"
        )
        return workflow

    @handle_service_errors(raise_errors=True)
    def generate_offboarding(
        self,
        employee_name: str,
        employee_email: Optional[str],
        job_code: str,
        created_by: str,
    ) -> Workflow:
        """Generate an offboarding workflow from job role mappings and standard items.

        Args:
            employee_name: Full name of the employee.
            employee_email: Email address (nullable for net-new hires per D-03).
            job_code: Job code string to look up mappings.
            created_by: Email of the admin creating the workflow.

        Returns:
            The created Workflow with populated items.

        Raises:
            ValueError: If no active mappings exist for the job code.
        """
        mappings = JobRoleMapping.get_active_mappings_for_job_code(job_code)
        if not mappings:
            raise ValueError(
                f"No active role mappings found for job code '{job_code}'"
            )

        job_code_obj = JobCode.get_by_job_code(job_code)
        job_title = job_code_obj.job_title if job_code_obj else None

        workflow = Workflow(
            workflow_type="offboarding",
            status="active",
            employee_name=employee_name,
            employee_email=employee_email,
            job_code=job_code,
            job_title=job_title,
            created_by=created_by,
        )
        workflow.save(commit=False)

        sort_index = 0
        for mapping in mappings:
            if mapping.mapping_type == "prohibited":
                continue

            system_name = mapping.system_role.system_name
            role_name = mapping.system_role.role_name
            item_text = f"Remove: {role_name} ({system_name})"

            item = WorkflowItem(
                workflow_id=workflow.id,
                item_text=item_text,
                item_source="role_mapping",
                source_detail=f"{system_name}.{role_name} ({mapping.mapping_type})",
                action_type="remove",
                system_name=system_name,
                role_name=role_name,
                sort_order=sort_index,
                status="pending",
            )
            item.save(commit=False)
            sort_index += 1

        # Append standard offboarding items
        standard_items = StandardOffboardingItem.get_all_active()
        for std_item in standard_items:
            item = WorkflowItem(
                workflow_id=workflow.id,
                item_text=std_item.item_text,
                item_source="standard_offboarding",
                source_detail=None,
                action_type="action",
                system_name=None,
                role_name=None,
                sort_order=sort_index,
                status="pending",
            )
            item.save(commit=False)
            sort_index += 1

        db.session.commit()
        logger.info(
            f"Generated offboarding workflow for {employee_name} "
            f"(job_code={job_code}, items={sort_index})"
        )
        return workflow

    @handle_service_errors(raise_errors=True)
    def complete_item(self, item_id: int, completed_by: str) -> WorkflowItem:
        """Mark a workflow item as completed.

        Args:
            item_id: The WorkflowItem primary key.
            completed_by: Email of the user completing the item.

        Returns:
            The updated WorkflowItem.

        Raises:
            ValueError: If item not found or not in pending status.
        """
        item = WorkflowItem.query.get(item_id)
        if item is None:
            raise ValueError(f"Workflow item {item_id} not found")
        if item.status != "pending":
            raise ValueError(
                f"Workflow item {item_id} is already '{item.status}', "
                f"cannot complete"
            )

        item.status = "completed"
        item.completed_by = completed_by
        item.completed_at = datetime.now(timezone.utc)
        item.save(commit=False)

        self._check_workflow_completion(item.workflow)
        db.session.commit()
        return item

    @handle_service_errors(raise_errors=True)
    def skip_item(
        self, item_id: int, completed_by: str, reason: str
    ) -> WorkflowItem:
        """Mark a workflow item as skipped with a required reason.

        Args:
            item_id: The WorkflowItem primary key.
            completed_by: Email of the user skipping the item.
            reason: Reason for skipping (required, per D-06).

        Returns:
            The updated WorkflowItem.

        Raises:
            ValueError: If reason is empty, item not found, or not pending.
        """
        if not reason or not reason.strip():
            raise ValueError("A reason is required when skipping a workflow item")

        item = WorkflowItem.query.get(item_id)
        if item is None:
            raise ValueError(f"Workflow item {item_id} not found")
        if item.status != "pending":
            raise ValueError(
                f"Workflow item {item_id} is already '{item.status}', "
                f"cannot skip"
            )

        item.status = "skipped"
        item.completed_by = completed_by
        item.completed_at = datetime.now(timezone.utc)
        item.skip_reason = reason.strip()
        item.save(commit=False)

        self._check_workflow_completion(item.workflow)
        db.session.commit()
        return item

    @handle_service_errors(raise_errors=True)
    def cancel_workflow(self, workflow_id: int) -> Workflow:
        """Cancel an active workflow.

        Args:
            workflow_id: The Workflow primary key.

        Returns:
            The updated Workflow.

        Raises:
            ValueError: If workflow not found.
        """
        workflow = Workflow.query.get(workflow_id)
        if workflow is None:
            raise ValueError(f"Workflow {workflow_id} not found")

        workflow.status = "cancelled"
        workflow.completed_at = datetime.now(timezone.utc)
        workflow.save()

        logger.info(f"Cancelled workflow {workflow_id}")
        return workflow

    @handle_service_errors(raise_errors=True)
    def get_dashboard_stats(self) -> Dict[str, Any]:
        """Compute dashboard statistics for the workflow overview.

        Returns:
            Dict with active, overdue, completed_this_month, avg_completion_days.
        """
        active_count = Workflow.query.filter_by(status="active").count()

        overdue_count: int = (
            db.session.query(func.count(WorkflowItem.id))
            .join(Workflow)
            .filter(
                Workflow.status == "active",
                WorkflowItem.status == "pending",
                WorkflowItem.due_date.isnot(None),
                WorkflowItem.due_date < date.today(),
            )
            .scalar()
            or 0
        )

        # Completed this month
        today = date.today()
        first_of_month = today.replace(day=1)
        first_of_month_dt = datetime(
            first_of_month.year, first_of_month.month, first_of_month.day,
            tzinfo=timezone.utc,
        )
        completed_this_month: int = (
            Workflow.query.filter(
                Workflow.status == "completed",
                Workflow.completed_at >= first_of_month_dt,
            ).count()
        )

        # Average completion days for completed workflows
        avg_seconds = (
            db.session.query(
                func.avg(
                    func.extract(
                        "epoch",
                        Workflow.completed_at - Workflow.created_at,
                    )
                )
            )
            .filter(Workflow.status == "completed")
            .scalar()
        )
        avg_completion_days = round(avg_seconds / 86400, 1) if avg_seconds else 0

        return {
            "active": active_count,
            "overdue": overdue_count,
            "completed_this_month": completed_this_month,
            "avg_completion_days": avg_completion_days,
        }

    @handle_service_errors(raise_errors=True)
    def get_active_workflows(self) -> List[Workflow]:
        """Return all active workflows."""
        return Workflow.get_active_workflows()

    @handle_service_errors(raise_errors=True)
    def get_completed_workflows(
        self, page: int = 1, per_page: int = 20
    ) -> Any:
        """Return paginated completed workflows.

        Args:
            page: Page number (1-based).
            per_page: Items per page.

        Returns:
            Flask-SQLAlchemy pagination object.
        """
        return (
            Workflow.query.filter_by(status="completed")
            .order_by(Workflow.completed_at.desc())
            .paginate(page=page, per_page=per_page)
        )

    @handle_service_errors(raise_errors=True)
    def get_workflow(self, workflow_id: int) -> Optional[Workflow]:
        """Get a single workflow by ID.

        Args:
            workflow_id: The Workflow primary key.

        Returns:
            Workflow instance or None.
        """
        return Workflow.query.get(workflow_id)

    def _check_workflow_completion(self, workflow: Workflow) -> None:
        """Auto-complete the workflow when all items are done or skipped.

        Args:
            workflow: The parent Workflow to check.
        """
        all_done = all(
            item.status in ("completed", "skipped") for item in workflow.items
        )
        if all_done and workflow.items:
            workflow.status = "completed"
            workflow.completed_at = datetime.now(timezone.utc)
            workflow.save(commit=False)
            logger.info(f"Auto-completed workflow {workflow.id}")
