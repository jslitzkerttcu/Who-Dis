#!/usr/bin/env python3
"""Test configuration decryption to diagnose startup issues."""

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import init_db
from app import create_app
from app.services.simple_config import config_get, _config
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def test_config_decryption():
    """Test if configuration values can be decrypted properly."""
    print("Testing configuration decryption...")
    print(f"WHODIS_ENCRYPTION_KEY exists: {'WHODIS_ENCRYPTION_KEY' in os.environ}")
    if 'WHODIS_ENCRYPTION_KEY' in os.environ:
        print(f"WHODIS_ENCRYPTION_KEY length: {len(os.environ['WHODIS_ENCRYPTION_KEY'])}")
    
    # Create app context
    app = create_app()
    with app.app_context():
        # Test Graph configuration
        print("\nTesting Microsoft Graph configuration:")
        client_id = config_get("graph.client_id")
        client_secret = config_get("graph.client_secret")
        tenant_id = config_get("graph.tenant_id")
        
        print(f"  client_id: {'✓' if client_id else '✗'} {repr(client_id) if client_id else 'None'}")
        print(f"  client_secret: {'✓' if client_secret else '✗'} {'*' * 8 if client_secret else 'None'}")
        print(f"  tenant_id: {'✓' if tenant_id else '✗'} {repr(tenant_id) if tenant_id else 'None'}")
        
        # Check if values look encrypted (start with 'gAAAAA')
        for key in ["graph.client_id", "graph.client_secret", "graph.tenant_id"]:
            value = config_get(key)
            if value and value.startswith("gAAAAA"):
                print(f"\nWARNING: {key} appears to still be encrypted!")
                print(f"  This means decryption failed.")
        
        # Test LDAP configuration
        print("\n\nTesting LDAP configuration:")
        ldap_password = config_get("ldap.bind_password")
        print(f"  bind_password: {'✓' if ldap_password else '✗'} {'*' * 8 if ldap_password else 'None'}")
        
        # Check Fernet status
        print(f"\n\nFernet instance available: {_config._fernet is not None}")
        
if __name__ == "__main__":
    test_config_decryption()