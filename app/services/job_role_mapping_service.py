"""
Job Role Mapping Management Service

This service provides CRUD operations and business logic for managing
job role mappings in the compliance matrix.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import date
import csv
import io

from app.database import db
from app.services.base import BaseConfigurableService
from app.utils.error_handler import handle_service_errors
from app.models.job_role_compliance import (
    JobCode,
    SystemRole,
    JobRoleMapping,
    JobRoleMappingHistory,
)

logger = logging.getLogger(__name__)


class JobRoleMappingService(BaseConfigurableService):
    """Service for managing job role mappings."""

    def __init__(self):
        super().__init__(config_prefix="job_role_compliance")

    @handle_service_errors(raise_errors=True)
    def create_mapping(
        self,
        job_code: str,
        role_name: str,
        system_name: str,
        mapping_type: str = "required",
        priority: int = 1,
        effective_date: Optional[date] = None,
        expiration_date: Optional[date] = None,
        notes: Optional[str] = None,
        created_by: str = "system",
        commit: bool = True,
    ) -> JobRoleMapping:
        """
        Create a new job role mapping.

        Args:
            job_code: The job code string
            role_name: The role name
            system_name: The system name (keystone, ad_groups, etc.)
            mapping_type: Type of mapping (required, optional, prohibited)
            priority: Priority level for ordering
            effective_date: When the mapping becomes effective
            expiration_date: When the mapping expires
            notes: Additional notes
            created_by: User creating the mapping
            commit: Whether to commit immediately

        Returns:
            The created JobRoleMapping instance
        """
        # Find or create job code
        job_code_obj = JobCode.get_by_job_code(job_code)
        if not job_code_obj:
            job_code_obj = JobCode(
                job_code=job_code,
                job_title=f"Job Code {job_code}",
                is_active=True,
            ).save(commit=False)

        # Find or create system role
        role_obj, role_created = SystemRole.find_or_create(
            role_name=role_name,
            system_name=system_name,
            role_type="application",  # Default type
        )
        if role_created:
            role_obj.save(commit=False)

        # Check for existing mapping
        existing_mapping = JobRoleMapping.query.filter_by(
            job_code_id=job_code_obj.id, system_role_id=role_obj.id
        ).first()

        if existing_mapping:
            raise ValueError(
                f"Mapping already exists for {job_code} -> {role_name} ({system_name})"
            )

        # Create the mapping
        mapping = JobRoleMapping(
            job_code_id=job_code_obj.id,
            system_role_id=role_obj.id,
            mapping_type=mapping_type,
            priority=priority,
            effective_date=effective_date or date.today(),
            expiration_date=expiration_date,
            notes=notes,
            created_by=created_by,
        )

        mapping.save(commit=False)

        # Log the creation
        JobRoleMappingHistory.log_change(
            mapping=mapping,
            change_type="created",
            changed_by=created_by,
            change_reason=f"Created new {mapping_type} mapping",
        )

        if commit:
            db.session.commit()

        logger.info(
            f"Created mapping: {job_code} -> {role_name} ({system_name}) as {mapping_type}"
        )
        return mapping

    @handle_service_errors(raise_errors=True)
    def update_mapping(
        self,
        mapping_id: int,
        mapping_type: Optional[str] = None,
        priority: Optional[int] = None,
        effective_date: Optional[date] = None,
        expiration_date: Optional[date] = None,
        notes: Optional[str] = None,
        updated_by: str = "system",
        change_reason: Optional[str] = None,
        commit: bool = True,
    ) -> JobRoleMapping:
        """
        Update an existing job role mapping.

        Args:
            mapping_id: ID of the mapping to update
            mapping_type: New mapping type
            priority: New priority
            effective_date: New effective date
            expiration_date: New expiration date
            notes: New notes
            updated_by: User making the update
            change_reason: Reason for the change
            commit: Whether to commit immediately

        Returns:
            The updated JobRoleMapping instance
        """
        mapping = JobRoleMapping.get_by_id(mapping_id)
        if not mapping:
            raise ValueError(f"Mapping with ID {mapping_id} not found")

        # Store old values for history
        old_values = {
            "mapping_type": mapping.mapping_type,
            "priority": mapping.priority,
            "effective_date": mapping.effective_date,
            "expiration_date": mapping.expiration_date,
            "notes": mapping.notes,
        }

        # Update fields if provided
        if mapping_type is not None:
            mapping.mapping_type = mapping_type
        if priority is not None:
            mapping.priority = priority
        if effective_date is not None:
            mapping.effective_date = effective_date
        if expiration_date is not None:
            mapping.expiration_date = expiration_date
        if notes is not None:
            mapping.notes = notes

        mapping.save(commit=False)

        # Log the change
        JobRoleMappingHistory.log_change(
            mapping=mapping,
            change_type="updated",
            changed_by=updated_by,
            old_values=old_values,
            change_reason=change_reason,
        )

        if commit:
            db.session.commit()

        logger.info(f"Updated mapping ID {mapping_id} by {updated_by}")
        return mapping  # type: ignore[no-any-return]

    @handle_service_errors(raise_errors=True)
    def delete_mapping(
        self,
        mapping_id: int,
        deleted_by: str = "system",
        change_reason: Optional[str] = None,
        commit: bool = True,
    ) -> bool:
        """
        Delete a job role mapping.

        Args:
            mapping_id: ID of the mapping to delete
            deleted_by: User deleting the mapping
            change_reason: Reason for deletion
            commit: Whether to commit immediately

        Returns:
            True if successful
        """
        mapping = JobRoleMapping.get_by_id(mapping_id)
        if not mapping:
            raise ValueError(f"Mapping with ID {mapping_id} not found")

        # Log the deletion before removing the mapping
        JobRoleMappingHistory.log_change(
            mapping=mapping,
            change_type="deleted",
            changed_by=deleted_by,
            change_reason=change_reason,
        )

        mapping.delete(commit=False)

        if commit:
            db.session.commit()

        logger.info(f"Deleted mapping ID {mapping_id} by {deleted_by}")
        return True

    def get_mappings_for_job_code(
        self, job_code: str, include_inactive: bool = False
    ) -> List[JobRoleMapping]:
        """
        Get all mappings for a specific job code.

        Args:
            job_code: The job code to look up
            include_inactive: Whether to include expired mappings

        Returns:
            List of JobRoleMapping instances
        """
        query = (
            JobRoleMapping.query.join(JobCode)
            .filter(JobCode.job_code == job_code)
            .order_by(JobRoleMapping.priority.desc(), JobRoleMapping.created_at)
        )

        if not include_inactive:
            today = date.today()
            query = query.filter(
                JobRoleMapping.effective_date <= today,
                db.or_(
                    JobRoleMapping.expiration_date.is_(None),
                    JobRoleMapping.expiration_date >= today,
                ),
            )

        return query.all()  # type: ignore[no-any-return]

    def get_mappings_for_role(
        self, role_name: str, system_name: str, include_inactive: bool = False
    ) -> List[JobRoleMapping]:
        """
        Get all mappings for a specific role.

        Args:
            role_name: The role name
            system_name: The system name
            include_inactive: Whether to include expired mappings

        Returns:
            List of JobRoleMapping instances
        """
        query = (
            JobRoleMapping.query.join(SystemRole)
            .filter(
                SystemRole.role_name == role_name, SystemRole.system_name == system_name
            )
            .order_by(JobRoleMapping.priority.desc(), JobRoleMapping.created_at)
        )

        if not include_inactive:
            today = date.today()
            query = query.filter(
                JobRoleMapping.effective_date <= today,
                db.or_(
                    JobRoleMapping.expiration_date.is_(None),
                    JobRoleMapping.expiration_date >= today,
                ),
            )

        return query.all()  # type: ignore[no-any-return]

    def get_mapping_matrix(self, system_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get the complete job role mapping matrix.

        Args:
            system_name: Filter by system name (optional)

        Returns:
            Dictionary with matrix data organized by job codes and roles
        """
        # Base query
        query = JobRoleMapping.query.join(JobCode).join(SystemRole)

        if system_name:
            query = query.filter(SystemRole.system_name == system_name)

        # Get active mappings only
        today = date.today()
        query = query.filter(
            JobRoleMapping.effective_date <= today,
            db.or_(
                JobRoleMapping.expiration_date.is_(None),
                JobRoleMapping.expiration_date >= today,
            ),
        )

        mappings = query.all()

        # Organize data
        matrix: Dict[str, Any] = {
            "job_codes": {},
            "roles": {},
            "mappings": [],
            "systems": set(),
        }

        for mapping in mappings:
            job_code = mapping.job_code.job_code
            role_name = mapping.system_role.role_name
            system_name = mapping.system_role.system_name

            # Add job code info
            if job_code not in matrix["job_codes"]:
                matrix["job_codes"][job_code] = {
                    "job_code": job_code,
                    "job_title": mapping.job_code.job_title,
                    "department": mapping.job_code.department,
                    "mappings": [],
                }

            # Add role info
            role_key = f"{system_name}.{role_name}"
            if role_key not in matrix["roles"]:
                matrix["roles"][role_key] = {
                    "role_name": role_name,
                    "system_name": system_name,
                    "role_type": mapping.system_role.role_type,
                    "mappings": [],
                }

            # Add mapping
            mapping_data = mapping.to_dict_with_relations()
            matrix["mappings"].append(mapping_data)
            matrix["job_codes"][job_code]["mappings"].append(mapping_data)
            matrix["roles"][role_key]["mappings"].append(mapping_data)
            matrix["systems"].add(system_name)

        # Convert sets to lists for JSON serialization
        matrix["systems"] = list(matrix["systems"])

        return matrix

    @handle_service_errors(raise_errors=True)
    def bulk_create_mappings(
        self,
        mappings_data: List[Dict[str, Any]],
        created_by: str = "system",
        commit: bool = True,
    ) -> Dict[str, Any]:
        """
        Create multiple mappings in bulk.

        Args:
            mappings_data: List of mapping dictionaries
            created_by: User creating the mappings
            commit: Whether to commit immediately

        Returns:
            Dictionary with creation statistics
        """
        created_count = 0
        error_count = 0
        errors = []

        for mapping_data in mappings_data:
            try:
                self.create_mapping(
                    job_code=mapping_data["job_code"],
                    role_name=mapping_data["role_name"],
                    system_name=mapping_data["system_name"],
                    mapping_type=mapping_data.get("mapping_type", "required"),
                    priority=mapping_data.get("priority", 1),
                    effective_date=mapping_data.get("effective_date"),
                    expiration_date=mapping_data.get("expiration_date"),
                    notes=mapping_data.get("notes"),
                    created_by=created_by,
                    commit=False,
                )
                created_count += 1
            except Exception as e:
                error_count += 1
                errors.append(f"Row {created_count + error_count}: {str(e)}")
                logger.error(f"Error creating mapping: {str(e)}")

        if commit and created_count > 0:
            db.session.commit()
            logger.info(f"Bulk created {created_count} mappings")

        return {
            "created": created_count,
            "errors": error_count,
            "error_details": errors,
        }

    def export_mappings_csv(
        self, system_name: Optional[str] = None, include_inactive: bool = False
    ) -> str:
        """
        Export mappings to CSV format.

        Args:
            system_name: Filter by system name (optional)
            include_inactive: Whether to include expired mappings

        Returns:
            CSV string
        """
        # Get mappings
        query = JobRoleMapping.query.join(JobCode).join(SystemRole)

        if system_name:
            query = query.filter(SystemRole.system_name == system_name)

        if not include_inactive:
            today = date.today()
            query = query.filter(
                JobRoleMapping.effective_date <= today,
                db.or_(
                    JobRoleMapping.expiration_date.is_(None),
                    JobRoleMapping.expiration_date >= today,
                ),
            )

        mappings = query.order_by(
            JobCode.job_code, SystemRole.system_name, SystemRole.role_name
        ).all()

        # Create CSV
        output = io.StringIO()
        fieldnames = [
            "job_code",
            "job_title",
            "department",
            "role_name",
            "system_name",
            "role_type",
            "mapping_type",
            "priority",
            "effective_date",
            "expiration_date",
            "notes",
            "created_by",
            "created_at",
        ]

        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        for mapping in mappings:
            writer.writerow(
                {
                    "job_code": mapping.job_code.job_code,
                    "job_title": mapping.job_code.job_title,
                    "department": mapping.job_code.department,
                    "role_name": mapping.system_role.role_name,
                    "system_name": mapping.system_role.system_name,
                    "role_type": mapping.system_role.role_type,
                    "mapping_type": mapping.mapping_type,
                    "priority": mapping.priority,
                    "effective_date": mapping.effective_date.isoformat()
                    if mapping.effective_date
                    else "",
                    "expiration_date": mapping.expiration_date.isoformat()
                    if mapping.expiration_date
                    else "",
                    "notes": mapping.notes or "",
                    "created_by": mapping.created_by,
                    "created_at": mapping.created_at.isoformat()
                    if mapping.created_at
                    else "",
                }
            )

        return output.getvalue()

    @handle_service_errors(raise_errors=True)
    def import_mappings_csv(
        self, csv_content: str, created_by: str = "system", commit: bool = True
    ) -> Dict[str, Any]:
        """
        Import mappings from CSV content.

        Args:
            csv_content: CSV string content
            created_by: User importing the mappings
            commit: Whether to commit immediately

        Returns:
            Dictionary with import statistics
        """
        reader = csv.DictReader(io.StringIO(csv_content))
        mappings_data = []

        for row in reader:
            # Parse dates
            effective_date = None
            if row.get("effective_date"):
                try:
                    effective_date = date.fromisoformat(row["effective_date"])
                except ValueError:
                    pass

            expiration_date = None
            if row.get("expiration_date"):
                try:
                    expiration_date = date.fromisoformat(row["expiration_date"])
                except ValueError:
                    pass

            mappings_data.append(
                {
                    "job_code": row["job_code"],
                    "role_name": row["role_name"],
                    "system_name": row["system_name"],
                    "mapping_type": row.get("mapping_type", "required"),
                    "priority": int(row.get("priority", 1)),
                    "effective_date": effective_date,
                    "expiration_date": expiration_date,
                    "notes": row.get("notes"),
                }
            )

        # Bulk create
        result = self.bulk_create_mappings(
            mappings_data=mappings_data, created_by=created_by, commit=commit
        )

        logger.info(
            f"CSV import completed: {result['created']} created, {result['errors']} errors"
        )
        return result  # type: ignore[no-any-return]

    def get_mapping_history(
        self, mapping_id: Optional[int] = None, job_code: Optional[str] = None
    ) -> List[JobRoleMappingHistory]:
        """
        Get mapping change history.

        Args:
            mapping_id: Filter by specific mapping ID
            job_code: Filter by job code

        Returns:
            List of JobRoleMappingHistory instances
        """
        query = JobRoleMappingHistory.query

        if mapping_id:
            query = query.filter(JobRoleMappingHistory.mapping_id == mapping_id)

        if job_code:
            query = query.filter(JobRoleMappingHistory.job_code == job_code)

        return query.order_by(JobRoleMappingHistory.created_at.desc()).all()  # type: ignore[no-any-return]

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get mapping statistics.

        Returns:
            Dictionary with various statistics
        """
        total_mappings = JobRoleMapping.query.count()
        active_mappings = JobRoleMapping.query.filter(
            JobRoleMapping.effective_date <= date.today(),
            db.or_(
                JobRoleMapping.expiration_date.is_(None),
                JobRoleMapping.expiration_date >= date.today(),
            ),
        ).count()

        # Count by mapping type
        mapping_types = (
            db.session.query(
                JobRoleMapping.mapping_type, db.func.count(JobRoleMapping.id)
            )
            .group_by(JobRoleMapping.mapping_type)
            .all()
        )

        # Count by system
        system_counts = (
            db.session.query(SystemRole.system_name, db.func.count(JobRoleMapping.id))
            .join(JobRoleMapping)
            .group_by(SystemRole.system_name)
            .all()
        )

        return {
            "total_mappings": total_mappings,
            "active_mappings": active_mappings,
            "inactive_mappings": total_mappings - active_mappings,
            "mapping_types": dict(mapping_types),
            "system_counts": dict(system_counts),
            "total_job_codes": JobCode.query.count(),
            "total_roles": SystemRole.query.count(),
        }


# Create singleton instance
job_role_mapping_service = JobRoleMappingService()
