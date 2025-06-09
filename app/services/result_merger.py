"""
Result merger service for combining and matching search results from multiple identity providers.

This service handles the complex logic of merging LDAP and Microsoft Graph data,
smart matching across services, and resolving multiple results scenarios.
"""

import logging
from typing import Optional, Dict, Any, List, Tuple
from flask import copy_current_request_context, current_app

from app.services.base import BaseConfigurableService

logger = logging.getLogger(__name__)


class ResultMerger(BaseConfigurableService):
    """Handles merging and smart matching of search results across identity providers."""

    def __init__(self):
        """Initialize the result merger."""
        super().__init__("search")

    @property
    def lazy_load_photos(self) -> bool:
        """Get lazy load photos configuration."""
        lazy_load_config = self._get_config("lazy_load_photos", "true")
        if isinstance(lazy_load_config, bool):
            return lazy_load_config
        return str(lazy_load_config).lower() == "true"

    def merge_ldap_graph_data(
        self,
        ldap_data: Optional[Dict[str, Any]],
        graph_data: Optional[Dict[str, Any]],
        include_photo: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """
        Merge LDAP and Graph data into a single Azure AD result.
        Graph data takes priority in case of conflicts.

        Args:
            ldap_data: LDAP user data
            graph_data: Microsoft Graph user data
            include_photo: Whether to include photo data

        Returns:
            Merged user data or None if both inputs are None
        """
        if not ldap_data and not graph_data:
            return None

        # Start with LDAP data as base
        merged = ldap_data.copy() if ldap_data else {}

        # Debug logging for password fields
        if ldap_data and "pwdLastSet" in ldap_data:
            logger.info(f"LDAP data contains pwdLastSet: {ldap_data['pwdLastSet']}")
        if ldap_data and "pwdExpires" in ldap_data:
            logger.info(f"LDAP data contains pwdExpires: {ldap_data['pwdExpires']}")

        # Remove LDAP thumbnail photo - we only want Graph photos
        if "thumbnailPhoto" in merged:
            logger.info("Removing LDAP thumbnail photo from merged data")
            del merged["thumbnailPhoto"]

        if graph_data:
            merged = self._merge_graph_data_into_ldap(merged, graph_data, include_photo)

        # Mark the data source
        merged["dataSource"] = "azureAD"

        # Debug logging for phone numbers
        if merged.get("phoneNumbers"):
            logger.info(f"Merged Azure AD phone numbers: {merged['phoneNumbers']}")

        return merged

    def _merge_graph_data_into_ldap(
        self, merged: Dict[str, Any], graph_data: Dict[str, Any], include_photo: bool
    ) -> Dict[str, Any]:
        """Merge Graph API data into the base LDAP data."""
        # Basic info (Graph takes priority)
        self._merge_basic_info(merged, graph_data)

        # Job and organization info
        self._merge_job_info(merged, graph_data)

        # Phone numbers - merge both sources
        self._merge_phone_numbers(merged, graph_data)

        # Account status from Graph
        if "accountEnabled" in graph_data:
            merged["enabled"] = graph_data["accountEnabled"]

        # Profile photo handling
        self._merge_photo_data(merged, graph_data, include_photo)

        # Additional Graph-only fields
        self._merge_additional_graph_fields(merged, graph_data)

        # Mark as having Graph data
        merged["hasGraphData"] = True

        return merged

    def _merge_basic_info(
        self, merged: Dict[str, Any], graph_data: Dict[str, Any]
    ) -> None:
        """Merge basic user information from Graph."""
        basic_fields = {
            "displayName": "displayName",
            "mail": "mail",
            "userPrincipalName": "userPrincipalName",
            "givenName": "givenName",
            "surname": "surname",
            "employeeId": "employeeID",  # Note the different case
        }

        for graph_field, merged_field in basic_fields.items():
            if graph_data.get(graph_field):
                merged[merged_field] = graph_data[graph_field]

    def _merge_job_info(
        self, merged: Dict[str, Any], graph_data: Dict[str, Any]
    ) -> None:
        """Merge job and organization information from Graph."""
        job_fields = {
            "jobTitle": "title",
            "department": "department",
            "officeLocation": "officeLocation",
            "companyName": "companyName",
            "employeeType": "employeeType",
        }

        for graph_field, merged_field in job_fields.items():
            if graph_data.get(graph_field):
                merged[merged_field] = graph_data[graph_field]

        # Manager info from Graph
        if graph_data.get("manager"):
            merged["manager"] = graph_data["manager"]
            merged["managerEmail"] = graph_data.get("managerEmail")

    def _merge_phone_numbers(
        self, merged: Dict[str, Any], graph_data: Dict[str, Any]
    ) -> None:
        """Merge phone numbers from both LDAP and Graph sources."""
        phone_numbers = merged.get("phoneNumbers", {})

        if graph_data.get("phoneNumbers"):
            for phone_type, number in graph_data["phoneNumbers"].items():
                # Map Graph phone types to our standard types
                if phone_type == "mobile":
                    phone_numbers["mobile"] = number
                elif phone_type.startswith("business"):
                    phone_numbers["business"] = number
                else:
                    phone_numbers[phone_type] = number

        merged["phoneNumbers"] = phone_numbers

    def _merge_photo_data(
        self, merged: Dict[str, Any], graph_data: Dict[str, Any], include_photo: bool
    ) -> None:
        """Merge profile photo data from Graph."""
        if include_photo and graph_data.get("photo"):
            logger.info("Setting thumbnailPhoto from Graph photo data")
            merged["thumbnailPhoto"] = graph_data["photo"]
        elif not include_photo and graph_data.get("hasPhoto"):
            # Photo exists but wasn't fetched (lazy loading)
            logger.info("Photo exists but not loaded (lazy loading enabled)")
            merged["hasPhotoCached"] = True
        else:
            logger.info("No photo data from Graph")

        # Always include Graph ID for photo lookups (for lazy loading)
        if graph_data.get("id"):
            merged["graphId"] = graph_data["id"]

    def _merge_additional_graph_fields(
        self, merged: Dict[str, Any], graph_data: Dict[str, Any]
    ) -> None:
        """Merge additional Graph-only fields if they exist."""
        additional_fields = [
            "address",
            "lastPasswordChangeDateTime",
            "createdDateTime",
            "employeeHireDate",
            "refreshTokensValidFromDateTime",
            "signInSessionsValidFromDateTime",
            "onPremisesLastSyncDateTime",
            "passwordPolicies",
            "dateOfBirth",
        ]

        for field in additional_fields:
            if graph_data.get(field):
                merged[field] = graph_data[field]

    def smart_match_services(
        self,
        azure_ad_result: Optional[Dict[str, Any]],
        azure_ad_multiple: bool,
        genesys_result: Optional[Dict[str, Any]],
        genesys_multiple: bool,
    ) -> Tuple[Optional[Dict[str, Any]], bool]:
        """
        Smart match Azure AD and Genesys results when one is single and other is multiple.

        Args:
            azure_ad_result: Azure AD search result
            azure_ad_multiple: Whether Azure AD returned multiple results
            genesys_result: Genesys search result
            genesys_multiple: Whether Genesys returned multiple results

        Returns:
            Tuple of (updated_genesys_result, updated_genesys_multiple)
        """
        # Smart matching: If we have single AD result and multiple Genesys results, try to match by email
        if (
            azure_ad_result
            and not azure_ad_multiple
            and genesys_multiple
            and genesys_result
            and genesys_result.get("results")
        ):
            return self._match_azure_ad_to_genesys(azure_ad_result, genesys_result)

        return genesys_result, genesys_multiple

    def _match_azure_ad_to_genesys(
        self, azure_ad_result: Dict[str, Any], genesys_result: Dict[str, Any]
    ) -> Tuple[Optional[Dict[str, Any]], bool]:
        """Match single Azure AD result to multiple Genesys results by email."""
        ad_email = azure_ad_result.get("mail")

        if not ad_email:
            return genesys_result, True

        logger.info(
            f"Smart matching: Single AD result with email {ad_email}, "
            f"checking {len(genesys_result['results'])} Genesys results"
        )

        # Look for a matching Genesys user by email or username
        matched_user = self._find_matching_genesys_user(
            ad_email, genesys_result["results"]
        )

        if matched_user and matched_user.get("id"):
            return self._fetch_full_genesys_user(matched_user)

        return genesys_result, True

    def _find_matching_genesys_user(
        self, ad_email: str, genesys_users: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Find a Genesys user that matches the Azure AD email."""
        for g_user in genesys_users:
            g_email = g_user.get("email", "").lower()
            g_username = g_user.get("username", "").lower()

            # Check if AD email matches Genesys email or username
            if g_email == ad_email.lower() or g_username == ad_email.lower():
                logger.info(
                    f"Smart match found: Genesys user {g_user.get('name')} "
                    f"(email: {g_email}, username: {g_username}) matches AD email {ad_email}"
                )
                return g_user

        return None

    def _fetch_full_genesys_user(
        self, matched_user: Dict[str, Any]
    ) -> Tuple[Optional[Dict[str, Any]], bool]:
        """Fetch full Genesys user details for a matched user."""
        try:
            genesys_service = current_app.container.get("genesys_service")
            full_genesys_user = copy_current_request_context(
                genesys_service.get_user_by_id
            )(matched_user["id"])

            if full_genesys_user:
                logger.info(
                    f"Smart match successful: Retrieved full Genesys user details "
                    f"for {matched_user.get('name')}"
                )
                return full_genesys_user, False

        except Exception as e:
            logger.error(f"Error retrieving matched Genesys user: {str(e)}")

        return None, True

    def merge_azure_ad_results(
        self,
        ldap_result: Dict[str, Any],
        genesys_result: Dict[str, Any],
        graph_result: Dict[str, Any],
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str], bool]:
        """
        Merge LDAP and Graph results into Azure AD result with smart matching.

        Args:
            ldap_result: LDAP search result dict with result/error/multiple keys
            genesys_result: Genesys search result dict
            graph_result: Graph search result dict

        Returns:
            Tuple of (azure_ad_result, azure_ad_error, azure_ad_multiple)
        """
        ldap_data = ldap_result.get("result")
        ldap_error = ldap_result.get("error")
        ldap_multiple = ldap_result.get("multiple", False)

        graph_data = graph_result.get("result")
        graph_error = graph_result.get("error")
        graph_multiple = graph_result.get("multiple", False)

        include_photo = not self.lazy_load_photos

        azure_ad_result = None
        azure_ad_error = None
        azure_ad_multiple = False

        # Handle single results - merge them (only when BOTH are single results)
        if (ldap_data and not ldap_multiple) and (graph_data and not graph_multiple):
            azure_ad_result = self.merge_ldap_graph_data(
                ldap_data, graph_data, include_photo
            )

        # Handle multiple results scenarios
        elif ldap_multiple or graph_multiple:
            azure_ad_result, azure_ad_multiple = self._handle_multiple_results(
                ldap_data, ldap_multiple, graph_data, graph_multiple, include_photo
            )

        # Handle case where we have only one source
        else:
            azure_ad_result = self._handle_single_source(
                ldap_data, graph_data, include_photo
            )

        # Combine errors
        azure_ad_error = self._combine_errors(ldap_error, graph_error)

        return azure_ad_result, azure_ad_error, azure_ad_multiple

    def _handle_multiple_results(
        self,
        ldap_data: Optional[Dict[str, Any]],
        ldap_multiple: bool,
        graph_data: Optional[Dict[str, Any]],
        graph_multiple: bool,
        include_photo: bool,
    ) -> Tuple[Optional[Dict[str, Any]], bool]:
        """Handle scenarios where one or both services returned multiple results."""
        logger.info(
            f"Handling multiple results - LDAP multiple: {ldap_multiple}, Graph multiple: {graph_multiple}"
        )

        # Smart matching: Single LDAP + Multiple Graph results
        if (
            ldap_data
            and not ldap_multiple
            and graph_multiple
            and graph_data
            and graph_data.get("results")
        ):
            return self._smart_match_ldap_to_graph(ldap_data, graph_data, include_photo)

        # Smart matching: Multiple LDAP + Single Graph result
        elif (
            ldap_multiple
            and ldap_data
            and ldap_data.get("results")
            and graph_data
            and not graph_multiple
        ):
            return self._smart_match_graph_to_ldap(ldap_data, graph_data, include_photo)

        # Both have multiple results
        elif ldap_multiple and graph_multiple:
            return self._combine_multiple_results(ldap_data, graph_data), True

        # Only one has multiple results
        elif ldap_multiple:
            return ldap_data, True
        else:  # graph_multiple only
            return graph_data, True

    def _smart_match_ldap_to_graph(
        self,
        ldap_data: Dict[str, Any],
        graph_data: Dict[str, Any],
        include_photo: bool,
    ) -> Tuple[Optional[Dict[str, Any]], bool]:
        """Smart match single LDAP result to multiple Graph results."""
        logger.info("Smart matching: Single LDAP + Multiple Graph results")

        ldap_email = ldap_data.get("mail")
        if not ldap_email:
            return graph_data, True

        # Find matching Graph user
        matched_graph = self._find_matching_graph_user(
            ldap_email, graph_data["results"]
        )

        if matched_graph:
            # Get full Graph details for the matched user
            full_graph_user = self._fetch_full_graph_user(matched_graph, include_photo)
            if full_graph_user:
                merged_result = self.merge_ldap_graph_data(
                    ldap_data, full_graph_user, include_photo
                )
                logger.info(
                    f"Smart match: Found Graph user {matched_graph.get('displayName')} matching LDAP email {ldap_email}"
                )
                return merged_result, False
            else:
                # Fallback to merging with basic data
                return self.merge_ldap_graph_data(
                    ldap_data, matched_graph, include_photo
                ), False

        # No match found, show multiple results
        return graph_data, True

    def _smart_match_graph_to_ldap(
        self,
        ldap_data: Dict[str, Any],
        graph_data: Dict[str, Any],
        include_photo: bool,
    ) -> Tuple[Optional[Dict[str, Any]], bool]:
        """Smart match single Graph result to multiple LDAP results."""
        graph_email = graph_data.get("mail")
        if not graph_email:
            return ldap_data, True

        # Find matching LDAP user
        matched_ldap = None
        for l_user in ldap_data["results"]:
            if l_user.get("mail", "").lower() == graph_email.lower():
                matched_ldap = l_user
                break

        if matched_ldap:
            merged_result = self.merge_ldap_graph_data(
                matched_ldap, graph_data, include_photo
            )
            logger.info(
                f"Smart match: Found LDAP user {matched_ldap.get('displayName')} matching Graph email {graph_email}"
            )
            return merged_result, False

        # No match found, show multiple results
        return ldap_data, True

    def _find_matching_graph_user(
        self, ldap_email: str, graph_users: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Find a Graph user that matches the LDAP email."""
        for g_user in graph_users:
            if g_user.get("mail", "").lower() == ldap_email.lower():
                return g_user
        return None

    def _fetch_full_graph_user(
        self, matched_graph: Dict[str, Any], include_photo: bool
    ) -> Optional[Dict[str, Any]]:
        """Fetch full Graph user details."""
        graph_user_id = matched_graph.get("id")
        if not graph_user_id:
            return None

        try:
            graph_service = current_app.container.get("graph_service")
            logger.info(f"Fetching full Graph details for user ID: {graph_user_id}")

            full_graph_user = copy_current_request_context(
                graph_service.get_user_by_id
            )(graph_user_id, include_photo)

            if full_graph_user and isinstance(full_graph_user, dict):
                logger.info(
                    f"Full Graph user data fields: {list(full_graph_user.keys())}"
                )
                # Type assertion since we verified it's a dict above
                return full_graph_user  # type: ignore[no-any-return]

        except Exception as e:
            logger.warning(
                f"Failed to fetch full Graph user details for ID: {graph_user_id}: {str(e)}"
            )

        return None

    def _combine_multiple_results(
        self, ldap_data: Optional[Dict[str, Any]], graph_data: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Combine multiple results from both LDAP and Graph."""
        return {
            "multiple_results": True,
            "ldap_results": ldap_data.get("results", []) if ldap_data else [],
            "graph_results": graph_data.get("results", []) if graph_data else [],
            "total": (ldap_data.get("total", 0) if ldap_data else 0)
            + (graph_data.get("total", 0) if graph_data else 0),
        }

    def _handle_single_source(
        self,
        ldap_data: Optional[Dict[str, Any]],
        graph_data: Optional[Dict[str, Any]],
        include_photo: bool,
    ) -> Optional[Dict[str, Any]]:
        """Handle case where only one source has results."""
        if ldap_data and not graph_data:
            return self.merge_ldap_graph_data(ldap_data, None, include_photo)
        elif graph_data and not ldap_data:
            return self.merge_ldap_graph_data(None, graph_data, include_photo)
        return None

    def _combine_errors(
        self, ldap_error: Optional[str], graph_error: Optional[str]
    ) -> Optional[str]:
        """Combine error messages from LDAP and Graph searches."""
        if ldap_error and graph_error:
            return (
                "Both Active Directory and Microsoft Graph searches encountered errors"
            )
        elif ldap_error:
            return ldap_error
        elif graph_error:
            return graph_error
        return None
