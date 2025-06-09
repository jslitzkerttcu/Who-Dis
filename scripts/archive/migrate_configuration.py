#!/usr/bin/env python3
"""
Migration script to move all configuration data from the old 'configuration' table
to the new 'simple_config' table, then drop the old table.

This consolidates all configuration into a single table structure.
"""

import os
import sys
from datetime import datetime, timezone
from dotenv import load_dotenv

# Add the app directory to the path so we can import modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

load_dotenv()

from app.app_factory import create_app
from app.database import db
from sqlalchemy import text


def migrate_configuration():
    """Migrate configuration data from configuration table to simple_config table."""

    app = create_app()

    with app.app_context():
        print("Starting configuration migration...")

        # Get all data from configuration table
        result = db.session.execute(
            text("""
            SELECT category, setting_key, setting_value, encrypted_value, updated_by, updated_at
            FROM configuration 
            ORDER BY category, setting_key
        """)
        ).fetchall()

        if not result:
            print("No configuration data found to migrate.")
            return

        print(f"Found {len(result)} configuration entries to migrate...")

        migrated_count = 0
        skipped_count = 0

        for row in result:
            (
                category,
                setting_key,
                setting_value,
                encrypted_value,
                updated_by,
                updated_at,
            ) = row

            # Construct the full key (category.setting_key)
            full_key = f"{category}.{setting_key}"

            # Determine the value to use (encrypted takes priority)
            if encrypted_value:
                # Handle memoryview objects from PostgreSQL BYTEA columns
                if hasattr(encrypted_value, "tobytes"):
                    value = encrypted_value.tobytes().decode("utf-8")
                else:
                    value = str(encrypted_value)
            else:
                value = setting_value or ""

            # Check if key already exists in simple_config
            existing = db.session.execute(
                text("""
                SELECT key FROM simple_config WHERE key = :key
            """),
                {"key": full_key},
            ).first()

            if existing:
                print(f"  SKIP: {full_key} (already exists in simple_config)")
                skipped_count += 1
                continue

            # Insert into simple_config table
            try:
                db.session.execute(
                    text("""
                    INSERT INTO simple_config (key, value, updated_by, updated_at)
                    VALUES (:key, :value, :updated_by, :updated_at)
                """),
                    {
                        "key": full_key,
                        "value": value,
                        "updated_by": updated_by or "migration",
                        "updated_at": updated_at or datetime.now(timezone.utc),
                    },
                )

                print(
                    f"  MIGRATED: {full_key} -> {value[:20] if value else '(empty)'}..."
                )
                migrated_count += 1

            except Exception as e:
                print(f"  ERROR migrating {full_key}: {e}")

        # Commit the transaction
        db.session.commit()

        print("\nMigration complete:")
        print(f"  - Migrated: {migrated_count} entries")
        print(f"  - Skipped: {skipped_count} entries (already existed)")

        # Ask user if they want to drop the old table
        print(
            f"\nMigration successful! All {migrated_count} configuration entries have been moved to simple_config."
        )
        print("The old 'configuration' table can now be safely removed.")

        return migrated_count


def drop_old_tables():
    """Drop the old configuration-related tables."""

    app = create_app()

    with app.app_context():
        try:
            # Drop configuration_history table first (if it exists)
            print("Dropping configuration_history table...")
            db.session.execute(
                text("DROP TABLE IF EXISTS configuration_history CASCADE")
            )

            # Drop configuration table
            print("Dropping configuration table...")
            db.session.execute(text("DROP TABLE IF EXISTS configuration CASCADE"))

            db.session.commit()
            print("✅ Old configuration tables successfully removed!")

        except Exception as e:
            print(f"❌ Error dropping tables: {e}")
            db.session.rollback()


if __name__ == "__main__":
    print("=== Configuration Migration Tool ===")
    print(
        "This script will migrate all data from 'configuration' table to 'simple_config' table"
    )
    print("and optionally remove the old tables.\n")

    # Step 1: Migrate data
    migrated_count = migrate_configuration()

    if migrated_count > 0:
        print("\n=== Migration Complete ===")
        print(f"Successfully migrated {migrated_count} configuration entries.")

        # Step 2: Ask about dropping old tables
        response = input(
            "\nDo you want to drop the old 'configuration' and 'configuration_history' tables? (y/N): "
        )
        if response.lower() in ["y", "yes"]:
            drop_old_tables()
        else:
            print("Old tables preserved. You can drop them manually later if needed:")
            print("  DROP TABLE IF EXISTS configuration_history CASCADE;")
            print("  DROP TABLE IF EXISTS configuration CASCADE;")
    else:
        print("No migration needed or migration failed.")
