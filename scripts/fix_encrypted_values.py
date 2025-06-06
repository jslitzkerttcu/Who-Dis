#!/usr/bin/env python3
"""
Fix encrypted values that were stored incorrectly
"""

import os
import sys
import psycopg2
from pathlib import Path
from dotenv import load_dotenv

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.encryption_service import EncryptionService


def main():
    """Fix encrypted values in the database"""
    print("🔧 Fixing Encrypted Configuration Values")
    print("=" * 50)

    # Load .env file
    load_dotenv()

    # Check encryption key
    encryption_key = os.getenv("CONFIG_ENCRYPTION_KEY")
    if not encryption_key:
        print("❌ CONFIG_ENCRYPTION_KEY not found in .env")
        return 1

    # Initialize encryption service
    try:
        encryption_service = EncryptionService(encryption_key)
    except Exception as e:
        print(f"❌ Error initializing encryption: {e}")
        return 1

    # Connect to database
    try:
        conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=os.getenv("POSTGRES_PORT", "5432"),
            database=os.getenv("POSTGRES_DB", "whodis_db"),
            user=os.getenv("POSTGRES_USER", "whodis_user"),
            password=os.getenv("POSTGRES_PASSWORD", ""),
        )
        conn.autocommit = True
        cursor = conn.cursor()
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return 1

    print("\n🔍 Checking for incorrectly stored encrypted values...")

    # Get all sensitive configs
    cursor.execute("""
        SELECT id, category, setting_key, setting_value, encrypted_value
        FROM configuration 
        WHERE is_sensitive = TRUE
        ORDER BY category, setting_key
    """)

    configs = cursor.fetchall()
    fixed_count = 0

    for config_id, category, key, setting_value, encrypted_value in configs:
        needs_fix = False
        value_to_encrypt = None

        # Check if we have a plain text value that needs encryption
        if setting_value and not encrypted_value:
            print(f"\n📝 Found plain text value for {category}.{key}")
            value_to_encrypt = setting_value
            needs_fix = True

        # Check if encrypted_value is stored as string instead of bytes
        elif encrypted_value and isinstance(encrypted_value, str):
            print(f"\n🔄 Found string-encoded encrypted value for {category}.{key}")
            # Try to decrypt it first to get the original value
            try:
                # If it's a base64 string, decode it
                import base64

                encrypted_bytes = base64.b64decode(encrypted_value)
                decrypted = encryption_service.decrypt(encrypted_bytes)
                value_to_encrypt = decrypted
                needs_fix = True
                print("   ✅ Successfully decoded and decrypted")
            except Exception as e:
                print(f"   ❌ Could not decode/decrypt: {e}")
                # Check if there's a value in .env we can use
                env_key = f"{category.upper()}_{key.upper()}"
                env_value = os.getenv(env_key)
                if env_value:
                    print(f"   ✅ Found value in .env: {env_key}")
                    value_to_encrypt = env_value
                    needs_fix = True
                else:
                    print(f"   ❌ No value found in .env for {env_key}")

        if needs_fix and value_to_encrypt:
            try:
                # Properly encrypt the value as bytes
                encrypted_bytes = encryption_service.encrypt(value_to_encrypt)

                # Update in database - store as BYTEA
                cursor.execute(
                    """
                    UPDATE configuration 
                    SET setting_value = NULL, 
                        encrypted_value = %s,
                        updated_by = 'fix_encryption_script'
                    WHERE id = %s
                """,
                    (encrypted_bytes, config_id),
                )

                print(f"   ✅ Fixed {category}.{key}")
                fixed_count += 1

            except Exception as e:
                print(f"   ❌ Error fixing {category}.{key}: {e}")

    print(f"\n✅ Fixed {fixed_count} configuration values")

    # Verify the fixes
    print("\n🔍 Verifying fixes...")
    cursor.execute("""
        SELECT category, setting_key, encrypted_value
        FROM configuration 
        WHERE is_sensitive = TRUE AND encrypted_value IS NOT NULL
        LIMIT 3
    """)

    test_count = 0
    for category, key, encrypted_value in cursor.fetchall():
        try:
            decrypted = encryption_service.decrypt(encrypted_value)
            print(f"✅ {category}.{key} decrypts successfully")
            test_count += 1
        except Exception as e:
            print(f"❌ {category}.{key} decryption failed: {e}")

    if test_count > 0:
        print(f"\n✅ Verification passed! Tested {test_count} values")
    else:
        print("\n❌ Verification failed!")

    cursor.close()
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
