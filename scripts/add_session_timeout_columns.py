#!/usr/bin/env python3
"""
Add session timeout columns to user_sessions table
"""

import os
import sys
import psycopg2

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def add_session_columns():
    """Add warning_shown and is_active columns to user_sessions table"""

    # Get database configuration from environment
    db_config = {
        "host": os.getenv("POSTGRES_HOST", "localhost"),
        "port": os.getenv("POSTGRES_PORT", "5432"),
        "database": os.getenv("POSTGRES_DB", "whodis_db"),
        "user": os.getenv("POSTGRES_USER", "whodis_user"),
        "password": os.getenv("POSTGRES_PASSWORD", ""),
    }

    conn = None
    cur = None

    try:
        # Connect to database
        conn = psycopg2.connect(**db_config)
        cur = conn.cursor()

        # Check if columns already exist
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'user_sessions' 
            AND column_name IN ('warning_shown', 'is_active')
        """)

        existing_columns = [row[0] for row in cur.fetchall()]

        # Add warning_shown column if it doesn't exist
        if "warning_shown" not in existing_columns:
            print("Adding warning_shown column...")
            cur.execute("""
                ALTER TABLE user_sessions 
                ADD COLUMN warning_shown BOOLEAN DEFAULT FALSE
            """)
            print("✓ Added warning_shown column")
        else:
            print("✓ warning_shown column already exists")

        # Add is_active column if it doesn't exist
        if "is_active" not in existing_columns:
            print("Adding is_active column...")
            cur.execute("""
                ALTER TABLE user_sessions 
                ADD COLUMN is_active BOOLEAN DEFAULT TRUE
            """)
            print("✓ Added is_active column")
        else:
            print("✓ is_active column already exists")

        # Also add session configuration if not present
        print("\nChecking session configuration...")
        cur.execute("""
            SELECT setting_key FROM configuration 
            WHERE category = 'session' 
            AND setting_key IN ('timeout_minutes', 'warning_minutes', 'check_interval_seconds')
        """)

        existing_settings = [row[0] for row in cur.fetchall()]

        settings_to_add = []
        if "timeout_minutes" not in existing_settings:
            settings_to_add.append(
                (
                    "session",
                    "timeout_minutes",
                    "15",
                    "integer",
                    "Session timeout in minutes (default 15)",
                    False,
                )
            )
        if "warning_minutes" not in existing_settings:
            settings_to_add.append(
                (
                    "session",
                    "warning_minutes",
                    "2",
                    "integer",
                    "Minutes before timeout to show warning (default 2)",
                    False,
                )
            )
        if "check_interval_seconds" not in existing_settings:
            settings_to_add.append(
                (
                    "session",
                    "check_interval_seconds",
                    "30",
                    "integer",
                    "How often to check session validity in seconds",
                    False,
                )
            )

        if settings_to_add:
            print(f"Adding {len(settings_to_add)} session configuration settings...")
            cur.executemany(
                """
                INSERT INTO configuration (category, setting_key, setting_value, data_type, description, is_sensitive)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (category, setting_key) DO NOTHING
            """,
                settings_to_add,
            )
            print("✓ Added session configuration settings")
        else:
            print("✓ All session configuration settings already exist")

        # Commit changes
        conn.commit()
        print("\n✅ Session timeout migration completed successfully!")

    except Exception as e:
        print(f"\n❌ Error during migration: {e}")
        if conn:
            conn.rollback()
        sys.exit(1)

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


if __name__ == "__main__":
    print("Session Timeout Migration")
    print("=" * 50)
    add_session_columns()
