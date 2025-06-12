"""
Search orchestrator service for coordinating concurrent searches across multiple identity providers.

This service handles the complexity of running LDAP, Genesys, and Microsoft Graph searches
concurrently with proper timeout handling and error management.
"""

import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from typing import Optional, Dict, Any, Tuple
from flask import copy_current_request_context, current_app

from app.services.base import BaseConfigurableService
from app.utils.error_handler import handle_service_errors

logger = logging.getLogger(__name__)


class SearchOrchestrator(BaseConfigurableService):
    """Orchestrates concurrent searches across multiple identity providers."""

    def __init__(self):
        """Initialize the search orchestrator."""
        super().__init__("search")
        self._ldap_service = None
        self._genesys_service = None
        self._graph_service = None

    @property
    def ldap_service(self):
        """Get LDAP service from container."""
        if self._ldap_service is None:
            self._ldap_service = current_app.container.get("ldap_service")
        return self._ldap_service

    @property
    def genesys_service(self):
        """Get Genesys service from container."""
        if self._genesys_service is None:
            self._genesys_service = current_app.container.get("genesys_service")
        return self._genesys_service

    @property
    def graph_service(self):
        """Get Graph service from container."""
        if self._graph_service is None:
            self._graph_service = current_app.container.get("graph_service")
        return self._graph_service

    @property
    def overall_timeout(self) -> int:
        """Get overall search timeout in seconds."""
        return int(self._get_config("overall_timeout", "8"))

    @property
    def ldap_timeout(self) -> int:
        """Get LDAP-specific timeout in seconds."""
        return int(self._get_config("ldap_timeout", "3"))

    @property
    def genesys_timeout(self) -> int:
        """Get Genesys-specific timeout in seconds."""
        return int(self._get_config("genesys_timeout", "5"))

    @property
    def graph_timeout(self) -> int:
        """Get Graph API-specific timeout in seconds."""
        return int(self._get_config("graph_timeout", "4"))

    @property
    def lazy_load_photos(self) -> bool:
        """Get lazy load photos configuration."""
        lazy_load_config = self._get_config("lazy_load_photos", "true")
        if isinstance(lazy_load_config, bool):
            return lazy_load_config
        return str(lazy_load_config).lower() == "true"

    @handle_service_errors(raise_errors=False)
    def execute_concurrent_search(
        self,
        search_term: str,
        genesys_user_id: Optional[str] = None,
        ldap_user_dn: Optional[str] = None,
        graph_user_id: Optional[str] = None,
    ) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
        """
        Execute concurrent searches across LDAP, Genesys, and Microsoft Graph.

        Args:
            search_term: The search term to use
            genesys_user_id: Specific Genesys user ID (for multiple result selection)
            ldap_user_dn: Specific LDAP user DN (for multiple result selection)
            graph_user_id: Specific Graph user ID (for multiple result selection)

        Returns:
            Tuple of (ldap_result, genesys_result, graph_result) dictionaries
            Each result dict contains: result, error, multiple_results flag
        """
        logger.info(f"Starting concurrent search for: {search_term}")
        logger.info(
            f"Timeout: {self.overall_timeout}s, Lazy load photos: {self.lazy_load_photos}"
        )

        # Initialize result containers
        ldap_result = {"result": None, "error": None, "multiple": False}
        genesys_result = {"result": None, "error": None, "multiple": False}
        graph_result = {"result": None, "error": None, "multiple": False}

        include_photo = not self.lazy_load_photos

        # Use ThreadPoolExecutor for concurrent searches
        with ThreadPoolExecutor(max_workers=3) as executor:
            # Submit searches concurrently
            ldap_future = self._submit_ldap_search(executor, search_term, ldap_user_dn)
            genesys_future = self._submit_genesys_search(
                executor, search_term, genesys_user_id
            )
            graph_future = self._submit_graph_search(
                executor, search_term, graph_user_id, include_photo
            )

            # Process results with timeout handling
            ldap_result = self._process_ldap_result(
                ldap_future, search_term, ldap_user_dn
            )
            genesys_result = self._process_genesys_result(
                genesys_future, search_term, genesys_user_id
            )
            graph_result = self._process_graph_result(
                graph_future, search_term, graph_user_id
            )

        return ldap_result, genesys_result, graph_result

    def _submit_ldap_search(
        self, executor, search_term: str, ldap_user_dn: Optional[str]
    ):
        """Submit LDAP search to executor."""
        if ldap_user_dn:
            return executor.submit(
                copy_current_request_context(self.ldap_service.get_user_by_dn),
                ldap_user_dn,
            )
        else:
            return executor.submit(
                copy_current_request_context(self.ldap_service.search_user), search_term
            )

    def _submit_genesys_search(
        self, executor, search_term: str, genesys_user_id: Optional[str]
    ):
        """Submit Genesys search to executor."""
        if genesys_user_id:
            return executor.submit(
                copy_current_request_context(self.genesys_service.get_user_by_id),
                genesys_user_id,
            )
        else:
            return executor.submit(
                copy_current_request_context(self.genesys_service.search_user),
                search_term,
            )

    def _submit_graph_search(
        self,
        executor,
        search_term: str,
        graph_user_id: Optional[str],
        include_photo: bool,
    ):
        """Submit Graph search to executor."""
        if graph_user_id:
            return executor.submit(
                copy_current_request_context(self.graph_service.get_user_by_id),
                graph_user_id,
                include_photo,
            )
        else:
            return executor.submit(
                copy_current_request_context(self.graph_service.search_user),
                search_term,
                include_photo,
            )

    def _process_ldap_result(
        self, future, search_term: str, ldap_user_dn: Optional[str]
    ) -> Dict[str, Any]:
        """Process LDAP search result with error handling."""
        result: Dict[str, Any] = {"result": None, "error": None, "multiple": False}

        try:
            ldap_data = future.result(timeout=self.ldap_timeout)

            if ldap_user_dn and ldap_data:
                result["result"] = ldap_data
                logger.info(f"LDAP fetch for specific user DN: {ldap_user_dn}")
            elif ldap_data:
                if isinstance(ldap_data, dict) and ldap_data.get("multiple_results"):
                    result["multiple"] = True
                    result["result"] = ldap_data
                    logger.info(
                        f"LDAP search for '{search_term}' - Multiple results: {len(ldap_data.get('results', []))}"
                    )
                else:
                    result["result"] = ldap_data
                    logger.info(f"LDAP search for '{search_term}' - Found single user")
            else:
                logger.info(f"LDAP search for '{search_term}' - No results")

        except FutureTimeoutError:
            error_msg = f"LDAP search timed out after {self.ldap_timeout} seconds. Please try a more specific search term."
            logger.error(error_msg)
            result["error"] = error_msg
            future.cancel()
        except TimeoutError as e:
            logger.error(f"LDAP timeout: {str(e)}")
            result["error"] = str(e)
        except Exception as e:
            logger.error(f"LDAP search error: {str(e)}")
            result["error"] = "LDAP search encountered an error"

        return result

    def _process_genesys_result(
        self, future, search_term: str, genesys_user_id: Optional[str]
    ) -> Dict[str, Any]:
        """Process Genesys search result with error handling."""
        result: Dict[str, Any] = {"result": None, "error": None, "multiple": False}

        try:
            genesys_data = future.result(timeout=self.genesys_timeout)

            if genesys_user_id and genesys_data:
                result["result"] = genesys_data
                logger.info(f"Genesys fetch for specific user ID: {genesys_user_id}")
            elif genesys_data:
                if isinstance(genesys_data, dict):
                    if genesys_data.get("error") == "too_many_results":
                        result["error"] = genesys_data.get("message")
                        logger.info(
                            f"Genesys search for '{search_term}' - Too many results: {genesys_data.get('total')}"
                        )
                    elif genesys_data.get("multiple_results"):
                        result["multiple"] = True
                        result["result"] = genesys_data
                        logger.info(
                            f"Genesys search for '{search_term}' - Multiple results: {len(genesys_data.get('results', []))}"
                        )
                    else:
                        result["result"] = genesys_data
                        logger.info(
                            f"Genesys search for '{search_term}' - Found single user"
                        )
                else:
                    result["result"] = genesys_data
            else:
                logger.info(f"Genesys search for '{search_term}' - No results")

        except FutureTimeoutError:
            error_msg = f"Genesys search timed out after {self.genesys_timeout} seconds. Please try a more specific search term."
            logger.error(error_msg)
            result["error"] = error_msg
            future.cancel()
        except TimeoutError as e:
            logger.error(f"Genesys timeout: {str(e)}")
            result["error"] = str(e)
        except Exception as e:
            logger.error(f"Genesys search error: {str(e)}")
            result["error"] = "Genesys search encountered an error"

        return result

    def _process_graph_result(
        self, future, search_term: str, graph_user_id: Optional[str]
    ) -> Dict[str, Any]:
        """Process Graph search result with error handling."""
        result: Dict[str, Any] = {"result": None, "error": None, "multiple": False}

        try:
            graph_data = future.result(timeout=self.graph_timeout)

            if graph_user_id and graph_data:
                result["result"] = graph_data
                logger.info(f"Graph API fetch for specific user ID: {graph_user_id}")
            elif graph_data:
                if isinstance(graph_data, dict) and graph_data.get("multiple_results"):
                    result["multiple"] = True
                    result["result"] = graph_data
                    logger.info(
                        f"Graph API search for '{search_term}' - Multiple results: {len(graph_data.get('results', []))}"
                    )
                else:
                    result["result"] = graph_data
                    logger.info(
                        f"Graph API search for '{search_term}' - Found single user"
                    )
            else:
                logger.info(f"Graph API search for '{search_term}' - No results")

        except FutureTimeoutError:
            error_msg = f"Microsoft Graph search timed out after {self.graph_timeout} seconds. Please try a more specific search term."
            logger.error(error_msg)
            result["error"] = error_msg
            future.cancel()
        except TimeoutError as e:
            logger.error(f"Graph API timeout: {str(e)}")
            result["error"] = str(e)
        except Exception as e:
            logger.error(f"Graph API search error: {str(e)}")
            result["error"] = "Microsoft Graph search encountered an error"

        return result

    def all_searches_timed_out(
        self,
        ldap_result: Dict[str, Any],
        genesys_result: Dict[str, Any],
        graph_result: Dict[str, Any],
    ) -> bool:
        """Check if all searches timed out."""
        ldap_error = ldap_result.get("error")
        genesys_error = genesys_result.get("error")
        graph_error = graph_result.get("error")

        return (
            bool(ldap_error)
            and bool(genesys_error)
            and bool(graph_error)
            and "timed out" in str(ldap_error)
            and "timed out" in str(genesys_error)
            and "timed out" in str(graph_error)
        )
