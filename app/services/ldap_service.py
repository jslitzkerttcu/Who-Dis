import os
from typing import Optional, Dict, Any, List
from ldap3 import Server, Connection, ALL, SUBTREE
from ldap3.core.exceptions import LDAPException
import logging

logger = logging.getLogger(__name__)


class LDAPService:
    def __init__(self):
        self.host = os.getenv('LDAP_HOST', 'ldap://localhost')
        self.port = int(os.getenv('LDAP_PORT', '389'))
        self.use_ssl = os.getenv('LDAP_USE_SSL', 'False').lower() == 'true'
        self.bind_dn = os.getenv('LDAP_BIND_DN')
        self.bind_password = os.getenv('LDAP_BIND_PASSWORD')
        self.base_dn = os.getenv('LDAP_BASE_DN')
        self.user_search_base = os.getenv('LDAP_USER_SEARCH_BASE', self.base_dn)
        
    def search_user(self, search_term: str) -> Optional[Dict[str, Any]]:
        """
        Search for a user in Active Directory by username or email.
        Returns user information including displayName, mail, telephoneNumber, and groupMembership.
        """
        logger.info(f"LDAP search starting for term: {search_term}")
        logger.info(f"LDAP config - Host: {self.host}, Port: {self.port}, SSL: {self.use_ssl}")
        logger.info(f"LDAP config - Bind DN: {self.bind_dn}, Base DN: {self.base_dn}")
        logger.info(f"LDAP config - User search base: {self.user_search_base}")
        
        try:
            logger.info(f"Creating LDAP server connection to {self.host}:{self.port}")
            server = Server(self.host, port=self.port, use_ssl=self.use_ssl, get_info=ALL)
            
            logger.info(f"Attempting to bind as {self.bind_dn}")
            with Connection(server, user=self.bind_dn, password=self.bind_password, auto_bind=True) as conn:
                logger.info(f"Successfully bound to LDAP server")
                # If search term contains @, also search for username without domain
                search_terms = [search_term]
                if '@' in search_term:
                    username_only = search_term.split('@')[0]
                    search_terms.append(username_only)
                    logger.info(f"Email detected, also searching for username: {username_only}")
                
                # Build search filter with all variations
                filter_parts = []
                for term in search_terms:
                    filter_parts.extend([
                        f'(sAMAccountName={term})',
                        f'(mail={term})',
                        f'(userPrincipalName={term})'
                    ])
                
                search_filter = f'(|{" ".join(filter_parts)})'
                
                attributes = ['displayName', 'mail', 'telephoneNumber', 'memberOf', 
                             'sAMAccountName', 'userPrincipalName', 'department', 'title',
                             'userAccountControl', 'lockoutTime', 'badPwdCount', 'employeeID',
                             'ipPhone', 'extensionAttribute4', 'thumbnailPhoto', 'manager']
                
                logger.info(f"Searching with filter: {search_filter}")
                logger.info(f"Search base: {self.user_search_base}")
                logger.info(f"Attributes requested: {attributes}")
                
                # First try the specific user search base
                conn.search(
                    search_base=self.user_search_base,
                    search_filter=search_filter,
                    search_scope=SUBTREE,
                    attributes=attributes
                )
                
                logger.info(f"Search in {self.user_search_base} completed. Found {len(conn.entries)} entries")
                
                # If no results, try searching from the base DN
                if len(conn.entries) == 0:
                    logger.info(f"No results in user OU, trying broader search from {self.base_dn}")
                    conn.search(
                        search_base=self.base_dn,
                        search_filter=search_filter,
                        search_scope=SUBTREE,
                        attributes=attributes
                    )
                    logger.info(f"Broader search completed. Found {len(conn.entries)} entries")
                
                if conn.entries:
                    entry = conn.entries[0]
                    logger.info(f"Processing entry: {entry.entry_dn}")
                    
                    groups = []
                    if hasattr(entry, 'memberOf') and entry.memberOf:
                        groups = self._parse_group_names(entry.memberOf.values)
                        logger.info(f"Found {len(groups)} groups")
                    
                    # Parse account status
                    enabled = True
                    locked = False
                    if hasattr(entry, 'userAccountControl'):
                        uac = int(entry.userAccountControl.value) if entry.userAccountControl else 0
                        enabled = not (uac & 2)  # ACCOUNTDISABLE flag
                        logger.info(f"UserAccountControl: {uac}, Enabled: {enabled}")
                    
                    if hasattr(entry, 'lockoutTime') and entry.lockoutTime and entry.lockoutTime.value:
                        # lockoutTime needs to be checked more carefully
                        try:
                            lockout_value = entry.lockoutTime.value
                            # Handle different types of lockoutTime values
                            if isinstance(lockout_value, (int, float)):
                                # Windows FileTime: 0 means not locked
                                locked = lockout_value > 0
                            elif isinstance(lockout_value, str):
                                # String representation of FileTime
                                locked = int(lockout_value) > 0
                            elif hasattr(lockout_value, 'year'):  # datetime object
                                # If it's a valid datetime in the past, account is locked
                                # DateTime(1601, 1, 1) is the epoch for Windows FileTime and means not locked
                                locked = lockout_value.year > 1601
                            else:
                                locked = False
                            logger.info(f"LockoutTime type: {type(lockout_value)}, value: {lockout_value}, Locked: {locked}")
                        except Exception as e:
                            logger.error(f"Error parsing lockoutTime: {str(e)}")
                            locked = False
                    else:
                        # No lockoutTime attribute means not locked
                        locked = False
                    
                    # Extract phone numbers - can have both
                    phone_numbers = {}
                    
                    if hasattr(entry, 'extensionAttribute4') and entry.extensionAttribute4:
                        phone_numbers['genesys'] = str(entry.extensionAttribute4)
                    
                    if hasattr(entry, 'telephoneNumber') and entry.telephoneNumber:
                        phone_numbers['teams'] = str(entry.telephoneNumber)
                    
                    # Extract extension from ipPhone
                    extension = str(entry.ipPhone) if hasattr(entry, 'ipPhone') and entry.ipPhone else None
                    
                    # Extract thumbnail photo if available
                    thumbnail_photo = None
                    if hasattr(entry, 'thumbnailPhoto') and entry.thumbnailPhoto:
                        import base64
                        try:
                            photo_bytes = entry.thumbnailPhoto.value
                            if photo_bytes:
                                thumbnail_photo = f"data:image/jpeg;base64,{base64.b64encode(photo_bytes).decode('utf-8')}"
                                logger.info(f"Found thumbnail photo, size: {len(photo_bytes)} bytes")
                        except Exception as e:
                            logger.error(f"Error encoding thumbnail photo: {str(e)}")
                    
                    # Extract manager name from DN
                    manager_name = None
                    if hasattr(entry, 'manager') and entry.manager:
                        try:
                            manager_dn = str(entry.manager)
                            # Extract CN from manager DN (e.g., "CN=John Doe,OU=Users,DC=ttcu,DC=com")
                            if manager_dn.startswith('CN='):
                                manager_name = manager_dn.split(',')[0][3:]  # Remove "CN="
                        except Exception as e:
                            logger.error(f"Error parsing manager DN: {str(e)}")
                    
                    user_info = {
                        'displayName': str(entry.displayName) if hasattr(entry, 'displayName') else None,
                        'mail': str(entry.mail) if hasattr(entry, 'mail') else None,
                        'phoneNumbers': phone_numbers,
                        'extension': extension,
                        'employeeID': str(entry.employeeID) if hasattr(entry, 'employeeID') and entry.employeeID else None,
                        'sAMAccountName': str(entry.sAMAccountName) if hasattr(entry, 'sAMAccountName') else None,
                        'userPrincipalName': str(entry.userPrincipalName) if hasattr(entry, 'userPrincipalName') else None,
                        'department': str(entry.department) if hasattr(entry, 'department') else None,
                        'title': str(entry.title) if hasattr(entry, 'title') else None,
                        'manager': manager_name,
                        'groupMembership': sorted(groups),  # Sort alphabetically
                        'enabled': enabled,
                        'locked': locked,
                        'thumbnailPhoto': thumbnail_photo
                    }
                    
                    logger.info(f"Returning user info for: {user_info.get('displayName', 'Unknown')}")
                    return user_info
                else:
                    logger.info("No entries found in LDAP search")
                    return None
                    
        except LDAPException as e:
            logger.error(f"LDAP search error: {str(e)}")
            logger.error(f"LDAP Exception type: {type(e).__name__}")
        except Exception as e:
            logger.error(f"Unexpected error during LDAP search: {str(e)}")
            logger.error(f"Exception type: {type(e).__name__}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            
        return None
    
    def _parse_group_names(self, group_dns: List[str]) -> List[str]:
        """Extract group names from distinguished names."""
        groups = []
        for dn in group_dns:
            try:
                cn_part = dn.split(',')[0]
                if cn_part.startswith('CN='):
                    groups.append(cn_part[3:])
            except:
                continue
        return groups


ldap_service = LDAPService()