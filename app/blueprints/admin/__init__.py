from flask import Blueprint, render_template, jsonify, request, redirect, url_for, flash
from app.middleware.auth import require_role, load_role_lists
from app.services.genesys_cache import genesys_cache
import os
from dotenv import load_dotenv, set_key
import re

admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/")
@require_role("admin")
def index():
    return render_template("admin/index.html")


@admin_bp.route("/cache-status")
@require_role("admin")
def cache_status():
    """Get Genesys cache status."""
    return jsonify(genesys_cache.get_cache_status())


@admin_bp.route("/users")
@require_role("admin")
def manage_users():
    """Display user management page."""
    viewers, editors, admins = load_role_lists()

    users = []
    for email in admins:
        if email:
            users.append({"email": email, "role": "admin"})
    for email in editors:
        if email and email not in admins:
            users.append({"email": email, "role": "editor"})
    for email in viewers:
        if email and email not in editors and email not in admins:
            users.append({"email": email, "role": "viewer"})

    return render_template("admin/users.html", users=users)


@admin_bp.route("/users/add", methods=["POST"])
@require_role("admin")
def add_user():
    """Add a new user with role."""
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

    viewers, editors, admins = load_role_lists()

    # Remove from all lists first
    viewers = [e for e in viewers if e != email]
    editors = [e for e in editors if e != email]
    admins = [e for e in admins if e != email]

    # Add to appropriate list
    if role == "admin":
        admins.append(email)
    elif role == "editor":
        editors.append(email)
    else:
        viewers.append(email)

    # Update .env file
    env_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
        ".env",
    )
    load_dotenv(env_path)

    set_key(env_path, "VIEWERS", ",".join(viewers))
    set_key(env_path, "EDITORS", ",".join(editors))
    set_key(env_path, "ADMINS", ",".join(admins))

    return jsonify(
        {
            "success": True,
            "message": f"User {email} added as {role}. May the Force be with them.",
        }
    )


@admin_bp.route("/users/update", methods=["POST"])
@require_role("admin")
def update_user():
    """Update user role."""
    email = request.form.get("email", "").strip().lower()
    new_role = request.form.get("role", "viewer")

    viewers, editors, admins = load_role_lists()

    # Check if user exists
    if email not in viewers + editors + admins:
        return jsonify(
            {"success": False, "message": "User not found. They must have ghosted us."}
        ), 404

    # Remove from all lists
    viewers = [e for e in viewers if e != email]
    editors = [e for e in editors if e != email]
    admins = [e for e in admins if e != email]

    # Add to new role list
    if new_role == "admin":
        admins.append(email)
    elif new_role == "editor":
        editors.append(email)
    else:
        viewers.append(email)

    # Update .env file
    env_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
        ".env",
    )
    load_dotenv(env_path)

    set_key(env_path, "VIEWERS", ",".join(viewers))
    set_key(env_path, "EDITORS", ",".join(editors))
    set_key(env_path, "ADMINS", ",".join(admins))

    return jsonify(
        {
            "success": True,
            "message": f"User {email} promoted/demoted to {new_role}. With great power...",
        }
    )


@admin_bp.route("/users/delete", methods=["POST"])
@require_role("admin")
def delete_user():
    """Remove user access."""
    email = request.form.get("email", "").strip().lower()

    viewers, editors, admins = load_role_lists()

    # Remove from all lists
    viewers = [e for e in viewers if e != email]
    editors = [e for e in editors if e != email]
    admins = [e for e in admins if e != email]

    # Update .env file
    env_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
        ".env",
    )
    load_dotenv(env_path)

    set_key(env_path, "VIEWERS", ",".join(viewers))
    set_key(env_path, "EDITORS", ",".join(editors))
    set_key(env_path, "ADMINS", ",".join(admins))

    return jsonify(
        {
            "success": True,
            "message": f"User {email} has been yeeted from the system. 👋",
        }
    )
