#!/usr/bin/env python3
"""
Verify that encrypted configuration is properly set up and ready to use
"""

import os
import sys
import psycopg2
from pathlib import Path
from dotenv import load_dotenv
from tabulate import tabulate

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.encryption_service import EncryptionService


def main():
    """Check if encrypted configuration is ready"""
    print("🔍 Verifying Encrypted Configuration Setup")
    print("=" * 50)

    # Load .env file
    load_dotenv()

    # Check 1: Encryption key exists
    print("\n1. Checking encryption key...")
    encryption_key = os.getenv("CONFIG_ENCRYPTION_KEY")
    if not encryption_key:
        print("❌ CONFIG_ENCRYPTION_KEY not found in .env")
        return False
    print("✅ CONFIG_ENCRYPTION_KEY found")

    # Check 2: Can initialize encryption service
    print("\n2. Testing encryption service...")
    try:
        encryption_service = EncryptionService(encryption_key)
        # Test encrypt/decrypt
        test_value = "test_secret_123"
        encrypted = encryption_service.encrypt(test_value)
        decrypted = encryption_service.decrypt(encrypted)
        if decrypted != test_value:
            print("❌ Encryption/decryption test failed")
            return False
        print("✅ Encryption service working correctly")
    except Exception as e:
        print(f"❌ Error initializing encryption: {e}")
        return False

    # Check 3: Database connection
    print("\n3. Checking database connection...")
    try:
        conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=os.getenv("POSTGRES_PORT", "5432"),
            database=os.getenv("POSTGRES_DB", "whodis_db"),
            user=os.getenv("POSTGRES_USER", "whodis_user"),
            password=os.getenv("POSTGRES_PASSWORD", ""),
        )
        cursor = conn.cursor()
        print("✅ Database connection successful")
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False

    # Check 4: Configuration table structure
    print("\n4. Checking configuration table structure...")
    try:
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'configuration' 
            AND column_name IN ('encrypted_value', 'is_sensitive', 'encryption_method')
        """)
        columns = [row[0] for row in cursor.fetchall()]

        missing = []
        for required in ["encrypted_value", "is_sensitive"]:
            if required not in columns:
                missing.append(required)

        if missing:
            print(f"❌ Missing columns: {', '.join(missing)}")
            print(
                "   Run: psql -U whodis_user -d whodis_db -f database/add_encryption_to_configuration.sql"
            )
            return False
        print("✅ Configuration table has encryption columns")
    except Exception as e:
        print(f"❌ Error checking table structure: {e}")
        return False

    # Check 5: Verify sensitive configs are populated
    print("\n5. Checking sensitive configuration values...")
    try:
        cursor.execute("""
            SELECT category, setting_key, 
                   CASE WHEN encrypted_value IS NOT NULL THEN '✅ Encrypted'
                        WHEN setting_value IS NOT NULL THEN '⚠️  Plain text'
                        ELSE '❌ Empty' END as status
            FROM configuration 
            WHERE is_sensitive = TRUE
            ORDER BY category, setting_key
        """)

        sensitive_configs = cursor.fetchall()

        if not sensitive_configs:
            print("❌ No sensitive configurations found")
            print("   Run: python scripts/migrate_config_to_db.py")
            return False

        print("\nSensitive Configuration Status:")
        print(
            tabulate(
                sensitive_configs,
                headers=["Category", "Key", "Status"],
                tablefmt="grid",
            )
        )

        # Count statuses
        encrypted_count = sum(1 for row in sensitive_configs if "Encrypted" in row[2])
        plain_count = sum(1 for row in sensitive_configs if "Plain text" in row[2])
        empty_count = sum(1 for row in sensitive_configs if "Empty" in row[2])

        print(
            f"\nSummary: {encrypted_count} encrypted, {plain_count} plain text, {empty_count} empty"
        )

        if empty_count > 0:
            print(
                "\n⚠️  Some sensitive configs are empty. Make sure these are in your .env:"
            )
            for row in sensitive_configs:
                if "Empty" in row[2]:
                    env_key = f"{row[0].upper()}_{row[1].upper()}"
                    print(f"   - {env_key}")

    except Exception as e:
        print(f"❌ Error checking sensitive configs: {e}")
        return False

    # Check 6: Test decryption of a value
    print("\n6. Testing decryption of stored values...")
    try:
        cursor.execute("""
            SELECT category, setting_key, encrypted_value
            FROM configuration 
            WHERE is_sensitive = TRUE AND encrypted_value IS NOT NULL
            LIMIT 1
        """)

        row = cursor.fetchone()
        if row:
            category, key, encrypted_value = row
            try:
                decrypted = encryption_service.decrypt(encrypted_value)
                print(f"✅ Successfully decrypted {category}.{key}")
            except Exception as e:
                print(f"❌ Failed to decrypt {category}.{key}: {e}")
                print("   The encryption key might have changed!")
                return False
        else:
            print("⚠️  No encrypted values found to test")

    except Exception as e:
        print(f"❌ Error testing decryption: {e}")
        return False

    # Check 7: Compare .env values with database
    print("\n7. Checking for values still in .env that should be in database...")
    env_keys_to_check = [
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

    still_in_env = []
    for key in env_keys_to_check:
        if os.getenv(key):
            still_in_env.append(key)

    if still_in_env:
        print(f"⚠️  Found {len(still_in_env)} sensitive values still in .env:")
        for key in still_in_env:
            print(f"   - {key}")
        print(
            "\n   These should be removed from .env after verifying they're in the database"
        )
    else:
        print("✅ No sensitive values found in .env")

    # Final summary
    print("\n" + "=" * 50)
    if encrypted_count > 0 and empty_count == 0:
        print("✅ READY: Your encrypted configuration is set up correctly!")
        print("\n📋 Next steps:")
        print(
            "1. Remove sensitive values from .env (keep only database connection and CONFIG_ENCRYPTION_KEY)"
        )
        print("2. Restart your application")
        print("3. Test that everything works correctly")
        return True
    else:
        print("❌ NOT READY: Please address the issues above")
        if empty_count > 0:
            print("\nRun: python scripts/migrate_config_to_db.py")
        return False

    conn.close()


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
