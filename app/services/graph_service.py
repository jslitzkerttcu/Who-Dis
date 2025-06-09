"""Microsoft Graph service with simplified configuration."""

import logging
from typing import Optional, Dict, Any
from msal import ConfidentialClientApplication  # type: ignore[import-untyped]
import base64
from app.services.base import BaseAPITokenService
from app.models import GraphPhoto
from app.database import get_db
from app.interfaces.search_service import ISearchService
from app.interfaces.token_service import ITokenService

logger = logging.getLogger(__name__)


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

    def _photo_exists_in_cache(self, user_id: str) -> bool:
        """Check if user photo exists in cache and is fresh."""
        try:
            from flask import current_app

            if current_app:
                with get_db() as conn:
                    cached_photo = conn.execute(
                        "SELECT photo_data FROM graph_photos WHERE user_id = %s AND updated_at > NOW() - INTERVAL '24 hours'",
                        (user_id,),
                    ).first()
                    return cached_photo is not None
        except Exception:
            pass
        return False

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

        all_results = []

        for search_query in search_variations:
            try:
                # Try direct user lookup by userPrincipalName or email first
                if "@" in search_query:
                    user_url = f"{self.graph_base_url}/users/{search_query}"
                    response = self._make_request("GET", user_url, token)

                    if response.status_code == 200:
                        user = self._handle_response(response)
                        return self._process_user_data(user, include_photo)

                    # Also try as mail filter for exact match
                    mail_filter = f"mail eq '{search_query}'"
                    select_fields = self._get_select_fields()

                    search_url = f"{self.graph_base_url}/users"
                    params = {
                        "$filter": mail_filter,
                        "$select": ",".join(select_fields),
                    }

                    response = self._make_request(
                        "GET", search_url, token, params=params
                    )
                    if response.status_code == 200:
                        data = self._handle_response(response)
                        users = data.get("value", [])
                        if users:
                            return self._process_user_data(users[0], include_photo)

                # Search using filter - only use startswith as contains is not supported
                filter_query = (
                    f"startswith(userPrincipalName,'{search_query}') or "
                    f"startswith(displayName,'{search_query}') or "
                    f"startswith(mail,'{search_query}')"
                )

                select_fields = self._get_select_fields()
                search_url = f"{self.graph_base_url}/users"
                params = {"$filter": filter_query, "$select": ",".join(select_fields)}

                response = self._make_request("GET", search_url, token, params=params)

                if response.status_code == 200:
                    data = self._handle_response(response)
                    users = data.get("value", [])

                    # Add to results if found
                    all_results.extend(users)

            except (TimeoutError, ConnectionError):
                # Base class already handles these with proper error messages
                raise
            except Exception as e:
                logger.error(f"Error searching Graph API: {str(e)}")
                # Continue with other search variations instead of raising
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
            response = self._make_request("GET", user_url, token)
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
            # Get user photo if requested and not cached
            photo_data = None
            user_id = user.get("id")
            if include_photo and user_id and not self._photo_exists_in_cache(user_id):
                user_principal_name = user.get("userPrincipalName") or ""
                photo_data = self.get_user_photo(user_id, user_principal_name)
            elif include_photo:
                # Get from cache
                try:
                    from flask import current_app

                    if current_app:
                        with get_db() as db:
                            cached_photo = GraphPhoto.get_photo(db, user.get("id"))
                            if cached_photo:
                                photo_data = cached_photo.photo_data
                except Exception:
                    pass

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
                "photo": photo_data,
            }

            # Get manager info if present
            if user.get("manager"):
                manager_id = user["manager"].get("id")
                if manager_id:
                    manager_data = self.get_user_by_id(manager_id, include_photo=False)
                    if manager_data:
                        result["manager"] = {
                            "id": manager_data.get("id"),
                            "displayName": manager_data.get("displayName"),
                            "mail": manager_data.get("mail"),
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

                    # Cache the photo
                    try:
                        from flask import current_app

                        if current_app:
                            with get_db() as db:
                                GraphPhoto.upsert_photo(
                                    db, user_id, photo_data.encode()
                                )
                    except Exception as e:
                        logger.debug(f"Could not cache photo: {e}")

                    return photo_data

            except Exception as e:
                logger.debug(f"Error fetching photo from {endpoint}: {str(e)}")
                continue

        return None


graph_service = GraphService()
