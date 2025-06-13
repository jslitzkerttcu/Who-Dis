"""
Job Role Compliance Matrix Models

This module contains SQLAlchemy models for managing job role compliance
across multiple systems (Keystone, AD, Genesys, etc.).
"""

from datetime import datetime, timezone, date
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import UniqueConstraint
from app.database import db
from app.models.base import BaseModel, TimestampMixin, JSONDataMixin


class JobCode(BaseModel, TimestampMixin, JSONDataMixin):
    """Model for job codes from UKG/data warehouse."""

    __tablename__ = "job_codes"

    job_code = db.Column(db.String(50), unique=True, nullable=False, index=True)
    job_title = db.Column(db.String(255), nullable=False)
    department = db.Column(db.String(255), index=True)
    job_family = db.Column(db.String(100))
    job_level = db.Column(db.String(50))
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True, index=True)
    synced_at = db.Column(
        db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    role_mappings = db.relationship(
        "JobRoleMapping", back_populates="job_code", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<JobCode {self.job_code}: {self.job_title}>"

    @classmethod
    def get_by_job_code(cls, job_code: str) -> Optional["JobCode"]:
        """Get job code by code string."""
        return cls.query.filter_by(job_code=job_code).first()

    @classmethod
    def get_active_job_codes(cls) -> List["JobCode"]:
        """Get all active job codes."""
        return cls.query.filter_by(is_active=True).order_by(cls.job_code).all()

    @classmethod
    def get_by_department(cls, department: str) -> List["JobCode"]:
        """Get job codes by department."""
        return (
            cls.query.filter_by(department=department, is_active=True)
            .order_by(cls.job_code)
            .all()
        )

    def get_role_mappings(
        self, mapping_type: Optional[str] = None
    ) -> List["JobRoleMapping"]:
        """Get role mappings for this job code."""
        query = self.role_mappings
        if mapping_type:
            query = query.filter(JobRoleMapping.mapping_type == mapping_type)
        return query.order_by(JobRoleMapping.priority.desc()).all()


class SystemRole(BaseModel, TimestampMixin, JSONDataMixin):
    """Model for system roles across all systems."""

    __tablename__ = "system_roles"
    __table_args__ = (
        UniqueConstraint(
            "role_name", "system_name", "role_type", name="uq_system_role"
        ),
    )

    role_name = db.Column(db.String(255), nullable=False, index=True)
    system_name = db.Column(
        db.String(100), nullable=False, index=True
    )  # 'keystone', 'ad_groups', 'genesys'
    role_type = db.Column(
        db.String(50), nullable=False, index=True
    )  # 'application', 'security_group', 'distribution_list'
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True, index=True)
    synced_at = db.Column(
        db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    role_mappings = db.relationship(
        "JobRoleMapping", back_populates="system_role", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<SystemRole {self.system_name}.{self.role_name} ({self.role_type})>"

    @classmethod
    def get_active_roles(cls) -> List["SystemRole"]:
        """Get all active system roles."""
        return (
            cls.query.filter_by(is_active=True)
            .order_by(cls.system_name, cls.role_name)
            .all()
        )

    @classmethod
    def get_by_system(cls, system_name: str) -> List["SystemRole"]:
        """Get all roles for a system."""
        return (
            cls.query.filter_by(system_name=system_name, is_active=True)
            .order_by(cls.role_name)
            .all()
        )

    @classmethod
    def get_by_system_and_type(
        cls, system_name: str, role_type: str
    ) -> List["SystemRole"]:
        """Get roles by system and type."""
        return (
            cls.query.filter_by(
                system_name=system_name, role_type=role_type, is_active=True
            )
            .order_by(cls.role_name)
            .all()
        )

    @classmethod
    def find_or_create(
        cls, role_name: str, system_name: str, role_type: str, **kwargs
    ) -> Tuple["SystemRole", bool]:
        """Find existing role or create new one."""
        role = cls.query.filter_by(
            role_name=role_name, system_name=system_name, role_type=role_type
        ).first()

        if role:
            return role, False

        role = cls(
            role_name=role_name, system_name=system_name, role_type=role_type, **kwargs
        )
        return role.save(), True


class JobRoleMapping(BaseModel, TimestampMixin, JSONDataMixin):
    """Model for job role mappings - defines expected roles for each job code."""

    __tablename__ = "job_role_mappings"
    __table_args__ = (
        UniqueConstraint("job_code_id", "system_role_id", name="uq_job_role_mapping"),
    )

    job_code_id = db.Column(
        db.Integer, db.ForeignKey("job_codes.id"), nullable=False, index=True
    )
    system_role_id = db.Column(
        db.Integer, db.ForeignKey("system_roles.id"), nullable=False, index=True
    )
    mapping_type = db.Column(
        db.String(50), nullable=False, default="required", index=True
    )  # 'required', 'optional', 'prohibited'
    priority = db.Column(db.Integer, default=1)  # for ordering/importance
    effective_date = db.Column(db.Date, default=date.today)
    expiration_date = db.Column(db.Date)
    notes = db.Column(db.Text)
    created_by = db.Column(db.String(255), nullable=False, index=True)

    # Relationships
    job_code = db.relationship("JobCode", back_populates="role_mappings")
    system_role = db.relationship("SystemRole", back_populates="role_mappings")

    def __repr__(self):
        return f"<JobRoleMapping {self.job_code.job_code} -> {self.system_role.role_name} ({self.mapping_type})>"

    @property
    def is_active(self) -> bool:
        """Check if mapping is currently active."""
        today = date.today()
        return self.effective_date <= today and (
            self.expiration_date is None or self.expiration_date >= today
        )

    @classmethod
    def get_mappings_for_job_code(
        cls, job_code: str, mapping_type: Optional[str] = None
    ) -> List["JobRoleMapping"]:
        """Get mappings for a specific job code."""
        query = cls.query.join(JobCode).filter(JobCode.job_code == job_code)
        if mapping_type:
            query = query.filter(cls.mapping_type == mapping_type)
        return query.order_by(cls.priority.desc()).all()

    @classmethod
    def get_active_mappings_for_job_code(cls, job_code: str) -> List["JobRoleMapping"]:
        """Get active mappings for a job code."""
        today = date.today()
        return (
            cls.query.join(JobCode)
            .filter(
                JobCode.job_code == job_code,
                cls.effective_date <= today,
                db.or_(cls.expiration_date.is_(None), cls.expiration_date >= today),
            )
            .order_by(cls.priority.desc())
            .all()
        )

    @classmethod
    def get_current_mappings(cls) -> List["JobRoleMapping"]:
        """Get all currently active mappings."""
        today = date.today()
        return (
            cls.query.filter(
                cls.effective_date <= today,
                db.or_(cls.expiration_date.is_(None), cls.expiration_date >= today),
            )
            .order_by(cls.priority.desc())
            .all()
        )

    def to_dict_with_relations(self) -> Dict[str, Any]:
        """Convert to dict including related job code and system role data."""
        result = self.to_dict()
        result["job_code"] = self.job_code.job_code if self.job_code else None
        result["job_title"] = self.job_code.job_title if self.job_code else None
        result["role_name"] = self.system_role.role_name if self.system_role else None
        result["system_name"] = (
            self.system_role.system_name if self.system_role else None
        )
        result["role_type"] = self.system_role.role_type if self.system_role else None
        result["is_active"] = self.is_active
        return result


class JobRoleMappingHistory(BaseModel):
    """Model for tracking changes to job role mappings."""

    __tablename__ = "job_role_mapping_history"

    mapping_id = db.Column(
        db.Integer, db.ForeignKey("job_role_mappings.id"), index=True
    )
    job_code = db.Column(db.String(50), nullable=False, index=True)
    role_name = db.Column(db.String(255), nullable=False)
    system_name = db.Column(db.String(100), nullable=False)
    old_mapping_type = db.Column(db.String(50))
    new_mapping_type = db.Column(db.String(50))
    old_priority = db.Column(db.Integer)
    new_priority = db.Column(db.Integer)
    change_type = db.Column(
        db.String(20), nullable=False, index=True
    )  # 'created', 'updated', 'deleted'
    changed_by = db.Column(db.String(255), nullable=False, index=True)
    change_reason = db.Column(db.Text)
    additional_data = db.Column(JSONB, default=dict)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    def __repr__(self):
        return f"<JobRoleMappingHistory {self.job_code} -> {self.role_name} ({self.change_type})>"

    @classmethod
    def log_change(
        cls,
        mapping: JobRoleMapping,
        change_type: str,
        changed_by: str,
        old_values: Optional[Dict[str, Any]] = None,
        change_reason: Optional[str] = None,
    ):
        """Log a change to a job role mapping."""
        history = cls(
            mapping_id=mapping.id if mapping.id else None,
            job_code=mapping.job_code.job_code,
            role_name=mapping.system_role.role_name,
            system_name=mapping.system_role.system_name,
            change_type=change_type,
            changed_by=changed_by,
            change_reason=change_reason,
        )

        if old_values and change_type == "updated":
            history.old_mapping_type = old_values.get("mapping_type")
            history.new_mapping_type = mapping.mapping_type
            history.old_priority = old_values.get("priority")
            history.new_priority = mapping.priority
        elif change_type == "created":
            history.new_mapping_type = mapping.mapping_type
            history.new_priority = mapping.priority
        elif change_type == "deleted":
            history.old_mapping_type = mapping.mapping_type
            history.old_priority = mapping.priority

        return history.save()


class ComplianceCheckRun(BaseModel, TimestampMixin, JSONDataMixin):
    """Model for compliance check run metadata."""

    __tablename__ = "compliance_check_runs"

    run_id = db.Column(db.String(100), unique=True, nullable=False, index=True)
    run_type = db.Column(
        db.String(50), nullable=False, default="manual"
    )  # 'manual', 'scheduled', 'triggered'
    scope = db.Column(
        db.String(100), default="all"
    )  # 'all', 'department', 'job_code', 'individual'
    scope_filter = db.Column(db.String(255))  # additional filter criteria
    total_employees = db.Column(db.Integer, default=0)
    total_checks = db.Column(db.Integer, default=0)
    compliant_count = db.Column(db.Integer, default=0)
    violation_count = db.Column(db.Integer, default=0)
    error_count = db.Column(db.Integer, default=0)
    duration_seconds = db.Column(db.Integer)
    status = db.Column(
        db.String(50), default="running", index=True
    )  # 'running', 'completed', 'failed', 'cancelled'
    started_by = db.Column(db.String(255), nullable=False, index=True)
    started_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    completed_at = db.Column(db.DateTime(timezone=True))
    error_message = db.Column(db.Text)

    # Relationships
    compliance_checks = db.relationship(
        "ComplianceCheck", back_populates="check_run", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<ComplianceCheckRun {self.run_id} ({self.status})>"

    def mark_completed(self, commit=True):
        """Mark the run as completed."""
        self.status = "completed"
        self.completed_at = datetime.now(timezone.utc)
        if self.started_at:
            self.duration_seconds = int(
                (self.completed_at - self.started_at).total_seconds()
            )
        return self.save(commit=commit)

    def mark_failed(self, error_message: str, commit=True):
        """Mark the run as failed."""
        self.status = "failed"
        self.completed_at = datetime.now(timezone.utc)
        self.error_message = error_message
        if self.started_at:
            self.duration_seconds = int(
                (self.completed_at - self.started_at).total_seconds()
            )
        return self.save(commit=commit)

    def update_stats(self, commit=True):
        """Update statistics from related compliance checks."""
        checks = self.compliance_checks
        self.total_checks = len(checks)
        self.compliant_count = sum(
            1 for c in checks if c.compliance_status == "compliant"
        )
        self.violation_count = sum(
            1 for c in checks if c.compliance_status != "compliant"
        )
        return self.save(commit=commit)


class ComplianceCheck(BaseModel, TimestampMixin, JSONDataMixin):
    """Model for individual compliance check results."""

    __tablename__ = "compliance_checks"

    check_run_id = db.Column(
        db.String(100),
        db.ForeignKey("compliance_check_runs.run_id"),
        nullable=False,
        index=True,
    )
    employee_upn = db.Column(db.String(255), nullable=False, index=True)
    job_code = db.Column(db.String(50), nullable=False, index=True)
    system_name = db.Column(db.String(100), nullable=False, index=True)
    role_name = db.Column(db.String(255), nullable=False)
    expected_mapping_type = db.Column(
        db.String(50)
    )  # what the mapping says it should be
    actual_assignment = db.Column(
        db.Boolean, nullable=False
    )  # whether they actually have the role
    compliance_status = db.Column(
        db.String(50), nullable=False, index=True
    )  # 'compliant', 'missing_required', 'has_prohibited', 'unexpected_role'
    violation_severity = db.Column(
        db.String(20), default="medium", index=True
    )  # 'low', 'medium', 'high', 'critical'
    notes = db.Column(db.Text)
    remediation_action = db.Column(
        db.String(100)
    )  # 'add_role', 'remove_role', 'no_action', 'manual_review'

    # Relationships
    check_run = db.relationship(
        "ComplianceCheckRun", back_populates="compliance_checks"
    )

    def __repr__(self):
        return f"<ComplianceCheck {self.employee_upn}: {self.role_name} ({self.compliance_status})>"

    @property
    def is_violation(self) -> bool:
        """Check if this is a compliance violation."""
        return self.compliance_status != "compliant"

    @classmethod
    def get_violations_for_employee(cls, employee_upn: str) -> List["ComplianceCheck"]:
        """Get all violations for an employee."""
        return (
            cls.query.filter(
                cls.employee_upn == employee_upn, cls.compliance_status != "compliant"
            )
            .order_by(cls.violation_severity.desc(), cls.created_at.desc())
            .all()
        )

    @classmethod
    def get_violations_by_severity(cls, severity: str) -> List["ComplianceCheck"]:
        """Get violations by severity level."""
        return (
            cls.query.filter(
                cls.violation_severity == severity, cls.compliance_status != "compliant"
            )
            .order_by(cls.created_at.desc())
            .all()
        )

    def to_dict_with_employee_info(self) -> Dict[str, Any]:
        """Convert to dict with additional employee context."""
        result = self.to_dict()
        # Add employee info from employee_profiles if available
        from app.models.employee_profiles import EmployeeProfiles

        profile = EmployeeProfiles.query.filter_by(upn=self.employee_upn).first()
        if profile:
            result["employee_job_code"] = profile.ukg_job_code
            result["employee_live_role"] = profile.live_role
        return result


class EmployeeRoleAssignment(BaseModel, TimestampMixin, JSONDataMixin):
    """Model for caching current role assignments from all systems."""

    __tablename__ = "employee_role_assignments"
    __table_args__ = (
        UniqueConstraint(
            "employee_upn",
            "system_name",
            "role_name",
            name="uq_employee_role_assignment",
        ),
    )

    employee_upn = db.Column(db.String(255), nullable=False, index=True)
    system_name = db.Column(db.String(100), nullable=False, index=True)
    role_name = db.Column(db.String(255), nullable=False, index=True)
    assignment_type = db.Column(
        db.String(50), default="direct"
    )  # 'direct', 'inherited', 'nested_group'
    assignment_source = db.Column(db.String(255))  # source group/container if inherited
    is_active = db.Column(db.Boolean, default=True, index=True)
    assigned_date = db.Column(db.DateTime(timezone=True))
    last_verified = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    def __repr__(self):
        return f"<EmployeeRoleAssignment {self.employee_upn}: {self.system_name}.{self.role_name}>"

    @classmethod
    def get_roles_for_employee(
        cls, employee_upn: str, system_name: Optional[str] = None
    ) -> List["EmployeeRoleAssignment"]:
        """Get all active role assignments for an employee."""
        query = cls.query.filter_by(employee_upn=employee_upn, is_active=True)
        if system_name:
            query = query.filter_by(system_name=system_name)
        return query.order_by(cls.system_name, cls.role_name).all()

    @classmethod
    def get_employees_with_role(
        cls, system_name: str, role_name: str
    ) -> List["EmployeeRoleAssignment"]:
        """Get all employees with a specific role."""
        return (
            cls.query.filter_by(
                system_name=system_name, role_name=role_name, is_active=True
            )
            .order_by(cls.employee_upn)
            .all()
        )

    @classmethod
    def sync_employee_roles(
        cls,
        employee_upn: str,
        system_name: str,
        current_roles: List[Dict[str, Any]],
        commit=True,
    ) -> Dict[str, int]:
        """Sync current roles for an employee in a specific system."""
        # Mark all existing roles as inactive first
        existing_assignments = cls.query.filter_by(
            employee_upn=employee_upn, system_name=system_name
        ).all()

        for assignment in existing_assignments:
            assignment.is_active = False

        # Process current roles
        created_count = 0
        updated_count = 0

        for role_data in current_roles:
            role_name = role_data.get("role_name")
            if not role_name:
                continue

            assignment = cls.query.filter_by(
                employee_upn=employee_upn, system_name=system_name, role_name=role_name
            ).first()

            if assignment:
                assignment.is_active = True
                assignment.last_verified = datetime.now(timezone.utc)
                assignment.assignment_type = role_data.get("assignment_type", "direct")
                assignment.assignment_source = role_data.get("assignment_source")
                updated_count += 1
            else:
                assignment = cls(
                    employee_upn=employee_upn,
                    system_name=system_name,
                    role_name=role_name,
                    assignment_type=role_data.get("assignment_type", "direct"),
                    assignment_source=role_data.get("assignment_source"),
                    assigned_date=role_data.get("assigned_date"),
                    is_active=True,
                )
                assignment.save(commit=False)
                created_count += 1

        if commit:
            db.session.commit()

        return {"created": created_count, "updated": updated_count}
