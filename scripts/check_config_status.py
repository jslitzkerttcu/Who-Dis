#!/usr/bin/env python3
"""
Quick check of configuration status
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

    # Get counts
    cursor.execute("""
        SELECT 
            COUNT(*) FILTER (WHERE is_sensitive = TRUE AND encrypted_value IS NOT NULL) as encrypted,
            COUNT(*) FILTER (WHERE is_sensitive = TRUE AND encrypted_value IS NULL AND setting_value IS NOT NULL) as plain_sensitive,
            COUNT(*) FILTER (WHERE is_sensitive = TRUE AND encrypted_value IS NULL AND setting_value IS NULL) as empty_sensitive,
            COUNT(*) FILTER (WHERE is_sensitive = FALSE) as non_sensitive
        FROM configuration
    """)

    result = cursor.fetchone()
    if result is None:
        print("Error: No configuration data found")
        sys.exit(1)
    encrypted, plain_sensitive, empty_sensitive, non_sensitive = result

    print("Configuration Status:")
    print(f"✅ Encrypted sensitive values: {encrypted}")
    print(f"⚠️  Plain text sensitive values: {plain_sensitive}")
    print(f"❌ Empty sensitive values: {empty_sensitive}")
    print(f"📋 Non-sensitive values: {non_sensitive}")

    if encrypted > 0 and plain_sensitive == 0 and empty_sensitive == 0:
        print("\n✅ Ready to run with encrypted configuration!")
    else:
        print("\n❌ Not ready - run: python scripts/migrate_config_to_db.py")

    conn.close()

except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
