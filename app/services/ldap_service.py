import os
from typing import Optional, Dict, Any, List
from ldap3 import Server, Connection, ALL, SUBTREE
from ldap3.core.exceptions import (
    LDAPException,
    LDAPSocketOpenError,
    LDAPSocketReceiveError,
)
import logging

logger = logging.getLogger(__name__)


class LDAPService:
    def __init__(self):
        self.host = os.getenv("LDAP_HOST", "ldap://localhost")
        self.port = int(os.getenv("LDAP_PORT", "389"))
        self.use_ssl = os.getenv("LDAP_USE_SSL", "False").lower() == "true"
        self.bind_dn = os.getenv("LDAP_BIND_DN")
        self.bind_password = os.getenv("LDAP_BIND_PASSWORD")
        self.base_dn = os.getenv("LDAP_BASE_DN")
        self.user_search_base = os.getenv("LDAP_USER_SEARCH_BASE", self.base_dn)
        # Timeout configuration
        self.connect_timeout = int(
            os.getenv("LDAP_CONNECT_TIMEOUT", "5")
        )  # Connection timeout in seconds
        self.operation_timeout = int(
            os.getenv("LDAP_OPERATION_TIMEOUT", "10")
        )  # Operation timeout in seconds

    def search_user(self, search_term: str) -> Optional[Dict[str, Any]]:
        """
        Search for a user in Active Directory by username or email.
        Returns user information including displayName, mail, telephoneNumber, and groupMembership.
        """
        logger.info(f"LDAP search starting for term: {search_term}")
        logger.info(
            f"LDAP config - Host: {self.host}, Port: {self.port}, SSL: {self.use_ssl}"
        )
        logger.info(f"LDAP config - Bind DN: {self.bind_dn}, Base DN: {self.base_dn}")
        logger.info(f"LDAP config - User search base: {self.user_search_base}")

        try:
            logger.info(f"Creating LDAP server connection to {self.host}:{self.port}")
            logger.info(
                f"Timeouts - Connect: {self.connect_timeout}s, Operation: {self.operation_timeout}s"
            )
            server = Server(
                self.host,
                port=self.port,
                use_ssl=self.use_ssl,
                get_info=ALL,
                connect_timeout=self.connect_timeout,
            )

            logger.info(f"Attempting to bind as {self.bind_dn}")
            with Connection(
                server,
                user=self.bind_dn,
                password=self.bind_password,
                auto_bind=True,
                receive_timeout=self.operation_timeout,
            ) as conn:
                logger.info("Successfully bound to LDAP server")
                # If search term contains @, also search for username without domain
                search_terms = [search_term]
                if "@" in search_term:
                    username_only = search_term.split("@")[0]
                    search_terms.append(username_only)
                    logger.info(
                        f"Email detected, also searching for username: {username_only}"
                    )

                # Build search filter with all variations including fuzzy matching
                filter_parts = []
                for term in search_terms:
                    # Exact matches
                    filter_parts.extend(
                        [
                            f"(sAMAccountName={term})",
                            f"(mail={term})",
                            f"(userPrincipalName={term})",
                        ]
                    )
                    # Fuzzy/wildcard matches for partial strings
                    if len(term) >= 3:  # Only do fuzzy search for terms 3+ characters
                        filter_parts.extend(
                            [
                                f"(sAMAccountName=*{term}*)",
                                f"(mail=*{term}*)",
                                f"(userPrincipalName=*{term}*)",
                                f"(displayName=*{term}*)",
                                f"(givenName=*{term}*)",
                                f"(sn=*{term}*)",  # surname
                            ]
                        )

                # Remove duplicates while preserving order
                unique_filters = []
                seen = set()
                for f in filter_parts:
                    if f not in seen:
                        seen.add(f)
                        unique_filters.append(f)

                search_filter = f"(&(objectClass=user)(objectCategory=person)(|{' '.join(unique_filters)}))"

                attributes = [
                    "displayName",
                    "mail",
                    "telephoneNumber",
                    "memberOf",
                    "sAMAccountName",
                    "userPrincipalName",
                    "department",
                    "title",
                    "userAccountControl",
                    "lockoutTime",
                    "badPwdCount",
                    "employeeID",
                    "ipPhone",
                    "extensionAttribute4",
                    "thumbnailPhoto",
                    "manager",
                    "pwdLastSet",
                    "accountExpires",
                    "msDS-UserPasswordExpiryTimeComputed",
                ]

                logger.info(f"Searching with filter: {search_filter}")
                logger.info(f"Search base: {self.user_search_base}")
                logger.info(f"Attributes requested: {attributes}")

                # First try the specific user search base
                conn.search(
                    search_base=self.user_search_base,
                    search_filter=search_filter,
                    search_scope=SUBTREE,
                    attributes=attributes,
                )

                logger.info(
                    f"Search in {self.user_search_base} completed. Found {len(conn.entries)} entries"
                )

                # If no results, try searching from the base DN
                if len(conn.entries) == 0:
                    logger.info(
                        f"No results in user OU, trying broader search from {self.base_dn}"
                    )
                    conn.search(
                        search_base=self.base_dn,
                        search_filter=search_filter,
                        search_scope=SUBTREE,
                        attributes=attributes,
                    )
                    logger.info(
                        f"Broader search completed. Found {len(conn.entries)} entries"
                    )

                if conn.entries:
                    # If we have multiple results from fuzzy search, return them for selection
                    if len(conn.entries) > 1:
                        logger.info(f"Multiple LDAP entries found: {len(conn.entries)}")
                        results = []
                        for entry in conn.entries[:10]:  # Limit to 10 results
                            try:
                                user_data = {
                                    "dn": str(entry.entry_dn),
                                    "displayName": str(entry.displayName)
                                    if hasattr(entry, "displayName")
                                    and entry.displayName
                                    else None,
                                    "mail": str(entry.mail)
                                    if hasattr(entry, "mail") and entry.mail
                                    else None,
                                    "sAMAccountName": str(entry.sAMAccountName)
                                    if hasattr(entry, "sAMAccountName")
                                    and entry.sAMAccountName
                                    else None,
                                    "department": str(entry.department)
                                    if hasattr(entry, "department") and entry.department
                                    else None,
                                    "title": str(entry.title)
                                    if hasattr(entry, "title") and entry.title
                                    else None,
                                }
                                results.append(user_data)
                            except Exception as e:
                                logger.error(
                                    f"Error processing entry {entry.entry_dn}: {str(e)}"
                                )

                        return {
                            "multiple_results": True,
                            "results": results,
                            "total": len(conn.entries),
                        }

                    # Single result - process as before
                    entry = conn.entries[0]
                    logger.info(f"Processing single entry: {entry.entry_dn}")
                    return self._process_ldap_entry(entry)
                else:
                    logger.info("No entries found in LDAP search")
                    return None

        except (LDAPSocketOpenError, LDAPSocketReceiveError) as e:
            logger.error(f"LDAP timeout error: {str(e)}")
            logger.error(f"Timeout type: {type(e).__name__}")
            raise TimeoutError(
                f"LDAP operation timed out after {self.operation_timeout} seconds. Please try a more specific search term."
            )
        except LDAPException as e:
            logger.error(f"LDAP search error: {str(e)}")
            logger.error(f"LDAP Exception type: {type(e).__name__}")
        except Exception as e:
            logger.error(f"Unexpected error during LDAP search: {str(e)}")
            logger.error(f"Exception type: {type(e).__name__}")
            import traceback

            logger.error(f"Traceback: {traceback.format_exc()}")

        return None

    def get_user_by_dn(self, user_dn: str) -> Optional[Dict[str, Any]]:
        """Get a specific user by their Distinguished Name."""
        logger.info(f"Getting user by DN: {user_dn}")

        try:
            server = Server(
                self.host,
                port=self.port,
                use_ssl=self.use_ssl,
                get_info=ALL,
                connect_timeout=self.connect_timeout,
            )

            with Connection(
                server,
                user=self.bind_dn,
                password=self.bind_password,
                auto_bind=True,
                receive_timeout=self.operation_timeout,
            ) as conn:
                attributes = [
                    "displayName",
                    "mail",
                    "telephoneNumber",
                    "memberOf",
                    "sAMAccountName",
                    "userPrincipalName",
                    "department",
                    "title",
                    "userAccountControl",
                    "lockoutTime",
                    "badPwdCount",
                    "employeeID",
                    "ipPhone",
                    "extensionAttribute4",
                    "thumbnailPhoto",
                    "manager",
                    "pwdLastSet",
                    "accountExpires",
                    "msDS-UserPasswordExpiryTimeComputed",
                ]

                # Search for the specific DN
                conn.search(
                    search_base=user_dn,
                    search_filter="(objectClass=*)",
                    search_scope="BASE",  # Only search the exact DN
                    attributes=attributes,
                )

                if conn.entries:
                    entry = conn.entries[0]
                    # Process the entry using the same logic as search_user
                    return self._process_ldap_entry(entry)

        except Exception as e:
            logger.error(f"Error getting user by DN: {str(e)}")

        return None

    def _process_ldap_entry(self, entry) -> Dict[str, Any]:
        """Process a single LDAP entry into user data."""
        groups = []
        if hasattr(entry, "memberOf") and entry.memberOf:
            groups = self._parse_group_names(entry.memberOf.values)

        # Parse account status
        enabled = True
        locked = False
        if hasattr(entry, "userAccountControl"):
            uac = int(entry.userAccountControl.value) if entry.userAccountControl else 0
            enabled = not (uac & 2)  # ACCOUNTDISABLE flag

        if (
            hasattr(entry, "lockoutTime")
            and entry.lockoutTime
            and entry.lockoutTime.value
        ):
            try:
                lockout_value = entry.lockoutTime.value
                if isinstance(lockout_value, (int, float)):
                    locked = lockout_value > 0
                elif isinstance(lockout_value, str):
                    locked = int(lockout_value) > 0
                elif hasattr(lockout_value, "year"):
                    locked = lockout_value.year > 1601
                else:
                    locked = False
            except Exception as e:
                logger.error(f"Error parsing lockoutTime: {str(e)}")
                locked = False

        # Extract phone numbers
        phone_numbers = {}
        if hasattr(entry, "extensionAttribute4") and entry.extensionAttribute4:
            phone_numbers["genesys"] = str(entry.extensionAttribute4)
        if hasattr(entry, "telephoneNumber") and entry.telephoneNumber:
            phone_numbers["teams"] = str(entry.telephoneNumber)

        extension = (
            str(entry.ipPhone) if hasattr(entry, "ipPhone") and entry.ipPhone else None
        )

        # Extract thumbnail photo
        thumbnail_photo = None
        if hasattr(entry, "thumbnailPhoto") and entry.thumbnailPhoto:
            import base64

            try:
                photo_bytes = entry.thumbnailPhoto.value
                if photo_bytes:
                    thumbnail_photo = f"data:image/jpeg;base64,{base64.b64encode(photo_bytes).decode('utf-8')}"
            except Exception as e:
                logger.error(f"Error encoding thumbnail photo: {str(e)}")

        # Extract manager name
        manager_name = None
        if hasattr(entry, "manager") and entry.manager:
            try:
                manager_dn = str(entry.manager)
                if manager_dn.startswith("CN="):
                    manager_name = manager_dn.split(",")[0][3:]
            except Exception as e:
                logger.error(f"Error parsing manager DN: {str(e)}")

        # Process password-related attributes
        pwd_last_set = None
        pwd_expires = None

        if hasattr(entry, "pwdLastSet") and entry.pwdLastSet and entry.pwdLastSet.value:
            try:
                pwd_last_set_raw = entry.pwdLastSet.value
                logger.info(f"Raw pwdLastSet value type: {type(pwd_last_set_raw)}")

                # Check if it's already a datetime object
                from datetime import datetime

                if isinstance(pwd_last_set_raw, datetime):
                    pwd_last_set = pwd_last_set_raw
                    logger.info(f"pwdLastSet is already datetime: {pwd_last_set}")
                else:
                    # Convert Windows FILETIME to datetime
                    # FILETIME is 100-nanosecond intervals since January 1, 1601
                    pwd_last_set_value = int(pwd_last_set_raw)
                    logger.info(f"Raw pwdLastSet integer value: {pwd_last_set_value}")
                    if pwd_last_set_value > 0:
                        # Convert to Unix timestamp
                        unix_timestamp = (
                            pwd_last_set_value - 116444736000000000
                        ) / 10000000
                        pwd_last_set = datetime.fromtimestamp(unix_timestamp)
                        logger.info(f"Parsed pwdLastSet: {pwd_last_set}")
            except Exception as e:
                logger.error(f"Error parsing pwdLastSet: {str(e)}")

        # Handle the attribute with hyphen using bracket notation
        pwd_expiry_attr = None
        try:
            # Try different ways to access the attribute
            if hasattr(entry, "msDS_UserPasswordExpiryTimeComputed"):
                pwd_expiry_attr = getattr(entry, "msDS_UserPasswordExpiryTimeComputed")
            elif "msDS-UserPasswordExpiryTimeComputed" in entry:
                pwd_expiry_attr = entry["msDS-UserPasswordExpiryTimeComputed"]
            else:
                # Try accessing through entry attributes
                for attr_name in dir(entry):
                    if "passwordexpiry" in attr_name.lower():
                        logger.info(f"Found password expiry attribute: {attr_name}")
                        pwd_expiry_attr = getattr(entry, attr_name)
                        break
        except Exception as e:
            logger.error(f"Error accessing password expiry attribute: {str(e)}")

        if (
            pwd_expiry_attr
            and hasattr(pwd_expiry_attr, "value")
            and pwd_expiry_attr.value
        ):
            try:
                # This is also a Windows FILETIME
                pwd_expiry_value = int(pwd_expiry_attr.value)
                logger.info(f"Raw password expiry value: {pwd_expiry_value}")
                if (
                    pwd_expiry_value > 0 and pwd_expiry_value != 9223372036854775807
                ):  # Never expires value
                    from datetime import datetime

                    unix_timestamp = (pwd_expiry_value - 116444736000000000) / 10000000
                    pwd_expires = datetime.fromtimestamp(unix_timestamp)
                    logger.info(f"Parsed password expiry: {pwd_expires}")
            except Exception as e:
                logger.error(f"Error parsing password expiry: {str(e)}")

        result = {
            "displayName": str(entry.displayName)
            if hasattr(entry, "displayName")
            else None,
            "mail": str(entry.mail) if hasattr(entry, "mail") else None,
            "phoneNumbers": phone_numbers,
            "extension": extension,
            "employeeID": str(entry.employeeID)
            if hasattr(entry, "employeeID") and entry.employeeID
            else None,
            "sAMAccountName": str(entry.sAMAccountName)
            if hasattr(entry, "sAMAccountName")
            else None,
            "userPrincipalName": str(entry.userPrincipalName)
            if hasattr(entry, "userPrincipalName")
            else None,
            "department": str(entry.department)
            if hasattr(entry, "department")
            else None,
            "title": str(entry.title) if hasattr(entry, "title") else None,
            "manager": manager_name,
            "groupMembership": sorted(groups),
            "enabled": enabled,
            "locked": locked,
            "thumbnailPhoto": thumbnail_photo,
            "pwdLastSet": pwd_last_set.isoformat() if pwd_last_set else None,
            "pwdExpires": pwd_expires.isoformat() if pwd_expires else None,
        }

        # Debug log password fields
        if result.get("pwdLastSet") or result.get("pwdExpires"):
            logger.info(
                f"Returning LDAP data with pwdLastSet: {result.get('pwdLastSet')}, pwdExpires: {result.get('pwdExpires')}"
            )

        return result

    def _parse_group_names(self, group_dns: List[str]) -> List[str]:
        """Extract group names from distinguished names."""
        groups = []
        for dn in group_dns:
            try:
                cn_part = dn.split(",")[0]
                if cn_part.startswith("CN="):
                    groups.append(cn_part[3:])
            except Exception:
                continue
        return groups


ldap_service = LDAPService()
