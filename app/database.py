from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import create_engine, pool
from sqlalchemy.orm import scoped_session, sessionmaker
import os
import logging

logger = logging.getLogger(__name__)

db = SQLAlchemy()


def get_database_uri():
    """Get PostgreSQL database URI from environment variables

    Note: We must use os.getenv here instead of config_get because
    the configuration service needs a database connection to function.
    PostgreSQL credentials must remain in environment variables.
    """
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    database = os.getenv("POSTGRES_DB", "whodis_db")
    user = os.getenv("POSTGRES_USER", "whodis_user")
    password = os.getenv("POSTGRES_PASSWORD", "")

    if not password:
        logger.warning("POSTGRES_PASSWORD not set in environment variables")

    return f"postgresql://{user}:{password}@{host}:{port}/{database}"


def init_db(app):
    """Initialize database with Flask app"""
    app.config["SQLALCHEMY_DATABASE_URI"] = get_database_uri()
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_size": 10,
        "pool_recycle": 3600,
        "pool_pre_ping": True,
        "max_overflow": 20,
    }

    db.init_app(app)

    # Create tables if they don't exist
    with app.app_context():
        try:
            db.create_all()
            logger.info("Database tables created/verified successfully")
        except Exception as e:
            logger.error(f"Failed to create database tables: {e}")


# For direct database access without Flask context
class DatabaseConnection:
    """Standalone database connection for background tasks"""

    def __init__(self):
        self.engine = None
        self.session_factory = None
        self._session = None

    def connect(self):
        """Create database engine and session factory"""
        if not self.engine:
            self.engine = create_engine(
                get_database_uri(),
                poolclass=pool.QueuePool,
                pool_size=5,
                pool_recycle=3600,
                pool_pre_ping=True,
            )
            self.session_factory = sessionmaker(bind=self.engine)
            self._session = scoped_session(self.session_factory)

    @property
    def session(self):
        """Get current session"""
        if not self._session:
            self.connect()
        return self._session

    def close(self):
        """Close database connection"""
        if self._session:
            self._session.remove()
        if self.engine:
            self.engine.dispose()
