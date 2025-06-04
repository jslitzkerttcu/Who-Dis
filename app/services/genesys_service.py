import os
import requests
from typing import Optional, Dict, Any
import logging
from datetime import datetime, timedelta
from app.services.genesys_cache import genesys_cache

logger = logging.getLogger(__name__)


class GenesysCloudService:
    def __init__(self):
        self.client_id = os.getenv('GENESYS_CLIENT_ID')
        self.client_secret = os.getenv('GENESYS_CLIENT_SECRET')
        self.region = os.getenv('GENESYS_REGION', 'mypurecloud.com')
        self.base_url = f'https://api.{self.region}'
        self.token_url = f'https://login.{self.region}/oauth/token'
        self._token = None
        self._token_expiry = None
        
    def _get_access_token(self) -> Optional[str]:
        """Get access token using client credentials grant."""
        if self._token and self._token_expiry and datetime.now() < self._token_expiry:
            return self._token
            
        try:
            response = requests.post(
                self.token_url,
                data={
                    'grant_type': 'client_credentials',
                    'client_id': self.client_id,
                    'client_secret': self.client_secret
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                self._token = data['access_token']
                expires_in = data.get('expires_in', 3600)
                self._token_expiry = datetime.now() + timedelta(seconds=expires_in - 60)
                return self._token
            else:
                logger.error(f"Failed to get access token: {response.status_code} - {response.text}")
                
        except Exception as e:
            logger.error(f"Error getting access token: {str(e)}")
            
        return None
    
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
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'
            }
            
            # Search by exact email first
            search_body = {
                'pageSize': 25,
                'pageNumber': 1,
                'query': [
                    {
                        'type': 'EXACT',
                        'fields': ['email'],
                        'values': [search_term]
                    }
                ],
                'sortOrder': 'ASC',
                'sortBy': 'email'
            }
            
            response = requests.post(
                f'{self.base_url}/api/v2/users/search',
                headers=headers,
                json=search_body
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('results') and len(data['results']) > 0:
                    user = data['results'][0]
                else:
                    # If no exact match, try searching by username
                    search_body['query'] = [
                        {
                            'type': 'EXACT',
                            'fields': ['username'],
                            'values': [search_term]
                        }
                    ]
                    response = requests.post(
                        f'{self.base_url}/api/v2/users/search',
                        headers=headers,
                        json=search_body
                    )
                    if response.status_code == 200:
                        data = response.json()
                        if data.get('results') and len(data['results']) > 0:
                            user = data['results'][0]
                        else:
                            return None
                    else:
                        return None
                
                user_id = user.get('id')
                if user_id:
                    detailed_user = self._get_user_details(user_id, headers)
                    if detailed_user:
                        user = detailed_user
                
                try:
                    result = {
                        'id': user.get('id'),
                        'name': user.get('name'),
                        'email': user.get('email'),
                        'username': user.get('username'),
                        'department': user.get('department'),
                        'title': user.get('title'),
                        'manager': None,
                        'state': user.get('state'),
                        'presence': None,
                        'phoneNumbers': {},
                        'groups': [],
                        'skills': [],
                        'languages': [],
                        'locations': []
                    }
                    
                    # Safe extraction of manager
                    if user.get('manager') and isinstance(user.get('manager'), dict):
                        result['manager'] = user.get('manager', {}).get('name')
                    
                    # Safe extraction of presence
                    if user.get('presence') and isinstance(user.get('presence'), dict):
                        presence_def = user.get('presence', {}).get('presenceDefinition')
                        if presence_def and isinstance(presence_def, dict):
                            result['presence'] = presence_def.get('systemPresence')
                    
                    # Safe extraction of phone numbers
                    try:
                        result['phoneNumbers'] = self._extract_phone_numbers(user)
                        if result['phoneNumbers']:
                            logger.info(f"Extracted phone numbers: {result['phoneNumbers']}")
                    except Exception as e:
                        logger.error(f"Error extracting phone numbers: {str(e)}")
                    
                    # Safe extraction of lists
                    for field in ['groups', 'skills', 'languages', 'locations', 'queues']:
                        if user.get(field) and isinstance(user.get(field), list):
                            result[field] = []
                            for item in user.get(field):
                                if isinstance(item, dict):
                                    # Extract name from various possible fields
                                    name = None
                                    if 'name' in item:
                                        name = item['name']
                                    elif 'groupName' in item:
                                        name = item['groupName']
                                    elif field == 'groups' and item.get('id'):
                                        # For groups without names, look up in cache
                                        group_id = item.get('id')
                                        name = genesys_cache.get_group_name(group_id)
                                        if name == group_id:  # Cache miss
                                            logger.debug(f"Group {group_id} not found in cache")
                                    else:
                                        # Use ID as fallback
                                        name = item.get('id', 'Unknown')
                                    result[field].append(name)
                                elif isinstance(item, str):
                                    # If the item is just a string (probably an ID)
                                    if field == 'groups':
                                        # Look up group name in cache
                                        name = genesys_cache.get_group_name(item)
                                        result[field].append(name)
                                    else:
                                        result[field].append(item)
                                else:
                                    result[field].append(str(item))
                            
                            # Sort groups and queues alphabetically
                            if field in ['groups', 'queues']:
                                result[field].sort()
                    
                    return result
                    
                except Exception as e:
                    logger.error(f"Error processing user data: {str(e)}")
                    return None
                    
            else:
                logger.error(f"User search failed: {response.status_code} - {response.text}")
                
        except Exception as e:
            logger.error(f"Error searching for user in Genesys: {str(e)}")
            
        return None
    
    def _get_user_details(self, user_id: str, headers: Dict[str, str]) -> Optional[Dict[str, Any]]:
        """Get detailed user information including groups and skills."""
        try:
            # API call to get detailed user info with all expansions
            url = f'{self.base_url}/api/v2/users/{user_id}?expand=groups,skills,languages,locations,manager,presence,profileSkills,certifications,employerInfo,routingStatus,conversationSummary,outOfOffice,geolocation,station,authorization,queues&expand=groups.name'
            logger.info(f"Fetching user details from: {url}")
            
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                user_data = response.json()
                # Log available fields for debugging
                logger.info(f"Available fields in user data: {list(user_data.keys())}")
                if user_data.get('primaryContactInfo'):
                    if isinstance(user_data.get('primaryContactInfo'), dict):
                        logger.info(f"Primary contact info fields: {list(user_data['primaryContactInfo'].keys())}")
                        logger.info(f"Primary contact info data: {user_data['primaryContactInfo']}")
                    else:
                        logger.info(f"Primary contact info is not a dict, it's: {type(user_data.get('primaryContactInfo'))}")
                return user_data
                
        except Exception as e:
            logger.error(f"Error getting user details: {str(e)}")
            
        return None
    
    def _extract_phone_numbers(self, user: Dict[str, Any]) -> Dict[str, str]:
        """Extract phone numbers from user data."""
        phones = {}
        
        try:
            # Check primaryContactInfo for phone numbers
            contact_info = user.get('primaryContactInfo')
            
            # Handle primaryContactInfo as a list
            if contact_info and isinstance(contact_info, list):
                logger.info(f"primaryContactInfo is a list with {len(contact_info)} items")
                for idx, contact in enumerate(contact_info):
                    if isinstance(contact, dict):
                        logger.info(f"Contact {idx} data: {contact}")
                        # Common phone fields
                        if contact.get('mediaType') == 'PHONE' and contact.get('address'):
                            phone_type = contact.get('type', f'phone_{idx}').lower()
                            phones[phone_type] = contact.get('display', contact['address'])
                            
            # Handle primaryContactInfo as a dict (fallback)
            elif contact_info and isinstance(contact_info, dict):
                logger.info(f"Found primaryContactInfo dict with fields: {list(contact_info.keys())}")
                # Check for various phone number fields
                phone_fields = ['phoneNumber', 'phoneNumber2', 'phoneNumber3', 
                               'otherPhone', 'mobilePhone', 'homePhone', 'businessPhone', 'address']
                
                for phone_type in phone_fields:
                    if contact_info.get(phone_type):
                        phones[phone_type] = contact_info[phone_type]
            
            # Check for phone numbers in other possible locations
            if user.get('phoneNumber'):
                phones['direct'] = user['phoneNumber']
                
            # Check addresses array
            if user.get('addresses') and isinstance(user.get('addresses'), list):
                logger.info(f"Found addresses list with {len(user['addresses'])} items")
                for idx, address in enumerate(user['addresses']):
                    if isinstance(address, dict):
                        logger.info(f"Address {idx} data: {address}")
                        if address.get('mediaType') == 'PHONE':
                            phone_type = address.get('type', f'phone_{idx}').lower()
                            # Don't duplicate if already in phones
                            if phone_type not in phones:
                                if address.get('extension'):
                                    phones[f"{phone_type}_ext"] = address.get('extension')
                                elif address.get('address'):
                                    phones[phone_type] = address.get('display', address['address'])
                        
        except Exception as e:
            logger.error(f"Error in _extract_phone_numbers: {str(e)}")
                    
        return phones


genesys_service = GenesysCloudService()