"""
User management functionality for admin blueprint.
Handles user CRUD operations, role management, and user notes.
"""

from flask import render_template, jsonify, request, make_response
from app.middleware.auth import require_role
from app.database import db
import re
from datetime import datetime


@require_role("admin")
def manage_users():
    """Display user management page."""
    return render_template("admin/users.html")


@require_role("admin")
def api_users():
    """API endpoint to get all users - returns HTML for Htmx or JSON."""
    from app.models import User, UserNote

    # Get all users from database
    users = User.get_all_active()

    # Check if this is an Htmx request
    if request.headers.get('HX-Request'):
        # Build HTML response for Htmx
        html_rows = []
        for user in users:
            notes_count = UserNote.query.filter_by(user_id=user.id, is_active=True).count()
            html_rows.append(_render_user_row(user, notes_count))
        return ''.join(html_rows)
    
    # Original JSON response
    user_list = []
    for user in users:
        notes_count = UserNote.query.filter_by(user_id=user.id, is_active=True).count()
        user_dict = user.to_dict()
        user_dict["notes_count"] = notes_count
        user_list.append(user_dict)

    return jsonify({"users": user_list})


@require_role("admin")
def add_user():
    """Add a new user with role."""
    from app.models import User

    email = request.form.get("email", "").strip().lower()
    role = request.form.get("role", "viewer")

    if not email or not re.match(
        r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email
    ):
        return jsonify(
            {
                "success": False,
                "message": "Invalid email format. Even we have standards.",
            }
        ), 400

    # Check if user already exists
    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        if existing_user.is_active:
            return jsonify(
                {
                    "success": False,
                    "message": f"User {email} already exists.",
                }
            ), 400
        else:
            # Reactivate existing user
            admin_email = request.headers.get(
                "X-MS-CLIENT-PRINCIPAL-NAME", request.remote_user or "unknown"
            )
            existing_user.is_active = True
            existing_user.role = role
            existing_user.updated_by = admin_email
            db.session.commit()

            message = f"User {email} reactivated as {role}."
    else:
        # Create new user
        admin_email = request.headers.get(
            "X-MS-CLIENT-PRINCIPAL-NAME", request.remote_user or "unknown"
        )

        try:
            User.create_user(email=email, role=role, created_by=admin_email)
            message = f"User {email} added as {role}. May the Force be with them."
        except Exception as e:
            return jsonify(
                {
                    "success": False,
                    "message": f"Failed to add user: {str(e)}",
                }
            ), 500

    # Audit log
    from app.services.audit_service_postgres import audit_service

    admin_email = request.headers.get(
        "X-MS-CLIENT-PRINCIPAL-NAME", request.remote_user or "unknown"
    )
    admin_role = getattr(request, "user_role", None)
    user_ip = request.headers.get("X-Forwarded-For", request.remote_addr)

    audit_service.log_admin_action(
        user_email=admin_email,
        action="add_user",
        target=f"user:{email}",
        details={"new_user": email, "assigned_role": role},
        user_role=admin_role,
        ip_address=user_ip,
        user_agent=request.headers.get("User-Agent"),
        success=True,
    )

    # Check if this is an Htmx request
    if request.headers.get('HX-Request'):
        # Get the newly created/updated user
        user = User.query.filter_by(email=email).first()
        notes_count = 0
        return _render_user_row(user, notes_count)
    
    return jsonify(
        {
            "success": True,
            "message": message,
        }
    )


@require_role("admin")
def update_user():
    """Update user role."""
    from app.models import User

    email = request.form.get("email", "").strip().lower()
    new_role = request.form.get("role", "viewer")

    # Get admin info
    admin_email = request.headers.get(
        "X-MS-CLIENT-PRINCIPAL-NAME", request.remote_user or "unknown"
    )

    # Update user in database
    user = User.update_user_role(email, new_role, admin_email)

    if not user:
        return jsonify(
            {"success": False, "message": "User not found. They must have ghosted us."}
        ), 404

    # Audit log
    from app.services.audit_service_postgres import audit_service

    admin_role = getattr(request, "user_role", None)
    user_ip = request.headers.get("X-Forwarded-For", request.remote_addr)

    audit_service.log_admin_action(
        user_email=admin_email,
        action="update_user_role",
        target=f"user:{email}",
        user_role=admin_role,
        ip_address=user_ip,
        user_agent=request.headers.get("User-Agent"),
        success=True,
        details={"user": email, "new_role": new_role},
    )

    return jsonify(
        {
            "success": True,
            "message": f"User {email} promoted/demoted to {new_role}. With great power...",
        }
    )


@require_role("admin")
def delete_user():
    """Remove user access."""
    from app.models import User

    email = request.form.get("email", "").strip().lower()

    # Get admin info
    admin_email = request.headers.get(
        "X-MS-CLIENT-PRINCIPAL-NAME", request.remote_user or "unknown"
    )

    # Deactivate user in database (soft delete)
    user = User.deactivate_user(email, admin_email)

    if not user:
        return jsonify(
            {"success": False, "message": "User not found. Already yeeted?"}
        ), 404

    # Audit log
    from app.services.audit_service_postgres import audit_service

    admin_role = getattr(request, "user_role", None)
    user_ip = request.headers.get("X-Forwarded-For", request.remote_addr)

    audit_service.log_admin_action(
        user_email=admin_email,
        action="delete_user",
        target=f"user:{email}",
        user_role=admin_role,
        ip_address=user_ip,
        user_agent=request.headers.get("User-Agent"),
        success=True,
        details={"deleted_user": email},
    )

    return jsonify(
        {
            "success": True,
            "message": f"User {email} has been yeeted from the system. 👋",
        }
    )


@require_role("admin")
def get_user_notes(user_id):
    """Get all notes for a specific user."""
    from app.models import UserNote

    notes = (
        UserNote.query.filter_by(user_id=user_id, is_active=True)
        .order_by(UserNote.created_at.desc())
        .all()
    )

    notes_list = []
    for note in notes:
        notes_list.append(
            {
                "id": note.id,
                "note": note.note,
                "created_by": note.created_by,
                "created_at": note.created_at.isoformat(),
                "updated_at": note.updated_at.isoformat(),
            }
        )

    return jsonify({"notes": notes_list})


@require_role("editor")  # Allow editors and admins
def add_user_note(user_id):
    """Add a note for a specific user."""
    from app.models import User, UserNote
    from app.services.audit_service_postgres import audit_service

    # Verify user exists
    user = User.query.get(user_id)
    if not user:
        return jsonify({"success": False, "message": "User not found"}), 404

    note_text = request.json.get("note", "").strip()
    if not note_text:
        return jsonify({"success": False, "message": "Note cannot be empty"}), 400

    # Get admin info
    admin_email = request.headers.get(
        "X-MS-CLIENT-PRINCIPAL-NAME", request.remote_user or "unknown"
    )

    # Create note
    note = UserNote(user_id=user_id, note=note_text, created_by=admin_email)
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
        details={
            "user": user.email,
            "note_id": note.id,
            "note_preview": note_text[:50] + "..."
            if len(note_text) > 50
            else note_text,
        },
    )

    return jsonify(
        {
            "success": True,
            "message": "Note added successfully",
            "note": {
                "id": note.id,
                "note": note.note,
                "created_by": note.created_by,
                "created_at": note.created_at.isoformat(),
            },
        }
    )


# ===== Htmx Helper Functions =====

def _render_user_row(user, notes_count=0):
    """Helper function to render a user table row."""
    created_date = user.created_at.strftime('%Y-%m-%d') if user.created_at else 'N/A'
    updated_date = user.updated_at.strftime('%Y-%m-%d') if user.updated_at else 'N/A'
    
    status_class = 'bg-green-100 text-green-800' if user.is_active else 'bg-red-100 text-red-800'
    status_text = 'Active' if user.is_active else 'Inactive'
    
    return f'''
    <tr class="hover:bg-gray-50">
        <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{user.email}</td>
        <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
            <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-purple-100 text-purple-800">
                {user.role.upper()}
            </span>
        </td>
        <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
            <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full {status_class}">
                {status_text}
            </span>
        </td>
        <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{created_date}</td>
        <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{updated_date}</td>
        <td class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
            <button class="text-indigo-600 hover:text-indigo-900 mr-3"
                    hx-get="/admin/api/users/{user.id}/edit"
                    hx-target="#editUserContent"
                    hx-swap="innerHTML">
                Edit
            </button>
            <button class="text-red-600 hover:text-red-900"
                    hx-post="/admin/users/toggle/{user.id}"
                    hx-target="#userTableBody"
                    hx-swap="innerHTML"
                    hx-confirm="Are you sure you want to {'deactivate' if user.is_active else 'reactivate'} this user?">
                {'Deactivate' if user.is_active else 'Reactivate'}
            </button>
        </td>
    </tr>
    '''


# ===== New Htmx Routes =====

@require_role("admin")
def edit_user_modal(user_id):
    """Get edit user modal content."""
    from app.models import User
    
    user = User.query.get(user_id)
    if not user:
        return '<div class="p-4 text-red-600">User not found</div>', 404
    
    roles = ['viewer', 'editor', 'admin']
    role_options = ''.join([
        f'<option value="{role}" {"selected" if user.role == role else ""}>{role.capitalize()}</option>'
        for role in roles
    ])
    
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
    from app.models import User
    from app.services.audit_service_postgres import audit_service
    
    user = User.query.get(user_id)
    if not user:
        return '<div class="p-4 text-red-600">User not found</div>', 404
    
    new_role = request.form.get('role', user.role)
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
    from app.models import User
    from app.services.audit_service_postgres import audit_service
    
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


@require_role("editor")  # Allow editors and admins
def update_user_note(note_id):
    """Update an existing user note."""
    from app.models import UserNote
    from app.services.audit_service_postgres import audit_service

    note = UserNote.query.get(note_id)
    if not note or not note.is_active:
        return jsonify({"success": False, "message": "Note not found"}), 404

    note_text = request.json.get("note", "").strip()
    if not note_text:
        return jsonify({"success": False, "message": "Note cannot be empty"}), 400

    old_note_text = note.note
    note.note = note_text
    db.session.commit()

    # Audit log
    admin_email = request.headers.get(
        "X-MS-CLIENT-PRINCIPAL-NAME", request.remote_user or "unknown"
    )
    admin_role = getattr(request, "user_role", None)
    user_ip = request.headers.get("X-Forwarded-For", request.remote_addr)

    audit_service.log_admin_action(
        user_email=admin_email,
        action="update_user_note",
        target=f"note:{note_id}",
        user_role=admin_role,
        ip_address=user_ip,
        user_agent=request.headers.get("User-Agent"),
        success=True,
        details={
            "note_id": note_id,
            "old_note": old_note_text[:50] + "..."
            if len(old_note_text) > 50
            else old_note_text,
            "new_note": note_text[:50] + "..." if len(note_text) > 50 else note_text,
        },
    )

    return jsonify({"success": True, "message": "Note updated successfully"})


@require_role("editor")  # Allow editors and admins
def delete_user_note(note_id):
    """Delete (soft delete) a user note."""
    from app.models import UserNote
    from app.services.audit_service_postgres import audit_service

    note = UserNote.query.get(note_id)
    if not note or not note.is_active:
        return jsonify({"success": False, "message": "Note not found"}), 404

    note.is_active = False
    db.session.commit()

    # Audit log
    admin_email = request.headers.get(
        "X-MS-CLIENT-PRINCIPAL-NAME", request.remote_user or "unknown"
    )
    admin_role = getattr(request, "user_role", None)
    user_ip = request.headers.get("X-Forwarded-For", request.remote_addr)

    audit_service.log_admin_action(
        user_email=admin_email,
        action="delete_user_note",
        target=f"note:{note_id}",
        user_role=admin_role,
        ip_address=user_ip,
        user_agent=request.headers.get("User-Agent"),
        success=True,
        details={
            "note_id": note_id,
            "note_preview": note.note[:50] + "..."
            if len(note.note) > 50
            else note.note,
        },
    )

    return jsonify({"success": True, "message": "Note deleted successfully"})


@require_role("viewer")
def get_user_notes_by_email(email):
    """Get notes for a user by email (for search results)."""
    from app.models import User, UserNote

    # All authenticated users can see notes
    user_role = getattr(request, "user_role", "viewer")

    # Find user by email
    user = User.query.filter_by(email=email.lower()).first()
    if not user:
        return jsonify({"notes": []})

    # Get active notes
    notes = (
        UserNote.query.filter_by(user_id=user.id, is_active=True)
        .order_by(UserNote.created_at.desc())
        .all()
    )

    notes_list = []
    for note in notes:
        notes_list.append(
            {
                "id": note.id,
                "note": note.note,
                "created_by": note.created_by,
                "created_at": note.created_at.isoformat(),
                "updated_at": note.updated_at.isoformat(),
                "can_edit": user_role
                in ["admin", "editor"],  # Add edit permission flag
            }
        )

    return jsonify({"notes": notes_list, "can_edit": user_role in ["admin", "editor"]})


@require_role("editor")  # Allow editors and admins
def add_user_note_by_email(email):
    """Add a note for a user by email."""
    from app.models import User, UserNote
    from app.services.audit_service_postgres import audit_service

    # Find user by email, create if doesn't exist
    user = User.query.filter_by(email=email.lower()).first()

    if not user:
        # Create user if they don't exist
        admin_email = request.headers.get(
            "X-MS-CLIENT-PRINCIPAL_NAME", request.remote_user or "unknown"
        )
        user = User.create_user(
            email=email.lower(), role="viewer", created_by=admin_email
        )

    note_text = request.json.get("note", "").strip()
    if not note_text:
        return jsonify({"success": False, "message": "Note cannot be empty"}), 400

    # Get admin info
    admin_email = request.headers.get(
        "X-MS-CLIENT-PRINCIPAL-NAME", request.remote_user or "unknown"
    )

    # Create note
    note = UserNote(user_id=user.id, note=note_text, created_by=admin_email)
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
        details={
            "user": user.email,
            "note_id": note.id,
            "note_preview": note_text[:50] + "..."
            if len(note_text) > 50
            else note_text,
        },
    )

    return jsonify(
        {
            "success": True,
            "message": "Note added successfully",
            "note": {
                "id": note.id,
                "note": note.note,
                "created_by": note.created_by,
                "created_at": note.created_at.isoformat(),
            },
        }
    )


# ===== Htmx Helper Functions =====

def _render_user_row(user, notes_count=0):
    """Helper function to render a user table row."""
    created_date = user.created_at.strftime('%Y-%m-%d') if user.created_at else 'N/A'
    updated_date = user.updated_at.strftime('%Y-%m-%d') if user.updated_at else 'N/A'
    
    status_class = 'bg-green-100 text-green-800' if user.is_active else 'bg-red-100 text-red-800'
    status_text = 'Active' if user.is_active else 'Inactive'
    
    return f'''
    <tr class="hover:bg-gray-50">
        <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{user.email}</td>
        <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
            <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-purple-100 text-purple-800">
                {user.role.upper()}
            </span>
        </td>
        <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
            <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full {status_class}">
                {status_text}
            </span>
        </td>
        <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{created_date}</td>
        <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{updated_date}</td>
        <td class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
            <button class="text-indigo-600 hover:text-indigo-900 mr-3"
                    hx-get="/admin/api/users/{user.id}/edit"
                    hx-target="#editUserContent"
                    hx-swap="innerHTML">
                Edit
            </button>
            <button class="text-red-600 hover:text-red-900"
                    hx-post="/admin/users/toggle/{user.id}"
                    hx-target="#userTableBody"
                    hx-swap="innerHTML"
                    hx-confirm="Are you sure you want to {'deactivate' if user.is_active else 'reactivate'} this user?">
                {'Deactivate' if user.is_active else 'Reactivate'}
            </button>
        </td>
    </tr>
    '''


# ===== New Htmx Routes =====

@require_role("admin")
def edit_user_modal(user_id):
    """Get edit user modal content."""
    from app.models import User
    
    user = User.query.get(user_id)
    if not user:
        return '<div class="p-4 text-red-600">User not found</div>', 404
    
    roles = ['viewer', 'editor', 'admin']
    role_options = ''.join([
        f'<option value="{role}" {"selected" if user.role == role else ""}>{role.capitalize()}</option>'
        for role in roles
    ])
    
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
    from app.models import User
    from app.services.audit_service_postgres import audit_service
    
    user = User.query.get(user_id)
    if not user:
        return '<div class="p-4 text-red-600">User not found</div>', 404
    
    new_role = request.form.get('role', user.role)
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
    from app.models import User
    from app.services.audit_service_postgres import audit_service
    
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
