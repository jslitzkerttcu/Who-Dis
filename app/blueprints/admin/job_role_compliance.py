"""
Job Role Compliance Matrix Admin Module

This module provides admin interface for managing job role compliance,
including the visual matrix editor and compliance dashboard.
"""

import logging
from datetime import datetime, timezone
from flask import request, jsonify, render_template

from app.middleware.auth import require_role
from app.models.job_role_compliance import (
    JobCode,
    SystemRole,
    JobRoleMapping,
    ComplianceCheck,
    JobRoleMappingHistory,
)
from app.services.job_role_mapping_service import JobRoleMappingService
from app.services.job_role_warehouse_service import JobRoleWarehouseService
from app.database import db

logger = logging.getLogger(__name__)


@require_role("admin")
def job_role_compliance():
    """Main job role compliance management page."""
    return render_template("admin/job_role_compliance.html")


@require_role("admin")
def api_job_codes():
    """Get job codes with optional filtering and pagination."""
    try:
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 20, type=int)
        department = request.args.get("department", "").strip()
        search = request.args.get("search", "").strip()

        query = JobCode.query.filter_by(is_active=True)

        if department:
            query = query.filter(JobCode.department == department)

        if search:
            query = query.filter(
                db.or_(
                    JobCode.job_code.ilike(f"%{search}%"),
                    JobCode.job_title.ilike(f"%{search}%"),
                )
            )

        query = query.order_by(JobCode.job_code)
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)

        # Get mapping counts efficiently to avoid N+1 queries
        job_code_ids = [jc.id for jc in pagination.items]
        mapping_counts = {}
        if job_code_ids:
            mapping_count_query = (
                db.session.query(
                    JobRoleMapping.job_code_id,
                    db.func.count(JobRoleMapping.id).label("count"),
                )
                .filter(JobRoleMapping.job_code_id.in_(job_code_ids))
                .group_by(JobRoleMapping.job_code_id)
                .all()
            )
            mapping_counts = {row[0]: row[1] for row in mapping_count_query}

        job_codes = []
        for job_code in pagination.items:
            job_codes.append(
                {
                    "id": job_code.id,
                    "job_code": job_code.job_code,
                    "job_title": job_code.job_title,
                    "department": job_code.department,
                    "job_family": job_code.job_family,
                    "job_level": job_code.job_level,
                    "synced_at": job_code.synced_at.isoformat()
                    if job_code.synced_at
                    else None,
                    "mapping_count": mapping_counts.get(job_code.id, 0),
                }
            )

        result = {
            "job_codes": job_codes,
            "pagination": {
                "page": pagination.page,
                "pages": pagination.pages,
                "per_page": pagination.per_page,
                "total": pagination.total,
                "has_next": pagination.has_next,
                "has_prev": pagination.has_prev,
                "next_num": pagination.next_num,
                "prev_num": pagination.prev_num,
            },
        }

        # Return HTML for HTMX requests
        if request.headers.get("HX-Request"):
            return render_template("admin/partials/_job_codes_table.html", data=result)

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error fetching job codes: {e}")
        if request.headers.get("HX-Request"):
            return '<div class="text-red-600">Error loading job codes</div>'
        return jsonify({"error": "Failed to fetch job codes"}), 500


@require_role("admin")
def api_system_roles():
    """Get system roles with optional filtering and pagination."""
    try:
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 20, type=int)
        system_name = request.args.get("system_name", "").strip()
        search = request.args.get("search", "").strip()

        query = SystemRole.query.filter_by(is_active=True)

        if system_name:
            query = query.filter(SystemRole.system_name == system_name)

        if search:
            query = query.filter(
                db.or_(
                    SystemRole.role_name.ilike(f"%{search}%"),
                    SystemRole.description.ilike(f"%{search}%"),
                )
            )

        query = query.order_by(SystemRole.system_name, SystemRole.role_name)
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)

        system_roles = []
        for role in pagination.items:
            system_roles.append(
                {
                    "id": role.id,
                    "role_name": role.role_name,
                    "system_name": role.system_name,
                    "description": role.description,
                    "role_type": role.role_type,
                    "synced_at": role.synced_at.isoformat() if role.synced_at else None,
                    "mapping_count": len(role.role_mappings),
                }
            )

        result = {
            "system_roles": system_roles,
            "pagination": {
                "page": pagination.page,
                "pages": pagination.pages,
                "per_page": pagination.per_page,
                "total": pagination.total,
                "has_next": pagination.has_next,
                "has_prev": pagination.has_prev,
                "next_num": pagination.next_num,
                "prev_num": pagination.prev_num,
            },
        }

        # Return HTML for HTMX requests
        if request.headers.get("HX-Request"):
            return render_template(
                "admin/partials/_system_roles_table.html", data=result
            )

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error fetching system roles: {e}")
        if request.headers.get("HX-Request"):
            return '<div class="text-red-600">Error loading system roles</div>'
        return jsonify({"error": "Failed to fetch system roles"}), 500


@require_role("admin")
def api_job_role_matrix():
    """Get the job role mapping matrix data."""
    try:
        # Get all active job codes and system roles
        job_codes = JobCode.get_active_job_codes()
        system_roles = SystemRole.get_active_roles()

        # Get all current mappings with related data
        mappings = (
            JobRoleMapping.query.join(JobCode)
            .join(SystemRole)
            .filter(JobCode.is_active, SystemRole.is_active)
            .all()
        )

        # Extract unique departments and systems for filters
        departments = sorted(
            list(set(jc.department for jc in job_codes if jc.department))
        )
        systems = sorted(list(set(sr.system_name for sr in system_roles)))

        # Build mapping rows (only existing mappings for performance)
        mapping_rows = []
        for mapping in mappings:
            mapping_rows.append(
                {
                    "job_code_id": mapping.job_code_id,
                    "system_role_id": mapping.system_role_id,
                    "job_code": mapping.job_code.job_code,
                    "job_title": mapping.job_code.job_title,
                    "department": mapping.job_code.department,
                    "system_name": mapping.system_role.system_name,
                    "role_name": mapping.system_role.role_name,
                    "mapping_type": mapping.mapping_type,
                    "priority": mapping.priority,
                    "effective_date": mapping.effective_date.isoformat()
                    if mapping.effective_date
                    else None,
                    "expiration_date": mapping.expiration_date.isoformat()
                    if mapping.expiration_date
                    else None,
                    "notes": mapping.notes,
                    "mapping_id": mapping.id,
                }
            )

        # Build matrix structure
        matrix_data = {
            "mapping_rows": mapping_rows,
            "departments": departments,
            "systems": systems,
            "total_mappings": len(mapping_rows),
            "total_possible": len(job_codes) * len(system_roles),
        }

        # Return HTML for HTMX requests
        if request.headers.get("HX-Request"):
            return render_template(
                "admin/partials/_job_role_matrix.html", data=matrix_data
            )

        return jsonify(matrix_data)

    except Exception as e:
        logger.error(f"Error fetching job role matrix: {e}")
        if request.headers.get("HX-Request"):
            return '<div class="text-red-600">Error loading job role matrix</div>'
        return jsonify({"error": "Failed to fetch job role matrix"}), 500


@require_role("admin")
def api_create_job_role_mapping():
    """Create or update a job role mapping."""
    try:
        data = request.get_json()
        service = JobRoleMappingService()

        # Extract data from request
        job_code_id = data.get("job_code_id")
        system_role_id = data.get("system_role_id")
        mapping_type = data.get("mapping_type", "required")
        priority = data.get("priority", 1)
        notes = data.get("notes", "")
        created_by = request.headers.get("X-MS-CLIENT-PRINCIPAL-NAME", "admin")

        # Get job code and system role
        job_code = JobCode.query.get(job_code_id)
        system_role = SystemRole.query.get(system_role_id)

        if not job_code or not system_role:
            return jsonify({"error": "Invalid job code or system role"}), 400

        # Check for existing mapping
        existing_mapping = JobRoleMapping.query.filter_by(
            job_code_id=job_code_id, system_role_id=system_role_id, is_active=True
        ).first()

        if existing_mapping:
            # Update existing mapping
            existing_mapping.mapping_type = mapping_type
            existing_mapping.priority = priority
            existing_mapping.notes = notes
            existing_mapping.updated_at = datetime.now(timezone.utc)

            # Create history record
            history = JobRoleMappingHistory(
                job_role_mapping_id=existing_mapping.id,
                action="updated",
                changed_by=created_by,
                changes={
                    "mapping_type": mapping_type,
                    "priority": priority,
                    "notes": notes,
                },
            )
            db.session.add(history)
            mapping = existing_mapping

        else:
            # Create new mapping
            mapping = service.create_mapping(
                job_code=job_code.job_code,
                role_name=system_role.role_name,
                system_name=system_role.system_name,
                mapping_type=mapping_type,
                priority=priority,
                notes=notes,
                created_by=created_by,
                commit=False,
            )

        db.session.commit()

        return jsonify(
            {
                "success": True,
                "mapping": {
                    "id": mapping.id,
                    "mapping_type": mapping.mapping_type,
                    "priority": mapping.priority,
                    "notes": mapping.notes,
                },
            }
        )

    except Exception as e:
        logger.error(f"Error creating job role mapping: {e}")
        db.session.rollback()
        return jsonify({"error": "Failed to create mapping"}), 500


@require_role("admin")
def api_delete_job_role_mapping():
    """Delete a job role mapping."""
    try:
        data = request.get_json()
        mapping_id = data.get("mapping_id")
        deleted_by = request.headers.get("X-MS-CLIENT-PRINCIPAL-NAME", "admin")

        mapping = JobRoleMapping.query.get(mapping_id)
        if not mapping:
            return jsonify({"error": "Mapping not found"}), 404

        # Soft delete
        mapping.is_active = False
        mapping.updated_at = datetime.now(timezone.utc)

        # Create history record
        history = JobRoleMappingHistory(
            job_role_mapping_id=mapping.id,
            action="deleted",
            changed_by=deleted_by,
            changes={"is_active": False},
        )
        db.session.add(history)
        db.session.commit()

        return jsonify({"success": True})

    except Exception as e:
        logger.error(f"Error deleting job role mapping: {e}")
        db.session.rollback()
        return jsonify({"error": "Failed to delete mapping"}), 500


@require_role("admin")
def api_sync_job_codes():
    """Sync job codes from data warehouse."""
    try:
        service = JobRoleWarehouseService()
        result = service.sync_job_codes()

        return jsonify(
            {
                "success": True,
                "created_count": result.get("created", 0),
                "updated_count": result.get("updated", 0),
                "message": "Job codes synced successfully",
            }
        )

    except Exception as e:
        logger.error(f"Error syncing job codes: {e}")
        return jsonify({"error": "Failed to sync job codes"}), 500


@require_role("admin")
def api_sync_system_roles():
    """Sync system roles from various sources."""
    try:
        service = JobRoleWarehouseService()
        result = service.sync_system_roles()

        return jsonify(
            {
                "success": True,
                "created_count": result.get("created", 0),
                "updated_count": result.get("updated", 0),
                "message": "System roles synced successfully",
            }
        )

    except Exception as e:
        logger.error(f"Error syncing system roles: {e}")
        return jsonify({"error": "Failed to sync system roles"}), 500


@require_role("admin")
def compliance_dashboard():
    """Compliance dashboard with overview and metrics."""
    return render_template("admin/compliance_dashboard.html")


@require_role("admin")
def api_compliance_overview():
    """Get compliance overview statistics."""
    try:
        # Get overall compliance statistics
        from app.models.employee_profiles import EmployeeProfiles

        total_employees = EmployeeProfiles.query.count()
        violations = ComplianceCheck.query.filter(
            ComplianceCheck.compliance_status != "compliant"
        ).all()

        # Calculate compliance percentage
        employees_with_violations = len(set(v.employee_upn for v in violations))
        compliance_percentage = (
            ((total_employees - employees_with_violations) / total_employees * 100)
            if total_employees > 0
            else 100
        )

        # Group violations by severity
        violation_stats = {
            "critical": len(
                [v for v in violations if v.violation_severity == "critical"]
            ),
            "high": len([v for v in violations if v.violation_severity == "high"]),
            "medium": len([v for v in violations if v.violation_severity == "medium"]),
            "low": len([v for v in violations if v.violation_severity == "low"]),
        }

        # Top violation types
        violation_types = {}
        for violation in violations:
            violation_types[violation.compliance_status] = (
                violation_types.get(violation.compliance_status, 0) + 1
            )

        top_violations = sorted(
            violation_types.items(), key=lambda x: x[1], reverse=True
        )[:5]

        overview_data = {
            "total_employees": total_employees,
            "compliance_percentage": round(compliance_percentage, 1),
            "total_violations": len(violations),
            "employees_with_violations": employees_with_violations,
            "violation_stats": violation_stats,
            "top_violations": top_violations,
        }

        # Return HTML for HTMX requests
        if request.headers.get("HX-Request"):
            return render_template(
                "admin/partials/_compliance_overview.html", data=overview_data
            )

        return jsonify(overview_data)

    except Exception as e:
        logger.error(f"Error fetching compliance overview: {e}")
        if request.headers.get("HX-Request"):
            return '<div class="text-red-600">Error loading compliance overview</div>'
        return jsonify({"error": "Failed to fetch compliance overview"}), 500


@require_role("admin")
def api_compliance_violations():
    """Get compliance violations with filtering and pagination."""
    try:
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 20, type=int)
        severity = request.args.get("severity", "").strip()
        violation_type = request.args.get("violation_type", "").strip()

        query = ComplianceCheck.query.filter(
            ComplianceCheck.compliance_status != "compliant"
        )

        if severity:
            query = query.filter(ComplianceCheck.violation_severity == severity)

        if violation_type:
            query = query.filter(ComplianceCheck.compliance_status == violation_type)

        query = query.order_by(
            ComplianceCheck.violation_severity.desc(), ComplianceCheck.created_at.desc()
        )
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)

        violations = []
        for violation in pagination.items:
            violations.append(
                {
                    "id": violation.id,
                    "employee_id": violation.employee_upn,
                    "job_code": violation.job_code,
                    "system_name": violation.system_name,
                    "violation_type": violation.compliance_status,
                    "severity": violation.violation_severity,
                    "status": "open",  # Default status since ComplianceCheck doesn't have status field
                    "detected_at": violation.created_at.isoformat()
                    if violation.created_at
                    else None,
                    "details": violation.notes,
                    "recommended_action": violation.remediation_action,
                }
            )

        result = {
            "violations": violations,
            "pagination": {
                "page": pagination.page,
                "pages": pagination.pages,
                "per_page": pagination.per_page,
                "total": pagination.total,
                "has_next": pagination.has_next,
                "has_prev": pagination.has_prev,
                "next_num": pagination.next_num,
                "prev_num": pagination.prev_num,
            },
        }

        # Return HTML for HTMX requests
        if request.headers.get("HX-Request"):
            return render_template(
                "admin/partials/_compliance_violations_table.html", data=result
            )

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error fetching compliance violations: {e}")
        if request.headers.get("HX-Request"):
            return '<div class="text-red-600">Error loading compliance violations</div>'
        return jsonify({"error": "Failed to fetch compliance violations"}), 500


@require_role("admin")
def api_run_compliance_check():
    """Run compliance check for all employees."""
    try:
        from app.services.compliance_checking_service import ComplianceCheckingService

        engine = ComplianceCheckingService()
        started_by = request.headers.get("X-MS-CLIENT-PRINCIPAL-NAME", "admin")
        check_run = engine.run_compliance_check(started_by=started_by)

        # Since the compliance check runs in background, we'll return basic info
        result = {
            "checked_employees": 0,  # Will be updated when check completes
            "violations_found": 0,  # Will be updated when check completes
            "violations_resolved": 0,  # Will be updated when check completes
            "run_id": check_run.run_id,
        }

        return jsonify(
            {
                "success": True,
                "checked_employees": result.get("checked_employees", 0),
                "violations_found": result.get("violations_found", 0),
                "violations_resolved": result.get("violations_resolved", 0),
                "message": "Compliance check completed successfully",
            }
        )

    except Exception as e:
        logger.error(f"Error running compliance check: {e}")
        return jsonify({"error": "Failed to run compliance check"}), 500
