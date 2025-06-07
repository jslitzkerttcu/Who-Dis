import os
import logging
from typing import Optional, Dict, Any, Union
from msal import ConfidentialClientApplication  # type: ignore[import-untyped]
import requests
from requests.exceptions import Timeout, ConnectionError
from app.services.configuration_service import config_get
from app.models import ApiToken, GraphPhoto
from app.database import get_db
import base64

logger = logging.getLogger(__name__)


class GraphService:
    def __init__(self):
        # Get credentials from config service (encrypted in database)
        self.client_id = config_get("graph", "client_id", os.getenv("GRAPH_CLIENT_ID"))
        self.client_secret = config_get(
            "graph", "client_secret", os.getenv("GRAPH_CLIENT_SECRET")
        )
        self.tenant_id = config_get("graph", "tenant_id", os.getenv("GRAPH_TENANT_ID"))
        # Timeout from config service
        self.timeout = int(
            config_get("graph", "api_timeout", os.getenv("GRAPH_API_TIMEOUT", "15"))
        )

        # Graph API endpoints
        self.authority = f"https://login.microsoftonline.com/{self.tenant_id}"
        self.scope = ["https://graph.microsoft.com/.default"]
        self.graph_base_url = "https://graph.microsoft.com/beta"

        # Token cache
        self._token = None
        self._token_expiry = None

        # Initialize MSAL app
        self.app = None
        if self.client_id and self.client_secret and self.tenant_id:
            self.app = ConfidentialClientApplication(
                self.client_id,
                authority=self.authority,
                client_credential=self.client_secret,
            )
            logger.info("Microsoft Graph service initialized")
        else:
            logger.warning("Microsoft Graph API credentials not configured")

    def _get_access_token(self) -> Optional[str]:
        """Get access token using client credentials flow with database storage."""
        if not self.app:
            return None

        # First, try to get token from database
        try:
            # Check if we're in an application context
            from flask import current_app

            if current_app:
                token_record = ApiToken.get_token("microsoft_graph")
                if token_record:
                    logger.info(
                        f"Using cached Graph API token, expires at {token_record.expires_at}"
                    )
                    return str(token_record.access_token)
        except Exception as e:
            # This is expected when running outside app context during initialization
            if "application context" not in str(e):
                logger.warning(
                    f"Failed to get token from database: {e}. Will fetch new token."
                )

        # Token not in database or expired, get a new one
        logger.info("Graph API token not found or expired, fetching new token")
        try:
            # Get new token
            result = self.app.acquire_token_silent(self.scope, account=None)
            if not result:
                result = self.app.acquire_token_for_client(scopes=self.scope)

            if "access_token" in result:
                access_token = result["access_token"]
                # Default to 1 hour if not specified
                expires_in = result.get("expires_in", 3600)

                # Try to store token in database
                try:
                    # Check if we're in an application context
                    from flask import current_app

                    if current_app:
                        token_record = ApiToken.upsert_token(
                            service_name="microsoft_graph",
                            access_token=access_token,
                            expires_in_seconds=expires_in,
                            token_type=result.get("token_type", "Bearer"),
                            additional_data={
                                "tenant_id": self.tenant_id,
                                "client_id": self.client_id,
                                "scope": self.scope,
                            },
                        )
                        logger.info(
                            f"New Graph API token stored, expires at {token_record.expires_at}"
                        )
                except Exception as e:
                    # This is expected when running outside app context
                    if "application context" not in str(e):
                        logger.warning(
                            f"Failed to store token in database: {e}. Token will work for this session."
                        )
                return str(access_token)
            else:
                logger.error(
                    f"Failed to acquire token: {result.get('error_description', 'Unknown error')}"
                )
                return None

        except Exception as e:
            logger.error(f"Error getting Graph API access token: {str(e)}")
            return None

    def refresh_token_if_needed(self) -> bool:
        """Check and refresh token if needed. Returns True if token is valid."""
        try:
            token = self._get_access_token()
            return token is not None
        except Exception as e:
            logger.error(f"Error refreshing Graph API token: {str(e)}")
            return False

    def has_cached_photo(
        self, user_id: str, user_principal_name: Optional[str] = None
    ) -> bool:
        """Check if we have a cached photo for the user."""
        try:
            from flask import current_app

            if current_app:
                with get_db() as db:
                    cached_photo = GraphPhoto.get_photo(
                        db, user_id, user_principal_name
                    )
                    return cached_photo is not None and not GraphPhoto.is_stale(
                        cached_photo, hours=24
                    )
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
        if not self.app:
            logger.info("Graph API not configured, skipping search")
            return None

        token = self._get_access_token()
        if not token:
            logger.error("Failed to get Graph API access token")
            return None

        try:
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "ConsistencyLevel": "eventual",  # Required for advanced queries
            }

            # Build search query - search across multiple fields
            # Using $search requires ConsistencyLevel header
            search_query = f'"displayName:{search_term}" OR "mail:{search_term}" OR "userPrincipalName:{search_term}"'

            # Select specific fields we want
            select_fields = [
                "id",
                "displayName",
                "givenName",
                "surname",
                "mail",
                "userPrincipalName",
                "jobTitle",
                "department",
                "officeLocation",
                "mobilePhone",
                "businessPhones",
                "companyName",
                "employeeId",
                "employeeType",
                "accountEnabled",
                "createdDateTime",
                "lastPasswordChangeDateTime",
                "city",
                "state",
                "country",
                "postalCode",
                "streetAddress",
                "manager",
            ]

            params: Dict[str, Union[str, int]] = {
                "$search": search_query,
                "$select": ",".join(select_fields),
                "$count": "true",  # Include count of results
                "$top": 25,  # Limit results
            }

            response = requests.get(
                f"{self.graph_base_url}/users",
                headers=headers,
                params=params,
                timeout=self.timeout,
            )

            if response.status_code == 200:
                data = response.json()
                users = data.get("value", [])
                total_count = data.get("@odata.count", len(users))

                logger.info(
                    f"Graph API search for '{search_term}' returned {len(users)} results"
                )

                if len(users) == 0:
                    return None
                elif len(users) == 1:
                    # Single result - get additional details
                    return self._process_user_data(users[0], headers, include_photo)
                else:
                    # Multiple results
                    return {
                        "multiple_results": True,
                        "results": users,
                        "total": total_count,
                    }
            else:
                logger.error(
                    f"Graph API search failed: {response.status_code} - {response.text}"
                )
                return None

        except Timeout:
            logger.error(f"Graph API timeout after {self.timeout} seconds")
            raise TimeoutError(
                f"Microsoft Graph search timed out after {self.timeout} seconds. Please try a more specific search term."
            )
        except ConnectionError as e:
            logger.error(f"Connection error to Graph API: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error searching Graph API: {str(e)}")
            return None

    def get_user_by_id(
        self, user_id: str, include_photo: bool = True
    ) -> Optional[Dict[str, Any]]:
        """Get a specific user by their Graph ID."""
        if not self.app:
            return None

        token = self._get_access_token()
        if not token:
            return None

        try:
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }

            # Get user with expanded manager information
            params = {
                "$select": "id,displayName,givenName,surname,mail,userPrincipalName,jobTitle,department,officeLocation,mobilePhone,businessPhones,companyName,employeeId,employeeType,accountEnabled,createdDateTime,lastPasswordChangeDateTime,city,state,country,postalCode,streetAddress",
                "$expand": "manager($select=displayName,mail)",
            }

            response = requests.get(
                f"{self.graph_base_url}/users/{user_id}",
                headers=headers,
                params=params,
                timeout=self.timeout,
            )

            if response.status_code == 200:
                user_data = response.json()
                logger.info(
                    f"Raw Graph user data fields from get_user_by_id: {list(user_data.keys())}"
                )
                if "lastPasswordChangeDateTime" in user_data:
                    logger.info(
                        f"Raw password change date: {user_data['lastPasswordChangeDateTime']}"
                    )
                processed_data = self._process_user_data(
                    user_data, headers, include_photo
                )
                logger.info(
                    f"Processed Graph user data fields: {list(processed_data.keys())}"
                )
                return processed_data
            else:
                logger.error(
                    f"Failed to get user by ID: {response.status_code} - {response.text}"
                )
                return None

        except Timeout:
            logger.error(f"Graph API timeout after {self.timeout} seconds")
            raise TimeoutError(
                f"Microsoft Graph user fetch timed out after {self.timeout} seconds."
            )
        except Exception as e:
            logger.error(f"Error getting user from Graph API: {str(e)}")
            return None

    def _process_user_data(
        self,
        user: Dict[str, Any],
        headers: Optional[Dict[str, str]] = None,
        include_photo: bool = True,
    ) -> Dict[str, Any]:
        """Process and enrich user data from Graph API."""
        try:
            # Handle photo based on include_photo flag
            photo_url = None
            has_photo = False

            if headers:
                if include_photo:
                    # Fetch the actual photo data
                    photo_url = self._get_user_photo(
                        user["id"], headers, user.get("userPrincipalName", "")
                    )
                    has_photo = photo_url is not None
                else:
                    # Just check if photo exists (for lazy loading)
                    has_photo = self.has_cached_photo(
                        user["id"], user.get("userPrincipalName")
                    ) or self._check_photo_exists(
                        user["id"], headers, user.get("userPrincipalName")
                    )

            # Format phone numbers
            phone_numbers = {}
            if user.get("mobilePhone"):
                phone_numbers["mobile"] = user["mobilePhone"]
            if user.get("businessPhones"):
                for i, phone in enumerate(user["businessPhones"]):
                    if i == 0:
                        phone_numbers["business"] = phone
                    else:
                        phone_numbers[f"business{i + 1}"] = phone

            # Extract manager info if expanded
            manager_name = None
            manager_email = None
            if user.get("manager"):
                manager_name = user["manager"].get("displayName")
                manager_email = user["manager"].get("mail")

            # Build processed user data
            result = {
                "id": user.get("id"),
                "displayName": user.get("displayName"),
                "givenName": user.get("givenName"),
                "surname": user.get("surname"),
                "mail": user.get("mail"),
                "userPrincipalName": user.get("userPrincipalName"),
                "jobTitle": user.get("jobTitle"),
                "department": user.get("department"),
                "officeLocation": user.get("officeLocation"),
                "companyName": user.get("companyName"),
                "employeeId": user.get("employeeId"),
                "employeeType": user.get("employeeType"),
                "accountEnabled": user.get("accountEnabled"),
                "phoneNumbers": phone_numbers,
                "address": {
                    "street": user.get("streetAddress"),
                    "city": user.get("city"),
                    "state": user.get("state"),
                    "postalCode": user.get("postalCode"),
                    "country": user.get("country"),
                },
                "manager": manager_name,
                "managerEmail": manager_email,
                "createdDateTime": user.get("createdDateTime"),
                "lastPasswordChangeDateTime": user.get("lastPasswordChangeDateTime"),
                "photoUrl": photo_url,
                "hasPhoto": has_photo,  # Flag for lazy loading
                # Additional fields from beta API
                "employeeHireDate": user.get("employeeHireDate"),
                "refreshTokensValidFromDateTime": user.get(
                    "refreshTokensValidFromDateTime"
                ),
                "signInSessionsValidFromDateTime": user.get(
                    "signInSessionsValidFromDateTime"
                ),
                "onPremisesLastSyncDateTime": user.get("onPremisesLastSyncDateTime"),
                "passwordPolicies": user.get("passwordPolicies"),
                "usageLocation": user.get("usageLocation"),
                "legalAgeGroupClassification": user.get("legalAgeGroupClassification"),
            }

            # Extract extension attributes that might have additional data
            for key, value in user.items():
                if key.startswith("extension_") and value is not None:
                    # Extract meaningful field names from extension attributes
                    if "dateOfBirth" in key:
                        result["dateOfBirth"] = value
                    elif "dateOfHire" in key:
                        result["employeeHireDate"] = (
                            value  # Override if extension has it
                        )
                    elif "pager" in key or "primaryTelexNumber" in key:
                        # Add pager/extension number to phone numbers
                        if value:
                            phone_numbers["extension"] = value
                    elif "extensionAttribute4" in key and value:
                        # This seems to be another phone number
                        phone_numbers["alternate"] = value

            # Update phone numbers if we added any
            if phone_numbers:
                result["phoneNumbers"] = phone_numbers

            # Remove None values and empty dicts
            result = {k: v for k, v in result.items() if v is not None and v != {}}

            return result

        except Exception as e:
            logger.error(f"Error processing Graph user data: {str(e)}")
            return user

    def get_user_photo(
        self, user_id: str, user_principal_name: Optional[str] = None
    ) -> Optional[str]:
        """Public method to get user's profile photo from Graph API."""
        token = self._get_access_token()
        if not token:
            logger.error("Failed to get Graph API access token for photo fetch")
            return None

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        return self._get_user_photo(user_id, headers, user_principal_name)

    def _get_user_photo(
        self,
        user_id: str,
        headers: Dict[str, str],
        user_principal_name: Optional[str] = None,
    ) -> Optional[str]:
        """Get user's profile photo from Graph API with database caching."""
        try:
            # Check if we're in an application context
            from flask import current_app

            if current_app:
                # Check database cache first
                with get_db() as db:
                    cached_photo = GraphPhoto.get_photo(
                        db, user_id, user_principal_name
                    )

                    if cached_photo and not GraphPhoto.is_stale(cached_photo, hours=24):
                        # Return cached photo
                        logger.info(
                            f"Using cached photo for user {user_id}, last updated: {cached_photo.updated_at}"
                        )
                        photo_data = base64.b64encode(cached_photo.photo_data).decode(
                            "utf-8"
                        )
                        return f"data:{cached_photo.content_type};base64,{photo_data}"
                    elif cached_photo:
                        logger.info(
                            f"Cached photo for user {user_id} is stale, will refresh"
                        )
        except Exception as e:
            # This is expected when running outside app context
            if "application context" not in str(e):
                logger.warning(f"Failed to check photo cache: {e}")

        # Fetch from Graph API
        photo_bytes = None
        content_type = "image/jpeg"

        try:
            # Try to get the photo using ID first
            logger.info(
                f"Attempting to fetch photo from Graph API for user ID: {user_id}"
            )
            response = requests.get(
                f"{self.graph_base_url}/users/{user_id}/photo/$value",
                headers=headers,
                timeout=5,  # Short timeout for photo
            )

            if response.status_code == 200:
                photo_bytes = response.content
                content_type = response.headers.get("Content-Type", "image/jpeg")
                logger.info(
                    f"Successfully fetched photo for user ID {user_id}, size: {len(response.content)} bytes"
                )
            elif response.status_code == 404:
                logger.info(f"No photo found for user ID {user_id} (404)")
                if user_principal_name:
                    # Try with userPrincipalName if ID didn't work
                    logger.info(
                        f"Attempting to fetch photo using UPN: {user_principal_name}"
                    )
                    response = requests.get(
                        f"{self.graph_base_url}/users/{user_principal_name}/photo/$value",
                        headers=headers,
                        timeout=5,
                    )
                    if response.status_code == 200:
                        photo_bytes = response.content
                        content_type = response.headers.get(
                            "Content-Type", "image/jpeg"
                        )
                        logger.info(
                            f"Successfully fetched photo using UPN, size: {len(response.content)} bytes"
                        )
                    else:
                        logger.info(
                            f"No photo found for UPN {user_principal_name} (status: {response.status_code})"
                        )
            else:
                logger.warning(
                    f"Unexpected status code {response.status_code} when fetching photo for user {user_id}"
                )

        except Exception as e:
            logger.error(f"Error getting user photo from Graph API: {str(e)}")
            return None

        # Cache the photo if we got one
        if photo_bytes:
            try:
                from flask import current_app

                if current_app:
                    with get_db() as db:
                        GraphPhoto.upsert_photo(
                            db,
                            user_id=user_id,
                            photo_data=photo_bytes,
                            user_principal_name=user_principal_name,
                            content_type=content_type,
                        )
                        logger.info(f"Cached photo for user {user_id} in database")
            except Exception as e:
                # Don't fail if caching fails
                if "application context" not in str(e):
                    logger.warning(f"Failed to cache photo: {e}")

            # Return the photo data URL
            photo_data = base64.b64encode(photo_bytes).decode("utf-8")
            return f"data:{content_type};base64,{photo_data}"

        return None

    def _check_photo_exists(
        self,
        user_id: str,
        headers: Dict[str, str],
        user_principal_name: Optional[str] = None,
    ) -> bool:
        """Check if user has a photo without downloading it."""
        try:
            # Try HEAD request first (most efficient)
            response = requests.head(
                f"{self.graph_base_url}/users/{user_id}/photo",
                headers=headers,
                timeout=2,  # Very short timeout for existence check
            )

            if response.status_code == 200:
                return True
            elif response.status_code == 404 and user_principal_name:
                # Try with UPN if ID didn't work
                response = requests.head(
                    f"{self.graph_base_url}/users/{user_principal_name}/photo",
                    headers=headers,
                    timeout=2,
                )
                return response.status_code == 200

            return False

        except Exception as e:
            logger.debug(f"Error checking photo existence: {str(e)}")
            return False


# Global instance
graph_service = GraphService()
