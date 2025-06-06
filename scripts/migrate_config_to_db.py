#!/usr/bin/env python3
"""
Migrate configuration from .env file to PostgreSQL database with encryption
"""

import os
import sys
import psycopg2
from pathlib import Path
from dotenv import load_dotenv

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.encryption_service import EncryptionService

# Load environment variables
load_dotenv()


def main():
    """Migrate configuration from .env to database"""
    # Check for encryption key
    encryption_key = os.getenv("CONFIG_ENCRYPTION_KEY")
    if not encryption_key:
        print("\nNo CONFIG_ENCRYPTION_KEY found in .env")
        print("Generating a new encryption key...")
        encryption_key = EncryptionService.generate_key()
        print("\nAdd this to your .env file:")
        print(f"CONFIG_ENCRYPTION_KEY={encryption_key}")
        print("\nThen run this script again.")
        return 1

    # Initialize encryption service
    try:
        encryption_service = EncryptionService(encryption_key)
    except Exception as e:
        print(f"Error initializing encryption: {e}")
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
        print("Connected to database successfully")
    except Exception as e:
        print(f"Error connecting to database: {e}")
        return 1

    # Configuration to migrate
    configs_to_migrate = [
        # Sensitive configurations (will be encrypted)
        ("auth", "viewers", os.getenv("VIEWERS", ""), True),
        ("auth", "editors", os.getenv("EDITORS", ""), True),
        ("auth", "admins", os.getenv("ADMINS", ""), True),
        ("flask", "secret_key", os.getenv("SECRET_KEY", ""), True),
        ("ldap", "bind_dn", os.getenv("LDAP_BIND_DN", ""), True),
        ("ldap", "bind_password", os.getenv("LDAP_BIND_PASSWORD", ""), True),
        ("genesys", "client_id", os.getenv("GENESYS_CLIENT_ID", ""), True),
        ("genesys", "client_secret", os.getenv("GENESYS_CLIENT_SECRET", ""), True),
        ("graph", "client_id", os.getenv("GRAPH_CLIENT_ID", ""), True),
        ("graph", "client_secret", os.getenv("GRAPH_CLIENT_SECRET", ""), True),
        ("graph", "tenant_id", os.getenv("GRAPH_TENANT_ID", ""), True),
        # Non-sensitive configurations
        ("flask", "host", os.getenv("FLASK_HOST", "0.0.0.0"), False),
        ("flask", "port", os.getenv("FLASK_PORT", "5000"), False),
        ("flask", "debug", os.getenv("FLASK_DEBUG", "False"), False),
        ("ldap", "host", os.getenv("LDAP_HOST", ""), False),
        ("ldap", "port", os.getenv("LDAP_PORT", "389"), False),
        ("ldap", "use_ssl", os.getenv("LDAP_USE_SSL", "False"), False),
        ("ldap", "base_dn", os.getenv("LDAP_BASE_DN", ""), False),
        ("ldap", "user_search_base", os.getenv("LDAP_USER_SEARCH_BASE", ""), False),
        ("ldap", "connect_timeout", os.getenv("LDAP_CONNECT_TIMEOUT", "5"), False),
        ("ldap", "operation_timeout", os.getenv("LDAP_OPERATION_TIMEOUT", "10"), False),
        ("genesys", "region", os.getenv("GENESYS_REGION", ""), False),
        ("genesys", "api_timeout", os.getenv("GENESYS_API_TIMEOUT", "15"), False),
        ("graph", "api_timeout", os.getenv("GRAPH_API_TIMEOUT", "15"), False),
        ("search", "overall_timeout", os.getenv("SEARCH_OVERALL_TIMEOUT", "20"), False),
    ]

    print("\nMigrating configuration to database...")
    migrated = 0
    skipped = 0

    for category, key, value, is_sensitive in configs_to_migrate:
        if not value:
            skipped += 1
            continue

        try:
            # Check if config already exists
            cursor.execute(
                "SELECT id, is_sensitive FROM configuration WHERE category = %s AND setting_key = %s",
                (category, key),
            )
            existing = cursor.fetchone()

            if existing:
                config_id, existing_sensitive = existing
                if is_sensitive and not existing_sensitive:
                    # Update to encrypted
                    encrypted_value = encryption_service.encrypt(value)
                    cursor.execute(
                        """UPDATE configuration 
                           SET setting_value = NULL, encrypted_value = %s, 
                               is_sensitive = TRUE, updated_by = 'migration_script'
                           WHERE id = %s""",
                        (encrypted_value, config_id),
                    )
                    print(f"✓ Updated {category}.{key} (encrypted)")
                elif is_sensitive and existing_sensitive:
                    # Update encrypted value
                    encrypted_value = encryption_service.encrypt(value)
                    cursor.execute(
                        """UPDATE configuration 
                           SET encrypted_value = %s, updated_by = 'migration_script'
                           WHERE id = %s""",
                        (encrypted_value, config_id),
                    )
                    print(f"✓ Updated {category}.{key} (encrypted)")
                else:
                    # Update plain value
                    cursor.execute(
                        """UPDATE configuration 
                           SET setting_value = %s, updated_by = 'migration_script'
                           WHERE id = %s""",
                        (value, config_id),
                    )
                    print(f"✓ Updated {category}.{key}")
            else:
                # Insert new config
                if is_sensitive:
                    encrypted_value = encryption_service.encrypt(value)
                    cursor.execute(
                        """INSERT INTO configuration 
                           (category, setting_key, encrypted_value, is_sensitive, 
                            data_type, updated_by)
                           VALUES (%s, %s, %s, TRUE, 'string', 'migration_script')""",
                        (category, key, encrypted_value),
                    )
                    print(f"✓ Created {category}.{key} (encrypted)")
                else:
                    cursor.execute(
                        """INSERT INTO configuration 
                           (category, setting_key, setting_value, is_sensitive, 
                            data_type, updated_by)
                           VALUES (%s, %s, %s, FALSE, 'string', 'migration_script')""",
                        (category, key, value),
                    )
                    print(f"✓ Created {category}.{key}")

            migrated += 1

        except Exception as e:
            print(f"✗ Error migrating {category}.{key}: {e}")

    print(f"\nMigration complete: {migrated} configs migrated, {skipped} skipped")

    # Show new minimal .env content
    print("\n" + "=" * 50)
    print("Your new minimal .env file should contain only:")
    print("=" * 50)
    print("# Database connection")
    print(f"POSTGRES_HOST={os.getenv('POSTGRES_HOST', 'localhost')}")
    print(f"POSTGRES_PORT={os.getenv('POSTGRES_PORT', '5432')}")
    print(f"POSTGRES_DB={os.getenv('POSTGRES_DB', 'whodis_db')}")
    print(f"POSTGRES_USER={os.getenv('POSTGRES_USER', 'whodis_user')}")
    print(f"POSTGRES_PASSWORD={os.getenv('POSTGRES_PASSWORD', '')}")
    print("\n# Encryption key for configuration")
    print(f"CONFIG_ENCRYPTION_KEY={encryption_key}")
    print("=" * 50)

    cursor.close()
    conn.close()
    return 0


if __name__ == "__main__":
    print("Configuration Migration Script")
    print("==============================")
    print("This script will migrate ALL configuration from .env to PostgreSQL.")
    print("Sensitive values will be encrypted in the database.\n")

    response = input("Do you want to proceed? (yes/no): ")
    if response.lower() == "yes":
        sys.exit(main())
    else:
        print("Migration cancelled.")
        sys.exit(0)
