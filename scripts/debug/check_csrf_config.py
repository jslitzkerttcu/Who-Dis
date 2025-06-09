#!/usr/bin/env python3
"""Check CSRF configuration in database."""

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.configuration_service import config_get

# Check CSRF configuration
print("CSRF Configuration:")
print("-" * 50)
print(f"Cookie Name: {config_get('csrf.cookie_name', '_csrf_token')}")
print(f"Cookie HTTPOnly: {config_get('csrf.cookie_httponly', 'false')}")
print(f"Cookie Secure: {config_get('csrf.cookie_secure', 'false')}")
print(f"Cookie SameSite: {config_get('csrf.cookie_samesite', 'Lax')}")
print(f"Cookie Path: {config_get('csrf.cookie_path', '/')}")
print(f"Header Name: {config_get('csrf.header_name', 'X-CSRF-Token')}")
print(f"Token Expire: {config_get('csrf.token_expire', '3600')}")
