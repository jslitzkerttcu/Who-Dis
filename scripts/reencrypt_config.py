#!/usr/bin/env python3
"""
Re-encrypt all sensitive configuration values properly
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
    """Re-encrypt all sensitive values"""
    print("🔄 Re-encrypting All Sensitive Configuration Values")
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

    # First, clear all encrypted values to start fresh
    print("\n🧹 Clearing existing encrypted values...")
    cursor.execute("""
        UPDATE configuration 
        SET encrypted_value = NULL
        WHERE is_sensitive = TRUE
    """)

    # Map of configuration keys to environment variables
    config_env_map = {
        ("auth", "viewers"): "VIEWERS",
        ("auth", "editors"): "EDITORS",
        ("auth", "admins"): "ADMINS",
        ("flask", "secret_key"): "SECRET_KEY",
        ("ldap", "bind_dn"): "LDAP_BIND_DN",
        ("ldap", "bind_password"): "LDAP_BIND_PASSWORD",
        ("genesys", "client_id"): "GENESYS_CLIENT_ID",
        ("genesys", "client_secret"): "GENESYS_CLIENT_SECRET",
        ("graph", "client_id"): "GRAPH_CLIENT_ID",
        ("graph", "client_secret"): "GRAPH_CLIENT_SECRET",
        ("graph", "tenant_id"): "GRAPH_TENANT_ID",
    }

    print("\n📝 Encrypting values from environment variables...")
    encrypted_count = 0
    missing_count = 0

    for (category, key), env_var in config_env_map.items():
        env_value = os.getenv(env_var)

        if env_value:
            try:
                # Encrypt the value
                encrypted_bytes = encryption_service.encrypt(env_value)

                # Store in database
                cursor.execute(
                    """
                    UPDATE configuration 
                    SET setting_value = NULL, 
                        encrypted_value = %s,
                        updated_by = 'reencrypt_script'
                    WHERE category = %s AND setting_key = %s
                """,
                    (encrypted_bytes, category, key),
                )

                if cursor.rowcount > 0:
                    print(f"✅ Encrypted {category}.{key} from {env_var}")
                    encrypted_count += 1
                else:
                    # Insert if not exists
                    cursor.execute(
                        """
                        INSERT INTO configuration 
                        (category, setting_key, encrypted_value, is_sensitive, 
                         data_type, description, updated_by)
                        VALUES (%s, %s, %s, TRUE, 'string', %s, 'reencrypt_script')
                        ON CONFLICT (category, setting_key) DO UPDATE
                        SET encrypted_value = EXCLUDED.encrypted_value,
                            setting_value = NULL,
                            is_sensitive = TRUE,
                            updated_by = EXCLUDED.updated_by
                    """,
                        (category, key, encrypted_bytes, f"{env_var} value"),
                    )
                    print(f"✅ Created and encrypted {category}.{key} from {env_var}")
                    encrypted_count += 1

            except Exception as e:
                print(f"❌ Error encrypting {category}.{key}: {e}")
        else:
            print(f"⚠️  No value found for {env_var} (needed for {category}.{key})")
            missing_count += 1

    print(f"\n📊 Results: {encrypted_count} encrypted, {missing_count} missing")

    # Verify encryption worked
    print("\n🔍 Verifying encrypted values...")
    cursor.execute("""
        SELECT category, setting_key, encrypted_value
        FROM configuration 
        WHERE is_sensitive = TRUE AND encrypted_value IS NOT NULL
    """)

    verified_count = 0
    for category, key, encrypted_value in cursor.fetchall():
        try:
            # psycopg2 returns memoryview for bytea, convert to bytes
            if hasattr(encrypted_value, "tobytes"):
                encrypted_bytes = encrypted_value.tobytes()
            else:
                encrypted_bytes = bytes(encrypted_value)

            encryption_service.decrypt(encrypted_bytes)
            print(f"✅ {category}.{key} - Decryption successful")
            verified_count += 1
        except Exception as e:
            print(f"❌ {category}.{key} - Decryption failed: {e}")

    print(f"\n✅ Verified {verified_count} encrypted values")

    # Final status check
    cursor.execute("""
        SELECT 
            COUNT(*) FILTER (WHERE is_sensitive = TRUE AND encrypted_value IS NOT NULL) as encrypted,
            COUNT(*) FILTER (WHERE is_sensitive = TRUE AND encrypted_value IS NULL) as missing
        FROM configuration
    """)

    encrypted, missing = cursor.fetchone()

    print("\n" + "=" * 50)
    print(f"Final Status: {encrypted} encrypted, {missing} missing")

    if missing > 0:
        print("\n⚠️  Some values are still missing. Check your .env file for:")
        cursor.execute("""
            SELECT category, setting_key 
            FROM configuration 
            WHERE is_sensitive = TRUE AND encrypted_value IS NULL
        """)
        for category, key in cursor.fetchall():
            env_var = config_env_map.get(
                (category, key), f"{category.upper()}_{key.upper()}"
            )
            print(f"   - {env_var}")

    if encrypted > 0 and missing == 0:
        print("\n✅ All sensitive values are now properly encrypted!")
        print("You can now remove these from your .env file.")

    cursor.close()
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
