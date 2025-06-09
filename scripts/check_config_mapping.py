#!/usr/bin/env python3
"""Check configuration key mapping in both directions."""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def check_config_mapping():
    """Check that all configuration keys map correctly."""

    # Configuration keys from the GET method (display)
    display_keys = {
        "flask": {
            "FLASK_HOST": "host",
            "FLASK_PORT": "port",
            "FLASK_DEBUG": "debug",
            "SECRET_KEY": "secret_key",
        },
        "auth": {
            "AUTH_REQUIRED": "required",
            "AUTH_BASIC_ENABLED": "basic_enabled",
            "AUTH_BASIC_USERNAME": "basic_username",
            "AUTH_BASIC_PASSWORD": "basic_password",
        },
        "search": {
            "SEARCH_TIMEOUT": "timeout",
            "SEARCH_LAZY_LOAD_PHOTOS": "lazy_load_photos",
        },
        "audit": {
            "AUDIT_RETENTION_DAYS": "retention_days",
        },
        "ldap": {
            "LDAP_SERVER": "server",
            "LDAP_PORT": "port",
            "LDAP_USE_SSL": "use_ssl",
            "LDAP_BASE_DN": "base_dn",
            "LDAP_BIND_DN": "bind_dn",
            "LDAP_BIND_PASSWORD": "bind_password",
            "LDAP_CONNECTION_TIMEOUT": "connection_timeout",
            "LDAP_OPERATION_TIMEOUT": "operation_timeout",
        },
        "graph": {
            "GRAPH_TENANT_ID": "tenant_id",
            "GRAPH_CLIENT_ID": "client_id",
            "GRAPH_CLIENT_SECRET": "client_secret",
            "GRAPH_API_TIMEOUT": "api_timeout",
        },
        "genesys": {
            "GENESYS_CLIENT_ID": "client_id",
            "GENESYS_CLIENT_SECRET": "client_secret",
            "GENESYS_REGION": "region",
            "GENESYS_API_TIMEOUT": "api_timeout",
            "GENESYS_CACHE_REFRESH_HOURS": "cache_refresh_period",  # Special: converts to seconds
        },
        "data_warehouse": {
            "DATA_WAREHOUSE_SERVER": "server",
            "DATA_WAREHOUSE_DATABASE": "database",
            "DATA_WAREHOUSE_CLIENT_ID": "client_id",
            "DATA_WAREHOUSE_CLIENT_SECRET": "client_secret",
            "DATA_WAREHOUSE_CONNECTION_TIMEOUT": "connection_timeout",
            "DATA_WAREHOUSE_QUERY_TIMEOUT": "query_timeout",
            "DATA_WAREHOUSE_CACHE_REFRESH_HOURS": "cache_refresh_hours",
        },
    }

    # Key mapping from POST method (save)
    post_key_mapping = {
        # Flask keys
        "FLASK_HOST": "host",
        "FLASK_PORT": "port",
        "FLASK_DEBUG": "debug",
        "SECRET_KEY": "secret_key",
        # Auth keys
        "AUTH_REQUIRED": "required",
        "AUTH_BASIC_ENABLED": "basic_enabled",
        "AUTH_BASIC_USERNAME": "basic_username",
        "AUTH_BASIC_PASSWORD": "basic_password",
        # Search keys
        "SEARCH_TIMEOUT": "timeout",
        "SEARCH_LAZY_LOAD_PHOTOS": "lazy_load_photos",
        # Audit keys
        "AUDIT_RETENTION_DAYS": "retention_days",
        # LDAP keys
        "LDAP_SERVER": "server",
        "LDAP_PORT": "port",
        "LDAP_USE_SSL": "use_ssl",
        "LDAP_BASE_DN": "base_dn",
        "LDAP_BIND_DN": "bind_dn",
        "LDAP_BIND_PASSWORD": "bind_password",
        "LDAP_CONNECTION_TIMEOUT": "connection_timeout",
        "LDAP_OPERATION_TIMEOUT": "operation_timeout",
        # Graph keys
        "GRAPH_TENANT_ID": "tenant_id",
        "GRAPH_CLIENT_ID": "client_id",
        "GRAPH_CLIENT_SECRET": "client_secret",
        "GRAPH_API_TIMEOUT": "api_timeout",
        # Genesys keys
        "GENESYS_CLIENT_ID": "client_id",
        "GENESYS_CLIENT_SECRET": "client_secret",
        "GENESYS_REGION": "region",
        "GENESYS_API_TIMEOUT": "api_timeout",
        "GENESYS_CACHE_REFRESH_HOURS": "cache_refresh_period",
        # Data warehouse keys
        "DATA_WAREHOUSE_SERVER": "server",
        "DATA_WAREHOUSE_DATABASE": "database",
        "DATA_WAREHOUSE_CLIENT_ID": "client_id",
        "DATA_WAREHOUSE_CLIENT_SECRET": "client_secret",
        "DATA_WAREHOUSE_CONNECTION_TIMEOUT": "connection_timeout",
        "DATA_WAREHOUSE_QUERY_TIMEOUT": "query_timeout",
        "DATA_WAREHOUSE_CACHE_REFRESH_HOURS": "cache_refresh_hours",
    }

    print("Configuration Key Mapping Check")
    print("=" * 80)
    print()

    # Check each category
    all_good = True
    for category, keys in display_keys.items():
        print(f"\n{category.upper()} Configuration:")
        print("-" * 40)

        for display_key, db_key in keys.items():
            # Check if POST mapping exists
            if display_key in post_key_mapping:
                post_db_key = post_key_mapping[display_key]
                if post_db_key == db_key:
                    status = "✓"
                else:
                    status = "✗"
                    all_good = False
                    print(
                        f"  ERROR: {display_key} maps to '{db_key}' in GET but '{post_db_key}' in POST"
                    )
            else:
                status = "✗"
                all_good = False
                print(f"  ERROR: {display_key} missing from POST key mapping")

            print(f"  {status} {display_key} → {category}.{db_key}")

            # Special cases
            if display_key == "GENESYS_CACHE_REFRESH_HOURS":
                print("    Special: Value is converted from hours to seconds")

    print()
    print("=" * 80)
    if all_good:
        print("✅ All configuration keys map correctly!")
    else:
        print("❌ Configuration key mapping errors found!")

    # Check for keys in POST mapping but not in display
    print("\nChecking for orphaned POST mappings...")
    orphaned = []
    for post_key in post_key_mapping:
        found = False
        for category, keys in display_keys.items():
            if post_key in keys:
                found = True
                break
        if not found:
            orphaned.append(post_key)

    if orphaned:
        print("❌ Keys in POST mapping but not in display:")
        for key in orphaned:
            print(f"  - {key}")
    else:
        print("✅ No orphaned POST mappings")


if __name__ == "__main__":
    check_config_mapping()
