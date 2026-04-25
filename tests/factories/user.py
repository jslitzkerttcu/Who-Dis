"""factory_boy factory for User model (D-07).

Emails are lowercase to satisfy User.get_by_email() contract (it does .lower().strip() before lookup).
"""
import factory
from factory.alchemy import SQLAlchemyModelFactory
from app.database import db
from app.models.user import User


class UserFactory(SQLAlchemyModelFactory):
    class Meta:
        model = User
        sqlalchemy_session = db.session
        sqlalchemy_session_persistence = "flush"

    email = factory.Sequence(lambda n: f"user{n}@test.local")
    role = User.ROLE_VIEWER
    is_active = True
