"""factory_boy factories for workflow models (app/models/workflow.py).

Provides WorkflowFactory, WorkflowItemFactory, and StandardOffboardingItemFactory
for use in unit and integration tests.
"""

import factory
from factory.alchemy import SQLAlchemyModelFactory
from app.database import db
from app.models.workflow import Workflow, WorkflowItem, StandardOffboardingItem


class WorkflowFactory(SQLAlchemyModelFactory):
    class Meta:
        model = Workflow
        sqlalchemy_session = db.session
        sqlalchemy_session_persistence = "flush"

    workflow_type = "onboarding"
    status = "active"
    employee_name = factory.Sequence(lambda n: f"Employee {n}")
    employee_email = factory.LazyAttribute(
        lambda o: f"{o.employee_name.lower().replace(' ', '.')}@test.com"
    )
    job_code = "JC0001"
    created_by = "admin@test.com"


class WorkflowItemFactory(SQLAlchemyModelFactory):
    class Meta:
        model = WorkflowItem
        sqlalchemy_session = db.session
        sqlalchemy_session_persistence = "flush"

    workflow = factory.SubFactory(WorkflowFactory)
    item_text = factory.Sequence(lambda n: f"Test item {n}")
    item_source = "role_mapping"
    action_type = "add"
    sort_order = 0
    status = "pending"


class StandardOffboardingItemFactory(SQLAlchemyModelFactory):
    class Meta:
        model = StandardOffboardingItem
        sqlalchemy_session = db.session
        sqlalchemy_session_persistence = "flush"

    item_text = factory.Sequence(lambda n: f"Standard offboarding item {n}")
    sort_order = 0
    is_active = True
    created_by = "admin@test.com"
