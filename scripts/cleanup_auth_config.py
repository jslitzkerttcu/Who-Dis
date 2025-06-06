#!/usr/bin/env python3
"""
Clean up obsolete auth configuration entries.
User roles are now managed in the users table, not configuration.
"""

import os
import sys
import psycopg2
from pathlib import Path
from dotenv import load_dotenv

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables
load_dotenv()


def cleanup_auth_config():
    """Remove obsolete auth configuration entries."""
    print("🧹 Cleaning up obsolete auth configuration entries")
    print("=" * 50)

    try:
        # Connect to database
        conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=os.getenv("POSTGRES_PORT", "5432"),
            database=os.getenv("POSTGRES_DB", "whodis_db"),
            user=os.getenv("POSTGRES_USER", "whodis_user"),
            password=os.getenv("POSTGRES_PASSWORD", ""),
        )
        conn.autocommit = True
        cur = conn.cursor()

        # Check what we're about to delete
        cur.execute("""
            SELECT category, setting_key, is_sensitive 
            FROM configuration 
            WHERE category = 'auth' 
            AND setting_key IN ('viewers', 'editors', 'admins')
        """)

        entries = cur.fetchall()

        if not entries:
            print("✅ No obsolete auth configuration entries found")
            return

        print(f"\n📋 Found {len(entries)} obsolete entries to remove:")
        for category, key, sensitive in entries:
            print(f"   - {category}.{key} (sensitive: {sensitive})")

        # Delete the entries
        cur.execute("""
            DELETE FROM configuration 
            WHERE category = 'auth' 
            AND setting_key IN ('viewers', 'editors', 'admins')
        """)

        deleted_count = cur.rowcount
        print(f"\n✅ Deleted {deleted_count} obsolete configuration entries")

        # Show current user management info
        cur.execute("SELECT COUNT(*) FROM users WHERE is_active = true")
        active_users = cur.fetchone()[0]

        cur.execute(
            "SELECT role, COUNT(*) FROM users WHERE is_active = true GROUP BY role"
        )
        role_counts = cur.fetchall()

        print("\n📊 Current user management status:")
        print(f"   Total active users: {active_users}")
        for role, count in role_counts:
            print(f"   - {role}: {count}")

        print("\n✅ User roles are now managed exclusively through the 'users' table")
        print("   Access the admin panel at /admin/users to manage user access")

        cur.close()
        conn.close()

    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        return 1

    return 0


if __name__ == "__main__":
    exit(cleanup_auth_config())
