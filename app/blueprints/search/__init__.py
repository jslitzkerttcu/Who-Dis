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
        enhanced_results['keystone'] = None
        enhanced_results['keystone_error'] = f'Error loading Keystone data: {str(e)}'
        enhanced_results['keystone_multiple'] = False

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
    keystone_result = enhanced_results.get('keystone')
    keystone_error = enhanced_results.get('keystone_error')
    
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
                "keystone_role_mismatch": keystone_result.get('role_mismatch') if keystone_result else False,
                "keystone_warning_level": keystone_result.get('role_warning_level') if keystone_result else None,
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
        return jsonify({"notes": []})

    # Get notes with search context
    notes = UserNote.get_user_notes(user.id, context="search")
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

    data = request.get_json()
    note_text = data.get("note", "").strip()

    if not note_text:
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
        return jsonify({"success": False, "message": "Note not found"}), 404

    data = request.get_json()
    note_text = data.get("note", "").strip()

    if not note_text:
        return jsonify({"success": False, "message": "Note cannot be empty"}), 400

    note.update_note(note_text)

    return jsonify({"success": True, "message": "Note updated successfully"})


@search_bp.route("/api/notes/<int:note_id>", methods=["DELETE"])
@require_role("viewer")
@handle_errors(json_response=True)
def delete_search_note(note_id):
    """Delete a search note."""
    from app.models.user_note import UserNote

    note = UserNote.query.filter_by(id=note_id, context="search").first()
    if not note:
        return jsonify({"success": False, "message": "Note not found"}), 404

    # Soft delete
    note.deactivate()

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


def _render_user_preview(email, azure_ad_result, genesys_data):
    """Render user preview HTML for Htmx."""
    ad_data = azure_ad_result.get("results") if azure_ad_result else None
    
    html = '<div class="bg-white rounded-lg shadow-lg p-6">'
    html += '<div class="flex justify-between items-start mb-4">'
    html += f'<h3 class="text-lg font-semibold text-gray-900">{email}</h3>'
    html += '<button onclick="this.closest(\'.htmx-preview\').innerHTML=\'\'" class="text-gray-400 hover:text-gray-500">'
    html += '<i class="fas fa-times"></i></button></div>'
    
    # Azure AD Section
    if ad_data:
        html += '<div class="mb-4">'
        html += '<h4 class="text-sm font-medium text-gray-700 mb-2 flex items-center">'
        html += '<span class="w-2 h-2 bg-ttcu-green rounded-full mr-2"></span>Azure AD</h4>'
        html += '<div class="text-sm text-gray-600 space-y-1">'
        html += f'<div><strong>Name:</strong> {ad_data.get("displayName", "N/A")}</div>'
        html += f'<div><strong>Title:</strong> {ad_data.get("jobTitle", "N/A")}</div>'
        html += f'<div><strong>Department:</strong> {ad_data.get("department", "N/A")}</div>'
        html += f'<div><strong>Manager:</strong> {ad_data.get("manager", "N/A")}</div>'
        
        # Phone numbers
        phones = []
        if ad_data.get("telephoneNumber"):
            phones.append(f'{ad_data["telephoneNumber"]} (Office)')
        if ad_data.get("mobile"):
            phones.append(f'{ad_data["mobile"]} (Mobile)')
        if phones:
            html += f'<div><strong>Phone:</strong> {", ".join(phones)}</div>'
        
        # Account status
        enabled = ad_data.get("accountEnabled", True)
        locked = ad_data.get("accountLocked", False)
        status_text = "Enabled" if enabled else "Disabled"
        if locked:
            status_text += " (Locked)"
        status_class = "text-green-600" if enabled and not locked else "text-red-600"
        html += f'<div><strong>Status:</strong> <span class="{status_class}">{status_text}</span></div>'
        
        html += '</div></div>'
    
    # Genesys Section
    if genesys_data:
        html += '<div class="mb-4">'
        html += '<h4 class="text-sm font-medium text-gray-700 mb-2 flex items-center">'
        html += '<span class="w-2 h-2 bg-genesys-orange rounded-full mr-2"></span>Genesys Cloud</h4>'
        html += '<div class="text-sm text-gray-600 space-y-1">'
        html += f'<div><strong>Username:</strong> {genesys_data.get("username", "N/A")}</div>'
        html += f'<div><strong>Division:</strong> {genesys_data.get("division", {}).get("name", "N/A")}</div>'
        
        # Skills
        skills = genesys_data.get("skills", [])
        if skills:
            skill_names = [s["name"] for s in skills[:3]]  # Show first 3
            if len(skills) > 3:
                skill_names.append(f"+{len(skills) - 3} more")
            html += f'<div><strong>Skills:</strong> {", ".join(skill_names)}</div>'
        
        # Queues
        queues = genesys_data.get("queues", [])
        if queues:
            queue_names = [q["name"] for q in queues[:3]]  # Show first 3
            if len(queues) > 3:
                queue_names.append(f"+{len(queues) - 3} more")
            html += f'<div><strong>Queues:</strong> {", ".join(queue_names)}</div>'
        
        html += '</div></div>'
    
    # Actions
    html += '<div class="flex justify-end space-x-2 pt-4 border-t">'
    html += f'<button onclick="document.getElementById(\'searchInput\').value=\'{email}\'; document.getElementById(\'searchForm\').dispatchEvent(new Event(\'submit\'))" '
    html += 'class="px-4 py-2 bg-ttcu-green text-white rounded-md hover:bg-green-700 text-sm">'
    html += '<i class="fas fa-search mr-1"></i>Full Details</button>'
    html += '</div>'
    
    html += '</div>'
    
    return html
