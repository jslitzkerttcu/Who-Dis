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
import os
from typing import Optional, Dict, Any
import base64

logger = logging.getLogger(__name__)

search_bp = Blueprint("search", __name__)


# Configuration will be loaded lazily to avoid app context issues
_config_cache: Dict[str, Any] = {}


def get_search_timeout() -> int:
    """Get search timeout configuration lazily"""
    if "timeout" not in _config_cache:
        config_service: IConfigurationService = current_app.container.get("config")
        timeout_value = int(
            config_service.get(
                "search.overall_timeout", os.getenv("search_timeout", "20")
            )
        )
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
    azure_data = (
        results.get("azureAD", {}).get("results") if results.get("azureAD") else None
    )
    genesys_data = results.get("genesys")
    keystone_data = results.get("keystone")

    html = '<div class="grid md:grid-cols-2 gap-6">'

    # Azure AD Card
    if azure_data:
        html += _render_azure_ad_card(azure_data)

    # Genesys Card
    if genesys_data:
        html += _render_genesys_card(genesys_data)

    html += "</div>"

    # Keystone Card (full width)
    if keystone_data:
        html += _render_keystone_card(keystone_data)

    return html


def _render_azure_ad_card(user_data):
    """Render Azure AD user card."""
    # Extract user details
    display_name = user_data.get("displayName", "Unknown User")
    email = user_data.get("mail", "No email")
    job_title = user_data.get("jobTitle", "No title")
    department = user_data.get("department", "No department")
    manager = user_data.get("manager", "No manager")

    # Account status
    enabled = user_data.get("accountEnabled", True)
    locked = user_data.get("accountLocked", False)

    html = """
    <div class="bg-white rounded-lg shadow-md overflow-hidden">
        <div class="bg-ttcu-green text-white px-6 py-4">
            <h3 class="text-xl font-semibold flex items-center">
                <i class="fas fa-microsoft mr-3"></i>
                Azure AD / Office 365
            </h3>
        </div>
        <div class="p-6">
    """

    # User photo and basic info
    html += f"""
        <div class="flex items-start mb-6">
            <img src="/static/img/user-placeholder.svg" 
                 class="w-24 h-24 rounded-full bg-gray-200 mr-4"
                 alt="User photo">
            <div class="flex-1">
                <h4 class="text-xl font-semibold text-gray-900">{display_name}</h4>
                <p class="text-gray-600">{email}</p>
                <p class="text-sm text-gray-500">{job_title} - {department}</p>
    """

    # Status badges
    if enabled and not locked:
        html += '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800 mt-2">'
        html += '<i class="fas fa-check-circle mr-1"></i>Active</span>'
    else:
        html += '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800 mt-2">'
        html += '<i class="fas fa-times-circle mr-1"></i>'
        html += "Disabled" if not enabled else "Locked"
        html += "</span>"

    html += "</div></div>"

    # Additional details
    html += '<div class="space-y-3 text-sm">'
    html += f"<div><strong>Manager:</strong> {manager}</div>"

    # Phone numbers
    phones = []
    if user_data.get("telephoneNumber"):
        phones.append(f"{user_data['telephoneNumber']} (Office)")
    if user_data.get("mobile"):
        phones.append(f"{user_data['mobile']} (Mobile)")
    if phones:
        html += f"<div><strong>Phone:</strong> {', '.join(phones)}</div>"

    # Location
    if user_data.get("officeLocation"):
        html += f"<div><strong>Office:</strong> {user_data['officeLocation']}</div>"

    html += "</div>"

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
    """Render Genesys user card."""
    # Extract user details
    name = user_data.get("name", "Unknown User")
    email = user_data.get("email", "No email")
    username = user_data.get("username", "No username")
    division = user_data.get("division", {}).get("name", "No division")

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

    # Basic info
    html += f"""
        <div class="mb-6">
            <h4 class="text-xl font-semibold text-gray-900">{name}</h4>
            <p class="text-gray-600">{email}</p>
            <p class="text-sm text-gray-500">Username: {username}</p>
            <p class="text-sm text-gray-500">Division: {division}</p>
        </div>
    """

    # Skills
    skills = user_data.get("skills", [])
    if skills:
        html += '<div class="mb-4">'
        html += '<h5 class="text-sm font-medium text-gray-900 mb-2">Skills</h5>'
        html += '<div class="flex flex-wrap gap-2">'
        for skill in skills:
            html += f'<span class="px-2 py-1 text-xs bg-blue-100 text-blue-800 rounded-full">{skill["name"]}</span>'
        html += "</div></div>"

    # Queues
    queues = user_data.get("queues", [])
    if queues:
        html += '<div class="mb-4">'
        html += '<h5 class="text-sm font-medium text-gray-900 mb-2">Queues</h5>'
        html += '<div class="flex flex-wrap gap-2">'
        for queue in queues[:5]:  # Limit to first 5
            html += f'<span class="px-2 py-1 text-xs bg-green-100 text-green-800 rounded-full">{queue["name"]}</span>'
        if len(queues) > 5:
            html += f'<span class="px-2 py-1 text-xs bg-gray-100 text-gray-600 rounded-full">+{len(queues) - 5} more</span>'
        html += "</div></div>"

    # Groups
    groups = user_data.get("groups", [])
    if groups:
        html += "<div>"
        html += '<h5 class="text-sm font-medium text-gray-900 mb-2">Groups</h5>'
        html += '<div class="flex flex-wrap gap-2">'
        for group in groups[:3]:  # Limit to first 3
            html += f'<span class="px-2 py-1 text-xs bg-purple-100 text-purple-800 rounded-full">{group["name"]}</span>'
        if len(groups) > 3:
            html += f'<span class="px-2 py-1 text-xs bg-gray-100 text-gray-600 rounded-full">+{len(groups) - 3} more</span>'
        html += "</div></div>"

    html += "</div></div>"
    return html


def _render_keystone_card(keystone_data):
    """Render Keystone data card."""
    html = """
    <div class="bg-white rounded-lg shadow-md overflow-hidden mt-6">
        <div class="bg-gray-800 text-white px-6 py-4">
            <h3 class="text-xl font-semibold flex items-center">
                <i class="fas fa-database mr-3"></i>
                Keystone Data
            </h3>
        </div>
        <div class="p-6">
    """

    # Role information
    if keystone_data.get("role_mismatch"):
        html += """
        <div class="bg-yellow-50 border-l-4 border-yellow-400 p-4 mb-4">
            <div class="flex">
                <div class="flex-shrink-0">
                    <i class="fas fa-exclamation-triangle text-yellow-400"></i>
                </div>
                <div class="ml-3">
                    <p class="text-sm text-yellow-700">
                        Role mismatch detected between systems
                    </p>
                </div>
            </div>
        </div>
        """

    # Additional Keystone data would be rendered here
    html += '<p class="text-gray-600">Additional member data from Keystone system</p>'

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
    return f"""
    <div class="space-y-2">
        <p class="text-sm text-gray-500">No notes yet</p>
        <button hx-get="/search/notes/new?email={email}"
                hx-target="#noteModalContent"
                hx-swap="innerHTML"
                class="text-sm text-blue-600 hover:text-blue-800">
            <i class="fas fa-plus-circle mr-1"></i>Add Note
        </button>
    </div>
    """


def _render_notes_list(notes, email):
    """Render notes list."""
    html = '<div class="space-y-2">'

    for note in notes:
        html += _render_single_note(note, email)

    html += f"""
    <button hx-get="/search/notes/new?email={email}"
            hx-target="#noteModal"
            hx-swap="innerHTML"
            class="text-sm text-blue-600 hover:text-blue-800 mt-2">
        <i class="fas fa-plus-circle mr-1"></i>Add Note
    </button>
    </div>
    """

    return html


def _render_single_note(note, email):
    """Render a single note card."""
    # Format dates
    created_date = note.created_at.strftime("%m/%d/%Y") if note.created_at else ""
    updated_date = note.updated_at.strftime("%m/%d/%Y") if note.updated_at else ""

    date_info = f"Created {created_date} by {note.created_by or 'Unknown'}"
    if updated_date and updated_date != created_date:
        date_info += f" • Updated {updated_date}"

    return f'''
    <div class="bg-gray-50 p-3 rounded-md note-card" data-note-id="{note.id}">
        <div class="flex justify-between items-start">
            <div class="flex-1">
                <p class="text-sm text-gray-700 whitespace-pre-wrap">{note.note}</p>
                <p class="text-xs text-gray-500 mt-1">{date_info}</p>
            </div>
            <div class="ml-2 space-x-1">
                <button hx-get="/search/notes/{note.id}/edit"
                        hx-target=".note-card[data-note-id='{note.id}']"
                        hx-swap="outerHTML"
                        class="text-blue-600 hover:text-blue-800 text-sm">
                    <i class="fas fa-edit"></i>
                </button>
                <button hx-delete="/search/api/notes/{note.id}"
                        hx-confirm="Are you sure you want to delete this note?"
                        hx-target=".note-card[data-note-id='{note.id}']"
                        hx-swap="outerHTML"
                        class="text-red-600 hover:text-red-800 text-sm">
                    <i class="fas fa-trash"></i>
                </button>
            </div>
        </div>
    </div>
    '''


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
