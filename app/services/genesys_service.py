"""Genesys Cloud service with simplified configuration."""

from typing import Optional, Dict, Any, List
import logging
from app.services.base import BaseAPITokenService
from app.services.genesys_cache_db import genesys_cache_db as genesys_cache
from app.interfaces.search_service import ISearchService
from app.interfaces.token_service import ITokenService

logger = logging.getLogger(__name__)


class GenesysCloudService(BaseAPITokenService, ISearchService, ITokenService):
    def __init__(self):
        super().__init__(config_prefix="genesys", token_service_name="genesys")
        # Region auth mapping for Genesys Cloud regions
        self._region_auth_mapping = {
            "mypurecloud.com": "login.mypurecloud.com",
            "use2.us-gov-pure.cloud": "login.use2.us-gov-pure.cloud",
            "usw2.pure.cloud": "login.usw2.pure.cloud",
            "cac1.pure.cloud": "login.cac1.pure.cloud",
            "mypurecloud.ie": "login.mypurecloud.ie",
            "euw2.pure.cloud": "login.euw2.pure.cloud",
            "mypurecloud.de": "login.mypurecloud.de",
            "euc2.pure.cloud": "login.euc2.pure.cloud",
            "aps1.pure.cloud": "login.aps1.pure.cloud",
            "mypurecloud.jp": "login.mypurecloud.jp",
            "apne2.pure.cloud": "login.apne2.pure.cloud",
            "apne3.pure.cloud": "login.apne3.pure.cloud",
            "mypurecloud.com.au": "login.mypurecloud.com.au",
            "sae1.pure.cloud": "login.sae1.pure.cloud",
            "mec1.pure.cloud": "login.mec1.pure.cloud",
        }

    @property
    def client_id(self):
        return self._get_config("client_id")

    @property
    def client_secret(self):
        return self._get_config("client_secret")

    @property
    def region(self):
        return self._get_config("region", "mypurecloud.com")

    @property
    def base_url(self):
        return f"https://api.{self.region}"

    @property
    def token_url(self):
        auth_domain = self._region_auth_mapping.get(self.region, f"login.{self.region}")
        return f"https://{auth_domain}/oauth/token"

    @property
    def service_name(self) -> str:
        """Get the name of this search service."""
        return "genesys"

    @property
    def token_service_name(self) -> str:
        """Get the name used for token storage/identification."""
        return "genesys"

    def _fetch_new_token(self) -> Optional[str]:
        """Fetch new token from Genesys Cloud using client credentials."""
        try:
            # Use standard HTTP requests for OAuth2 client credentials flow
            response = self._make_request(
                "POST",
                self.token_url,
                token=None,  # No auth needed for token request
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

            data = self._handle_response(response)
            access_token = data["access_token"]
            expires_in = data.get("expires_in", 3600)

            # Store token using base class method
            self._store_token(access_token, expires_in)
            return str(access_token)

        except Exception as e:
            logger.error(f"Error getting Genesys access token: {str(e)}")
            return None

    def test_connection(self) -> bool:
        """Test connection to Genesys API with fresh token (no cache)."""
        # Clear cache to force reload of configuration
        self._clear_config_cache()

        # Check if credentials are configured
        client_id = self.client_id
        client_secret = self.client_secret

        if not client_id or not client_secret:
            logger.error("Genesys client ID or secret not configured")
            return False

        try:
            # Get fresh token (bypasses cache)
            token = self._fetch_new_token()
            if not token:
                logger.error("Failed to obtain Genesys API token")
                return False

            # Test the token with a simple API call using base class method
            test_url = f"{self.base_url}/api/v2/organizations/me"
            response = self._make_request("GET", test_url, token, timeout=5)

            if response.status_code == 200:
                logger.debug("Genesys API connection test successful")
                return True
            else:
                logger.error(
                    f"Genesys API test failed with status: {response.status_code}"
                )
                return False

        except Exception as e:
            logger.error(f"Error testing Genesys connection: {str(e)}")
            return False

    def search_user(self, search_term: str) -> Optional[Dict[str, Any]]:
        """
        Search for a user in Genesys Cloud by email or username.
        Returns user profile information.
        """
        token = self.get_access_token()
        if not token:
            logger.error("Failed to get access token")
            return None

        # Use base class method to normalize search terms
        search_queries = self._normalize_search_term(search_term)
        logger.debug(f"Searching Genesys Cloud for user with queries: {search_queries}")

        for query in search_queries:
            try:
                # Use the general search API which is more flexible
                search_payload = {
                    "query": [
                        {
                            "fields": ["name", "email", "username"],
                            "value": query,
                            "type": "CONTAINS",
                        }
                    ],
                    "expand": [
                        "groups",
                        "dateLastLogin",
                        "skills",
                        "languages",
                        "routingStatus",
                        "addresses",
                        "locations",
                    ],
                }
                logger.info(f"Genesys search URL: {self.base_url}/api/v2/users/search")
                logger.info(f"Genesys search payload: {search_payload}")

                response = self._make_request(
                    "POST",
                    f"{self.base_url}/api/v2/users/search",
                    token,
                    json=search_payload,
                )

                data = self._handle_response(response)
                results = data.get("results", [])
                logger.info(f"Genesys search response: {len(results)} results found")

                if results:
                    # Check if we have exactly one result
                    if len(results) == 1:
                        user = results[0]
                        logger.info(
                            f"Found single user: {user.get('name')} ({user.get('email')})"
                        )
                        # Process the user data with all expanded fields
                        return self._process_expanded_user_data(user)

                    # Multiple results - use base class method to format them
                    logger.info(f"Found {len(results)} users matching '{query}'")

                    # Get basic info for each result to allow selection
                    users_list = []
                    for result in results[:10]:  # Limit to first 10
                        users_list.append(
                            {
                                "id": result.get("id"),
                                "name": result.get("name"),
                                "email": result.get("email"),
                                "username": result.get("username"),
                                "department": result.get("department"),
                                "title": result.get("title"),
                                "dateLastLogin": result.get("dateLastLogin"),
                            }
                        )

                    return self._format_multiple_results(users_list, len(results))

            except (TimeoutError, ConnectionError):
                # Base class already handles these with proper error messages
                raise
            except Exception as e:
                logger.error(f"Error searching for user in Genesys: {str(e)}")
                raise

        return None

    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific user by ID."""
        token = self.get_access_token()
        if not token:
            logger.error("Failed to get access token")
            return None

        try:
            # Get user details
            response = self._make_request(
                "GET",
                f"{self.base_url}/api/v2/users/{user_id}",
                token,
                params={
                    "expand": "groups,dateLastLogin,skills,languages,routingStatus,addresses,locations"
                },
            )

            user = self._handle_response(response)

            # Queues will be handled if included in the user data
            queues: List[Dict[str, Any]] = []

            # Process skills
            skills = []
            for skill in user.get("skills", []):
                skill_name = genesys_cache.get_skill_name(skill.get("id"))
                if skill_name:
                    skills.append(
                        {
                            "id": skill.get("id"),
                            "name": skill_name,
                            "proficiency": skill.get("proficiency", 0),
                        }
                    )

            # Process groups
            groups = []
            for group in user.get("groups", []):
                # Get cached group name
                group_name = genesys_cache.get_group_name(group.get("id"))
                if group_name:
                    groups.append({"id": group.get("id"), "name": group_name})

            # Process locations
            locations = []
            for location in user.get("locations", []):
                location_info = genesys_cache.get_location_info(location.get("id"))
                if location_info:
                    locations.append(location_info)

            # Log user data structure for debugging
            logger.debug(f"User contact info: {user.get('contact', {})}")
            logger.debug(f"User addresses: {user.get('addresses', [])}")

            phone_numbers = self._extract_phone_numbers(user)
            logger.info(
                f"Extracted phone numbers for {user.get('name')}: {phone_numbers}"
            )

            return {
                "id": user.get("id"),
                "username": user.get("username"),
                "email": user.get("email"),
                "name": user.get("name"),
                "displayName": user.get("name"),
                "title": user.get("title"),
                "department": user.get("department"),
                "state": user.get("state"),
                "presence": user.get("presence", {})
                .get("presenceDefinition", {})
                .get("systemPresence"),
                "skills": skills,
                "queues": queues,
                "groups": groups,
                "locations": locations,
                "phoneNumbers": phone_numbers,
                "manager": user.get("manager"),
                "images": user.get("images", []),
                "addresses": user.get(
                    "addresses", []
                ),  # Include raw addresses for debugging
                "dateLastLogin": user.get("dateLastLogin"),
            }

        except Exception as e:
            logger.error(f"Error getting user details: {str(e)}")

        return None

    def _process_expanded_user_data(self, user: Dict[str, Any]) -> Dict[str, Any]:
        """Process user data that already has expanded fields from search results."""
        # Process skills
        skills = []
        for skill in user.get("skills", []):
            skill_name = genesys_cache.get_skill_name(skill.get("id"))
            if skill_name:
                skills.append(
                    {
                        "id": skill.get("id"),
                        "name": skill_name,
                        "proficiency": skill.get("proficiency", 0),
                    }
                )

        # Process groups
        groups = []
        for group in user.get("groups", []):
            # Get cached group name
            group_name = genesys_cache.get_group_name(group.get("id"))
            if group_name:
                groups.append({"id": group.get("id"), "name": group_name})

        # Process locations
        locations = []
        for location in user.get("locations", []):
            location_info = genesys_cache.get_location_info(location.get("id"))
            if location_info:
                locations.append(location_info)

        # Process queues (if included in expand)
        queues = []
        if user.get("queues"):
            for queue in user.get("queues", []):
                queues.append({"id": queue.get("id"), "name": queue.get("name")})

        # Log user data structure for debugging
        logger.info(f"Processing user: {user.get('name')}")
        logger.info(f"User contact info: {user.get('contact', {})}")
        logger.info(f"User addresses: {user.get('addresses', [])}")
        logger.info(f"User dateLastLogin: {user.get('dateLastLogin')}")
        logger.info(f"User primaryContactInfo: {user.get('primaryContactInfo')}")

        phone_numbers = self._extract_phone_numbers(user)
        logger.info(f"Extracted phone numbers for {user.get('name')}: {phone_numbers}")

        return {
            "id": user.get("id"),
            "username": user.get("username"),
            "email": user.get("email"),
            "name": user.get("name"),
            "displayName": user.get("name"),
            "title": user.get("title"),
            "department": user.get("department"),
            "division": user.get("division", {}).get("name")
            if user.get("division")
            else None,
            "state": user.get("state"),
            "presence": user.get("presence", {})
            .get("presenceDefinition", {})
            .get("systemPresence"),
            "skills": skills,
            "queues": queues,
            "groups": groups,
            "locations": locations,
            "phoneNumbers": phone_numbers,
            "manager": user.get("manager"),
            "images": user.get("images", []),
            "addresses": user.get(
                "addresses", []
            ),  # Include raw addresses for debugging
            "dateLastLogin": user.get("dateLastLogin"),
        }

    def _extract_phone_numbers(self, user: Dict[str, Any]) -> Dict[str, Any]:
        """Extract phone numbers from user data."""
        phone_numbers = {}

        try:
            # Primary contact info - can be a list
            primary_contact = user.get("primaryContactInfo", [])
            if isinstance(primary_contact, list):
                for contact in primary_contact:
                    if (
                        isinstance(contact, dict)
                        and contact.get("mediaType") == "PHONE"
                    ):
                        address = contact.get("address")
                        if address:
                            phone_numbers["primary"] = address

            # Additional phone numbers from addresses array
            addresses = user.get("addresses", [])
            if isinstance(addresses, list):
                logger.debug(f"Found {len(addresses)} addresses")
                for address in addresses:
                    if isinstance(address, dict):
                        # Process each address

                        # Check for PHONE mediaType OR type field
                        if (
                            address.get("mediaType") == "PHONE"
                            or address.get("type") == "PHONE"
                        ):
                            # For WORK2, the extension is in the "extension" field, not "address"
                            if address.get("type") == "WORK2" and address.get(
                                "extension"
                            ):
                                number = address.get("extension")
                            else:
                                number = address.get("address")

                            name = address.get("name", "")
                            addr_type = address.get("type", "")

                            logger.debug(
                                f"Found phone - name: {name}, type: {addr_type}, number: {number}"
                            )

                            if number:
                                name_lower = name.lower()
                                # Map common phone types
                                if "work phone 2" in name_lower or addr_type == "WORK2":
                                    phone_numbers["extension"] = number
                                    phone_numbers["work2"] = number
                                elif (
                                    "work phone 3" in name_lower or addr_type == "WORK3"
                                ):
                                    phone_numbers["work3"] = number
                                elif (
                                    ("work" in name_lower or addr_type == "WORK")
                                    and "work2" not in phone_numbers
                                    and "work3" not in phone_numbers
                                ):
                                    phone_numbers["work"] = number
                                elif (
                                    "mobile" in name_lower
                                    or "cell" in name_lower
                                    or addr_type == "MOBILE"
                                ):
                                    phone_numbers["mobile"] = number
                                elif "home" in name_lower or addr_type == "HOME":
                                    phone_numbers["home"] = number
                                else:
                                    # Store with sanitized name
                                    key = (
                                        name_lower.replace(" ", "_")
                                        if name
                                        else addr_type.lower()
                                    )
                                    if key:
                                        phone_numbers[key] = number

            # Additional phone numbers from contact list (legacy format)
            contact_info = user.get("contact")
            if contact_info and isinstance(contact_info, dict):
                phone_list = contact_info.get("phoneNumbers", [])
                if phone_list:
                    for phone in phone_list:
                        number = phone.get("number")
                        phone_type = phone.get("type", "").lower()
                        if number and phone_type and phone_type not in phone_numbers:
                            phone_numbers[phone_type] = number

        except Exception as e:
            logger.error(f"Error extracting phone numbers: {str(e)}")

        return phone_numbers


genesys_service = GenesysCloudService()
