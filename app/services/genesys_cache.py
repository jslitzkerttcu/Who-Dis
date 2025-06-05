import os
import requests
from requests.exceptions import Timeout, ConnectionError
import logging
from typing import Dict, Optional
from datetime import datetime, timedelta
from threading import Lock, Thread
import time

logger = logging.getLogger(__name__)


class GenesysCache:
    def __init__(self):
        self.client_id = os.getenv('GENESYS_CLIENT_ID')
        self.client_secret = os.getenv('GENESYS_CLIENT_SECRET')
        self.region = os.getenv('GENESYS_REGION', 'mypurecloud.com')
        self.base_url = f'https://api.{self.region}'
        self.token_url = f'https://login.{self.region}/oauth/token'
        
        self._token = None
        self._token_expiry = None
        self._groups_cache = {}
        self._locations_cache = {}
        self._cache_lock = Lock()
        self._last_cache_update = None
        self._cache_ttl = timedelta(hours=6)  # Refresh cache every 6 hours
        # Timeout configuration for cache operations
        self.cache_timeout = int(os.getenv('GENESYS_CACHE_TIMEOUT', '30'))  # Longer timeout for cache operations
        
        # Start background thread to populate cache
        self._start_cache_refresh()
    
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
                },
                timeout=self.cache_timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                self._token = data['access_token']
                expires_in = data.get('expires_in', 3600)
                self._token_expiry = datetime.now() + timedelta(seconds=expires_in - 60)
                return self._token
                
        except Timeout:
            logger.error(f"Timeout getting access token for cache after {self.cache_timeout} seconds")
        except Exception as e:
            logger.error(f"Error getting access token for cache: {str(e)}")
            
        return None
    
    def _fetch_all_groups(self):
        """Fetch all groups from Genesys Cloud."""
        token = self._get_access_token()
        if not token:
            logger.error("Failed to get token for groups cache")
            return
        
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        
        try:
            # Fetch all groups in one request (up to 500)
            response = requests.get(
                f'{self.base_url}/api/v2/groups',
                headers=headers,
                params={
                    'pageSize': 500  # Max allowed
                },
                timeout=self.cache_timeout
            )
            
            if response.status_code != 200:
                logger.error(f"Failed to fetch groups: {response.status_code} - {response.text}")
                return
            
            data = response.json()
            groups = data.get('entities', [])
            total_count = data.get('total', 0)
            
            with self._cache_lock:
                # Clear old cache
                self._groups_cache.clear()
                
                for group in groups:
                    group_id = group.get('id')
                    group_name = group.get('name', 'Unknown')
                    if group_id:
                        self._groups_cache[group_id] = group_name
            
            self._last_cache_update = datetime.now()
            logger.info(f"Successfully cached {len(groups)} groups (total in system: {total_count})")
            
            # Log cache status
            cache_info = self.get_cache_status()
            logger.info(f"Cache status: {cache_info}")
            
        except Timeout:
            logger.error(f"Timeout fetching groups after {self.cache_timeout} seconds")
        except Exception as e:
            logger.error(f"Error fetching groups for cache: {str(e)}")
    
    def _fetch_all_locations(self):
        """Fetch all locations from Genesys Cloud."""
        token = self._get_access_token()
        if not token:
            logger.error("Failed to get token for locations cache")
            return
        
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        
        try:
            # Fetch all locations in one request (up to 500)
            response = requests.get(
                f'{self.base_url}/api/v2/locations',
                headers=headers,
                params={
                    'pageSize': 500  # Max allowed
                },
                timeout=self.cache_timeout
            )
            
            if response.status_code != 200:
                logger.error(f"Failed to fetch locations: {response.status_code} - {response.text}")
                return
            
            data = response.json()
            locations = data.get('entities', [])
            total_count = data.get('total', 0)
            
            with self._cache_lock:
                # Clear old cache
                self._locations_cache.clear()
                
                for location in locations:
                    location_id = location.get('id')
                    location_name = location.get('name', 'Unknown')
                    if location_id:
                        self._locations_cache[location_id] = location_name
            
            logger.info(f"Successfully cached {len(locations)} locations (total in system: {total_count})")
            
        except Timeout:
            logger.error(f"Timeout fetching locations after {self.cache_timeout} seconds")
        except Exception as e:
            logger.error(f"Error fetching locations for cache: {str(e)}")
    
    def _cache_refresh_worker(self):
        """Background worker to refresh cache periodically."""
        # Initial delay to let the app start
        time.sleep(5)
        
        while True:
            try:
                if (not self._last_cache_update or 
                    datetime.now() - self._last_cache_update > self._cache_ttl):
                    logger.info("Refreshing Genesys cache...")
                    self._fetch_all_groups()
                    self._fetch_all_locations()
                
                # Check every 5 minutes if cache needs refresh
                time.sleep(300)
                
            except Exception as e:
                logger.error(f"Error in cache refresh worker: {str(e)}")
                time.sleep(300)  # Wait 5 minutes before retrying
    
    def _start_cache_refresh(self):
        """Start background thread for cache refresh."""
        thread = Thread(target=self._cache_refresh_worker, daemon=True)
        thread.start()
        logger.info("Started Genesys cache refresh thread")
    
    def get_group_name(self, group_id: str) -> str:
        """Get group name from cache."""
        with self._cache_lock:
            return self._groups_cache.get(group_id, group_id)
    
    def get_location_name(self, location_id: str) -> str:
        """Get location name from cache."""
        with self._cache_lock:
            return self._locations_cache.get(location_id, location_id)
    
    def get_cache_status(self) -> Dict:
        """Get cache status information."""
        with self._cache_lock:
            return {
                'groups_cached': len(self._groups_cache),
                'locations_cached': len(self._locations_cache),
                'last_update': self._last_cache_update.isoformat() if self._last_cache_update else None,
                'cache_age': str(datetime.now() - self._last_cache_update) if self._last_cache_update else None
            }


# Global cache instance
genesys_cache = GenesysCache()