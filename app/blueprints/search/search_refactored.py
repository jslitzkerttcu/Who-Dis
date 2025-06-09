"""Example of refactored search blueprint using dependency injection."""

from flask import (
    Blueprint,
    render_template,
    request,
    jsonify,
    make_response,
    current_app,
    g,
)
from app.middleware.auth import require_role
from app.utils.error_handler import handle_errors
from app.interfaces.search_service import ISearchService
import logging
import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
import base64

logger = logging.getLogger(__name__)

search_bp = Blueprint("search", __name__)


def get_search_timeout():
    """Get search timeout configuration from container."""
    config = current_app.container.get("config")
    return int(config.get("search.overall_timeout", os.getenv("search_timeout", "20")))


def get_lazy_load_photos():
    """Get lazy load photos configuration from container."""
    config = current_app.container.get("config")
    lazy_load_config = config.get("search.lazy_load_photos", "true")
    if isinstance(lazy_load_config, bool):
        return lazy_load_config
    return str(lazy_load_config).lower() == "true"


def merge_ldap_graph_data(ldap_data, graph_data, include_photo=True):
    """
    Merge LDAP and Graph data into a single Azure AD result.
    Graph data takes priority in case of conflicts.
    """
    if not ldap_data and not graph_data:
        return None

    # Implementation remains the same
    # ... (omitted for brevity)


@search_bp.route("/")
@require_role("viewer")
@handle_errors()
def index():
    """Render the main search page."""
    lazy_load_photos = get_lazy_load_photos()
    return render_template("search/index.html", lazy_load_photos=lazy_load_photos)


@search_bp.route("/user", methods=["POST"])
@require_role("viewer")
@handle_errors(json_response=True)
def search_user():
    """Search for users across all configured services using dependency injection."""
    # Get search term
    search_term = request.json.get("search_term", "").strip()
    if not search_term:
        return jsonify({"error": "Search term is required"}), 400

    # Get services from container
    search_services = current_app.container.get_all_by_interface(ISearchService)
    audit_logger = current_app.container.get("audit_logger")

    # Create a mapping of service names to services
    services_map = {service.service_name: service for service in search_services}

    # Group services by type for organized searching
    ldap_service = services_map.get("ldap")
    graph_service = services_map.get("graph")
    genesys_service = services_map.get("genesys")

    logger.info(f"User search request for term: {search_term}")

    results = {
        "ldap": None,
        "graph": None,
        "genesys": None,
        "azure_ad": None,  # Combined LDAP + Graph
        "search_term": search_term,
    }

    # Track which services were actually used
    services_used = []

    # Search concurrently with timeout
    timeout = get_search_timeout()

    def search_azure_ad():
        """Search both LDAP and Graph, then merge results."""
        ldap_result = None
        graph_result = None

        # Search LDAP
        if ldap_service:
            try:
                ldap_result = ldap_service.search_user(search_term)
                if ldap_result:
                    services_used.append("ldap")
            except Exception as e:
                logger.error(f"LDAP search error: {str(e)}")

        # Search Graph
        if graph_service:
            try:
                graph_result = graph_service.search_user(search_term)
                if graph_result:
                    services_used.append("graph")
            except Exception as e:
                logger.error(f"Graph search error: {str(e)}")

        # Merge results
        lazy_load = get_lazy_load_photos()
        include_photo = not lazy_load
        merged = merge_ldap_graph_data(ldap_result, graph_result, include_photo)

        results["ldap"] = ldap_result
        results["graph"] = graph_result
        results["azure_ad"] = merged

    def search_genesys():
        """Search Genesys service."""
        if not genesys_service:
            return

        try:
            result = genesys_service.search_user(search_term)
            if result:
                services_used.append("genesys")
                results["genesys"] = result
        except Exception as e:
            logger.error(f"Genesys search error: {str(e)}")

    # Execute searches concurrently
    with ThreadPoolExecutor(max_workers=2) as executor:
        azure_future = executor.submit(search_azure_ad)
        genesys_future = executor.submit(search_genesys)

        # Wait for completion with timeout
        try:
            azure_future.result(timeout=timeout)
        except FutureTimeoutError:
            logger.warning(f"Azure AD search timed out after {timeout} seconds")
        except Exception as e:
            logger.error(f"Azure AD search error: {str(e)}")

        try:
            genesys_future.result(timeout=timeout)
        except FutureTimeoutError:
            logger.warning(f"Genesys search timed out after {timeout} seconds")
        except Exception as e:
            logger.error(f"Genesys search error: {str(e)}")

    # Log the search using injected audit logger
    total_results = sum(1 for r in [results["azure_ad"], results["genesys"]] if r)

    # Log search event
    audit_logger.log_search(
        user_email=g.user,
        search_query=search_term,
        results_count=total_results,
        services=services_used,
        ip_address=request.remote_addr,
        user_agent=request.headers.get("User-Agent", "Unknown"),
    )

    return jsonify(results)


@search_bp.route("/photo/<user_id>")
@require_role("viewer")
def get_user_photo(user_id):
    """Get user photo using injected Graph service."""
    try:
        # Get services from container
        graph_service = None
        search_services = current_app.container.get_all_by_interface(ISearchService)

        for service in search_services:
            if service.service_name == "graph":
                graph_service = service
                break

        if not graph_service:
            raise ValueError("Graph service not available")

        # Try to get UPN from request args
        user_principal_name = request.args.get("upn")

        # Get photo from Graph service
        photo_url = graph_service.get_user_photo(user_id, user_principal_name)

        if photo_url and photo_url.startswith("data:"):
            # Extract base64 data
            parts = photo_url.split(",", 1)
            if len(parts) == 2:
                mime_type = parts[0].split(";")[0].replace("data:", "")
                photo_data = base64.b64decode(parts[1])

                response = make_response(photo_data)
                response.headers["Content-Type"] = mime_type
                response.headers["Cache-Control"] = "private, max-age=3600"
                return response

        # Return transparent pixel if no photo
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
