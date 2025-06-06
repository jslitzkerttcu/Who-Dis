#!/usr/bin/env python3
"""
Diagnose configuration encryption issues
"""

import os
import sys
import psycopg2
from pathlib import Path
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

load_dotenv()

try:
    conn = psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=os.getenv("POSTGRES_PORT", "5432"),
        database=os.getenv("POSTGRES_DB", "whodis_db"),
        user=os.getenv("POSTGRES_USER", "whodis_user"),
        password=os.getenv("POSTGRES_PASSWORD", ""),
    )
    cursor = conn.cursor()

    print("🔍 Sensitive Configuration Diagnostic")
    print("=" * 50)

    # Check what's in the database
    cursor.execute("""
        SELECT category, setting_key, 
               setting_value IS NOT NULL as has_plain,
               encrypted_value IS NOT NULL as has_encrypted,
               octet_length(encrypted_value) as encrypted_size,
               pg_typeof(encrypted_value) as encrypted_type
        FROM configuration 
        WHERE is_sensitive = TRUE
        ORDER BY category, setting_key
    """)

    print("\nSensitive configs in database:")
    print(
        f"{'Category':<10} {'Key':<20} {'Plain':<7} {'Encrypted':<10} {'Size':<6} {'Type'}"
    )
    print("-" * 70)

    for row in cursor.fetchall():
        category, key, has_plain, has_encrypted, size, dtype = row
        print(
            f"{category:<10} {key:<20} {'Yes' if has_plain else 'No':<7} {'Yes' if has_encrypted else 'No':<10} {size or 0:<6} {dtype}"
        )

    # Check a sample encrypted value
    cursor.execute("""
        SELECT category, setting_key, encrypted_value
        FROM configuration 
        WHERE is_sensitive = TRUE AND encrypted_value IS NOT NULL
        LIMIT 1
    """)

    sample_row = cursor.fetchone()
    if sample_row is not None:
        category, key, encrypted_value = sample_row
        print(f"\n📊 Sample encrypted value ({category}.{key}):")
        print(f"   Type: {type(encrypted_value)}")
        print(f"   Has tobytes: {hasattr(encrypted_value, 'tobytes')}")
        if hasattr(encrypted_value, "tobytes"):
            print(f"   Bytes length: {len(encrypted_value.tobytes())}")
            print(f"   First 20 bytes: {encrypted_value.tobytes()[:20]}...")

    # Check environment variables
    print("\n🔍 Environment variables check:")
    env_vars = [
        "VIEWERS",
        "EDITORS",
        "ADMINS",
        "SECRET_KEY",
        "LDAP_BIND_DN",
        "LDAP_BIND_PASSWORD",
        "GENESYS_CLIENT_ID",
        "GENESYS_CLIENT_SECRET",
        "GRAPH_CLIENT_ID",
        "GRAPH_CLIENT_SECRET",
        "GRAPH_TENANT_ID",
    ]

    for var in env_vars:
        value = os.getenv(var)
        if value:
            print(f"✅ {var:<25} = {'*' * min(len(value), 20)}...")
        else:
            print(f"❌ {var:<25} = Not set")

    conn.close()

except Exception as e:
    print(f"Error: {e}")
    import traceback

    traceback.print_exc()
