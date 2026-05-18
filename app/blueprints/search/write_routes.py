"""Write operation endpoints for the search blueprint.

Provides HTMX-compatible POST endpoints for admin actions:
- AD: unlock account, reset password, enable/disable account.
- License: assign, remove, swap M365 licenses + available SKUs fragment.

Each endpoint validates input, delegates to WriteOperationsService, and
returns HX-Trigger headers for toast/banner notifications.
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

    # ------------------------------------------------------------------
    # License write endpoints (Phase 9, Plan 03)
    # ------------------------------------------------------------------

    @search_bp.route("/api/write/available-skus", methods=["GET"])
    @require_role("admin")
    @handle_errors(json_response=True)
    def available_skus():  # type: ignore[no-untyped-def]
        """Return an HTML fragment of available SKU options for dropdowns."""
        exclude_sku_id = request.args.get("exclude_sku_id", "").strip()

        graph_service = current_app.container.get("graph_service")
        sku_catalog = current_app.container.get("sku_catalog_cache")

        raw_skus = graph_service.get_subscribed_skus()

        # Handle permission_missing sentinel
        if isinstance(raw_skus, dict) and raw_skus.get("error") == "permission_missing":
            return make_response("Graph API permission missing: Organization.Read.All", 403)

        if not raw_skus:
            raw_skus = []

        skus = []
        for sku in raw_skus:
            sku_id = sku.get("skuId", "")
            if exclude_sku_id and sku_id == exclude_sku_id:
                continue
            if sku.get("capabilityStatus") != "Enabled":
                continue

            prepaid = sku.get("prepaidUnits", {})
            enabled_count = prepaid.get("enabled", 0)
            consumed = sku.get("consumedUnits", 0)
            available = enabled_count - consumed

            display_name = None
            if sku_catalog:
                display_name = sku_catalog.get_sku_name(sku_id)
            if not display_name:
                display_name = sku.get("skuPartNumber", sku_id)

            skus.append({
                "sku_id": sku_id,
                "display_name": display_name,
                "available": max(available, 0),
                "total": enabled_count,
            })

        return render_template("search/_license_select.html", skus=skus)

    @search_bp.route("/api/write/assign-license", methods=["POST"])
    @require_role("admin")
    @csrf_double_submit.protect
    @handle_errors(json_response=True)
    def write_assign_license():  # type: ignore[no-untyped-def]
        """Assign an M365 license to a user."""
        user_id = request.form.get("user_id", "").strip()
        user_email = request.form.get("user_email", "").strip()
        sku_id = request.form.get("sku_id", "").strip()
        sku_name = request.form.get("sku_name", "").strip()
        reason = request.form.get("reason", "").strip()

        if len(reason) < 3:
            return make_response("Reason must be at least 3 characters.", 400)

        write_ops = current_app.container.get("write_operations")
        result = write_ops.assign_license(user_id, user_email, sku_id, sku_name, reason)

        if result.get("error") == "permission_missing":
            return make_response(
                "Graph API permission missing: LicenseAssignment.ReadWrite.All", 403
            )

        if result.get("success"):
            resp = make_response("", 200)
            resp.headers["HX-Trigger"] = json.dumps(
                {"showToast": {"message": "License assigned successfully", "type": "success"}}
            )
            return resp

        error_msg = result.get("error", "License assignment failed")
        return make_response(error_msg, 500)

    @search_bp.route("/api/write/remove-license", methods=["POST"])
    @require_role("admin")
    @csrf_double_submit.protect
    @handle_errors(json_response=True)
    def write_remove_license():  # type: ignore[no-untyped-def]
        """Remove an M365 license from a user (high-risk per D-14)."""
        user_id = request.form.get("user_id", "").strip()
        user_email = request.form.get("user_email", "").strip()
        sku_id = request.form.get("sku_id", "").strip()
        sku_name = request.form.get("sku_name", "").strip()
        reason = request.form.get("reason", "").strip()

        if len(reason) < 3:
            return make_response("Reason must be at least 3 characters.", 400)

        write_ops = current_app.container.get("write_operations")
        result = write_ops.remove_license(user_id, user_email, sku_id, sku_name, reason)

        if result.get("error") == "permission_missing":
            return make_response(
                "Graph API permission missing: LicenseAssignment.ReadWrite.All", 403
            )

        if result.get("success"):
            resp = make_response("", 200)
            resp.headers["HX-Trigger"] = json.dumps(
                {"showToast": {"message": "License removed successfully", "type": "success"}}
            )
            return resp

        error_msg = result.get("error", "License removal failed")
        return make_response(error_msg, 500)

    @search_bp.route("/api/write/swap-license", methods=["POST"])
    @require_role("admin")
    @csrf_double_submit.protect
    @handle_errors(json_response=True)
    def write_swap_license():  # type: ignore[no-untyped-def]
        """Swap one M365 license for another (atomic with rollback)."""
        user_id = request.form.get("user_id", "").strip()
        user_email = request.form.get("user_email", "").strip()
        old_sku_id = request.form.get("old_sku_id", "").strip()
        old_sku_name = request.form.get("old_sku_name", "").strip()
        new_sku_id = request.form.get("new_sku_id", "").strip()
        new_sku_name = request.form.get("new_sku_name", "").strip()
        reason = request.form.get("reason", "").strip()

        if len(reason) < 3:
            return make_response("Reason must be at least 3 characters.", 400)

        write_ops = current_app.container.get("write_operations")
        result = write_ops.swap_license(
            user_id, user_email, old_sku_id, old_sku_name, new_sku_id, new_sku_name, reason
        )

        if result.get("success"):
            resp = make_response("", 200)
            resp.headers["HX-Trigger"] = json.dumps(
                {"showToast": {"message": "License swapped successfully", "type": "success"}}
            )
            return resp

        # Handle rollback scenarios (D-09)
        rollback_needed = result.get("rollback_needed", False)
        rollback_success = result.get("rollback_success")

        if rollback_needed and rollback_success:
            # Rollback succeeded -- warn but not critical
            resp = make_response("", 200)
            resp.headers["HX-Trigger"] = json.dumps(
                {"showToast": {
                    "message": (
                        f"License swap incomplete but rollback succeeded. "
                        f"{old_sku_name} has been restored."
                    ),
                    "type": "warning",
                }}
            )
            return resp

        if rollback_needed and rollback_success is False:
            # D-09: Double failure -- persistent error banner
            resp = make_response("", 500)
            resp.headers["HX-Trigger"] = json.dumps(
                {"showBanner": {
                    "message": (
                        f"CRITICAL: {user_email} may have no {old_sku_name} or "
                        f"{new_sku_name} assigned. Manual intervention required. "
                        f"Check audit log."
                    ),
                    "type": "error",
                    "duration": 0,
                }}
            )
            return resp

        # Standard failure (no rollback needed)
        error_msg = result.get("error", "License swap failed")
        return make_response(error_msg, 500)
