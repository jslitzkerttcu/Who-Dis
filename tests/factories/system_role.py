"""factory_boy factory for SystemRole (app/models/job_role_compliance.py:SystemRole).

Required columns: role_name, system_name, role_type. The model enforces a unique
constraint over (role_name, system_name, role_type) — the sequence on role_name
keeps generated rows distinct.
"""
import factory
from factory.alchemy import SQLAlchemyModelFactory
from app.database import db
from app.models.job_role_compliance import SystemRole


class SystemRoleFactory(SQLAlchemyModelFactory):
    class Meta:
        model = SystemRole
        sqlalchemy_session = db.session
        sqlalchemy_session_persistence = "flush"

    role_name = factory.Sequence(lambda n: f"role-{n}")
    system_name = "ad_groups"
    role_type = "security_group"
    is_active = True
