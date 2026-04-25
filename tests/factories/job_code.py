"""factory_boy factory for JobCode (app/models/job_role_compliance.py:JobCode).

Required columns: job_code (unique), job_title.
"""
import factory
from factory.alchemy import SQLAlchemyModelFactory
from app.database import db
from app.models.job_role_compliance import JobCode


class JobCodeFactory(SQLAlchemyModelFactory):
    class Meta:
        model = JobCode
        sqlalchemy_session = db.session
        sqlalchemy_session_persistence = "flush"

    job_code = factory.Sequence(lambda n: f"JC{n:04d}")
    job_title = factory.Sequence(lambda n: f"Test Role {n}")
    is_active = True
