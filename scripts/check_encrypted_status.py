#!/usr/bin/env python3
"""Check which configuration values are stored as encrypted."""

import os
import sys
import psycopg2
from pathlib import Path
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def main():
    """Check encrypted status of configuration values."""
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
    
    print("Configuration Storage Analysis")
    print("=" * 80)
    
    # Check specific fields
    problem_fields = [
        ("ldap", "bind_dn"),
        ("genesys", "client_id"),
        ("graph", "tenant_id"),
        ("graph", "client_id"),
    ]
    
    print("\nChecking problem fields:")
    print("-" * 40)
    
    for category, key in problem_fields:
        cursor.execute("""
            SELECT setting_value, encrypted_value, is_sensitive
            FROM configuration
            WHERE category = %s AND setting_key = %s
        """, (category, key))
        
        result = cursor.fetchone()
        if result:
            setting_value, encrypted_value, is_sensitive = result
            print(f"\n{category}.{key}:")
            print(f"  Has plain value: {setting_value is not None}")
            print(f"  Has encrypted value: {encrypted_value is not None}")
            print(f"  Marked as sensitive: {is_sensitive}")
            if setting_value:
                print(f"  Plain value length: {len(setting_value)}")
            if encrypted_value:
                print(f"  Encrypted value starts with: {str(encrypted_value)[:20]}...")
        else:
            print(f"\n{category}.{key}: NOT FOUND IN DATABASE")
    
    # Show all encrypted fields
    print("\n\nAll fields with encrypted values:")
    print("-" * 40)
    cursor.execute("""
        SELECT category, setting_key, is_sensitive
        FROM configuration
        WHERE encrypted_value IS NOT NULL
        ORDER BY category, setting_key
    """)
    
    for category, key, is_sensitive in cursor.fetchall():
        print(f"  {category}.{key} (sensitive={is_sensitive})")
    
    conn.close()

if __name__ == "__main__":
    main()