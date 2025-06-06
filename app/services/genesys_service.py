import os
import requests
from requests.exceptions import Timeout, ConnectionError
from typing import Optional, Dict, Any
import logging
from app.services.genesys_cache import genesys_cache
from app.services.configuration_service import config_get
from app.models import ApiToken

logger = logging.getLogger(__name__)


class GenesysCloudService:
    def __init__(self):
        # Get credentials from config service (encrypted in database)
        self.client_id = config_get(
            "genesys", "client_id", os.getenv("GENESYS_CLIENT_ID")
        )
        self.client_secret = config_get(
            "genesys", "client_secret", os.getenv("GENESYS_CLIENT_SECRET")
        )
        # Region and timeout from config service
        self.region = config_get(
            "genesys", "region", os.getenv("GENESYS_REGION", "mypurecloud.com")
        )
        self.base_url = f"https://api.{self.region}"
        self.token_url = f"https://login.{self.region}/oauth/token"
        self._token = None
        self._token_expiry = None
        # Timeout configuration
        self.timeout = int(
            config_get("genesys", "api_timeout", os.getenv("GENESYS_API_TIMEOUT", "15"))
        )  # API timeout in seconds

    def _get_access_token(self) -> Optional[str]:
        """Get access token using client credentials grant with database storage."""
        # First, try to get token from database
        try:
            token_record = ApiToken.get_token("genesys")
            if token_record:
                logger.info(
                    f"Using cached Genesys token, expires at {token_record.expires_at}"
                )
                return str(token_record.access_token)
        except Exception as e:
            logger.warning(
                f"Failed to get token from database: {e}. Will fetch new token."
            )

        # Token not in database or expired, get a new one
        logger.info("Genesys token not found or expired, fetching new token")
        try:
            response = requests.post(
                self.token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
                timeout=self.timeout,
            )

            if response.status_code == 200:
                data = response.json()
                access_token = data["access_token"]
                expires_in = data.get("expires_in", 3600)

                # Try to store token in database
                try:
                    token_record = ApiToken.upsert_token(
                        service_name="genesys",
                        access_token=access_token,
                        expires_in_seconds=expires_in,
                        token_type=data.get("token_type", "Bearer"),
                        additional_data={
                            "region": self.region,
                            "client_id": self.client_id,
                        },
                    )
                    logger.info(
                        f"New Genesys token stored, expires at {token_record.expires_at}"
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to store token in database: {e}. Token will work for this session."
                    )
                return str(access_token)
            else:
                logger.error(
                    f"Failed to get access token: {response.status_code} - {response.text}"
                )

        except Timeout:
            logger.error(f"Timeout getting access token after {self.timeout} seconds")
            raise TimeoutError("Authentication timed out. Please try again.")
        except Exception as e:
            logger.error(f"Error getting access token: {str(e)}")

        return None

    def refresh_token_if_needed(self) -> bool:
        """Check and refresh token if needed. Returns True if token is valid."""
        try:
            token = self._get_access_token()
            return token is not None
        except Exception as e:
            logger.error(f"Error refreshing Genesys token: {str(e)}")
            return False

    def search_user(self, search_term: str) -> Optional[Dict[str, Any]]:
        """
        Search for a user in Genesys Cloud by email or username.
        Returns user profile information.
        """
        token = self._get_access_token()
        if not token:
            logger.error("Failed to get access token")
            return None

        try:
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }

            # Search using CONTAINS across multiple fields
            search_body = {
                "query": [
                    {
                        "value": search_term,
                        "fields": ["name", "email", "username"],
                        "type": "CONTAINS",
                    }
                ],
                "expand": [
                    "groups",
                    "dateLastLogin",
                    "skills",
                    "languages",
                    "locations",
                    "manager",
                    "profileSkills",
                    "routingStatus",
                    "conversationSummary",
                    "outOfOffice",
                    "station",
                    "queues",
                ],
            }

            response = requests.post(
                f"{self.base_url}/api/v2/users/search",
                headers=headers,
                json=search_body,
                timeout=self.timeout,
            )

            if response.status_code == 200:
                data = response.json()
                total_results = data.get("total", 0)

                # Check if too many results
                if total_results > 25:
                    return {
                        "error": "too_many_results",
                        "message": f"Your search returned {total_results} results. Please be more specific.",
                        "total": total_results,
                    }

                # Check if we have results
                if not data.get("results") or len(data["results"]) == 0:
                    return None

                # If multiple results, return all of them for selection
                if len(data["results"]) > 1:
                    return {
                        "multiple_results": True,
                        "results": data["results"],
                        "total": total_results,
                    }

                # Single result - process it
                user = data["results"][0]
                return self._process_user_data(user)

            else:
                logger.error(
                    f"User search failed: {response.status_code} - {response.text}"
                )

        except Timeout:
            logger.error(f"Genesys API timeout after {self.timeout} seconds")
            raise TimeoutError(
                f"Genesys search timed out after {self.timeout} seconds. Please try a more specific search term."
            )
        except ConnectionError as e:
            logger.error(f"Connection error to Genesys API: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error searching for user in Genesys: {str(e)}")

        return None

    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific user by ID."""
        token = self._get_access_token()
        if not token:
            logger.error("Failed to get access token")
            return None

        try:
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }

            url = f"{self.base_url}/api/v2/users/{user_id}?expand=groups,skills,languages,locations,manager,profileSkills,routingStatus,conversationSummary,outOfOffice,station,dateLastLogin,queues"
            response = requests.get(url, headers=headers, timeout=self.timeout)

            if response.status_code == 200:
                user = response.json()
                return self._process_user_data(user)
            else:
                logger.error(
                    f"Failed to get user by ID: {response.status_code} - {response.text}"
                )

        except Timeout:
            logger.error(f"Genesys API timeout after {self.timeout} seconds")
            raise TimeoutError(
                f"Genesys user fetch timed out after {self.timeout} seconds."
            )
        except Exception as e:
            logger.error(f"Error getting user by ID: {str(e)}")

        return None

    def _process_user_data(self, user: Dict[str, Any]) -> Dict[str, Any]:
        """Process user data into standard format."""
        try:
            result: Dict[str, Any] = {
                "id": user.get("id"),
                "name": user.get("name"),
                "email": user.get("email"),
                "username": user.get("username"),
                "department": user.get("department"),
                "title": user.get("title"),
                "manager": None,
                "state": user.get("state"),
                "presence": None,
                "phoneNumbers": {},
                "groups": [],
                "skills": [],
                "languages": [],
                "locations": [],
                "profileImage": None,
                "dateLastLogin": user.get("dateLastLogin"),
            }

            # Extract profile image (highest resolution available)
            if user.get("images") and isinstance(user.get("images"), list):
                # Sort by resolution and get the highest
                images = user["images"]
                for res in ["x400", "x300", "x200", "x128", "x96", "x48"]:
                    for img in images:
                        if img.get("resolution") == res and img.get("imageUri"):
                            result["profileImage"] = img["imageUri"]
                            break
                    if result["profileImage"]:
                        break

            # Safe extraction of manager
            if user.get("manager") and isinstance(user.get("manager"), dict):
                result["manager"] = user.get("manager", {}).get("name")

            # Safe extraction of presence
            if user.get("presence") and isinstance(user.get("presence"), dict):
                presence_def = user.get("presence", {}).get("presenceDefinition")
                if presence_def and isinstance(presence_def, dict):
                    result["presence"] = presence_def.get("systemPresence")

            # Safe extraction of phone numbers
            try:
                result["phoneNumbers"] = self._extract_phone_numbers(user)
                if result["phoneNumbers"]:
                    logger.info(f"Extracted phone numbers: {result['phoneNumbers']}")
            except Exception as e:
                logger.error(f"Error extracting phone numbers: {str(e)}")

            # Safe extraction of lists
            for field in ["groups", "skills", "languages", "locations", "queues"]:
                if user.get(field) and isinstance(user.get(field), list):
                    result[field] = []
                    for item in user.get(field, []):
                        if isinstance(item, dict):
                            # Extract name from various possible fields
                            name = None
                            if "name" in item:
                                name = item["name"]
                            elif "groupName" in item:
                                name = item["groupName"]
                            elif field == "groups" and item.get("id"):
                                # For groups without names, look up in cache
                                group_id = item.get("id")
                                name = genesys_cache.get_group_name(str(group_id))
                                if name == group_id:  # Cache miss
                                    logger.debug(f"Group {group_id} not found in cache")
                            elif field == "locations":
                                # Locations might have locationDefinition field
                                if item.get("locationDefinition") and isinstance(
                                    item["locationDefinition"], dict
                                ):
                                    location_id = item["locationDefinition"].get("id")
                                    if location_id:
                                        name = genesys_cache.get_location_name(
                                            str(location_id)
                                        )
                                        if name == location_id:  # Cache miss
                                            logger.debug(
                                                f"Location {location_id} not found in cache"
                                            )
                                elif item.get("id"):
                                    # For locations without names, look up in cache
                                    location_id = item.get("id")
                                    name = genesys_cache.get_location_name(
                                        str(location_id)
                                    )
                                    if name == location_id:  # Cache miss
                                        logger.debug(
                                            f"Location {location_id} not found in cache"
                                        )
                            else:
                                # Use ID as fallback
                                name = item.get("id", "Unknown")
                            result[field].append(name)
                        elif isinstance(item, str):
                            # If the item is just a string (probably an ID)
                            if field == "groups":
                                # Look up group name in cache
                                name = genesys_cache.get_group_name(item)
                                result[field].append(name)
                            elif field == "locations":
                                # Look up location name in cache
                                name = genesys_cache.get_location_name(item)
                                result[field].append(name)
                            else:
                                result[field].append(item)
                        else:
                            result[field].append(str(item))

                    # Sort groups and queues alphabetically
                    if field in ["groups", "queues"]:
                        result[field].sort()

            return result

        except Exception as e:
            logger.error(f"Error processing user data: {str(e)}")
            return {}

    def _get_user_details(
        self, user_id: str, headers: Dict[str, str]
    ) -> Optional[Dict[str, Any]]:
        """Get detailed user information including groups and skills."""
        try:
            # API call to get detailed user info with all expansions
            url = f"{self.base_url}/api/v2/users/{user_id}?expand=groups,skills,languages,locations,manager,presence,profileSkills,certifications,employerInfo,routingStatus,conversationSummary,outOfOffice,geolocation,station,authorization,queues&expand=groups.name"
            logger.info(f"Fetching user details from: {url}")

            response = requests.get(url, headers=headers, timeout=self.timeout)

            if response.status_code == 200:
                user_data = response.json()
                # Log available fields for debugging
                logger.info(f"Available fields in user data: {list(user_data.keys())}")
                if user_data.get("primaryContactInfo"):
                    if isinstance(user_data.get("primaryContactInfo"), dict):
                        logger.info(
                            f"Primary contact info fields: {list(user_data['primaryContactInfo'].keys())}"
                        )
                        logger.info(
                            f"Primary contact info data: {user_data['primaryContactInfo']}"
                        )
                    else:
                        logger.info(
                            f"Primary contact info is not a dict, it's: {type(user_data.get('primaryContactInfo'))}"
                        )
                return dict(user_data)

        except Exception as e:
            logger.error(f"Error getting user details: {str(e)}")

        return None

    def _extract_phone_numbers(self, user: Dict[str, Any]) -> Dict[str, str]:
        """Extract phone numbers from user data."""
        phones = {}

        try:
            # Check primaryContactInfo for phone numbers
            contact_info = user.get("primaryContactInfo")

            # Handle primaryContactInfo as a list
            if contact_info and isinstance(contact_info, list):
                logger.info(
                    f"primaryContactInfo is a list with {len(contact_info)} items"
                )
                for idx, contact in enumerate(contact_info):
                    if isinstance(contact, dict):
                        logger.info(f"Contact {idx} data: {contact}")
                        # Common phone fields
                        if contact.get("mediaType") == "PHONE" and contact.get(
                            "address"
                        ):
                            phone_type = contact.get("type", f"phone_{idx}").lower()
                            phones[phone_type] = contact.get(
                                "display", contact["address"]
                            )

            # Handle primaryContactInfo as a dict (fallback)
            elif contact_info and isinstance(contact_info, dict):
                logger.info(
                    f"Found primaryContactInfo dict with fields: {list(contact_info.keys())}"
                )
                # Check for various phone number fields
                phone_fields = [
                    "phoneNumber",
                    "phoneNumber2",
                    "phoneNumber3",
                    "otherPhone",
                    "mobilePhone",
                    "homePhone",
                    "businessPhone",
                    "address",
                ]

                for phone_type in phone_fields:
                    if contact_info.get(phone_type):
                        phones[phone_type] = contact_info[phone_type]

            # Check for phone numbers in other possible locations
            if user.get("phoneNumber"):
                phones["direct"] = user["phoneNumber"]

            # Check addresses array
            if user.get("addresses") and isinstance(user.get("addresses"), list):
                logger.info(f"Found addresses list with {len(user['addresses'])} items")
                for idx, address in enumerate(user["addresses"]):
                    if isinstance(address, dict):
                        logger.info(f"Address {idx} data: {address}")
                        if address.get("mediaType") == "PHONE":
                            phone_type = address.get("type", f"phone_{idx}").lower()
                            # Don't duplicate if already in phones
                            if phone_type not in phones:
                                if address.get("extension"):
                                    phones[f"{phone_type}_ext"] = address.get(
                                        "extension"
                                    )
                                elif address.get("address"):
                                    phones[phone_type] = address.get(
                                        "display", address["address"]
                                    )

        except Exception as e:
            logger.error(f"Error in _extract_phone_numbers: {str(e)}")

        return {k: str(v) for k, v in phones.items()}


genesys_service = GenesysCloudService()
