#!/usr/bin/env python3
"""Debug why specific fields are not appearing."""

import os
import sys
import psycopg2
from pathlib import Path
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def main():
    """Debug missing configuration fields."""
    # Load .env file
    load_dotenv()

    # Connect to database
    try:
        conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=os.getenv("POSTGRES_PORT", "5432"),
            database=os.getenv("POSTGRES_DB", "whodis_db"),
            user=os.getenv("POSTGRES_USER", "whodis_user"),
            password=os.getenv("POSTGRES_PASSWORD", ""),
        )
        cursor = conn.cursor()
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        sys.exit(1)

    print("Debugging Missing Configuration Fields")
    print("=" * 80)

    # Check all LDAP and Genesys fields
    cursor.execute("""
        SELECT category, setting_key, setting_value, encrypted_value, is_sensitive
        FROM configuration
        WHERE category IN ('ldap', 'genesys')
        ORDER BY category, setting_key
    """)

    print("\nAll LDAP and Genesys configuration entries:")
    print("-" * 80)
    print(
        f"{'Category':<10} {'Key':<25} {'Plain':<10} {'Encrypted':<10} {'Sensitive':<10}"
    )
    print("-" * 80)

    for category, key, plain, encrypted, sensitive in cursor.fetchall():
        has_plain = "Yes" if plain else "No"
        has_encrypted = "Yes" if encrypted else "No"
        print(
            f"{category:<10} {key:<25} {has_plain:<10} {has_encrypted:<10} {sensitive!s:<10}"
        )

        # Show actual values for debugging
        if key in ["bind_dn", "client_id"]:
            if plain:
                print(f"          Plain value: '{plain}'")
            if encrypted:
                encrypted_preview = (
                    str(encrypted)[:50] + "..."
                    if len(str(encrypted)) > 50
                    else str(encrypted)
                )
                print(f"          Encrypted: {encrypted_preview}")

    # Now test what config_get returns
    print("\n\nTesting config_get for problem fields:")
    print("-" * 40)

    from app import create_app
    from app.services.simple_config import config_get

    app = create_app()
    with app.app_context():
        test_fields = [
            "ldap.bind_dn",
            "genesys.client_id",
            "graph.tenant_id",
            "graph.client_id",
        ]

        for field in test_fields:
            value = config_get(field)
            print(f"\n{field}:")
            print(f"  config_get returns: {repr(value)}")
            print(f"  Type: {type(value)}")
            print(f"  Is None: {value is None}")
            print(f"  Is empty string: {value == ''}")

    conn.close()


if __name__ == "__main__":
    main()
