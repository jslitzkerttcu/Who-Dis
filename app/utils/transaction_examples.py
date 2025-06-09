"""
Examples of using transaction management utilities in WhoDis.

This file demonstrates various transaction patterns for database operations.
"""

from app.utils import transaction_scope, batch_operation, safe_commit, with_transaction
from app.models import User, UserNote
from app.database import db


# Example 1: Using transaction_scope for multiple operations
def update_user_with_note(user_id: int, new_role: str, note_text: str):
    """Update user role and add a note in a single transaction."""
    with transaction_scope():
        # All operations within this block are part of the same transaction
        user = User.get_by_id(user_id)
        user.update(role=new_role, commit=False)  # Don't commit yet

        UserNote.create_note(
            user_id=user_id,
            note_text=f"Role changed to {new_role}: {note_text}",
            created_by="system",
            context="admin",
        ).save(commit=False)  # Don't commit yet

        # Both changes committed together at the end of the context
    # If any exception occurs, everything is rolled back


# Example 2: Using batch_operation for bulk updates
def deactivate_inactive_users(days_inactive: int = 90):
    """Deactivate users who haven't logged in for X days."""
    from datetime import datetime, timedelta

    cutoff_date = datetime.utcnow() - timedelta(days=days_inactive)

    with batch_operation():
        # Autoflush is disabled for better performance
        inactive_users = User.query.filter(
            User.last_login < cutoff_date, User.is_active
        ).all()

        for user in inactive_users:
            user.deactivate()  # Each deactivate doesn't commit
            UserNote.create_note(
                user_id=user.id,
                note_text=f"Auto-deactivated due to {days_inactive} days of inactivity",
                created_by="system",
                context="system",
            ).save(commit=False)

        # Single commit at the end for all changes

    return len(inactive_users)


# Example 3: Using the decorator pattern
@with_transaction
def bulk_role_update(email_role_pairs):
    """Update multiple users' roles in a single transaction."""
    updated_count = 0

    for email, new_role in email_role_pairs:
        user = User.get_by_email(email)
        if user:
            user.change_role(new_role).save(commit=False)
            updated_count += 1

    # Transaction automatically committed when function returns
    return updated_count


# Example 4: Using safe_commit for optional operations
def add_optional_note(user_id: int, note_text: str):
    """Add a note if possible, but don't fail the request if it doesn't work."""
    note = UserNote(user_id=user_id, note_text=note_text, created_by="system")
    db.session.add(note)

    # Returns True if commit succeeded, False otherwise
    if safe_commit():
        return {"success": True, "note_id": note.id}
    else:
        return {"success": False, "message": "Note could not be saved"}


# Example 5: Manual transaction control for complex operations
def complex_user_migration():
    """Example of manual transaction control for complex operations."""
    try:
        # Start manual transaction control
        # Note: autocommit is handled by SQLAlchemy automatically

        # Phase 1: Update all viewer roles
        User.query.filter_by(role="viewer").update(
            {"role": "reader"}, synchronize_session=False
        )

        # Check intermediate state
        reader_count = User.query.filter_by(role="reader").count()
        if reader_count == 0:
            db.session.rollback()
            return {"error": "No users were updated"}

        # Phase 2: Add migration notes
        for user in User.query.filter_by(role="reader"):
            UserNote(
                user_id=user.id,
                note_text="Role migrated from viewer to reader",
                created_by="migration",
            ).save(commit=False)

        # Everything looks good, commit
        db.session.commit()
        return {"success": True, "migrated": reader_count}

    except Exception as e:
        db.session.rollback()
        return {"error": str(e)}
    finally:
        # Note: autocommit is handled by SQLAlchemy automatically
        pass


# Example 6: Using get_or_create in batch operations
def ensure_users_exist(email_list):
    """Ensure multiple users exist, creating them if necessary."""
    with transaction_scope():
        results = {"created": 0, "existing": 0}

        for email in email_list:
            user, created = User.get_or_create(
                email=email.lower(), role="viewer", created_by="bulk_import"
            )
            # get_or_create uses save() internally, so we don't commit

            if created:
                results["created"] += 1
            else:
                results["existing"] += 1

        # All users created/verified in a single transaction
        return results


# Example 7: Cleanup operations with controlled commits
def cleanup_expired_data(batch_size=100):
    """Clean up expired data in batches to avoid long transactions."""
    from app.models import UserSession, SearchCache

    total_cleaned = 0

    # Clean up sessions in batches
    while True:
        with transaction_scope():
            # Get a batch of expired sessions
            # Get expired sessions using a proper class method or datetime comparison
            from datetime import datetime

            expired = (
                UserSession.query.filter(UserSession.expires_at < datetime.utcnow())
                .limit(batch_size)
                .all()
            )

            if not expired:
                break

            for session in expired:
                db.session.delete(session)

            total_cleaned += len(expired)

        # Each batch is a separate transaction

    # Clean up search cache
    SearchCache.cleanup_expired(commit=True)

    return total_cleaned


# Best Practices Summary:
# 1. Use transaction_scope() for operations that should succeed or fail together
# 2. Use batch_operation() for bulk updates to improve performance
# 3. Use @with_transaction decorator for functions that should be transactional
# 4. Use safe_commit() when a commit failure shouldn't break the flow
# 5. Always use commit=False when doing multiple operations in a transaction
# 6. Keep transactions as short as possible to avoid lock contention
# 7. Use batching for large cleanup or migration operations
