#!/usr/bin/env python3
"""
Clear encrypted configuration values when encryption key is lost or changed.
This will remove encrypted values but keep plain text values intact.
You'll need to re-enter sensitive values through the admin UI.
"""

import os
import sys
import psycopg2
from pathlib import Path
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def main():
    """Clear encrypted configuration values."""
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
        print(f"❌ Database connection failed: {e}", file=sys.stderr)
        sys.exit(1)

    print("⚠️  WARNING: This will clear all encrypted configuration values!")
    print("You will need to re-enter sensitive values through the admin UI.")
    response = input("\nContinue? (yes/no): ")
    
    if response.lower() != "yes":
        print("Cancelled.")
        return

    try:
        # First, show what will be cleared
        cursor.execute("""
            SELECT category, setting_key, is_sensitive
            FROM configuration
            WHERE encrypted_value IS NOT NULL
            ORDER BY category, setting_key
        """)
        
        encrypted_configs = cursor.fetchall()
        
        if not encrypted_configs:
            print("\n✅ No encrypted configuration values found.")
            return
        
        print(f"\n📋 Found {len(encrypted_configs)} encrypted configuration values:")
        for category, key, is_sensitive in encrypted_configs:
            print(f"   - {category}.{key}")
        
        # Clear encrypted values
        cursor.execute("""
            UPDATE configuration
            SET encrypted_value = NULL,
                setting_value = NULL,
                updated_at = NOW(),
                updated_by = 'clear_encrypted_config'
            WHERE encrypted_value IS NOT NULL
        """)
        
        affected = cursor.rowcount
        conn.commit()
        
        print(f"\n✅ Cleared {affected} encrypted configuration values.")
        print("\n📌 Next steps:")
        print("1. Start the application: python run.py")
        print("2. Navigate to /admin/configuration")
        print("3. Re-enter the following sensitive values:")
        
        for category, key, is_sensitive in encrypted_configs:
            print(f"   - {category}.{key}")
            
    except Exception as e:
        print(f"\n❌ Error clearing encrypted values: {e}", file=sys.stderr)
        conn.rollback()
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()