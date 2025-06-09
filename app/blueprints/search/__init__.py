from flask import (
    Blueprint,
    render_template,
    request,
    jsonify,
    make_response,
    current_app,
)
from app.middleware.auth import require_role
from app.utils.error_handler import handle_errors
from app.interfaces.configuration_service import IConfigurationService
from app.services.search_orchestrator import SearchOrchestrator
from app.services.result_merger import ResultMerger
import logging
from typing import Optional, Dict, Any
import base64
from app.utils.timezone import format_timestamp
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

search_bp = Blueprint("search", __name__)


# Configuration will be loaded lazily to avoid app context issues
_config_cache: Dict[str, Any] = {}


def get_search_timeout() -> int:
    """Get search timeout configuration lazily"""
    if "timeout" not in _config_cache:
        config_service: IConfigurationService = current_app.container.get("config")
        timeout_value = int(config_service.get("search.overall_timeout", "20"))
        _config_cache["timeout"] = timeout_value
    return int(_config_cache["timeout"])


def get_lazy_load_photos() -> bool:
    """Get lazy load photos configuration lazily"""
    if "lazy_load" not in _config_cache:
        config_service: IConfigurationService = current_app.container.get("config")
        lazy_load_config = config_service.get("search.lazy_load_photos", "true")
        # Handle both string and boolean values
        if isinstance(lazy_load_config, bool):
            lazy_load_value = lazy_load_config
        else:
            lazy_load_value = str(lazy_load_config).lower() == "true"
        _config_cache["lazy_load"] = lazy_load_value
    return bool(_config_cache["lazy_load"])


@search_bp.route("/")
@require_role("viewer")
@handle_errors
def index():
    from app.middleware.csrf import ensure_csrf_cookie

    # Apply CSRF cookie decorator
    @ensure_csrf_cookie
    def render():
        return render_template("search/index.html")

    return render()


@search_bp.route("/photo/<user_id>")
@require_role("viewer")
@handle_errors(json_response=True)
def get_user_photo(user_id):
    """Get user photo by Graph ID."""
    user_principal_name = request.args.get("upn")

    logger.info(f"Fetching photo for user ID: {user_id}, UPN: {user_principal_name}")

    try:
        # Get graph service from container
        graph_service = current_app.container.get("graph_service")
        # Get photo from Graph service (will use cache if available)
        photo_url = graph_service.get_user_photo(user_id, user_principal_name)

        if photo_url:
            # Extract the base64 data from the data URL
            if photo_url.startswith("data:"):
                # Format: data:image/jpeg;base64,<data>
                parts = photo_url.split(",", 1)
                if len(parts) == 2:
                    mime_type = parts[0].split(";")[0].replace("data:", "")
                    photo_data = base64.b64decode(parts[1])

                    response = make_response(photo_data)
                    response.headers["Content-Type"] = mime_type
                    response.headers["Cache-Control"] = "private, max-age=3600"
                    return response

        # Return a 1x1 transparent pixel if no photo found
        transparent_pixel = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
        )
        response = make_response(transparent_pixel)
        response.headers["Content-Type"] = "image/png"
        response.headers["Cache-Control"] = "private, max-age=3600"
        return response

    except Exception as e:
        logger.error(f"Error fetching photo for user {user_id}: {str(e)}")
        # Return error image
        transparent_pixel = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
        )
        response = make_response(transparent_pixel)
        response.headers["Content-Type"] = "image/png"
        return response


@search_bp.route("/user", methods=["POST"])
@require_role("viewer")
@handle_errors(json_response=True)
def search_user():
    """Search for users across LDAP, Genesys, and Microsoft Graph."""
    # CSRF protection
    from app.middleware.csrf import csrf_double_submit

    # Validate CSRF token
    cookie_token = csrf_double_submit.get_cookie_token()
    header_token = csrf_double_submit.get_header_token()

    if not cookie_token or not header_token:
        return jsonify({"error": "CSRF token missing"}), 403

    if cookie_token != header_token:
        return jsonify({"error": "CSRF token mismatch"}), 403

    if not csrf_double_submit.validate_token(cookie_token):
        return jsonify({"error": "CSRF token invalid or expired"}), 403

    # Parse request data
    data = request.get_json()
    search_term = data.get("search_term", "").strip()
    genesys_user_id = data.get("genesys_user_id")
    ldap_user_dn = data.get("ldap_user_dn")
    graph_user_id = data.get("graph_user_id")

    if not search_term:
        return jsonify({"error": "Search term is required"}), 400

    logger.info(f"Searching for user: {search_term}")

    # Get user info for audit logging
    user_email = request.headers.get(
        "X-MS-CLIENT-PRINCIPAL-NAME", request.remote_user or "unknown"
    )
    user_role = getattr(request, "user_role", None)
    user_ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    user_agent = request.headers.get("User-Agent")

    # Initialize services
    orchestrator = SearchOrchestrator()
    merger = ResultMerger()

    # Execute concurrent searches
    ldap_result, genesys_result, graph_result = orchestrator.execute_concurrent_search(
        search_term, genesys_user_id, ldap_user_dn, graph_user_id
    )

    # Check if all searches timed out
    if orchestrator.all_searches_timed_out(ldap_result, genesys_result, graph_result):
        return jsonify(
            {
                "error": "search_timeout",
                "message": f"Search timed out after {orchestrator.overall_timeout} seconds. Please use a more specific search term.",
                "search_term": search_term,
            }
        ), 408

    # Merge Azure AD results (LDAP + Graph)
    azure_ad_result, azure_ad_error, azure_ad_multiple = merger.merge_azure_ad_results(
        ldap_result, genesys_result, graph_result
    )

    # Smart match Azure AD and Genesys if applicable
    genesys_data = genesys_result.get("result")
    genesys_error = genesys_result.get("error")
    genesys_multiple = genesys_result.get("multiple", False)

    genesys_data, genesys_multiple = merger.smart_match_services(
        azure_ad_result, azure_ad_multiple, genesys_data, genesys_multiple
    )

    # Enhance results with data warehouse information
    search_results = {
        "azureAD": azure_ad_result,
        "azureAD_error": azure_ad_error,
        "azureAD_multiple": azure_ad_multiple,
        "genesys": genesys_data,
        "genesys_error": genesys_error,
        "genesys_multiple": genesys_multiple,
    }

    try:
        from app.services.search_enhancer import search_enhancer

        enhanced_results = search_enhancer.enhance_search_results(search_results)
    except Exception as e:
        logger.error(f"Error enhancing search results with data warehouse: {str(e)}")
        # Continue with original results if enhancement fails
        enhanced_results = search_results
        enhanced_results["keystone"] = None
        enhanced_results["keystone_error"] = f"Error loading Keystone data: {str(e)}"
        enhanced_results["keystone_multiple"] = False

    # Audit logging
    _log_search_audit(
        search_term,
        user_email,
        user_role,
        user_ip,
        user_agent,
        ldap_result,
        graph_result,
        genesys_result,
        enhanced_results,
        azure_ad_multiple,
        genesys_multiple,
        genesys_user_id,
        ldap_user_dn,
        graph_user_id,
    )

    # Return enhanced results
    response_data = enhanced_results.copy()
    response_data["search_term"] = search_term
    return jsonify(response_data)


def _log_search_audit(
    search_term: str,
    user_email: str,
    user_role: Optional[str],
    user_ip: str,
    user_agent: Optional[str],
    ldap_result: dict,
    graph_result: dict,
    genesys_result: dict,
    enhanced_results: dict,
    azure_ad_multiple: bool,
    genesys_multiple: bool,
    genesys_user_id: Optional[str],
    ldap_user_dn: Optional[str],
    graph_user_id: Optional[str],
) -> None:
    """Log search activity for audit purposes."""
    services_used = []
    total_results = 0
    error_messages = []

    # Track LDAP results
    if ldap_result.get("result") or ldap_result.get("error"):
        services_used.append("LDAP")
        if ldap_result.get("result") and not ldap_result.get("multiple"):
            total_results += 1
        elif ldap_result.get("multiple") and ldap_result.get("result", {}).get(
            "results"
        ):
            total_results += len(ldap_result["result"].get("results", []))
        if ldap_result.get("error"):
            error_messages.append(f"LDAP: {ldap_result['error']}")

    # Track Graph results
    if graph_result.get("result") or graph_result.get("error"):
        services_used.append("Graph")
        if graph_result.get("result") and not graph_result.get("multiple"):
            total_results += 1
        elif graph_result.get("multiple") and graph_result.get("result", {}).get(
            "results"
        ):
            total_results += len(graph_result["result"].get("results", []))
        if graph_result.get("error"):
            error_messages.append(f"Graph: {graph_result['error']}")

    # Track Genesys results
    if genesys_result.get("result") or genesys_result.get("error"):
        services_used.append("Genesys")
        if genesys_result.get("result") and not genesys_result.get("multiple"):
            total_results += 1
        elif genesys_result.get("multiple") and genesys_result.get("result", {}).get(
            "results"
        ):
            total_results += len(genesys_result["result"].get("results", []))
        if genesys_result.get("error"):
            error_messages.append(f"Genesys: {genesys_result['error']}")

    # Track Keystone results
    keystone_result = enhanced_results.get("keystone")
    keystone_error = enhanced_results.get("keystone_error")

    if keystone_result or keystone_error:
        services_used.append("Keystone")
        if keystone_result:
            total_results += 1
        if keystone_error:
            error_messages.append(f"Keystone: {keystone_error}")

    # Determine search success
    search_success = not (error_messages and len(error_messages) == len(services_used))

    # Log the search
    try:
        from app.services.audit_service_postgres import audit_service

        audit_service.log_search(
            user_email=user_email,
            search_query=search_term,
            results_count=total_results,
            services=services_used,
            user_role=user_role,
            ip_address=user_ip,
            user_agent=user_agent,
            success=search_success,
            error_message="; ".join(error_messages) if error_messages else None,
            additional_data={
                "specific_user_requested": bool(
                    genesys_user_id or ldap_user_dn or graph_user_id
                ),
                "multiple_results": azure_ad_multiple or genesys_multiple,
                "timeout_occurred": any("timed out" in msg for msg in error_messages),
                "keystone_data_found": bool(keystone_result),
                "keystone_role_mismatch": keystone_result.get("role_mismatch")
                if keystone_result
                else False,
                "keystone_warning_level": keystone_result.get("role_warning_level")
                if keystone_result
                else None,
            },
        )
    except Exception as e:
        logger.error(f"Failed to log search audit: {str(e)}")


@search_bp.route("/api/notes/<email>", methods=["GET"])
@require_role("viewer")
@handle_errors(json_response=True)
def get_search_notes(email):
    """Get notes for a searched user in search context."""
    from app.models.user import User
    from app.models.user_note import UserNote

    # Find user by email
    user = User.query.filter_by(email=email.lower()).first()
    if not user:
        # Check if this is an Htmx request
        if request.headers.get("HX-Request"):
            return _render_notes_empty(email)
        return jsonify({"notes": []})

    # Get notes with search context
    notes = UserNote.get_user_notes(user.id, context="search")

    # Check if this is an Htmx request
    if request.headers.get("HX-Request"):
        return _render_notes_list(notes, email)

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


@search_bp.route("/api/notes/<email>", methods=["POST"])
@require_role("viewer")
@handle_errors(json_response=True)
def add_search_note(email):
    """Add a note to a searched user in search context."""
    from app.models.user import User
    from app.models.user_note import UserNote
    from flask import session as flask_session

    # Check if this is an Htmx request
    if request.headers.get("HX-Request"):
        note_text = request.form.get("note", "").strip()
    else:
        data = request.get_json()
        note_text = data.get("note", "").strip()

    if not note_text:
        if request.headers.get("HX-Request"):
            return '<div class="text-red-600 text-sm">Note cannot be empty</div>', 400
        return jsonify({"success": False, "message": "Note cannot be empty"}), 400

    # Find or create user by email
    user = User.query.filter_by(email=email.lower()).first()
    if not user:
        # Create user with viewer role by default for searched users
        user = User.create_user(
            email=email.lower(), role="viewer", created_by="search_system"
        )

    # Get current user
    current_user = flask_session.get("user_email", "system")

    # Create note with search context
    note = UserNote.create_note(
        user_id=user.id, note_text=note_text, created_by=current_user, context="search"
    )

    # Check if this is an Htmx request
    if request.headers.get("HX-Request"):
        # Close modal and refresh notes
        notes = UserNote.get_user_notes(user.id, context="search")
        return _render_notes_list(notes, email)

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


@search_bp.route("/api/notes/<int:note_id>", methods=["PUT"])
@require_role("viewer")
@handle_errors(json_response=True)
def update_search_note(note_id):
    """Update a search note."""
    from app.models.user_note import UserNote

    note = UserNote.query.filter_by(id=note_id, context="search").first()
    if not note:
        if request.headers.get("HX-Request"):
            return '<div class="text-red-600 text-sm">Note not found</div>', 404
        return jsonify({"success": False, "message": "Note not found"}), 404

    # Check if this is an Htmx request
    if request.headers.get("HX-Request"):
        note_text = request.form.get("note", "").strip()
    else:
        data = request.get_json()
        note_text = data.get("note", "").strip()

    if not note_text:
        if request.headers.get("HX-Request"):
            return '<div class="text-red-600 text-sm">Note cannot be empty</div>', 400
        return jsonify({"success": False, "message": "Note cannot be empty"}), 400

    note.update_note(note_text)

    # Check if this is an Htmx request
    if request.headers.get("HX-Request"):
        # Return updated note card
        return _render_single_note(note, note.user.email)

    return jsonify({"success": True, "message": "Note updated successfully"})


@search_bp.route("/api/notes/<int:note_id>", methods=["DELETE"])
@require_role("viewer")
@handle_errors(json_response=True)
def delete_search_note(note_id):
    """Delete a search note."""
    from app.models.user_note import UserNote

    note = UserNote.query.filter_by(id=note_id, context="search").first()
    if not note:
        if request.headers.get("HX-Request"):
            return '<div class="text-red-600 text-sm">Note not found</div>', 404
        return jsonify({"success": False, "message": "Note not found"}), 404

    user_email = note.user.email
    user_id = note.user_id

    # Soft delete
    note.deactivate()

    # Check if this is an Htmx request
    if request.headers.get("HX-Request"):
        # Check if there are any remaining notes
        remaining_notes = UserNote.get_user_notes(user_id, context="search")
        if remaining_notes:
            # Just remove the deleted note card (Htmx will handle this with empty response)
            return ""
        else:
            # Return the empty notes message
            return _render_notes_empty(user_email)

    return jsonify({"success": True, "message": "Note deleted successfully"})


@search_bp.route("/api/user/<email>/preview")
@require_role("viewer")
@handle_errors(json_response=True)
def user_preview(email):
    """Get a quick preview of user information via Htmx."""
    from app.services.search_orchestrator import SearchOrchestrator
    from app.services.result_merger import ResultMerger

    logger.info(f"Loading preview for user: {email}")

    # Initialize services
    orchestrator = SearchOrchestrator()
    merger = ResultMerger()

    # Execute quick search with shorter timeout
    orchestrator.overall_timeout = 5  # Quick preview timeout
    ldap_result, genesys_result, graph_result = orchestrator.execute_concurrent_search(
        email
    )

    # Merge results
    azure_ad_result, _, _ = merger.merge_azure_ad_results(
        ldap_result, genesys_result, graph_result
    )

    # Get Genesys data
    genesys_data = genesys_result.get("result")

    # Build preview HTML
    return _render_user_preview(email, azure_ad_result, genesys_data)


@search_bp.route("/search", methods=["POST"])
@require_role("viewer")
@handle_errors
def search():
    """Search endpoint that returns HTML for Htmx."""
    search_term = request.form.get("query", "").strip()

    if not search_term:
        return '<div class="text-center text-gray-500 py-8">Please enter a search term</div>'

    logger.info(f"Searching for user: {search_term}")

    # Get user info for audit logging
    user_email = request.headers.get(
        "X-MS-CLIENT-PRINCIPAL-NAME", request.remote_user or "unknown"
    )
    user_role = getattr(request, "user_role", None)
    user_ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    user_agent = request.headers.get("User-Agent")

    # Initialize services
    orchestrator = SearchOrchestrator()
    merger = ResultMerger()

    # Execute concurrent searches
    ldap_result, genesys_result, graph_result = orchestrator.execute_concurrent_search(
        search_term
    )

    # Check if all searches timed out
    if orchestrator.all_searches_timed_out(ldap_result, genesys_result, graph_result):
        return _render_timeout_error(search_term, orchestrator.overall_timeout)

    # Merge results
    azure_ad_result, azure_ad_error, azure_ad_multiple = merger.merge_azure_ad_results(
        ldap_result, genesys_result, graph_result
    )

    # Smart match Azure AD and Genesys
    genesys_data = genesys_result.get("result")
    genesys_error = genesys_result.get("error")
    genesys_multiple = genesys_result.get("multiple", False)

    genesys_data, genesys_multiple = merger.smart_match_services(
        azure_ad_result, azure_ad_multiple, genesys_data, genesys_multiple
    )

    # Enhance with data warehouse
    search_results = {
        "azureAD": azure_ad_result,
        "azureAD_error": azure_ad_error,
        "azureAD_multiple": azure_ad_multiple,
        "genesys": genesys_data,
        "genesys_error": genesys_error,
        "genesys_multiple": genesys_multiple,
    }

    try:
        from app.services.search_enhancer import search_enhancer

        enhanced_results = search_enhancer.enhance_search_results(search_results)
    except Exception as e:
        logger.error(f"Error enhancing search results: {str(e)}")
        enhanced_results = search_results
        enhanced_results["keystone"] = None
        enhanced_results["keystone_error"] = f"Error loading Keystone data: {str(e)}"

    # Log audit
    _log_search_audit(
        search_term,
        user_email,
        user_role,
        user_ip,
        user_agent,
        ldap_result,
        graph_result,
        genesys_result,
        enhanced_results,
        azure_ad_multiple,
        genesys_multiple,
        None,
        None,
        None,
    )

    # Render results
    return _render_search_results(enhanced_results, search_term)


def _render_timeout_error(search_term, timeout):
    """Render timeout error message."""
    return f"""
    <div class="bg-yellow-50 border-l-4 border-yellow-400 p-4 rounded-lg">
        <div class="flex">
            <div class="flex-shrink-0">
                <i class="fas fa-clock text-yellow-400"></i>
            </div>
            <div class="ml-3">
                <h3 class="text-sm font-medium text-yellow-800">Search Timeout</h3>
                <p class="mt-1 text-sm text-yellow-700">
                    Search timed out after {timeout} seconds. Please try a more specific search term.
                </p>
            </div>
        </div>
    </div>
    """


def _render_search_results(results, search_term):
    """Render search results as HTML."""
    # Check if we have any results
    has_azure = results.get("azureAD") and not results.get("azureAD_error")
    has_genesys = results.get("genesys") and not results.get("genesys_error")
    has_keystone = results.get("keystone")

    # Check for multiple results
    azure_multiple = results.get("azureAD_multiple", False)
    genesys_multiple = results.get("genesys_multiple", False)

    if not has_azure and not has_genesys and not has_keystone:
        return _render_no_results()

    # If we have multiple results, show selection UI
    if azure_multiple or genesys_multiple:
        return _render_multiple_results(results, search_term)

    # Single result - show unified profile
    return _render_unified_profile(results)


def _render_no_results():
    """Render no results message."""
    return """
    <div class="bg-blue-50 border-l-4 border-blue-400 p-4 rounded-lg">
        <div class="flex">
            <div class="flex-shrink-0">
                <i class="fas fa-info-circle text-blue-400"></i>
            </div>
            <div class="ml-3">
                <p class="text-blue-700">
                    Nada. Zip. Nothing matched your search. Try again with fewer typos or better vibes.
                </p>
            </div>
        </div>
    </div>
    """


def _render_multiple_results(results, search_term):
    """Render multiple results selection UI."""
    html = '<div class="space-y-6">'
    html += '<h3 class="text-2xl font-semibold">Multiple Results Found</h3>'

    # Azure AD multiple results
    if results.get("azureAD_multiple") and results.get("azureAD", {}).get("results"):
        html += '<div class="bg-white rounded-lg shadow-md p-6">'
        html += '<h4 class="text-lg font-medium text-gray-900 mb-4 flex items-center">'
        html += '<span class="w-3 h-3 bg-ttcu-green rounded-full mr-2"></span>'
        html += "Azure AD Results</h4>"
        html += '<div class="space-y-3">'

        for user in results["azureAD"]["results"]:
            html += f'''
            <div class="border border-gray-200 rounded-lg p-4 hover:border-ttcu-green cursor-pointer"
                 hx-post="{{ url_for('search.search_specific') }}"
                 hx-vals='{{"search_term": "{search_term}", "graph_user_id": "{user.get("id", "")}", "ldap_user_dn": "{user.get("distinguishedName", "")}"}}'
                 hx-target="#searchResults"
                 hx-swap="innerHTML">
                <div class="flex items-start justify-between">
                    <div>
                        <h5 class="font-medium text-gray-900">{user.get("displayName", "Unknown")}</h5>
                        <p class="text-sm text-gray-600">{user.get("mail", "")}</p>
                        <p class="text-sm text-gray-500">{user.get("jobTitle", "")} - {user.get("department", "")}</p>
                    </div>
                    <i class="fas fa-chevron-right text-gray-400"></i>
                </div>
            </div>
            '''

        html += "</div></div>"

    # Genesys multiple results
    if results.get("genesys_multiple") and results.get("genesys", {}).get("results"):
        html += '<div class="bg-white rounded-lg shadow-md p-6">'
        html += '<h4 class="text-lg font-medium text-gray-900 mb-4 flex items-center">'
        html += '<span class="w-3 h-3 bg-genesys-orange rounded-full mr-2"></span>'
        html += "Genesys Cloud Results</h4>"
        html += '<div class="space-y-3">'

        for user in results["genesys"]["results"]:
            html += f'''
            <div class="border border-gray-200 rounded-lg p-4 hover:border-genesys-orange cursor-pointer"
                 hx-post="{{ url_for('search.search_specific') }}"
                 hx-vals='{{"search_term": "{search_term}", "genesys_user_id": "{user.get("id", "")}"}}'
                 hx-target="#searchResults"
                 hx-swap="innerHTML">
                <div class="flex items-start justify-between">
                    <div>
                        <h5 class="font-medium text-gray-900">{user.get("name", "Unknown")}</h5>
                        <p class="text-sm text-gray-600">{user.get("email", "")}</p>
                        <p class="text-sm text-gray-500">{user.get("username", "")}</p>
                    </div>
                    <i class="fas fa-chevron-right text-gray-400"></i>
                </div>
            </div>
            '''

        html += "</div></div>"

    html += "</div>"
    return html


def _render_unified_profile(results):
    """Render unified user profile."""
    # This is a simplified version - you would expand this to show all user details
    azure_data = results.get("azureAD")
    genesys_data = results.get("genesys")
    keystone_data = results.get("keystone")

    html = '<div class="grid grid-cols-1 lg:grid-cols-2 gap-6">'

    # Azure AD Card
    if azure_data:
        html += _render_azure_ad_card(azure_data)

    # Genesys Card
    if genesys_data:
        html += _render_genesys_card(genesys_data)

    html += "</div>"

    # Keystone Card (full width) - show even if there's an error
    keystone_error = results.get("keystone_error")
    if keystone_data or keystone_error:
        html += _render_keystone_card(keystone_data, keystone_error)

    return html


def _render_azure_ad_card(user_data):
    """Render Azure AD user card with comprehensive information."""
    # Extract user details
    display_name = user_data.get("displayName", "Unknown User")
    email = user_data.get("mail", "No email")
    # Title can come from LDAP (title) or Graph (mapped to title from jobTitle)
    job_title = user_data.get("title") or user_data.get("jobTitle", "No title")
    department = user_data.get("department", "No department")
    manager = user_data.get("manager", "No manager")
    manager_email = user_data.get("managerEmail")

    # Account status from LDAP data
    enabled = user_data.get("enabled", True)
    locked = user_data.get("locked", False)

    html = """
    <div class="bg-white rounded-lg shadow-md overflow-hidden">
        <div class="bg-ttcu-green text-white px-6 py-4">
            <h3 class="text-xl font-semibold flex items-center">
                <i class="fas fa-cloud mr-3"></i>
                Azure AD / Office 365
            </h3>
        </div>
        <div class="p-6">
    """

    # User photo and basic info - always prioritize Graph photo over LDAP
    photo_url = "/static/img/user-placeholder.svg"
    
    # First priority: Graph photo (either direct data or via Graph ID for lazy loading)
    if user_data.get("graphId"):
        # Use Graph service for photo
        photo_url = f"/search/photo/{user_data['graphId']}"
        if user_data.get("userPrincipalName"):
            photo_url += f"?upn={user_data['userPrincipalName']}"
    elif user_data.get("thumbnailPhoto") and user_data["thumbnailPhoto"].startswith("data:"):
        # Direct base64 photo data (from Graph)
        photo_url = user_data["thumbnailPhoto"]

    html += f"""
        <div class="flex items-start mb-6">
            <img src="{photo_url}" 
                 class="w-24 h-24 rounded-full bg-gray-200 mr-4 object-cover"
                 alt="User photo">
            <div class="flex-1">
                <h4 class="text-xl font-semibold text-gray-900">{display_name}</h4>
                <p class="text-gray-600">{email}</p>
                <p class="text-sm text-gray-500">{job_title}</p>
                <p class="text-sm text-gray-500">{department}</p>
                {f'<p class="text-sm text-gray-500">{user_data.get("officeLocation")}</p>' if user_data.get("officeLocation") else ""}
    """

    # Enhanced status badges
    html += '<div class="flex flex-wrap gap-2 mt-2">'

    # Account enabled/disabled status
    if enabled:
        html += '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">'
        html += '<i class="fas fa-check-circle mr-1"></i>AD Enabled</span>'
    else:
        html += '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800">'
        html += '<i class="fas fa-times-circle mr-1"></i>AD Disabled</span>'
    
    # Account locked/unlocked status
    if locked:
        html += '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800 ml-1">'
        html += '<i class="fas fa-lock mr-1"></i>Account Locked</span>'
    else:
        html += '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800 ml-1">'
        html += '<i class="fas fa-unlock mr-1"></i>Account Unlocked</span>'

    # User type badges
    phone_numbers = user_data.get("phoneNumbers", {})
    has_teams = (
        any("teams" in str(k).lower() for k in phone_numbers.keys())
        if phone_numbers
        else False
    )
    has_genesys = (
        any("genesys" in str(k).lower() for k in phone_numbers.keys())
        if phone_numbers
        else False
    )

    if has_teams:
        html += '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">'
        html += '<i class="fas fa-users mr-1"></i>Teams User</span>'

    if has_genesys:
        html += '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-orange-100 text-orange-800">'
        html += '<i class="fas fa-headset mr-1"></i>Genesys User</span>'

    html += "</div></div></div>"

    # Core Identity Section
    html += '<div class="grid grid-cols-1 md:grid-cols-2 gap-6 mt-4">'
    html += "<div>"
    html += '<h6 class="text-sm font-semibold text-gray-700 mb-3 flex items-center">'
    html += '<i class="fas fa-id-card mr-2"></i>Core Identity</h6>'
    html += '<div class="space-y-2 text-sm">'

    # Username and UPN
    if user_data.get("sAMAccountName"):
        html += f'<div><span class="font-medium">Username:</span> {user_data["sAMAccountName"]}'
        html += ' <span class="bg-blue-100 text-blue-800 text-xs px-2 py-1 rounded">AD</span></div>'

    if user_data.get("userPrincipalName") and user_data["userPrincipalName"] != email:
        html += f'<div><span class="font-medium">UPN:</span> {user_data["userPrincipalName"]}</div>'

    # Employee ID
    if user_data.get("employeeID"):
        html += f'<div><span class="font-medium">Employee ID:</span> {user_data["employeeID"]}</div>'

    # Manager
    if manager and manager != "No manager":
        html += f'<div><span class="font-medium">Manager:</span> {manager}'
        if manager_email:
            html += f' <span class="text-gray-500">({manager_email})</span>'
        html += "</div>"

    html += "</div></div>"

    # Contact Information Section
    html += "<div>"
    html += '<h6 class="text-sm font-semibold text-gray-700 mb-3 flex items-center">'
    html += '<i class="fas fa-phone mr-2"></i>Contact Information</h6>'
    html += '<div class="space-y-2 text-sm">'

    # Phone numbers with improved formatting
    if phone_numbers:
        for phone_type, number in phone_numbers.items():
            if number:
                formatted_number = _format_phone_number(number)
                badge_html = _get_phone_badge(phone_type)
                label = _get_phone_label(phone_type)
                html += f'<div><span class="font-medium">{label}:</span> {formatted_number} {badge_html}</div>'

    # Extension
    if user_data.get("extension"):
        html += (
            f'<div><span class="font-medium">Extension:</span> {user_data["extension"]}'
        )
        html += ' <span class="bg-orange-100 text-orange-800 text-xs px-2 py-1 rounded">Legacy</span></div>'

    html += "</div></div></div>"

    # Address Section
    address = user_data.get("address")
    if address and any(address.values() if isinstance(address, dict) else []):
        html += '<div class="mt-6">'
        html += (
            '<h6 class="text-sm font-semibold text-gray-700 mb-3 flex items-center">'
        )
        html += '<i class="fas fa-map-marker-alt mr-2"></i>Address</h6>'
        html += '<div class="text-sm text-gray-600">'
        if isinstance(address, dict):
            if address.get("street"):
                html += f"{address['street']}<br>"
            if address.get("city") or address.get("state") or address.get("postalCode"):
                parts = [
                    address.get("city"),
                    address.get("state"),
                    address.get("postalCode"),
                ]
                html += f"{', '.join(filter(None, parts))}<br>"
            if address.get("country"):
                html += address["country"]
        html += "</div></div>"

    # Important Dates Section
    dates = []
    if user_data.get("createdDateTime"):
        dates.append(("Account Created", user_data["createdDateTime"]))
    if user_data.get("employeeHireDate"):
        dates.append(("Hire Date", user_data["employeeHireDate"]))
    if user_data.get("pwdLastSet"):
        dates.append(("Password Changed", user_data["pwdLastSet"]))
    if user_data.get("pwdExpires"):
        dates.append(("Password Expires", user_data["pwdExpires"]))

    if dates:
        html += '<div class="mt-6">'
        html += (
            '<h6 class="text-sm font-semibold text-gray-700 mb-3 flex items-center">'
        )
        html += '<i class="fas fa-calendar-alt mr-2"></i>Important Dates</h6>'
        html += '<div class="space-y-1 text-sm">'
        for label, date_value in dates:
            formatted_date = _format_date_with_relative(date_value, label)
            html += f"<div>{formatted_date}</div>"
        html += "</div></div>"

    # Admin notes section
    if email and email != "No email":
        html += f"""
        <div class="mt-6 pt-6 border-t border-gray-200">
            <h5 class="text-sm font-medium text-gray-900 mb-3">Admin Notes</h5>
            <div hx-get="/search/api/notes/{email}"
                 hx-trigger="load"
                 hx-swap="innerHTML"
                 class="space-y-2">
                <div class="text-sm text-gray-500">Loading notes...</div>
            </div>
        </div>
        """

    html += "</div></div>"
    return html


def _render_genesys_card(user_data):
    """Render Genesys user card with comprehensive information."""
    # Extract user details
    name = user_data.get("name", "Unknown User")
    email = user_data.get("email", "No email")
    username = user_data.get("username", "No username")

    # Handle division as either string or dict
    division_data = user_data.get("division", "No division")
    if isinstance(division_data, dict):
        division = division_data.get("name", "No division")
    elif isinstance(division_data, str):
        division = division_data
    else:
        division = "No division"

    html = """
    <div class="bg-white rounded-lg shadow-md overflow-hidden">
        <div class="bg-genesys-orange text-white px-6 py-4">
            <h3 class="text-xl font-semibold flex items-center">
                <i class="fas fa-headset mr-3"></i>
                Genesys Cloud
            </h3>
        </div>
        <div class="p-6">
    """

    # Basic info with status
    html += f"""
        <div class="mb-6">
            <h4 class="text-xl font-semibold text-gray-900">{name}</h4>
            <p class="text-gray-600">{email}</p>
            <p class="text-sm text-gray-500">Username: {username}</p>
            <p class="text-sm text-gray-500">Division: {division}</p>
    """

    # Status badges
    state = user_data.get("state")
    presence = user_data.get("presence")

    html += '<div class="flex flex-wrap gap-2 mt-2">'
    if state:
        if state.lower() == "active":
            html += '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">'
            html += '<i class="fas fa-check-circle mr-1"></i>Active</span>'
        else:
            html += '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800">'
            html += f'<i class="fas fa-times-circle mr-1"></i>{state}</span>'

    if presence:
        html += '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">'
        html += f'<i class="fas fa-circle mr-1"></i>{presence}</span>'

    html += "</div></div>"

    # Contact Information Section
    phone_numbers = user_data.get("phoneNumbers", {})
    if phone_numbers:
        html += '<div class="mb-6">'
        html += (
            '<h6 class="text-sm font-semibold text-gray-700 mb-3 flex items-center">'
        )
        html += '<i class="fas fa-phone mr-2"></i>Contact Information</h6>'
        html += '<div class="space-y-2 text-sm">'

        for phone_type, number in phone_numbers.items():
            if number:
                formatted_number = _format_phone_number(number)
                label = _get_phone_label(phone_type)
                html += (
                    f'<div><span class="font-medium">{label}:</span> {formatted_number}'
                )
                html += ' <span class="bg-orange-100 text-orange-800 text-xs px-2 py-1 rounded">Genesys</span></div>'

        html += "</div></div>"

    # Last Login
    last_login = user_data.get("dateLastLogin")
    if last_login:
        html += '<div class="mb-6">'
        html += (
            '<h6 class="text-sm font-semibold text-gray-700 mb-3 flex items-center">'
        )
        html += '<i class="fas fa-clock mr-2"></i>Activity</h6>'
        html += '<div class="text-sm">'
        formatted_date = _format_date_with_relative(last_login, "Last Login")
        html += f"<div>{formatted_date}</div>"
        html += "</div></div>"

    # Skills with enhanced display
    skills = user_data.get("skills", [])
    if skills:
        html += '<div class="mb-4">'
        html += (
            '<h6 class="text-sm font-semibold text-gray-700 mb-3 flex items-center">'
        )
        html += f'<i class="fas fa-star mr-2 text-yellow-500"></i>Skills ({len(skills)})</h6>'
        html += '<div class="flex flex-wrap gap-2">'

        # Show first 8 skills, then collapse others
        for i, skill in enumerate(skills[:8]):
            skill_name = skill.get("name", skill) if isinstance(skill, dict) else skill
            html += f'<span class="px-2 py-1 text-xs bg-blue-100 text-blue-800 rounded-full transition-all duration-150 hover:bg-blue-200">{skill_name}</span>'

        if len(skills) > 8:
            html += '<button class="px-2 py-1 text-xs bg-gray-100 text-gray-600 rounded-full hover:bg-gray-200" onclick="toggleSkills(this)">'
            html += f"+{len(skills) - 8} more</button>"
            html += '<div class="hidden w-full mt-2">'
            for skill in skills[8:]:
                skill_name = (
                    skill.get("name", skill) if isinstance(skill, dict) else skill
                )
                html += f'<span class="inline-block px-2 py-1 text-xs bg-blue-100 text-blue-800 rounded-full mr-2 mb-2">{skill_name}</span>'
            html += "</div>"

        html += "</div></div>"

    # Queues with enhanced display
    queues = user_data.get("queues", [])
    if queues:
        html += '<div class="mb-4">'
        html += (
            '<h6 class="text-sm font-semibold text-gray-700 mb-3 flex items-center">'
        )
        html += f'<i class="fas fa-users mr-2 text-green-500"></i>Queues ({len(queues)})</h6>'
        html += '<div class="flex flex-wrap gap-2">'

        # Show first 5 queues
        for queue in queues[:5]:
            queue_name = queue.get("name", queue) if isinstance(queue, dict) else queue
            html += f'<span class="px-2 py-1 text-xs bg-green-100 text-green-800 rounded-full transition-all duration-150 hover:bg-green-200">{queue_name}</span>'

        if len(queues) > 5:
            html += '<button class="px-2 py-1 text-xs bg-gray-100 text-gray-600 rounded-full hover:bg-gray-200" onclick="toggleQueues(this)">'
            html += f"+{len(queues) - 5} more</button>"
            html += '<div class="hidden w-full mt-2">'
            for queue in queues[5:]:
                queue_name = (
                    queue.get("name", queue) if isinstance(queue, dict) else queue
                )
                html += f'<span class="inline-block px-2 py-1 text-xs bg-green-100 text-green-800 rounded-full mr-2 mb-2">{queue_name}</span>'
            html += "</div>"

        html += "</div></div>"

    # Locations
    locations = user_data.get("locations", [])
    if locations:
        html += '<div class="mb-4">'
        html += (
            '<h6 class="text-sm font-semibold text-gray-700 mb-3 flex items-center">'
        )
        html += f'<i class="fas fa-map-marker-alt mr-2 text-purple-500"></i>Locations ({len(locations)})</h6>'
        html += '<div class="flex flex-wrap gap-2">'

        for location in locations:
            location_name = (
                location.get("name", location)
                if isinstance(location, dict)
                else location
            )
            html += f'<span class="px-2 py-1 text-xs bg-purple-100 text-purple-800 rounded-full">{location_name}</span>'

        html += "</div></div>"

    # Groups with enhanced display
    groups = user_data.get("groups", [])
    if groups:
        html += '<div class="mb-4">'
        html += (
            '<h6 class="text-sm font-semibold text-gray-700 mb-3 flex items-center">'
        )
        html += f'<i class="fas fa-layer-group mr-2 text-indigo-500"></i>Groups ({len(groups)})</h6>'
        html += '<div class="flex flex-wrap gap-2">'

        # Show first 3 groups
        for group in groups[:3]:
            group_name = group.get("name", group) if isinstance(group, dict) else group
            html += f'<span class="px-2 py-1 text-xs bg-indigo-100 text-indigo-800 rounded-full">{group_name}</span>'

        if len(groups) > 3:
            html += '<button class="px-2 py-1 text-xs bg-gray-100 text-gray-600 rounded-full hover:bg-gray-200" onclick="toggleGroups(this)">'
            html += f"+{len(groups) - 3} more</button>"
            html += '<div class="hidden w-full mt-2">'
            for group in groups[3:]:
                group_name = (
                    group.get("name", group) if isinstance(group, dict) else group
                )
                html += f'<span class="inline-block px-2 py-1 text-xs bg-indigo-100 text-indigo-800 rounded-full mr-2 mb-2">{group_name}</span>'
            html += "</div>"

        html += "</div></div>"

    # Add JavaScript for toggle functionality
    html += """
    <script>
    function toggleSkills(button) {
        const hiddenDiv = button.nextElementSibling;
        if (hiddenDiv.classList.contains('hidden')) {
            hiddenDiv.classList.remove('hidden');
            button.textContent = 'Show less';
        } else {
            hiddenDiv.classList.add('hidden');
            const count = button.textContent.match(/\\d+/)[0];
            button.textContent = `+${count} more`;
        }
    }
    function toggleQueues(button) {
        const hiddenDiv = button.nextElementSibling;
        if (hiddenDiv.classList.contains('hidden')) {
            hiddenDiv.classList.remove('hidden');
            button.textContent = 'Show less';
        } else {
            hiddenDiv.classList.add('hidden');
            const count = button.textContent.match(/\\d+/)[0];
            button.textContent = `+${count} more`;
        }
    }
    function toggleGroups(button) {
        const hiddenDiv = button.nextElementSibling;
        if (hiddenDiv.classList.contains('hidden')) {
            hiddenDiv.classList.remove('hidden');
            button.textContent = 'Show less';
        } else {
            hiddenDiv.classList.add('hidden');
            const count = button.textContent.match(/\\d+/)[0];
            button.textContent = `+${count} more`;
        }
    }
    </script>
    """

    html += "</div></div>"
    return html


def _render_keystone_card(keystone_data, keystone_error=None):
    """Render Keystone data card with error handling."""
    html = """
    <div class="bg-white rounded-lg shadow-md overflow-hidden mt-6">
        <div class="bg-gray-800 text-white px-6 py-4">
            <h3 class="text-xl font-semibold flex items-center">
                <i class="fas fa-database mr-3"></i>
                Keystone Data Warehouse
            </h3>
        </div>
        <div class="p-6">
    """

    # Handle errors first
    if keystone_error:
        if "pyodbc not available" in str(keystone_error) or "Error loading Keystone data" in str(keystone_error):
            html += """
            <div class="bg-blue-50 border-l-4 border-blue-400 p-4 mb-4">
                <div class="flex">
                    <div class="flex-shrink-0">
                        <i class="fas fa-info-circle text-blue-400"></i>
                    </div>
                    <div class="ml-3">
                        <h4 class="text-sm font-medium text-blue-800">Data Warehouse Integration</h4>
                        <p class="text-sm text-blue-700 mt-1">
                            The Keystone data warehouse integration is currently unavailable. 
                            This service provides additional member information from internal systems.
                        </p>
                        <p class="text-xs text-blue-600 mt-2">
                            Status: Service requires SQL Server connectivity (pyodbc driver not available)
                        </p>
                    </div>
                </div>
            </div>
            """
        else:
            html += f"""
            <div class="bg-yellow-50 border-l-4 border-yellow-400 p-4 mb-4">
                <div class="flex">
                    <div class="flex-shrink-0">
                        <i class="fas fa-exclamation-triangle text-yellow-400"></i>
                    </div>
                    <div class="ml-3">
                        <h4 class="text-sm font-medium text-yellow-800">Data Warehouse Error</h4>
                        <p class="text-sm text-yellow-700 mt-1">{keystone_error}</p>
                    </div>
                </div>
            </div>
            """
    
    # Show data if available
    if keystone_data:
        # Role status indicator
        if keystone_data.get("role_mismatch"):
            warning_level = keystone_data.get("role_warning_level", "medium")
            
            if warning_level == "success":
                # Positive indicator for matching roles
                html += f"""
                <div class="bg-green-50 border-l-4 border-green-400 p-4 mb-4">
                    <div class="flex">
                        <div class="flex-shrink-0">
                            <i class="fas fa-check-circle text-green-400"></i>
                        </div>
                        <div class="ml-3">
                            <h4 class="text-sm font-medium text-green-800">Role Assignment Verified</h4>
                            <p class="text-sm text-green-700 mt-1">
                                {keystone_data['role_mismatch']}
                            </p>
                        </div>
                    </div>
                </div>
                """
            else:
                # Warning/error indicators for issues
                warning_color = "red" if warning_level == "high" else "yellow"
                warning_title = "Security Alert: Role Assignment Issue" if warning_level == "high" else "Audit Alert: Role Mapping Issue"
                html += f"""
                <div class="bg-{warning_color}-50 border-l-4 border-{warning_color}-400 p-4 mb-4">
                    <div class="flex">
                        <div class="flex-shrink-0">
                            <i class="fas fa-exclamation-triangle text-{warning_color}-400"></i>
                        </div>
                        <div class="ml-3">
                            <h4 class="text-sm font-medium text-{warning_color}-800">{warning_title}</h4>
                            <p class="text-sm text-{warning_color}-700 mt-1">
                                {keystone_data['role_mismatch']}
                            </p>
                        </div>
                    </div>
                </div>
                """

        # Display Keystone data in organized sections
        html += '<div class="grid grid-cols-1 md:grid-cols-2 gap-6">'
        
        # Keystone Identity Section
        html += '<div>'
        html += '<h6 class="text-sm font-semibold text-gray-700 mb-3 flex items-center">'
        html += '<i class="fas fa-id-badge mr-2"></i>Keystone Identity</h6>'
        html += '<div class="space-y-2 text-sm">'
        
        if keystone_data.get("user_serial"):
            html += f'<div><span class="font-medium">User Serial:</span> {keystone_data["user_serial"]}</div>'
        
        if keystone_data.get("upn"):
            html += f'<div><span class="font-medium">UPN:</span> {keystone_data["upn"]}</div>'
        
        if keystone_data.get("ukg_job_code"):
            html += f'<div><span class="font-medium">UKG Job Code:</span> {keystone_data["ukg_job_code"]}</div>'
        
        html += '</div></div>'
        
        # Role Information Section
        html += '<div>'
        html += '<h6 class="text-sm font-semibold text-gray-700 mb-3 flex items-center">'
        html += '<i class="fas fa-user-tag mr-2"></i>Role Information</h6>'
        html += '<div class="space-y-2 text-sm">'
        
        if keystone_data.get("live_role"):
            warning_level = keystone_data.get("role_warning_level")
            if warning_level == "success":
                role_class = "text-green-600"  # Green for matching roles
                role_icon = '<i class="fas fa-check-circle mr-1"></i>'
            elif warning_level == "high":
                role_class = "text-red-600"  # Red for mismatches/missing roles
                role_icon = '<i class="fas fa-exclamation-triangle mr-1"></i>'
            elif warning_level == "medium":
                role_class = "text-yellow-600"  # Yellow for unmapped job codes
                role_icon = '<i class="fas fa-question-circle mr-1"></i>'
            else:
                role_class = "text-gray-600"  # Default
                role_icon = ""
            
            html += f'<div><span class="font-medium">Live Role:</span> <span class="{role_class}">{role_icon}{keystone_data["live_role"]}</span></div>'
        
        if keystone_data.get("test_role"):
            html += f'<div><span class="font-medium">Test Role:</span> {keystone_data["test_role"]}</div>'
        
        if keystone_data.get("expected_role"):
            html += f'<div><span class="font-medium">Expected Role:</span> {keystone_data["expected_role"]}</div>'
        
        html += '</div></div></div>'
        
        # Account Status Section
        html += '<div class="mt-6">'
        html += '<h6 class="text-sm font-semibold text-gray-700 mb-3 flex items-center">'
        html += '<i class="fas fa-shield-alt mr-2"></i>Account Status</h6>'
        html += '<div class="space-y-2 text-sm">'
        
        if keystone_data.get("lock_status"):
            lock_class = "text-red-600" if keystone_data.get("login_locked") else "text-green-600"
            lock_icon = "fa-lock" if keystone_data.get("login_locked") else "fa-unlock"
            html += f'<div><span class="font-medium">Keystone Login Lock Status:</span> <span class="{lock_class}"><i class="fas {lock_icon} mr-1"></i>{keystone_data["lock_status"]}</span></div>'
        
        if keystone_data.get("last_login_formatted"):
            html += f'<div><span class="font-medium">Keystone Last Login:</span> {keystone_data["last_login_formatted"]}</div>'
        
        if keystone_data.get("last_cached"):
            formatted_cached = _format_date_with_relative(keystone_data["last_cached"], "Data Cached")
            html += f'<div>{formatted_cached}</div>'
        
        html += '</div></div>'
    else:
        # No data available
        if not keystone_error:
            html += """
            <div class="text-center py-4">
                <i class="fas fa-database text-gray-400 text-3xl mb-2"></i>
                <p class="text-gray-500">No Keystone data found for this user</p>
                <p class="text-xs text-gray-400 mt-1">Additional member information would appear here when available</p>
            </div>
            """

    html += "</div></div>"
    return html


def _render_user_preview(email, azure_ad_result, genesys_data):
    """Render user preview HTML for Htmx."""
    ad_data = azure_ad_result.get("results") if azure_ad_result else None

    html = '<div class="bg-white rounded-lg shadow-lg p-6">'
    html += '<div class="flex justify-between items-start mb-4">'
    html += f'<h3 class="text-lg font-semibold text-gray-900">{email}</h3>'
    html += "<button onclick=\"this.closest('.htmx-preview').innerHTML=''\" class=\"text-gray-400 hover:text-gray-500\">"
    html += '<i class="fas fa-times"></i></button></div>'

    # Azure AD Section
    if ad_data:
        html += '<div class="mb-4">'
        html += '<h4 class="text-sm font-medium text-gray-700 mb-2 flex items-center">'
        html += (
            '<span class="w-2 h-2 bg-ttcu-green rounded-full mr-2"></span>Azure AD</h4>'
        )
        html += '<div class="text-sm text-gray-600 space-y-1">'
        html += f"<div><strong>Name:</strong> {ad_data.get('displayName', 'N/A')}</div>"
        html += f"<div><strong>Title:</strong> {ad_data.get('jobTitle', 'N/A')}</div>"
        html += f"<div><strong>Department:</strong> {ad_data.get('department', 'N/A')}</div>"
        html += f"<div><strong>Manager:</strong> {ad_data.get('manager', 'N/A')}</div>"

        # Phone numbers
        phones = []
        if ad_data.get("telephoneNumber"):
            phones.append(f"{ad_data['telephoneNumber']} (Office)")
        if ad_data.get("mobile"):
            phones.append(f"{ad_data['mobile']} (Mobile)")
        if phones:
            html += f"<div><strong>Phone:</strong> {', '.join(phones)}</div>"

        # Account status
        enabled = ad_data.get("accountEnabled", True)
        locked = ad_data.get("accountLocked", False)
        status_text = "Enabled" if enabled else "Disabled"
        if locked:
            status_text += " (Locked)"
        status_class = "text-green-600" if enabled and not locked else "text-red-600"
        html += f'<div><strong>Status:</strong> <span class="{status_class}">{status_text}</span></div>'

        html += "</div></div>"

    # Genesys Section
    if genesys_data:
        html += '<div class="mb-4">'
        html += '<h4 class="text-sm font-medium text-gray-700 mb-2 flex items-center">'
        html += '<span class="w-2 h-2 bg-genesys-orange rounded-full mr-2"></span>Genesys Cloud</h4>'
        html += '<div class="text-sm text-gray-600 space-y-1">'
        html += f"<div><strong>Username:</strong> {genesys_data.get('username', 'N/A')}</div>"
        html += f"<div><strong>Division:</strong> {genesys_data.get('division', {}).get('name', 'N/A')}</div>"

        # Skills
        skills = genesys_data.get("skills", [])
        if skills:
            skill_names = [s["name"] for s in skills[:3]]  # Show first 3
            if len(skills) > 3:
                skill_names.append(f"+{len(skills) - 3} more")
            html += f"<div><strong>Skills:</strong> {', '.join(skill_names)}</div>"

        # Queues
        queues = genesys_data.get("queues", [])
        if queues:
            queue_names = [q["name"] for q in queues[:3]]  # Show first 3
            if len(queues) > 3:
                queue_names.append(f"+{len(queues) - 3} more")
            html += f"<div><strong>Queues:</strong> {', '.join(queue_names)}</div>"

        html += "</div></div>"

    # Actions
    html += '<div class="flex justify-end space-x-2 pt-4 border-t">'
    html += f"<button onclick=\"document.getElementById('searchInput').value='{email}'; document.getElementById('searchForm').dispatchEvent(new Event('submit'))\" "
    html += 'class="px-4 py-2 bg-ttcu-green text-white rounded-md hover:bg-green-700 text-sm">'
    html += '<i class="fas fa-search mr-1"></i>Full Details</button>'
    html += "</div>"

    html += "</div>"

    return html


def _render_notes_empty(email):
    """Render empty notes section."""
    from flask import g

    # Check if user can add notes (editor or admin)
    can_edit = hasattr(g, "role") and g.role in ["editor", "admin"]

    html = '<div class="space-y-2">'
    html += '<p class="text-sm text-gray-500">No notes yet</p>'

    if can_edit:
        html += f"""
        <button hx-get="/search/notes/new?email={email}"
                hx-target="#noteModalContent"
                hx-swap="innerHTML"
                class="text-sm text-blue-600 hover:text-blue-800 transition-colors duration-150">
            <i class="fas fa-plus-circle mr-1"></i>Add Note
        </button>
        """

    html += "</div>"
    return html


def _render_notes_list(notes, email):
    """Render notes list."""
    from flask import g

    # Check if user can add notes (editor or admin)
    can_edit = hasattr(g, "role") and g.role in ["editor", "admin"]

    html = '<div class="space-y-2">'

    for note in notes:
        html += _render_single_note(note, email)

    if can_edit:
        html += f"""
        <button hx-get="/search/notes/new?email={email}"
                hx-target="#noteModal"
                hx-swap="innerHTML"
                class="text-sm text-blue-600 hover:text-blue-800 mt-2 transition-colors duration-150">
            <i class="fas fa-plus-circle mr-1"></i>Add Note
        </button>
        """

    html += "</div>"
    return html


def _render_single_note(note, email):
    """Render a single note card."""
    from flask import g

    # Check if user can edit notes (editor or admin)
    can_edit = hasattr(g, "role") and g.role in ["editor", "admin"]

    # Format dates
    created_date = (
        format_timestamp(note.created_at, "%m/%d/%Y") if note.created_at else ""
    )
    updated_date = (
        format_timestamp(note.updated_at, "%m/%d/%Y") if note.updated_at else ""
    )

    date_info = f"Created {created_date} by {note.created_by or 'Unknown'}"
    if updated_date and updated_date != created_date:
        date_info += f" • Updated {updated_date}"

    html = f'''
    <div class="bg-gray-50 p-3 rounded-md note-card transition-all duration-150 hover:bg-gray-100" data-note-id="{note.id}">
        <div class="flex justify-between items-start">
            <div class="flex-1">
                <p class="text-sm text-gray-700 whitespace-pre-wrap">{note.note}</p>
                <p class="text-xs text-gray-500 mt-1">{date_info}</p>
            </div>
    '''

    if can_edit:
        html += f"""
            <div class="ml-2 space-x-1">
                <button hx-get="/search/notes/{note.id}/edit"
                        hx-target=".note-card[data-note-id='{note.id}']"
                        hx-swap="outerHTML"
                        class="text-blue-600 hover:text-blue-800 text-sm transition-colors duration-150">
                    <i class="fas fa-edit"></i>
                </button>
                <button hx-delete="/search/api/notes/{note.id}"
                        hx-confirm="Are you sure you want to delete this note?"
                        hx-target=".note-card[data-note-id='{note.id}']"
                        hx-swap="outerHTML"
                        class="text-red-600 hover:text-red-800 text-sm transition-colors duration-150">
                    <i class="fas fa-trash"></i>
                </button>
            </div>
        """

    html += """
        </div>
    </div>
    """

    return html


def _format_phone_number(phone):
    """Format phone numbers consistently."""
    if not phone:
        return phone

    import re

    # Remove all non-digits
    cleaned = re.sub(r"\D", "", str(phone))

    # If it's a 4-digit extension, leave it as is
    if len(cleaned) == 4:
        return cleaned

    # Handle 10-digit numbers (add US country code)
    if len(cleaned) == 10:
        return f"+1 {cleaned[:3]}-{cleaned[3:6]}-{cleaned[6:]}"

    # Handle 11-digit numbers starting with 1
    if len(cleaned) == 11 and cleaned.startswith("1"):
        return f"+1 {cleaned[1:4]}-{cleaned[4:7]}-{cleaned[7:]}"

    # Return original if we can't format it
    return phone


def _get_phone_label(phone_type):
    """Get display label for phone type."""
    type_map = {
        "mobile": "Cell Phone",
        "business": "Business",
        "teams": "Office",
        "teams_did": "DID",  # Simplified since we have source badges
        "genesys_did": "DID",  # Simplified since we have source badges
        "genesys_ext": "Ext",
        "genesys": "Office",
    }
    return type_map.get(phone_type, phone_type.replace("_", " ").title())


def _get_phone_badge(phone_type):
    """Get badge HTML for phone type."""
    if "teams" in phone_type.lower():
        return '<span class="bg-blue-100 text-blue-800 text-xs px-2 py-1 rounded">Teams</span>'
    elif "genesys" in phone_type.lower():
        return '<span class="bg-orange-100 text-orange-800 text-xs px-2 py-1 rounded">Genesys</span>'
    elif phone_type in ["mobile", "business"]:
        return '<span class="bg-blue-100 text-blue-800 text-xs px-2 py-1 rounded">AD</span>'
    return ""


def _format_date_with_relative(date_value, label):
    """Format date with relative time information."""
    if not date_value:
        return f"<span class='font-medium'>{label}:</span> <span class='text-gray-500'>-</span>"

    try:
        # Parse the date
        if isinstance(date_value, str):
            # Try to parse ISO format
            if "T" in date_value:
                date_obj = datetime.fromisoformat(date_value.replace("Z", "+00:00"))
            else:
                date_obj = datetime.fromisoformat(date_value)
        elif isinstance(date_value, datetime):
            date_obj = date_value
        else:
            return f"<span class='font-medium'>{label}:</span> <span class='text-gray-500'>{date_value}</span>"

        # Ensure timezone awareness
        if date_obj.tzinfo is None:
            date_obj = date_obj.replace(tzinfo=timezone.utc)

        # Format date as M/D/YYYY
        date_str = f"{date_obj.month}/{date_obj.day}/{date_obj.year}"

        # Format time in 24-hour format without seconds
        time_str = f"{date_obj.hour:02d}:{date_obj.minute:02d}"

        # Calculate relative time
        now = datetime.now(timezone.utc)
        days_diff = (date_obj - now).days
        abs_days = abs(days_diff)

        # Calculate years, months, and remaining days
        years = abs_days // 365
        months = (abs_days % 365) // 30
        days = abs_days % 30

        # Build relative string
        parts = []
        if years > 0:
            parts.append(f"{years}Yr")
            if months > 0:
                parts.append(f"{months}Mo")
        elif months > 0:
            parts.append(f"{months}Mo")
            if days > 0 and months < 3:
                parts.append(f"{days}d")
        elif abs_days > 0:
            parts.append(f"{abs_days}d")

        # Format based on past or future
        if days_diff < 0:
            relative = parts[0] + " ago" if parts else "Today"
        elif days_diff == 0:
            relative = "Today"
        else:
            relative = "in " + " ".join(parts)
            # Add warning classes for expiration
            if "expires" in label.lower():
                if days_diff < 7:
                    relative = (
                        f'<span class="text-red-600 font-medium">{relative}</span>'
                    )
                elif days_diff < 30:
                    relative = (
                        f'<span class="text-yellow-600 font-medium">{relative}</span>'
                    )

        return f"<span class='font-medium'>{label}:</span> {date_str} {time_str} <span class='text-gray-500'>({relative})</span>"

    except Exception as e:
        logger.warning(f"Error formatting date {date_value}: {str(e)}")
        return f"<span class='font-medium'>{label}:</span> <span class='text-gray-500'>{date_value}</span>"


@search_bp.route("/notes/new")
@require_role("viewer")
@handle_errors
def new_note_form():
    """Show new note form."""
    email = request.args.get("email", "")
    return f"""
    <div class="bg-white rounded-lg shadow-lg">
        <div class="p-6">
            <h3 class="text-lg font-semibold text-gray-900 mb-4">Add Note</h3>
            <form hx-post="/search/api/notes/{email}"
                  hx-target="[hx-get='/search/api/notes/{email}']"
                  hx-swap="innerHTML"
                  hx-on::after-request="document.getElementById('noteModal').classList.add('hidden')">
                <div class="mb-4">
                    <label class="block text-sm font-medium text-gray-700 mb-2">Note</label>
                    <textarea name="note" 
                              rows="3" 
                              class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                              required></textarea>
                </div>
                <div class="flex justify-end space-x-2">
                    <button type="button"
                            onclick="document.getElementById('noteModal').classList.add('hidden')"
                            class="px-4 py-2 text-gray-600 hover:text-gray-800">
                        Cancel
                    </button>
                    <button type="submit"
                            class="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700">
                        Add Note
                    </button>
                </div>
            </form>
        </div>
    </div>
    <script>
        document.getElementById('noteModal').classList.remove('hidden');
    </script>
    """


@search_bp.route("/notes/<int:note_id>/edit")
@require_role("viewer")
@handle_errors
def edit_note_form(note_id):
    """Show edit note form."""
    from app.models.user_note import UserNote

    note = UserNote.query.filter_by(id=note_id, context="search").first()
    if not note:
        return '<div class="text-red-600">Note not found</div>'

    return f'''
    <div class="bg-gray-50 p-3 rounded-md note-card" data-note-id="{note.id}">
        <form hx-put="/search/api/notes/{note.id}"
              hx-target=".note-card[data-note-id='{note.id}']"
              hx-swap="outerHTML">
            <textarea name="note" 
                      rows="3" 
                      class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 mb-2"
                      required>{note.note}</textarea>
            <div class="flex justify-end space-x-2">
                <button type="button"
                        hx-get="/search/api/notes/{note.user.email}"
                        hx-target="[hx-get='/search/api/notes/{note.user.email}']"
                        hx-swap="innerHTML"
                        class="px-3 py-1 text-sm text-gray-600 hover:text-gray-800">
                    Cancel
                </button>
                <button type="submit"
                        class="px-3 py-1 text-sm bg-blue-600 text-white rounded hover:bg-blue-700">
                    Save
                </button>
            </div>
        </form>
    </div>
    '''


@search_bp.route("/search_specific", methods=["POST"])
@require_role("viewer")
@handle_errors
def search_specific():
    """Search for a specific user from multiple results."""
    search_term = request.form.get("search_term", "")
    genesys_user_id = request.form.get("genesys_user_id")
    ldap_user_dn = request.form.get("ldap_user_dn")
    graph_user_id = request.form.get("graph_user_id")

    if not search_term:
        return '<div class="text-center text-gray-500 py-8">Invalid search parameters</div>'

    # Get user info for audit logging
    user_email = request.headers.get(
        "X-MS-CLIENT-PRINCIPAL-NAME", request.remote_user or "unknown"
    )
    user_role = getattr(request, "user_role", None)
    user_ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    user_agent = request.headers.get("User-Agent")

    # Initialize services
    orchestrator = SearchOrchestrator()
    merger = ResultMerger()

    # Execute specific search
    ldap_result, genesys_result, graph_result = orchestrator.execute_concurrent_search(
        search_term, genesys_user_id, ldap_user_dn, graph_user_id
    )

    # Merge results
    azure_ad_result, azure_ad_error, azure_ad_multiple = merger.merge_azure_ad_results(
        ldap_result, genesys_result, graph_result
    )

    # Get specific Genesys data
    genesys_data = genesys_result.get("result")
    genesys_error = genesys_result.get("error")

    # Enhance with data warehouse
    search_results = {
        "azureAD": azure_ad_result,
        "azureAD_error": azure_ad_error,
        "azureAD_multiple": False,  # Force single result
        "genesys": genesys_data,
        "genesys_error": genesys_error,
        "genesys_multiple": False,  # Force single result
    }

    try:
        from app.services.search_enhancer import search_enhancer

        enhanced_results = search_enhancer.enhance_search_results(search_results)
    except Exception as e:
        logger.error(f"Error enhancing search results: {str(e)}")
        enhanced_results = search_results
        enhanced_results["keystone"] = None
        enhanced_results["keystone_error"] = f"Error loading Keystone data: {str(e)}"

    # Log audit
    _log_search_audit(
        search_term,
        user_email,
        user_role,
        user_ip,
        user_agent,
        ldap_result,
        graph_result,
        genesys_result,
        enhanced_results,
        False,
        False,
        genesys_user_id,
        ldap_user_dn,
        graph_user_id,
    )

    # Render results
    return _render_unified_profile(enhanced_results)
