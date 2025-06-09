#!/usr/bin/env python3
"""Debug configuration values to see what's actually stored."""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import create_app
from app.services.simple_config import config_get, _config

def debug_config_values():
    """Check actual configuration values."""
    app = create_app()
    
    with app.app_context():
        print("Debugging Configuration Values")
        print("=" * 80)
        
        # Fields that are showing as blank
        problem_fields = [
            ("ldap.bind_dn", "LDAP Bind DN"),
            ("genesys.client_id", "Genesys Client ID"),
            ("graph.tenant_id", "Graph Tenant ID"),
            ("graph.client_id", "Graph Client ID"),
        ]
        
        print("\nChecking problem fields:")
        print("-" * 40)
        
        for key, label in problem_fields:
            value = config_get(key)
            print(f"\n{label} ({key}):")
            print(f"  Raw value: {repr(value)}")
            print(f"  Type: {type(value)}")
            print(f"  Length: {len(str(value)) if value else 0}")
            print(f"  Is None: {value is None}")
            print(f"  Is empty string: {value == ''}")
            print(f"  Starts with gAAAAA: {str(value).startswith('gAAAAA') if value else False}")
            
        # Check if values are in cache
        print("\n\nCache contents:")
        print("-" * 40)
        for key, value in _config._cache.items():
            if any(key.startswith(pf[0].split('.')[0]) for pf in problem_fields):
                print(f"{key}: {repr(value)}")
                
        # Check encryption status
        print("\n\nEncryption status:")
        print("-" * 40)
        print(f"Fernet instance available: {_config._fernet is not None}")
        print(f"Encryption key set: {'WHODIS_ENCRYPTION_KEY' in os.environ}")

if __name__ == "__main__":
    debug_config_values()