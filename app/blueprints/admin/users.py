"""
User management functionality for admin blueprint.
Handles user CRUD operations and role management.
"""

from flask import render_template, request, jsonify
from app.middleware.auth import require_role
from app.database import db
from app.models import User, UserNote
from app.services.audit_service_postgres import audit_service


@require_role("admin")
def manage_users():
    """Display user management page."""
    return render_template("admin/users.html")


@require_role("admin")
def api_users():
    """Get all users."""
    users = User.query.order_by(User.created_at.desc()).all()

    # Check if this is an Htmx request
    if request.headers.get("HX-Request"):
        return _render_users_table(users)

    results = []
    for user in users:
        results.append(
            {
                "id": user.id,
                "email": user.email,
                "role": user.role,
                "is_active": user.is_active,
                "created_at": user.created_at.isoformat(),
                "updated_at": user.updated_at.isoformat() if user.updated_at else None,
            }
        )

    return jsonify({"users": results})


@require_role("admin")
def add_user():
    """Add a new user."""
    data = request.get_json()
    email = data.get("email", "").lower()
    role = data.get("role", "viewer")

    if not email:
        return jsonify({"success": False, "error": "Email is required"}), 400

    # Check if user already exists
    if User.query.filter_by(email=email).first():
        return jsonify({"success": False, "error": "User already exists"}), 409

    # Add user
    admin_email = request.headers.get(
        "X-MS-CLIENT-PRINCIPAL-NAME", request.remote_user or "unknown"
    )
    user = User(email=email, role=role, created_by=admin_email)
    db.session.add(user)
    db.session.commit()

    # Audit log
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
        details={"user": email, "role": role},
    )

    return jsonify({"success": True, "message": "User added successfully"})


@require_role("admin")
def update_user():
    """Update an existing user."""
    data = request.get_json()
    user_id = data.get("user_id")
    role = data.get("role")
    is_active = data.get("is_active")

    if not user_id:
        return jsonify({"success": False, "error": "User ID is required"}), 400

    user = User.query.get(user_id)
    if not user:
        return jsonify({"success": False, "error": "User not found"}), 404

    # Track changes
    changes = []
    if role and role != user.role:
        changes.append(f"role: {user.role} → {role}")
        user.role = role

    if is_active is not None and is_active != user.is_active:
        changes.append(f"active: {user.is_active} → {is_active}")
        user.is_active = is_active

    if not changes:
        return jsonify({"success": True, "message": "No changes made"})

    # Update user
    admin_email = request.headers.get(
        "X-MS-CLIENT-PRINCIPAL-NAME", request.remote_user or "unknown"
    )
    user.updated_by = admin_email
    db.session.commit()

    # Audit log
    admin_role = getattr(request, "user_role", None)
    user_ip = request.headers.get("X-Forwarded-For", request.remote_addr)

    audit_service.log_admin_action(
        user_email=admin_email,
        action="update_user",
        target=f"user:{user.email}",
        user_role=admin_role,
        ip_address=user_ip,
        user_agent=request.headers.get("User-Agent"),
        success=True,
        details={"user": user.email, "changes": ", ".join(changes)},
    )

    return jsonify({"success": True, "message": "User updated successfully"})


@require_role("admin")
def delete_user():
    """Delete a user."""
    data = request.get_json()
    user_id = data.get("user_id")

    if not user_id:
        return jsonify({"success": False, "error": "User ID is required"}), 400

    user = User.query.get(user_id)
    if not user:
        return jsonify({"success": False, "error": "User not found"}), 404

    # Don't allow self-deletion
    admin_email = request.headers.get(
        "X-MS-CLIENT-PRINCIPAL-NAME", request.remote_user or "unknown"
    )
    if user.email == admin_email:
        return jsonify(
            {"success": False, "error": "Cannot delete your own account"}
        ), 400

    # Delete user
    user_email = user.email
    db.session.delete(user)
    db.session.commit()

    # Audit log
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
        details={"user": user_email},
    )

    return jsonify({"success": True, "message": "User deleted successfully"})


@require_role("admin")
def get_user_notes(user_id):
    """Get notes for a specific user."""
    notes = (
        UserNote.query.filter_by(user_id=user_id)
        .order_by(UserNote.created_at.desc())
        .all()
    )

    return jsonify(
        {
            "notes": [
                {
                    "id": note.id,
                    "content": note.content,
                    "created_by": note.created_by,
                    "created_at": note.created_at.isoformat(),
                    "updated_at": note.updated_at.isoformat()
                    if note.updated_at
                    else None,
                }
                for note in notes
            ]
        }
    )


@require_role("admin")
def add_user_note(user_id):
    """Add a note to a user."""
    # Verify user exists
    user = User.query.get(user_id)
    if not user:
        return jsonify({"success": False, "error": "User not found"}), 404

    data = request.get_json()
    content = data.get("content", "").strip()

    if not content:
        return jsonify({"success": False, "error": "Note content is required"}), 400

    # Create note
    admin_email = request.headers.get(
        "X-MS-CLIENT-PRINCIPAL-NAME", request.remote_user or "unknown"
    )
    note = UserNote(
        user_id=user_id,
        user_email=user.email,
        content=content,
        created_by=admin_email,
    )
    db.session.add(note)
    db.session.commit()

    # Audit log
    admin_role = getattr(request, "user_role", None)
    user_ip = request.headers.get("X-Forwarded-For", request.remote_addr)

    audit_service.log_admin_action(
        user_email=admin_email,
        action="add_user_note",
        target=f"user:{user.email}",
        user_role=admin_role,
        ip_address=user_ip,
        user_agent=request.headers.get("User-Agent"),
        success=True,
        details={"user": user.email, "note_id": note.id},
    )

    return jsonify(
        {
            "success": True,
            "note": {
                "id": note.id,
                "content": note.content,
                "created_by": note.created_by,
                "created_at": note.created_at.isoformat(),
            },
        }
    )


@require_role("admin")
def update_user_note(note_id):
    """Update a user note."""
    note = UserNote.query.get(note_id)
    if not note:
        return jsonify({"success": False, "error": "Note not found"}), 404

    data = request.get_json()
    content = data.get("content", "").strip()

    if not content:
        return jsonify({"success": False, "error": "Note content is required"}), 400

    # Update note
    admin_email = request.headers.get(
        "X-MS-CLIENT-PRINCIPAL-NAME", request.remote_user or "unknown"
    )
    note.content = content
    note.updated_by = admin_email
    db.session.commit()

    # Audit log
    admin_role = getattr(request, "user_role", None)
    user_ip = request.headers.get("X-Forwarded-For", request.remote_addr)

    audit_service.log_admin_action(
        user_email=admin_email,
        action="update_user_note",
        target=f"user:{note.user_email}",
        user_role=admin_role,
        ip_address=user_ip,
        user_agent=request.headers.get("User-Agent"),
        success=True,
        details={"user": note.user_email, "note_id": note.id},
    )

    return jsonify({"success": True, "message": "Note updated successfully"})


@require_role("admin")
def delete_user_note(note_id):
    """Delete a user note."""
    note = UserNote.query.get(note_id)
    if not note:
        return jsonify({"success": False, "error": "Note not found"}), 404

    # Delete note
    admin_email = request.headers.get(
        "X-MS-CLIENT-PRINCIPAL-NAME", request.remote_user or "unknown"
    )
    user_email = note.user_email
    db.session.delete(note)
    db.session.commit()

    # Audit log
    admin_role = getattr(request, "user_role", None)
    user_ip = request.headers.get("X-Forwarded-For", request.remote_addr)

    audit_service.log_admin_action(
        user_email=admin_email,
        action="delete_user_note",
        target=f"user:{user_email}",
        user_role=admin_role,
        ip_address=user_ip,
        user_agent=request.headers.get("User-Agent"),
        success=True,
        details={"user": user_email, "note_id": note_id},
    )

    return jsonify({"success": True, "message": "Note deleted successfully"})


@require_role("admin")
def get_user_notes_by_email(email):
    """Get notes for a user by email."""
    notes = (
        UserNote.query.filter_by(user_email=email)
        .order_by(UserNote.created_at.desc())
        .all()
    )

    return jsonify(
        {
            "notes": [
                {
                    "id": note.id,
                    "content": note.content,
                    "created_by": note.created_by,
                    "created_at": note.created_at.isoformat(),
                    "updated_at": note.updated_at.isoformat()
                    if note.updated_at
                    else None,
                }
                for note in notes
            ]
        }
    )


@require_role("admin")
def add_user_note_by_email(email):
    """Add a note by user email (for users not yet in the system)."""
    data = request.get_json()
    content = data.get("content", "").strip()

    if not content:
        return jsonify({"success": False, "error": "Note content is required"}), 400

    # Create note
    admin_email = request.headers.get(
        "X-MS-CLIENT-PRINCIPAL_NAME", request.remote_user or "unknown"
    )
    note = UserNote(
        user_email=email,
        content=content,
        created_by=admin_email,
    )
    db.session.add(note)
    db.session.commit()

    # Audit log
    admin_role = getattr(request, "user_role", None)
    user_ip = request.headers.get("X-Forwarded-For", request.remote_addr)

    audit_service.log_admin_action(
        user_email=admin_email,
        action="add_user_note",
        target=f"user:{email}",
        user_role=admin_role,
        ip_address=user_ip,
        user_agent=request.headers.get("User-Agent"),
        success=True,
        details={"user": email, "note_id": note.id},
    )

    return jsonify(
        {
            "success": True,
            "note": {
                "id": note.id,
                "content": note.content,
                "created_by": note.created_by,
                "created_at": note.created_at.isoformat(),
            },
        }
    )


# ===== Htmx Routes =====


@require_role("admin")
def edit_user_modal(user_id):
    """Get edit user modal content."""
    user = User.query.get(user_id)
    if not user:
        return '<div class="p-4 text-red-600">User not found</div>', 404

    roles = ["viewer", "editor", "admin"]
    role_options = "".join(
        [
            f'<option value="{role}" {"selected" if user.role == role else ""}>{role.capitalize()}</option>'
            for role in roles
        ]
    )

    return f'''
    <div class="bg-white rounded-lg">
        <div class="flex justify-between items-center p-4 border-b">
            <h3 class="text-lg font-semibold text-gray-900">Edit User</h3>
            <button onclick="document.getElementById('editUserModal').classList.add('hidden')"
                    class="text-gray-400 hover:text-gray-500">
                <i class="fas fa-times"></i>
            </button>
        </div>
        <form hx-post="/admin/api/users/{user.id}/update"
              hx-target="#userTableBody"
              hx-swap="innerHTML"
              class="p-4">
            <div class="mb-4">
                <label class="block text-sm font-medium text-gray-700 mb-2">Email</label>
                <input type="email" value="{user.email}" disabled
                       class="w-full px-3 py-2 border border-gray-300 rounded-md bg-gray-100">
            </div>
            <div class="mb-4">
                <label class="block text-sm font-medium text-gray-700 mb-2">Role</label>
                <select name="role" 
                        class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:border-ttcu-green">
                    {role_options}
                </select>
            </div>
            <div class="flex justify-end space-x-2">
                <button type="button"
                        onclick="document.getElementById('editUserModal').classList.add('hidden')"
                        class="px-4 py-2 bg-gray-200 text-gray-700 rounded-md hover:bg-gray-300">
                    Cancel
                </button>
                <button type="submit"
                        class="px-4 py-2 bg-ttcu-green text-white rounded-md hover:bg-green-700">
                    Save Changes
                </button>
            </div>
        </form>
    </div>
    '''


@require_role("admin")
def update_user_htmx(user_id):
    """Update user via Htmx - returns updated HTML."""
    user = User.query.get(user_id)
    if not user:
        return '<div class="p-4 text-red-600">User not found</div>', 404

    new_role = request.form.get("role", user.role)
    old_role = user.role

    # Update user
    admin_email = request.headers.get(
        "X-MS-CLIENT-PRINCIPAL-NAME", request.remote_user or "unknown"
    )
    user.role = new_role
    user.updated_by = admin_email
    db.session.commit()

    # Audit log
    admin_role = getattr(request, "user_role", None)
    user_ip = request.headers.get("X-Forwarded-For", request.remote_addr)

    audit_service.log_admin_action(
        user_email=admin_email,
        action="update_user_role",
        target=f"user:{user.email}",
        user_role=admin_role,
        ip_address=user_ip,
        user_agent=request.headers.get("User-Agent"),
        success=True,
        details={"user": user.email, "old_role": old_role, "new_role": new_role},
    )

    # Return updated table
    return api_users()


@require_role("admin")
def toggle_user_status(user_id):
    """Toggle user active status via Htmx."""
    user = User.query.get(user_id)
    if not user:
        return '<div class="p-4 text-red-600">User not found</div>', 404

    # Toggle status
    admin_email = request.headers.get(
        "X-MS-CLIENT-PRINCIPAL-NAME", request.remote_user or "unknown"
    )
    user.is_active = not user.is_active
    user.updated_by = admin_email
    db.session.commit()

    # Audit log
    action = "reactivate_user" if user.is_active else "deactivate_user"
    admin_role = getattr(request, "user_role", None)
    user_ip = request.headers.get("X-Forwarded-For", request.remote_addr)

    audit_service.log_admin_action(
        user_email=admin_email,
        action=action,
        target=f"user:{user.email}",
        user_role=admin_role,
        ip_address=user_ip,
        user_agent=request.headers.get("User-Agent"),
        success=True,
        details={"user": user.email, "is_active": user.is_active},
    )

    # Return updated table
    return api_users()


# ===== Htmx Helper Functions =====


def _render_users_table(users):
    """Render users table as HTML for Htmx."""
    if not users:
        return """
        <tr>
            <td colspan="6" class="px-6 py-4 text-center text-gray-500">
                No users found
            </td>
        </tr>
        """

    html = ""
    for user in users:
        status_color = "green" if user.is_active else "red"
        status_text = "Active" if user.is_active else "Inactive"
        created_date = user.created_at.strftime("%Y-%m-%d")

        # Role colors
        role_colors = {"admin": "purple", "editor": "blue", "viewer": "gray"}
        role_color = role_colors.get(user.role, "gray")

        html += _render_user_row(
            user, status_color, status_text, created_date, role_color
        )

    return html


def _render_user_row(user, status_color, status_text, created_date, role_color):
    """Render a single user row."""
    return f"""
    <tr class="hover:bg-gray-50">
        <td class="px-6 py-4 whitespace-nowrap">
            <div class="text-sm text-gray-900">{user.email}</div>
            <div class="text-sm text-gray-500">ID: {user.id}</div>
        </td>
        <td class="px-6 py-4 whitespace-nowrap">
            <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-{role_color}-100 text-{role_color}-800">
                {user.role}
            </span>
        </td>
        <td class="px-6 py-4 whitespace-nowrap">
            <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-{status_color}-100 text-{status_color}-800">
                {status_text}
            </span>
        </td>
        <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
            {created_date}
        </td>
        <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
            {user.created_by or "System"}
        </td>
        <td class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
            <button onclick="editUser({user.id})" 
                    class="text-ttcu-green hover:text-green-700 mr-3">
                <i class="fas fa-edit"></i>
            </button>
            <button hx-post="/admin/users/toggle/{user.id}"
                    hx-target="#userTableBody"
                    hx-swap="innerHTML"
                    hx-confirm="Are you sure you want to {"deactivate" if user.is_active else "reactivate"} this user?"
                    class="text-{status_color}-600 hover:text-{status_color}-700">
                <i class="fas fa-{"ban" if user.is_active else "check-circle"}"></i>
                {"Deactivate" if user.is_active else "Reactivate"}
            </button>
        </td>
    </tr>
    """
