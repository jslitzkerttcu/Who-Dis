"""Search enhancement service for adding data warehouse data to search results."""

import logging
from typing import Optional, Dict, Any
from app.services.data_warehouse_service import data_warehouse_service

logger = logging.getLogger(__name__)


class SearchEnhancer:
    """Service to enhance search results with data warehouse information."""

    def enhance_search_results(self, search_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enhance search results with data warehouse information.
        
        Args:
            search_results: Dictionary containing azureAD and genesys search results
            
        Returns:
            Enhanced search results with keystone data added
        """
        enhanced_results = search_results.copy()
        
        # Get Azure AD result
        azure_ad_result = search_results.get('azureAD')
        if not azure_ad_result:
            # No Azure AD result to enhance
            enhanced_results['keystone'] = None
            enhanced_results['keystone_error'] = 'No Azure AD data available for Keystone matching'
            return enhanced_results
        
        # Handle multiple Azure AD results
        if search_results.get('azureAD_multiple', False):
            enhanced_results['keystone'] = None
            enhanced_results['keystone_error'] = 'Multiple Azure AD users found - select specific user to view Keystone data'
            enhanced_results['keystone_multiple'] = False
            return enhanced_results
        
        # Extract UPN from Azure AD result
        upn = self._extract_upn_from_azure_result(azure_ad_result)
        if not upn:
            enhanced_results['keystone'] = None
            enhanced_results['keystone_error'] = 'No UPN found in Azure AD data'
            enhanced_results['keystone_multiple'] = False
            return enhanced_results
        
        # Get data warehouse data
        try:
            keystone_data = data_warehouse_service.get_user_data(upn)
            if keystone_data:
                enhanced_results['keystone'] = self._format_keystone_data(keystone_data)
                enhanced_results['keystone_error'] = None
            else:
                enhanced_results['keystone'] = None
                enhanced_results['keystone_error'] = f'No Keystone data found for {upn}'
            
            enhanced_results['keystone_multiple'] = False
            
        except Exception as e:
            logger.error(f"Error getting Keystone data for {upn}: {str(e)}")
            enhanced_results['keystone'] = None
            enhanced_results['keystone_error'] = 'Error retrieving Keystone data'
            enhanced_results['keystone_multiple'] = False
        
        return enhanced_results
    
    def _extract_upn_from_azure_result(self, azure_result: Dict[str, Any]) -> Optional[str]:
        """
        Extract UPN from Azure AD search result.
        
        Args:
            azure_result: Azure AD search result
            
        Returns:
            UPN string or None if not found
        """
        if not azure_result:
            return None
        
        # Try different possible UPN field names
        upn_fields = ['userPrincipalName', 'upn', 'email', 'mail']
        
        for field in upn_fields:
            upn = azure_result.get(field)
            if upn and '@' in upn:  # Basic UPN validation
                return upn.lower()  # Normalize to lowercase
        
        return None
    
    def _format_keystone_data(self, keystone_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format keystone data for search results display.
        
        Args:
            keystone_data: Raw keystone data from cache
            
        Returns:
            Formatted keystone data for UI
        """
        # Determine lock status
        ks_login_lock = keystone_data.get('ks_login_lock')
        is_locked = ks_login_lock == 'L' if ks_login_lock else False
        lock_status = 'Locked' if is_locked else 'Unlocked'
        
        # Format datetime
        ks_last_login_time = keystone_data.get('ks_last_login_time')
        last_login_formatted = None
        if ks_last_login_time:
            try:
                from datetime import datetime
                if isinstance(ks_last_login_time, str):
                    # Parse ISO format
                    dt = datetime.fromisoformat(ks_last_login_time.replace('Z', '+00:00'))
                    last_login_formatted = dt.strftime('%m/%d/%Y %I:%M %p')
                else:
                    last_login_formatted = ks_last_login_time.strftime('%m/%d/%Y %I:%M %p')
            except Exception as e:
                logger.warning(f"Error formatting datetime {ks_last_login_time}: {str(e)}")
                last_login_formatted = str(ks_last_login_time) if ks_last_login_time else None
        
        # Determine role mismatch
        live_role = keystone_data.get('live_role')
        expected_role = keystone_data.get('keystone_expected_role')
        
        role_mismatch = None
        role_warning_level = None
        role_warning_message = None
        
        if expected_role and live_role:
            if live_role != expected_role:
                role_mismatch = True
                role_warning_level = 'high'
                role_warning_message = f"Role mismatch: Expected '{expected_role}' but user has '{live_role}'. This is a security concern."
        elif live_role and not expected_role:
            role_mismatch = True
            role_warning_level = 'medium'
            role_warning_message = f"Role '{live_role}' not found in role mapping list. Please verify role assignment."
        
        return {
            'service': 'keystone',
            'upn': keystone_data.get('upn'),
            'user_serial': keystone_data.get('ks_user_serial'),
            'last_login_time': ks_last_login_time,
            'last_login_formatted': last_login_formatted,
            'login_locked': is_locked,
            'lock_status': lock_status,
            'live_role': live_role,
            'test_role': keystone_data.get('test_role'),
            'ukg_job_code': keystone_data.get('ukg_job_code'),
            'expected_role': expected_role,
            'role_mismatch': role_mismatch,
            'role_warning_level': role_warning_level,
            'role_warning_message': role_warning_message,
            'last_cached': keystone_data.get('last_cached')
        }


# Create singleton instance
search_enhancer = SearchEnhancer()