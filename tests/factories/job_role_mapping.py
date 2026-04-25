"""factory_boy factory for JobRoleMapping (Plan 02-05 gap closure).

Uses SubFactory to auto-create JobCode + SystemRole rows. Tests that need to
control parents should pre-create them and pass `job_code=...` /
`system_role=...` (relationship-style) so the SubFactory does not fire.

The JobRoleMapping model exposes ORM relationships `job_code` and
`system_role` (back-populated from JobCode.role_mappings and
SystemRole.role_mappings), so factory_boy's SubFactory + relationship
assignment resolves the FK ids on flush.
"""
import factory
from factory.alchemy import SQLAlchemyModelFactory
from app.database import db
from app.models.job_role_compliance import JobRoleMapping
from tests.factories.job_code import JobCodeFactory
from tests.factories.system_role import SystemRoleFactory


class JobRoleMappingFactory(SQLAlchemyModelFactory):
    class Meta:
        model = JobRoleMapping
        sqlalchemy_session = db.session
        sqlalchemy_session_persistence = "flush"

    job_code = factory.SubFactory(JobCodeFactory)
    system_role = factory.SubFactory(SystemRoleFactory)
    mapping_type = "required"
    priority = 1
    created_by = "test-suite"
