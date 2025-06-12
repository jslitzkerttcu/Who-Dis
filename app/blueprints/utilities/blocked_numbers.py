from flask import render_template, request, jsonify, g, current_app
from app.blueprints.utilities import utilities
from app.middleware.auth import auth_required, require_role
from app.services.genesys_service import genesys_service
from app.services.audit_service_postgres import audit_service
from app.utils.ip_utils import format_ip_info
from datetime import datetime
import pytz
import re


@utilities.route("/blocked-numbers")
@auth_required
@require_role("viewer")
def blocked_numbers():
    """Display the Genesys blocked numbers management page."""
    return render_template("utilities/blocked_numbers.html")


@utilities.route("/api/blocked-numbers")
@auth_required
@require_role("viewer")
def get_blocked_numbers():
    """Get all blocked numbers from Genesys."""
    try:
        data = genesys_service.get_blocked_numbers()
        if data is None:
            return jsonify({"error": "Failed to fetch blocked numbers"}), 500

        # Log the retrieval
        audit_service.log_search(
            user_email=g.user,
            search_query="blocked_numbers_list",
            results_count=len(data.get("entities", [])),
            services=["genesys"],
            search_type="blocked_numbers",
            ip_address=format_ip_info(),
            user_agent=request.headers.get("User-Agent"),
            additional_data={"action": "list"},
        )

        return jsonify(data)
    except Exception as e:
        current_app.logger.error(f"Error fetching blocked numbers: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500


@utilities.route("/api/blocked-numbers", methods=["POST"])
@auth_required
@require_role("editor")
def add_blocked_number():
    """Add a new blocked number."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        ani = data.get("key", "").strip()
        reason = data.get("Reason Blocked", "").strip()

        # Validate ANI (11 digits exactly)
        if not ani or not re.match(r"^\d{11}$", ani):
            return jsonify({"error": "ANI must be exactly 11 digits"}), 400

        # Validate reason (max 200 characters)
        if not reason or len(reason) > 200:
            return jsonify({"error": "Reason must be 1-200 characters"}), 400

        # Append user info to reason
        central_tz = pytz.timezone("America/Chicago")
        now = datetime.now(central_tz)
        formatted_date = now.strftime("%m/%d/%y at %H:%M CDT")
        enhanced_reason = (
            f"{reason} - Added by Who-Dis user {g.user} on {formatted_date}"
        )

        # Trim if too long after enhancement
        if len(enhanced_reason) > 255:  # Genesys limit
            max_original_length = 255 - len(
                f" - Added by Who-Dis user {g.user} on {formatted_date}"
            )
            reason = reason[:max_original_length]
            enhanced_reason = (
                f"{reason} - Added by Who-Dis user {g.user} on {formatted_date}"
            )

        payload = {"key": ani, "Reason Blocked": enhanced_reason}

        result = genesys_service.add_blocked_number(payload)
        if result is None:
            return jsonify({"error": "Failed to add blocked number"}), 500

        # Log the addition
        audit_service.log_search(
            user_email=g.user,
            search_query=ani,
            results_count=1,
            services=["genesys"],
            search_type="blocked_numbers",
            ip_address=format_ip_info(),
            user_agent=request.headers.get("User-Agent"),
            additional_data={
                "action": "add",
                "ani": ani,
                "original_reason": reason,
                "enhanced_reason": enhanced_reason,
            },
        )

        return jsonify({"success": True, "data": result})
    except Exception as e:
        current_app.logger.error(f"Error adding blocked number: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500


@utilities.route("/api/blocked-numbers/<ani>", methods=["PUT"])
@auth_required
@require_role("editor")
def update_blocked_number(ani):
    """Update an existing blocked number."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        new_ani = data.get("key", "").strip()
        reason = data.get("Reason Blocked", "").strip()

        # Validate new ANI (11 digits exactly)
        if not new_ani or not re.match(r"^\d{11}$", new_ani):
            return jsonify({"error": "ANI must be exactly 11 digits"}), 400

        # Validate reason (max 200 characters)
        if not reason or len(reason) > 200:
            return jsonify({"error": "Reason must be 1-200 characters"}), 400

        # Append user info to reason
        central_tz = pytz.timezone("America/Chicago")
        now = datetime.now(central_tz)
        formatted_date = now.strftime("%m/%d/%y at %H:%M CDT")
        enhanced_reason = (
            f"{reason} - Updated by Who-Dis user {g.user} on {formatted_date}"
        )

        # Trim if too long after enhancement
        if len(enhanced_reason) > 255:  # Genesys limit
            max_original_length = 255 - len(
                f" - Updated by Who-Dis user {g.user} on {formatted_date}"
            )
            reason = reason[:max_original_length]
            enhanced_reason = (
                f"{reason} - Updated by Who-Dis user {g.user} on {formatted_date}"
            )

        payload = {"key": new_ani, "Reason Blocked": enhanced_reason}

        result = genesys_service.update_blocked_number(ani, payload)
        if result is None:
            return jsonify({"error": "Failed to update blocked number"}), 500

        # Log the update
        audit_service.log_search(
            user_email=g.user,
            search_query=ani,
            results_count=1,
            services=["genesys"],
            search_type="blocked_numbers",
            ip_address=format_ip_info(),
            user_agent=request.headers.get("User-Agent"),
            additional_data={
                "action": "update",
                "old_ani": ani,
                "new_ani": new_ani,
                "original_reason": reason,
                "enhanced_reason": enhanced_reason,
            },
        )

        return jsonify({"success": True, "data": result})
    except Exception as e:
        current_app.logger.error(f"Error updating blocked number: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500


@utilities.route("/api/blocked-numbers/<ani>", methods=["DELETE"])
@auth_required
@require_role("editor")
def delete_blocked_number(ani):
    """Delete a blocked number."""
    try:
        result = genesys_service.delete_blocked_number(ani)
        if result is None:
            return jsonify({"error": "Failed to delete blocked number"}), 500

        # Log the deletion
        audit_service.log_search(
            user_email=g.user,
            search_query=ani,
            results_count=1,
            services=["genesys"],
            search_type="blocked_numbers",
            ip_address=format_ip_info(),
            user_agent=request.headers.get("User-Agent"),
            additional_data={"action": "delete", "ani": ani},
        )

        return jsonify({"success": True})
    except Exception as e:
        current_app.logger.error(f"Error deleting blocked number: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500
