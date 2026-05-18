"""REST API search endpoint.

Provides GET /api/v1/search with paginated JSON envelope results,
per-token rate limiting, and audit logging.
"""

import logging
import os
from typing import Any, Dict, List

from flask import g
from flask.views import MethodView
from flask_limiter.util import get_remote_address
from flask_smorest import Blueprint

from app import limiter
from app.blueprints.api.auth import require_api_token
from app.blueprints.api.schemas import SearchQuerySchema, SearchResponseSchema

logger = logging.getLogger(__name__)

# D-08/D-09: rate limit threshold from env var (config_get removed in Phase 9)
API_RATE_LIMIT = os.environ.get("API_RATE_LIMIT", "60/minute")

api_search_bp = Blueprint(
    "api_v1_search",
    __name__,
    description="Search across all identity providers",
)


def _api_token_rate_key() -> str:
    """Per-token rate limiting key.

    Returns a token-specific key when g.api_token is available (set by
    require_api_token decorator), falls back to remote IP address for
    unauthenticated requests per D-08.
    """
    api_token = getattr(g, "api_token", None)
    if api_token is not None:
        return f"api_token:{api_token.id}"
    return get_remote_address()


@api_search_bp.route("/search")
class SearchResource(MethodView):
    """Search across LDAP, Genesys Cloud, and Microsoft Graph."""

    @api_search_bp.arguments(SearchQuerySchema, location="query")
    @api_search_bp.response(200, SearchResponseSchema)
    @require_api_token
    @limiter.limit(lambda: API_RATE_LIMIT, key_func=_api_token_rate_key)
    def get(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a search and return paginated results.

        Args:
            args: Validated query parameters (q, page, page_size).

        Returns:
            D-04 envelope with search results, pagination metadata.
        """
        q = args["q"]
        page = args.get("page", 1)
        page_size = args.get("page_size", 25)

        # Use existing services via DI-compatible instantiation
        from app.services.search_orchestrator import SearchOrchestrator
        from app.services.result_merger import ResultMerger

        orchestrator = SearchOrchestrator()
        merger = ResultMerger()

        # Execute concurrent search across all providers
        ldap_result, genesys_result, graph_result = (
            orchestrator.execute_concurrent_search(q)
        )

        # Merge Azure AD (LDAP + Graph) results
        azure_ad_result, azure_ad_error, azure_ad_multiple = (
            merger.merge_azure_ad_results(ldap_result, genesys_result, graph_result)
        )

        # Collect all results into a list
        results: List[Dict[str, Any]] = []

        if azure_ad_result is not None:
            if azure_ad_multiple and isinstance(azure_ad_result, dict):
                # Multiple results are nested under "multiple_results" key
                multiple_items = azure_ad_result.get("multiple_results", [])
                if multiple_items:
                    results.extend(multiple_items)
                else:
                    results.append(azure_ad_result)
            else:
                results.append(azure_ad_result)

        # Include Genesys results if separate from Azure AD merge
        genesys_data = genesys_result.get("result") if isinstance(genesys_result, dict) else None
        genesys_multiple = genesys_result.get("multiple", False)
        if genesys_data is not None:
            if genesys_multiple and isinstance(genesys_data, dict):
                multiple_items = genesys_data.get("multiple_results", [])
                if multiple_items:
                    results.extend(multiple_items)
                else:
                    results.append(genesys_data)
            elif genesys_data and not azure_ad_result:
                # Only add standalone Genesys if not already merged
                results.append(genesys_data)

        total = len(results)

        # Apply pagination
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_results = results[start_idx:end_idx]

        # Audit the search (API-04: every call audited with token context)
        try:
            from flask import current_app

            audit_service = current_app.container.get("audit_service")
            audit_service.log_search(
                user_email=g.user,
                search_query=q,
                results_count=total,
                services=["ldap", "genesys", "graph"],
            )
        except Exception as e:
            logger.error(f"Failed to audit API search: {e}", exc_info=True)

        return {
            "data": paginated_results,
            "meta": {
                "page": page,
                "page_size": page_size,
                "total": total,
            },
            "errors": None,
        }
