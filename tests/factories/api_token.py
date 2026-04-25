"""factory_boy factory for ApiToken.

Default expires_at = now+1h; `expiring=True` trait sets expires_at within the
token-refresh service's 10-minute threshold (token_refresh_service.py:92-102).
"""
from datetime import datetime, timedelta, timezone
import factory
from factory.alchemy import SQLAlchemyModelFactory
from app.database import db
from app.models.api_token import ApiToken


class ApiTokenFactory(SQLAlchemyModelFactory):
    class Meta:
        model = ApiToken
        sqlalchemy_session = db.session
        sqlalchemy_session_persistence = "flush"

    service_name = factory.Sequence(lambda n: f"service-{n}")
    access_token = factory.Sequence(lambda n: f"fake-token-{n}")
    expires_at = factory.LazyFunction(lambda: datetime.now(timezone.utc) + timedelta(hours=1))

    class Params:
        # Trait: token within the 10-minute refresh threshold
        expiring = factory.Trait(
            expires_at=factory.LazyFunction(
                lambda: datetime.now(timezone.utc) + timedelta(minutes=5)
            )
        )
