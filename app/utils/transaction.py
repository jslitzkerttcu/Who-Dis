"""Transaction management utilities for WhoDis."""

import logging
from contextlib import contextmanager
from typing import Generator, Any
from app.database import db

logger = logging.getLogger(__name__)


@contextmanager
def transaction_scope() -> Generator[Any, None, None]:
    """Provide a transactional scope around a series of operations.

    Usage:
        with transaction_scope():
            user1.update(role='admin', commit=False)
            user2.update(role='editor', commit=False)
            # Both changes committed together

    If an exception occurs, all changes are rolled back.
    """
    try:
        yield db.session
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error(f"Transaction rolled back due to error: {e}")
        raise
    finally:
        # SQLAlchemy will handle closing the session when needed
        pass


@contextmanager
def batch_operation() -> Generator[None, None, None]:
    """Context manager for batch operations without auto-commit.

    Usage:
        with batch_operation():
            for user in users:
                user.update_last_login()  # No individual commits
            # Single commit at the end
    """
    # Store original autoflush state
    original_autoflush = db.session.autoflush

    try:
        # Disable autoflush for batch operations
        db.session.autoflush = False
        yield
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error(f"Batch operation failed: {e}")
        raise
    finally:
        # Restore original autoflush state
        db.session.autoflush = original_autoflush


def safe_commit() -> bool:
    """Safely commit the current transaction with error handling.

    Returns:
        bool: True if commit succeeded, False otherwise.
    """
    try:
        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        logger.error(f"Commit failed: {e}")
        return False


def with_transaction(func):
    """Decorator to wrap a function in a transaction.

    Usage:
        @with_transaction
        def update_multiple_users(user_ids, new_role):
            for user_id in user_ids:
                user = User.get_by_id(user_id)
                user.update(role=new_role, commit=False)
    """

    def wrapper(*args, **kwargs):
        with transaction_scope():
            return func(*args, **kwargs)

    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    return wrapper
