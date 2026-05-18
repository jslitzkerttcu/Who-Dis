"""Microsoft Graph service with simplified configuration."""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, Dict, Any, List
from msal import ConfidentialClientApplication  # type: ignore[import-untyped]
import base64
import requests
from app.services.base import BaseAPITokenService

from app.interfaces.search_service import ISearchService
from app.interfaces.token_service import ITokenService

logger = logging.getLogger(__name__)

# Module-level dedupe set for missing-permission ERROR logs (D-06).
# Each Graph permission string is logged exactly once per process startup
# so operators see a clear signal in stdout JSON without log spam on every call.
_logged_missing_perms: set = set()


class GraphService(BaseAPITokenService, ISearchService, ITokenService):
    def __init__(self):
        super().__init__(config_prefix="graph", token_service_name="microsoft_graph")
        self.scope = ["https://graph.microsoft.com/.default"]
        self.graph_base_url = "https://graph.microsoft.com/beta"
        self.app = None

    def _load_config(self):
        """Load Graph-specific configuration."""
        super()._load_config()

        # Get configuration values
        client_id = self._get_config("client_id")
        client_secret = self._get_config("client_secret")
        tenant_id = self._get_config("tenant_id")

        # Initialize MSAL app if we have credentials
        if client_id and client_secret and tenant_id:
            authority = f"https://login.microsoftonline.com/{tenant_id}"
            self.app = ConfidentialClientApplication(
                client_id,
                authority=authority,
                client_credential=client_secret,
            )
            logger.debug("Microsoft Graph service initialized")
        else:
            logger.warning("Microsoft Graph API credentials not configured")
            self.app = None

    @property
    def service_name(self) -> str:
        """Get the name of this search service."""
        return "graph"

    @property
    def token_service_name(self) -> str:
        """Get the name used for token storage/identification."""
        return "microsoft_graph"

    def _fetch_new_token(self) -> Optional[str]:
        """Fetch new token from Microsoft Graph using MSAL."""
        self._load_config()
        if not self.app:
            return None

        try:
            # Get new token using MSAL
            result = self.app.acquire_token_silent(self.scope, account=None)
            if not result:
                result = self.app.acquire_token_for_client(scopes=self.scope)

            if "access_token" in result:
                access_token = result["access_token"]
                expires_in = result.get("expires_in", 3600)

                # Store token using base class method
                self._store_token(access_token, expires_in)
                return str(access_token)
            else:
                logger.error(
                    f"Failed to acquire Graph token: {result.get('error_description', 'Unknown error')}"
                )
                return None

        except Exception as e:
            logger.error(f"Error getting Graph API access token: {str(e)}")
            return None

    def test_connection(self) -> bool:
        """Test connection to Graph API with fresh token (no cache)."""
        # Clear cache to force reload of configuration
        self._clear_config_cache()

        # Check if credentials are configured
        client_id = self._get_config("client_id")
        client_secret = self._get_config("client_secret")
        tenant_id = self._get_config("tenant_id")

        if not client_id or not client_secret or not tenant_id:
            logger.error("Graph API credentials not configured")
            return False

        try:
            # Reload configuration
            self._load_config()
            if not self.app:
                return False

            # Get fresh token (bypasses cache)
            token = self._fetch_new_token()
            if not token:
                logger.error("Failed to obtain Graph API token")
                return False

            # Test the token with a simple API call using base class method
            test_url = f"{self.graph_base_url}/organization"
            response = self._make_request("GET", test_url, token, timeout=5)

            if response.status_code == 200:
                logger.debug("Graph API connection test successful")
                return True
            else:
                logger.error(
                    f"Graph API test failed with status: {response.status_code}"
                )
                return False

        except Exception as e:
            logger.error(f"Error testing Graph connection: {str(e)}")
            return False

    def _get_photo_from_employee_profiles(self, upn: str) -> Optional[str]:
        """Get cached photo from employee_profiles table as base64 data URL."""
        try:
            from app.models.employee_profiles import EmployeeProfiles

            profile = EmployeeProfiles.get_by_upn(upn)
            if profile and profile.photo_data:
                photo_bytes = bytes(profile.photo_data) if isinstance(profile.photo_data, memoryview) else profile.photo_data
                photo_b64 = base64.b64encode(photo_bytes).decode("utf-8")
                content_type = profile.photo_content_type or "image/jpeg"
                return f"data:{content_type};base64,{photo_b64}"
        except Exception as e:
            logger.debug(f"Error fetching photo from employee_profiles for {upn}: {str(e)}")
        return None

    def search_user(
        self, search_term: str, include_photo: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Search for a user in Microsoft Graph by email, UPN, or display name.
        Returns user profile information from Azure AD.
        """
        self._load_config()
        if not self.app:
            return None

        token = self.get_access_token()
        if not token:
            logger.error("Failed to get Graph API access token")
            return None

        # Use base class method to normalize search terms
        search_variations = self._normalize_search_term(search_term)

        # Try direct lookup first for email addresses (fast path)
        for search_query in search_variations:
            if "@" in search_query:
                try:
                    user_url = f"{self.graph_base_url}/users/{search_query}"
                    response = self._make_request("GET", user_url, token)
                    if response.status_code == 200:
                        user = self._handle_response(response)
                        return self._process_user_data(user, include_photo)
                except (TimeoutError, ConnectionError):
                    raise
                except Exception:
                    pass

        # Build all filter queries and run them in parallel
        queries = []
        select_fields = self._get_select_fields()
        search_url = f"{self.graph_base_url}/users"

        for search_query in search_variations:
            if "@" in search_query:
                queries.append({
                    "$filter": f"mail eq '{search_query}'",
                    "$select": ",".join(select_fields),
                })

            filter_query = (
                f"startswith(userPrincipalName,'{search_query}') or "
                f"startswith(displayName,'{search_query}') or "
                f"startswith(mail,'{search_query}') or "
                f"startswith(surname,'{search_query}') or "
                f"startswith(givenName,'{search_query}')"
            )
            queries.append({
                "$filter": filter_query,
                "$select": ",".join(select_fields),
            })

        all_results = []

        def _run_filter_query(params: Dict[str, str]) -> List[Dict[str, Any]]:
            resp = self._make_request("GET", search_url, token, params=params)
            if resp.status_code == 200:
                data = self._handle_response(resp)
                results: List[Dict[str, Any]] = data.get("value", [])
                return results
            return []

        with ThreadPoolExecutor(max_workers=len(queries)) as executor:
            futures = {
                executor.submit(_run_filter_query, q): q for q in queries
            }
            for future in as_completed(futures):
                try:
                    users = future.result(timeout=5)
                    all_results.extend(users)
                except (TimeoutError, ConnectionError):
                    raise
                except Exception as e:
                    logger.error(f"Error searching Graph API: {str(e)}")
                    continue

        # Remove duplicates by user ID
        if all_results:
            unique_users = {}
            for user in all_results:
                user_id = user.get("id")
                if user_id and user_id not in unique_users:
                    unique_users[user_id] = user

            unique_results = list(unique_users.values())

            if len(unique_results) == 1:
                return self._process_user_data(unique_results[0], include_photo)
            elif len(unique_results) > 1:
                # Return multiple results format
                return {
                    "multiple_results": True,
                    "results": unique_results[:10],  # Limit to 10 results
                    "total": len(unique_results),
                }

        return None

    def _get_select_fields(self) -> list:
        """Get the list of fields to select from Graph API."""
        return [
            "id",
            "userPrincipalName",
            "displayName",
            "mail",
            "givenName",
            "surname",
            "jobTitle",
            "department",
            "officeLocation",
            "mobilePhone",
            "businessPhones",
            "employeeId",
            "manager",
            "accountEnabled",
            "createdDateTime",
            "lastPasswordChangeDateTime",
            "employeeHireDate",
            "employeeType",
            "userType",
            "signInActivity",  # D-01 — needs AuditLog.Read.All + Premium P1
            "assignedLicenses",  # D-04
        ]

    def get_user_by_id(
        self, user_id: str, include_photo: bool = True
    ) -> Optional[Dict[str, Any]]:
        """Get a specific user by their Graph ID."""
        self._load_config()
        if not self.app:
            return None

        token = self.get_access_token()
        if not token:
            return None

        try:
            user_url = f"{self.graph_base_url}/users/{user_id}"
            select_fields = self._get_select_fields()
            params = {
                "$select": ",".join(select_fields),
                "$expand": "manager($select=id,displayName,mail,jobTitle)",
            }
            response = self._make_request("GET", user_url, token, params=params)
            user = self._handle_response(response)
            return self._process_user_data(user, include_photo)

        except Exception as e:
            logger.error(f"Error getting user by ID from Graph: {str(e)}")

        return None

    def _process_user_data(
        self, user: Dict[str, Any], include_photo: bool = True
    ) -> Dict[str, Any]:
        """Process raw Graph API user data into our format."""
        try:
            photo_data = None
            user_id = user.get("id")
            user_principal_name = user.get("userPrincipalName") or ""

            if include_photo and user_principal_name:
                photo_data = self._get_photo_from_employee_profiles(user_principal_name)

            if include_photo and not photo_data and user_id:
                photo_data = self.get_user_photo(user_id, user_principal_name)

            # Build result
            result = {
                "id": user.get("id"),
                "userPrincipalName": user.get("userPrincipalName"),
                "displayName": user.get("displayName"),
                "mail": user.get("mail"),
                "givenName": user.get("givenName"),
                "surname": user.get("surname"),
                "jobTitle": user.get("jobTitle"),
                "department": user.get("department"),
                "officeLocation": user.get("officeLocation"),
                "businessPhones": user.get("businessPhones", []),
                "mobilePhone": user.get("mobilePhone"),
                "employeeId": user.get("employeeId"),
                "accountEnabled": user.get("accountEnabled"),
                "userType": user.get("userType"),
                "employeeType": user.get("employeeType"),
                "createdDateTime": user.get("createdDateTime"),
                "lastPasswordChangeDateTime": user.get("lastPasswordChangeDateTime"),
                "employeeHireDate": user.get("employeeHireDate"),
                "signInActivity": user.get("signInActivity"),  # D-01
                "assignedLicenses": user.get("assignedLicenses", []),  # D-04
                "photo": photo_data,
            }

            # Use inline manager data from $expand (no extra API call needed)
            if user.get("manager"):
                result["manager"] = {
                    "id": user["manager"].get("id"),
                    "displayName": user["manager"].get("displayName"),
                    "mail": user["manager"].get("mail"),
                }

            # Remove None values and empty dicts
            result = {k: v for k, v in result.items() if v is not None and v != {}}

            return result

        except Exception as e:
            logger.error(f"Error processing Graph user data: {str(e)}")
            return user

    def get_user_photo(
        self, user_id: str, user_principal_name: Optional[str] = None
    ) -> Optional[str]:
        """Get user's profile photo from Graph API."""
        token = self.get_access_token()
        if not token:
            logger.error("Failed to get Graph API access token for photo fetch")
            return None

        # Try different approaches to get the photo
        photo_endpoints = [
            f"{self.graph_base_url}/users/{user_id}/photo/$value",
        ]

        # If we have UPN, try that too
        if user_principal_name:
            photo_endpoints.append(
                f"{self.graph_base_url}/users/{user_principal_name}/photo/$value"
            )

        for endpoint in photo_endpoints:
            try:
                response = self._make_request("GET", endpoint, token)

                if response.status_code == 200:
                    # Convert binary photo to base64
                    photo_content = response.content
                    photo_base64 = base64.b64encode(photo_content).decode("utf-8")
                    photo_data = f"data:image/jpeg;base64,{photo_base64}"

                    # Legacy photo caching removed - photos now managed by employee_profiles service

                    return photo_data

            except Exception as e:
                logger.debug(f"Error fetching photo from {endpoint}: {str(e)}")
                continue

        return None

    def _permission_missing(self, permission: str) -> Dict[str, Any]:
        """Return the D-06 sentinel and log ERROR once per startup per permission.

        Callers MUST type-check the returned value (dict with "error" key) before
        iterating, since success responses return list payloads.
        """
        if permission not in _logged_missing_perms:
            logger.error(
                f"Graph permission missing: {permission} — feature will display "
                f"inline degradation banner",
            )
            _logged_missing_perms.add(permission)
        return {"error": "permission_missing", "permission": permission}

    def get_authentication_methods(self, user_id: str) -> Optional[Any]:
        """Get authentication methods (MFA) for a user from Graph.

        Requires UserAuthenticationMethod.Read.All permission on the app registration.
        Returns a list of methods on success, or {"error": "permission_missing",
        "permission": "UserAuthenticationMethod.Read.All"} on 403 (D-06).
        """
        token = self.get_access_token()
        if not token:
            logger.error(
                "Failed to get Graph API access token for authentication methods"
            )
            return None

        try:
            url = f"{self.graph_base_url}/users/{user_id}/authentication/methods"
            response = self._make_request("GET", url, token)
            data = self._handle_response(response)
            if not data or "value" not in data:
                return []
            return data["value"]
        except requests.HTTPError as e:
            # _make_request raises HTTPError on 4xx (response.raise_for_status).
            # Detect 403 here and degrade gracefully (D-06) instead of returning None.
            if e.response is not None and e.response.status_code == 403:
                return self._permission_missing("UserAuthenticationMethod.Read.All")
            logger.error(
                f"HTTP error fetching authentication methods for user {user_id}: "
                f"{str(e)}",
                exc_info=True,
            )
            return None
        except Exception as e:
            logger.error(
                f"Error fetching authentication methods for user {user_id}: {str(e)}",
                exc_info=True,
            )
            return None

    def get_license_details(self, user_id: str) -> Optional[Any]:
        """Get assigned license details for a user from Graph.

        Uses User.Read.All (already granted on existing app reg per D-05).
        Returns a list of license-detail dicts on success, or the permission_missing
        sentinel on 403 (defensive — should not happen in production).
        """
        token = self.get_access_token()
        if not token:
            logger.error("Failed to get Graph API access token for license details")
            return None

        try:
            url = f"{self.graph_base_url}/users/{user_id}/licenseDetails"
            response = self._make_request("GET", url, token)
            data = self._handle_response(response)
            if not data or "value" not in data:
                return []
            return data["value"]
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 403:
                return self._permission_missing("User.Read.All")
            logger.error(
                f"HTTP error fetching license details for user {user_id}: {str(e)}",
                exc_info=True,
            )
            return None
        except Exception as e:
            logger.error(
                f"Error fetching license details for user {user_id}: {str(e)}",
                exc_info=True,
            )
            return None

    def get_subscribed_skus(self) -> Optional[Any]:
        """Get the tenant SKU catalog from Graph.

        Requires Organization.Read.All permission on the app registration.
        Used by SkuCatalogCache (Plan 02) for daily SKU GUID → friendly name refresh.
        Returns a list of SKU dicts on success, or the permission_missing sentinel on 403.
        """
        token = self.get_access_token()
        if not token:
            logger.error("Failed to get Graph API access token for subscribed SKUs")
            return None

        try:
            url = f"{self.graph_base_url}/subscribedSkus"
            response = self._make_request("GET", url, token)
            data = self._handle_response(response)
            if not data or "value" not in data:
                return []
            return data["value"]
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 403:
                return self._permission_missing("Organization.Read.All")
            logger.error(
                f"HTTP error fetching subscribed SKUs: {str(e)}",
                exc_info=True,
            )
            return None
        except Exception as e:
            logger.error(
                f"Error fetching subscribed SKUs: {str(e)}",
                exc_info=True,
            )
            return None

    def get_sign_in_logs(
        self, user_id: str, top: int = 25
    ) -> Optional[List[Dict[str, Any]]]:
        """Get recent sign-in logs for a user from Azure AD audit logs.

        Requires AuditLog.Read.All permission on the app registration.
        """
        token = self.get_access_token()
        if not token:
            logger.error("Failed to get Graph API access token for sign-in logs")
            return None

        try:
            url = f"{self.graph_base_url}/auditLogs/signIns"
            params = {
                "$filter": f"userId eq '{user_id}'",
                "$top": str(top),
                "$orderby": "createdDateTime desc",
                "$select": (
                    "createdDateTime,appDisplayName,ipAddress,clientAppUsed,"
                    "status,location,deviceDetail,isInteractive"
                ),
            }

            response = self._make_request("GET", url, token, params=params)
            data = self._handle_response(response)

            if not data or "value" not in data:
                return []

            logs = []
            for entry in data["value"]:
                status = entry.get("status", {})
                location = entry.get("location", {})
                device = entry.get("deviceDetail", {})

                logs.append(
                    {
                        "createdDateTime": entry.get("createdDateTime"),
                        "appDisplayName": entry.get("appDisplayName", "Unknown"),
                        "ipAddress": entry.get("ipAddress", "N/A"),
                        "clientAppUsed": entry.get("clientAppUsed", "N/A"),
                        "errorCode": status.get("errorCode", 0),
                        "failureReason": status.get("failureReason", ""),
                        "city": location.get("city", ""),
                        "state": location.get("state", ""),
                        "country": location.get("countryOrRegion", ""),
                        "browser": device.get("browser", ""),
                        "operatingSystem": device.get("operatingSystem", ""),
                        "isInteractive": entry.get("isInteractive", True),
                    }
                )

            return logs

        except Exception as e:
            logger.error(f"Error fetching sign-in logs for user {user_id}: {str(e)}")
            return None

    def get_user_devices(
        self, user_id: str
    ) -> Optional[List[Dict[str, Any]]]:
        """Get devices registered/owned by a user from Graph.

        Requires Directory.Read.All permission on the app registration.
        """
        token = self.get_access_token()
        if not token:
            logger.error("Failed to get Graph API access token for user devices")
            return None

        try:
            url = f"{self.graph_base_url}/users/{user_id}/ownedDevices"
            params = {
                "$select": (
                    "id,displayName,operatingSystem,operatingSystemVersion,"
                    "trustType,isManaged,isCompliant,approximateLastSignInDateTime,"
                    "deviceId,model,manufacturer"
                ),
            }
            response = self._make_request("GET", url, token, params=params)
            data = self._handle_response(response)

            if not data or "value" not in data:
                return []

            devices = []
            for device in data["value"]:
                devices.append(
                    {
                        "displayName": device.get("displayName", "Unknown Device"),
                        "operatingSystem": device.get("operatingSystem", ""),
                        "osVersion": device.get("operatingSystemVersion", ""),
                        "trustType": device.get("trustType", ""),
                        "isManaged": device.get("isManaged"),
                        "isCompliant": device.get("isCompliant"),
                        "lastSignIn": device.get("approximateLastSignInDateTime"),
                        "model": device.get("model", ""),
                        "manufacturer": device.get("manufacturer", ""),
                    }
                )

            return devices

        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 403:
                return self._permission_missing("Directory.Read.All")
            logger.error(f"Error fetching devices for user {user_id}: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Error fetching devices for user {user_id}: {str(e)}")
            return None


    # ------------------------------------------------------------------ #
    # Bulk methods for Phase 8 Reporting                                   #
    # ------------------------------------------------------------------ #

    def get_all_users_with_licenses(self) -> List[Dict[str, Any]]:
        """Paginated iteration over all users with license and sign-in data.

        Fetches displayName, userPrincipalName, assignedLicenses, and
        signInActivity using /beta/users with ConsistencyLevel: eventual.

        Requires User.Read.All permission (D-05).

        Returns:
            List of user dicts, or permission_missing sentinel on 403.
        """
        token = self.get_access_token()
        if not token:
            logger.error("Failed to get Graph API access token for bulk users")
            return []

        all_users: List[Dict[str, Any]] = []
        url: Optional[str] = f"{self.graph_base_url}/users"
        params: Optional[Dict[str, str]] = {
            "$select": "displayName,userPrincipalName,assignedLicenses,signInActivity",
            "$top": "500",
        }
        headers = {"ConsistencyLevel": "eventual"}

        try:
            while url:
                response = self._make_request(
                    "GET", url, token, params=params, headers=headers,
                )
                data = self._handle_response(response)

                if isinstance(data, dict) and "error" in data:
                    return data  # type: ignore[return-value]

                users = data.get("value", []) if data else []
                all_users.extend(users)

                # Follow @odata.nextLink for pagination
                url = data.get("@odata.nextLink") if data else None
                # After first page, params are embedded in nextLink
                params = None

            logger.info(
                f"Fetched {len(all_users)} users with license data from Graph"
            )
            return all_users

        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 403:
                return self._permission_missing("User.Read.All")  # type: ignore[return-value]
            logger.error(
                f"HTTP error fetching bulk users: {str(e)}", exc_info=True,
            )
            return []
        except Exception as e:
            logger.error(
                f"Error fetching bulk users with licenses: {str(e)}",
                exc_info=True,
            )
            return []

    def get_mfa_registration_details(self) -> List[Dict[str, Any]]:
        """Bulk MFA registration details via v1.0 userRegistrationDetails.

        Uses the v1.0 endpoint (not beta) per RESEARCH.md Pattern 2.
        Requires AuditLog.Read.All permission.

        Returns:
            List of user registration detail dicts, or permission_missing
            sentinel on 403.
        """
        token = self.get_access_token()
        if not token:
            logger.error("Failed to get Graph API access token for MFA details")
            return []

        all_details: List[Dict[str, Any]] = []
        url: Optional[str] = (
            "https://graph.microsoft.com/v1.0"
            "/reports/authenticationMethods/userRegistrationDetails"
        )
        params: Optional[Dict[str, str]] = None

        try:
            while url:
                response = self._make_request(
                    "GET", url, token, params=params,
                )
                data = self._handle_response(response)

                if isinstance(data, dict) and "error" in data:
                    return data  # type: ignore[return-value]

                details = data.get("value", []) if data else []
                all_details.extend(details)

                url = data.get("@odata.nextLink") if data else None
                params = None

            logger.info(
                f"Fetched {len(all_details)} MFA registration records from Graph"
            )
            return all_details

        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 403:
                return self._permission_missing("AuditLog.Read.All")  # type: ignore[return-value]
            logger.error(
                f"HTTP error fetching MFA registration details: {str(e)}",
                exc_info=True,
            )
            return []
        except Exception as e:
            logger.error(
                f"Error fetching MFA registration details: {str(e)}",
                exc_info=True,
            )
            return []

    def get_failed_signins_bulk(
        self, from_date: str, to_date: str,
    ) -> List[Dict[str, Any]]:
        """Bulk failed sign-in logs within a date range.

        Queries /beta/auditLogs/signIns filtered by errorCode ne 0.
        Validates from_date and to_date as ISO 8601 before embedding
        in the OData $filter (T-08-04 mitigation).

        Requires AuditLog.Read.All permission.

        Args:
            from_date: ISO 8601 datetime string (inclusive lower bound).
            to_date: ISO 8601 datetime string (inclusive upper bound).

        Returns:
            List of sign-in log dicts, or permission_missing sentinel on 403.
        """
        # T-08-04: Validate date inputs to prevent OData injection
        import re

        iso_pattern = re.compile(
            r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z?$"
        )
        if not iso_pattern.match(from_date) or not iso_pattern.match(to_date):
            logger.error(
                f"Invalid date format for sign-in query: "
                f"from={from_date}, to={to_date}"
            )
            return []

        token = self.get_access_token()
        if not token:
            logger.error("Failed to get Graph API access token for sign-in logs")
            return []

        all_entries: List[Dict[str, Any]] = []
        url: Optional[str] = f"{self.graph_base_url}/auditLogs/signIns"
        params: Optional[Dict[str, str]] = {
            "$filter": (
                f"status/errorCode ne 0 "
                f"and createdDateTime ge {from_date} "
                f"and createdDateTime le {to_date}"
            ),
            "$orderby": "createdDateTime desc",
            "$top": "500",
            "$select": (
                "createdDateTime,userDisplayName,userPrincipalName,"
                "ipAddress,location,status,appDisplayName"
            ),
        }

        try:
            while url:
                response = self._make_request(
                    "GET", url, token, params=params,
                )
                data = self._handle_response(response)

                if isinstance(data, dict) and "error" in data:
                    return data  # type: ignore[return-value]

                entries = data.get("value", []) if data else []
                all_entries.extend(entries)

                url = data.get("@odata.nextLink") if data else None
                params = None

            logger.info(
                f"Fetched {len(all_entries)} failed sign-in entries from Graph"
            )
            return all_entries

        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 403:
                return self._permission_missing("AuditLog.Read.All")  # type: ignore[return-value]
            logger.error(
                f"HTTP error fetching failed sign-ins: {str(e)}",
                exc_info=True,
            )
            return []
        except Exception as e:
            logger.error(
                f"Error fetching failed sign-ins: {str(e)}", exc_info=True,
            )
            return []


    # ------------------------------------------------------------------ #
    # License write operations (Phase 9)                                   #
    # ------------------------------------------------------------------ #

    def assign_license(
        self, user_id: str, sku_id: str, disabled_plans: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Assign an M365 license to a user.

        Args:
            user_id: Graph user ID or UPN.
            sku_id: SKU GUID to assign.
            disabled_plans: Optional list of service plan IDs to disable.

        Returns:
            Dict with "success" bool, or permission_missing sentinel on 403.
        """
        token = self.get_access_token()
        if not token:
            return {"success": False, "error": "Failed to acquire access token"}

        url = f"{self.graph_base_url}/users/{user_id}/assignLicense"
        body = {
            "addLicenses": [
                {"skuId": sku_id, "disabledPlans": disabled_plans or []}
            ],
            "removeLicenses": [],
        }

        try:
            response = self._make_request("POST", url, token, json=body)
            if response.status_code == 200:
                return {"success": True}
            return {"success": False, "error": f"HTTP {response.status_code}"}
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 403:
                return self._permission_missing("LicenseAssignment.ReadWrite.All")
            return {"success": False, "error": str(e)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def remove_license(self, user_id: str, sku_id: str) -> Dict[str, Any]:
        """Remove an M365 license from a user.

        Args:
            user_id: Graph user ID or UPN.
            sku_id: SKU GUID to remove.

        Returns:
            Dict with "success" bool, or permission_missing sentinel on 403.
        """
        token = self.get_access_token()
        if not token:
            return {"success": False, "error": "Failed to acquire access token"}

        url = f"{self.graph_base_url}/users/{user_id}/assignLicense"
        body = {
            "addLicenses": [],
            "removeLicenses": [sku_id],
        }

        try:
            response = self._make_request("POST", url, token, json=body)
            if response.status_code == 200:
                return {"success": True}
            return {"success": False, "error": f"HTTP {response.status_code}"}
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 403:
                return self._permission_missing("LicenseAssignment.ReadWrite.All")
            return {"success": False, "error": str(e)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def swap_license(
        self, user_id: str, old_sku_id: str, new_sku_id: str
    ) -> Dict[str, Any]:
        """Swap one M365 license for another (atomic with fallback).

        Strategy: attempt a single POST with both addLicenses and removeLicenses.
        If that fails, fall back to two sequential calls with rollback on failure.

        Args:
            user_id: Graph user ID or UPN.
            old_sku_id: SKU GUID to remove.
            new_sku_id: SKU GUID to assign.

        Returns:
            Dict with keys: success, rollback_needed, rollback_success, error.
        """
        token = self.get_access_token()
        if not token:
            return {
                "success": False,
                "error": "Failed to acquire access token",
                "rollback_needed": False,
                "rollback_success": None,
            }

        # Attempt 1: atomic swap (single API call)
        url = f"{self.graph_base_url}/users/{user_id}/assignLicense"
        body = {
            "addLicenses": [{"skuId": new_sku_id, "disabledPlans": []}],
            "removeLicenses": [old_sku_id],
        }

        try:
            response = self._make_request("POST", url, token, json=body)
            if response.status_code == 200:
                return {"success": True, "rollback_needed": False, "rollback_success": None}
        except requests.HTTPError:
            # Atomic swap failed — fall through to two-call approach
            logger.warning(
                f"Atomic license swap failed for user {user_id}, "
                f"falling back to sequential remove+assign"
            )
        except Exception as e:
            logger.warning(f"Atomic swap unexpected error: {str(e)}")

        # Attempt 2: sequential remove then assign
        remove_result = self.remove_license(user_id, old_sku_id)
        if not remove_result.get("success"):
            return {
                "success": False,
                "error": f"Remove failed: {remove_result.get('error')}",
                "rollback_needed": False,
                "rollback_success": None,
            }

        assign_result = self.assign_license(user_id, new_sku_id)
        if assign_result.get("success"):
            return {"success": True, "rollback_needed": False, "rollback_success": None}

        # Assign failed after remove succeeded — attempt rollback
        logger.error(
            f"License swap partial failure for user {user_id}: "
            f"removed {old_sku_id} but failed to assign {new_sku_id}. "
            f"Attempting rollback."
        )

        rollback_result = self.assign_license(user_id, old_sku_id)
        rollback_success = rollback_result.get("success", False)

        if not rollback_success:
            logger.error(
                f"MANUAL_INTERVENTION_REQUIRED: License swap double failure "
                f"for user {user_id}. Removed {old_sku_id}, failed to assign "
                f"{new_sku_id}, AND failed to rollback. User has NO license "
                f"for this slot."
            )

        return {
            "success": False,
            "error": f"Assign failed after remove: {assign_result.get('error')}",
            "rollback_needed": True,
            "rollback_success": rollback_success,
        }


graph_service = GraphService()
