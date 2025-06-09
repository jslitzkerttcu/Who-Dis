"""Admin user management routes."""

from flask import render_template, request, jsonify, session
from app.middleware.auth import require_role
from app.models import User
from app.database import db
from app.utils.error_handler import handle_errors
from app.models.user_note import UserNote
from app.blueprints.admin import admin_bp
from sqlalchemy.orm import joinedload
import logging

logger = logging.getLogger(__name__)


@admin_bp.route("/users")
@require_role("admin")
@handle_errors()
def users():
    """User management page."""
    # Eager load notes to prevent N+1 queries when displaying note counts
    users_list = (
        User.query.options(joinedload(User.notes))
        .order_by(User.created_at.desc())
        .all()
    )
    return render_template("admin/users.html", users=users_list)


@admin_bp.route("/api/users")
@require_role("admin")
@handle_errors(json_response=True)
def api_users():
    """API endpoint for user management."""
    users_list = User.query.order_by(User.created_at.desc()).all()
    users_data = []

    for user in users_list:
        users_data.append(
            {
                "id": user.id,
                "email": user.email,
                "role": user.role,
                "is_active": user.is_active,
                "created_at": user.created_at.isoformat() if user.created_at else None,
                "last_login": user.last_login.isoformat() if user.last_login else None,
            }
        )

    return jsonify({"users": users_data})


@admin_bp.route("/api/users", methods=["POST"])
@require_role("admin")
@handle_errors(json_response=True)
def api_add_user():
    """Add a new user."""
    from app.services.audit_service_postgres import audit_service

    data = request.get_json()
    email = data.get("email", "").lower().strip()
    role = data.get("role", "viewer")

    if not email:
        return jsonify({"success": False, "message": "Email is required"}), 400

    # Check if user already exists
    if User.query.filter_by(email=email).first():
        return jsonify({"success": False, "message": "User already exists"}), 400

    # Create user
    admin_email = request.headers.get(
        "X-MS-CLIENT-PRINCIPAL-NAME", request.remote_user or "unknown"
    )

    user = User.create_user(email=email, role=role, created_by=admin_email)

    # Log action
    admin_role = getattr(request, "user_role", None)
    user_ip = request.headers.get("X-Forwarded-For", request.remote_addr)

    audit_service.log_admin_action(
        user_email=admin_email,
        action="add_user",
        target=f"user:{email}",
        user_role=admin_role,
        ip_address=user_ip,
        user_agent=request.headers.get("User-Agent"),
        success=True,
        details={"new_user": email, "role": role},
    )

    return jsonify(
        {
            "success": True,
            "message": "User added successfully",
            "user": {
                "id": user.id,
                "email": user.email,
                "role": user.role,
                "is_active": user.is_active,
                "created_at": user.created_at.isoformat(),
            },
        }
    )


@admin_bp.route("/api/users/<int:user_id>", methods=["PUT"])
@require_role("admin")
@handle_errors(json_response=True)
def api_update_user(user_id):
    """Update user details."""
    from app.services.audit_service_postgres import audit_service

    user = User.query.get(user_id)
    if not user:
        return jsonify({"success": False, "message": "User not found"}), 404

    data = request.get_json()
    old_role = user.role
    old_active = user.is_active

    # Example of using transaction context manager
    from app.utils import transaction_scope

    try:
        with transaction_scope():
            if "role" in data:
                user.role = data["role"]
            if "is_active" in data:
                user.is_active = data["is_active"]
            # No need to commit - transaction_scope handles it
    except Exception as e:
        logger.error(f"Failed to update user {user.email}: {e}")
        return jsonify({"success": False, "message": "Failed to update user"}), 500

    # Log action
    admin_email = request.headers.get(
        "X-MS-CLIENT-PRINCIPAL-NAME", request.remote_user or "unknown"
    )
    admin_role = getattr(request, "user_role", None)
    user_ip = request.headers.get("X-Forwarded-For", request.remote_addr)

    changes = []
    if old_role != user.role:
        changes.append(f"role: {old_role} → {user.role}")
    if old_active != user.is_active:
        changes.append(f"active: {old_active} → {user.is_active}")

    audit_service.log_admin_action(
        user_email=admin_email,
        action="update_user",
        target=f"user:{user.email}",
        user_role=admin_role,
        ip_address=user_ip,
        user_agent=request.headers.get("User-Agent"),
        success=True,
        details={
            "user": user.email,
            "changes": ", ".join(changes) if changes else "no changes",
        },
    )

    return jsonify({"success": True, "message": "User updated successfully"})


@admin_bp.route("/api/users/<int:user_id>", methods=["DELETE"])
@require_role("admin")
@handle_errors(json_response=True)
def api_delete_user(user_id):
    """Delete a user."""
    from app.services.audit_service_postgres import audit_service

    user = User.query.get(user_id)
    if not user:
        return jsonify({"success": False, "message": "User not found"}), 404

    user_email = user.email

    try:
        db.session.delete(user)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to delete user {user_email}: {e}")
        return jsonify({"success": False, "message": "Failed to delete user"}), 500

    # Log action
    admin_email = request.headers.get(
        "X-MS-CLIENT-PRINCIPAL-NAME", request.remote_user or "unknown"
    )
    admin_role = getattr(request, "user_role", None)
    user_ip = request.headers.get("X-Forwarded-For", request.remote_addr)

    audit_service.log_admin_action(
        user_email=admin_email,
        action="delete_user",
        target=f"user:{user_email}",
        user_role=admin_role,
        ip_address=user_ip,
        user_agent=request.headers.get("User-Agent"),
        success=True,
        details={"deleted_user": user_email},
    )

    return jsonify({"success": True, "message": "User deleted successfully"})


# User Notes Routes
@admin_bp.route("/api/users/<int:user_id>/notes", methods=["GET"])
@require_role("admin")
@handle_errors(json_response=True)
def api_get_user_notes(user_id):
    """Get notes for a specific user in admin context."""
    notes = UserNote.get_user_notes(user_id, context="admin")
    notes_data = []

    for note in notes:
        notes_data.append(
            {
                "id": note.id,
                "note": note.note,
                "created_by": note.created_by,
                "created_at": note.created_at.isoformat() if note.created_at else None,
                "updated_at": note.updated_at.isoformat() if note.updated_at else None,
            }
        )

    return jsonify({"notes": notes_data})


@admin_bp.route("/api/users/<int:user_id>/notes", methods=["POST"])
@require_role("admin")
@handle_errors(json_response=True)
def api_add_user_note(user_id):
    """Add a note to a user."""
    data = request.get_json()
    note_text = data.get("note", "").strip()

    if not note_text:
        return jsonify({"success": False, "message": "Note cannot be empty"}), 400

    # Get current user
    admin_email = session.get("user_email", "system")

    # Create note with admin context
    note = UserNote.create_note(
        user_id=user_id, note_text=note_text, created_by=admin_email, context="admin"
    )

    return jsonify(
        {
            "success": True,
            "message": "Note added successfully",
            "note": {
                "id": note.id,
                "note": note.note,
                "created_by": note.created_by,
                "created_at": note.created_at.isoformat() if note.created_at else None,
            },
        }
    )


@admin_bp.route("/api/users/notes/<int:note_id>", methods=["PUT"])
@require_role("admin")
@handle_errors(json_response=True)
def api_update_user_note(note_id):
    """Update a user note."""
    note = UserNote.query.get(note_id)
    if not note:
        return jsonify({"success": False, "message": "Note not found"}), 404

    data = request.get_json()
    note_text = data.get("note", "").strip()

    if not note_text:
        return jsonify({"success": False, "message": "Note cannot be empty"}), 400

    note.update_note(note_text)

    return jsonify({"success": True, "message": "Note updated successfully"})


@admin_bp.route("/api/users/notes/<int:note_id>", methods=["DELETE"])
@require_role("admin")
@handle_errors(json_response=True)
def api_delete_user_note(note_id):
    """Delete a user note."""
    note = UserNote.query.get(note_id)
    if not note:
        return jsonify({"success": False, "message": "Note not found"}), 404

    # Soft delete
    note.deactivate()

    return jsonify({"success": True, "message": "Note deleted successfully"})


@admin_bp.route("/api/users/by-email/<email>/notes", methods=["GET"])
@require_role("admin")
@handle_errors(json_response=True)
def api_get_user_notes_by_email(email):
    """Get notes for a user by email address."""
    # Find user by email
    user = User.query.filter_by(email=email.lower()).first()

    # Always return 200 with empty notes if user doesn't exist
    if not user:
        return jsonify({"notes": []})

    notes = UserNote.get_user_notes(user.id, context="admin")
    notes_data = []

    for note in notes:
        notes_data.append(
            {
                "id": note.id,
                "note": note.note,
                "created_by": note.created_by,
                "created_at": note.created_at.isoformat() if note.created_at else None,
                "updated_at": note.updated_at.isoformat() if note.updated_at else None,
            }
        )

    return jsonify({"notes": notes_data})
