"""AD write operation endpoints for the search blueprint.

Provides HTMX-compatible POST endpoints for admin AD actions:
unlock account, reset password, enable/disable account. Each endpoint
validates input, delegates to WriteOperationsService, and returns
HX-Trigger headers for toast notifications.
"""

import json
import logging
from typing import Any

from flask import current_app, make_response, render_template, request

from app.middleware.auth import require_role
from app.middleware.csrf import csrf_double_submit
from app.utils.error_handler import handle_errors

logger = logging.getLogger(__name__)


def register_routes(search_bp: Any) -> None:
    """Register write operation routes on the search blueprint.

    Args:
        search_bp: The search Blueprint instance.
    """

    @search_bp.route("/api/write/unlock", methods=["POST"])
    @require_role("admin")
    @csrf_double_submit.protect
    @handle_errors(json_response=True)
    def write_unlock_account():  # type: ignore[no-untyped-def]
        """Unlock a locked AD account."""
        user_dn = request.form.get("user_dn", "").strip()
        display_name = request.form.get("display_name", "").strip()
        reason = request.form.get("reason", "").strip()

        if len(reason) < 3:
            return make_response("Reason must be at least 3 characters.", 400)

        write_ops = current_app.container.get("write_operations")
        result = write_ops.unlock_account(user_dn, display_name, reason)

        if result.get("success"):
            resp = make_response("", 200)
            resp.headers["HX-Trigger"] = json.dumps(
                {"showToast": {"message": "Account unlocked successfully", "type": "success"}}
            )
            return resp

        error_msg = result.get("error", "Unlock failed")
        return make_response(error_msg, 500)

    @search_bp.route("/api/write/reset-password", methods=["POST"])
    @require_role("admin")
    @csrf_double_submit.protect
    @handle_errors(json_response=True)
    def write_reset_password():  # type: ignore[no-untyped-def]
        """Reset an AD user's password and return the temporary password banner."""
        user_dn = request.form.get("user_dn", "").strip()
        display_name = request.form.get("display_name", "").strip()
        reason = request.form.get("reason", "").strip()

        if len(reason) < 3:
            return make_response("Reason must be at least 3 characters.", 400)

        write_ops = current_app.container.get("write_operations")
        result = write_ops.reset_password(user_dn, display_name, reason)

        if result.get("success"):
            password = result["data"]["password"]
            html = render_template("search/_password_banner.html", password=password)
            resp = make_response(html, 200)
            resp.headers["HX-Trigger"] = json.dumps(
                {"showToast": {"message": "Password reset successfully", "type": "success"}}
            )
            return resp

        error_msg = result.get("error", "Password reset failed")
        return make_response(error_msg, 500)

    @search_bp.route("/api/write/enable", methods=["POST"])
    @require_role("admin")
    @csrf_double_submit.protect
    @handle_errors(json_response=True)
    def write_enable_account():  # type: ignore[no-untyped-def]
        """Enable a disabled AD account."""
        user_dn = request.form.get("user_dn", "").strip()
        display_name = request.form.get("display_name", "").strip()
        reason = request.form.get("reason", "").strip()

        if len(reason) < 3:
            return make_response("Reason must be at least 3 characters.", 400)

        write_ops = current_app.container.get("write_operations")
        result = write_ops.set_account_enabled(user_dn, display_name, True, reason)

        if result.get("success"):
            resp = make_response("", 200)
            resp.headers["HX-Trigger"] = json.dumps(
                {"showToast": {"message": "Account enabled successfully", "type": "success"}}
            )
            return resp

        error_msg = result.get("error", "Enable failed")
        return make_response(error_msg, 500)

    @search_bp.route("/api/write/disable", methods=["POST"])
    @require_role("admin")
    @csrf_double_submit.protect
    @handle_errors(json_response=True)
    def write_disable_account():  # type: ignore[no-untyped-def]
        """Disable an AD account."""
        user_dn = request.form.get("user_dn", "").strip()
        display_name = request.form.get("display_name", "").strip()
        reason = request.form.get("reason", "").strip()

        if len(reason) < 3:
            return make_response("Reason must be at least 3 characters.", 400)

        write_ops = current_app.container.get("write_operations")
        result = write_ops.set_account_enabled(user_dn, display_name, False, reason)

        if result.get("success"):
            resp = make_response("", 200)
            resp.headers["HX-Trigger"] = json.dumps(
                {"showToast": {"message": "Account disabled successfully", "type": "success"}}
            )
            return resp

        error_msg = result.get("error", "Disable failed")
        return make_response(error_msg, 500)
