#!/usr/bin/env python3
"""
Export current configuration values to JSON for backup purposes.
This exports decrypted values, so keep the output secure!
"""

import os
import sys
import json
import psycopg2
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime, timezone
from typing import Dict, Any

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.encryption_service import EncryptionService


def main() -> None:
    """Export all configuration values to JSON"""
    # Load .env file
    load_dotenv()

    # Initialize encryption service
    encryption_key = os.getenv("WHODIS_ENCRYPTION_KEY")
    if not encryption_key:
        print("❌ Error: WHODIS_ENCRYPTION_KEY not found in .env", file=sys.stderr)
        sys.exit(1)

    try:
        encryption_service = EncryptionService(encryption_key)
    except Exception as e:
        print(f"❌ Error initializing encryption: {e}", file=sys.stderr)
        sys.exit(1)

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

    # Export configuration with explicit typing
    export_data: Dict[str, Any] = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "encryption_key_info": "Current key used for decryption",
        "configurations": {},
    }

    try:
        # Get all configurations
        cursor.execute("""
            SELECT category, setting_key, setting_value, encrypted_value, is_sensitive
            FROM configuration
            ORDER BY category, setting_key
        """)

        for row in cursor.fetchall():
            category, key, plain_value, encrypted_value, is_sensitive = row

            # Create category if it doesn't exist
            if category not in export_data["configurations"]:
                export_data["configurations"][category] = {}

            # Determine the actual value
            if encrypted_value is not None:
                try:
                    value = encryption_service.decrypt(encrypted_value)
                except Exception as e:
                    value = f"[DECRYPTION FAILED: {str(e)}]"
            else:
                value = plain_value

            export_data["configurations"][category][key] = {
                "value": value,
                "is_sensitive": is_sensitive,
                "was_encrypted": encrypted_value is not None,
            }

    except Exception as e:
        print(f"❌ Error exporting configuration: {e}", file=sys.stderr)
        sys.exit(1)

    # Also export from simple_config table if it exists
    try:
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'simple_config'
            )
        """)

        result = cursor.fetchone()
        if result and result[0]:
            cursor.execute("SELECT key, value FROM simple_config ORDER BY key")
            simple_configs = {}

            for key, value in cursor.fetchall():
                # Try to decrypt if it looks encrypted
                try:
                    if encryption_service.is_encrypted(value):
                        decrypted_value = encryption_service.decrypt_string(value)
                        simple_configs[key] = {
                            "value": decrypted_value,
                            "was_encrypted": True,
                        }
                    else:
                        simple_configs[key] = {"value": value, "was_encrypted": False}
                except Exception:
                    simple_configs[key] = {"value": value, "was_encrypted": False}

            if simple_configs:
                export_data["simple_config"] = simple_configs

    except Exception:
        # Ignore if simple_config doesn't exist
        pass

    conn.close()

    # Output as JSON
    print(json.dumps(export_data, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
