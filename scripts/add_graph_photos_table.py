#!/usr/bin/env python3
"""
Script to add the graph_photos table to the database.
Run this if you get "relation graph_photos does not exist" error.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from app.database import get_database_uri


def run_migration():
    """Create the graph_photos table and related configuration."""

    # Read the SQL file
    sql_file = Path(__file__).parent.parent / "database" / "add_graph_photos_table.sql"
    if not sql_file.exists():
        print(f"ERROR: SQL file not found: {sql_file}")
        return False

    with open(sql_file, "r") as f:
        sql_content = f.read()

    # Create engine
    engine = create_engine(get_database_uri())

    try:
        with engine.connect() as conn:
            # Split into individual statements (crude but works for our case)
            statements = [
                s.strip()
                for s in sql_content.split(";")
                if s.strip() and not s.strip().startswith("--")
            ]

            for statement in statements:
                if statement:
                    try:
                        conn.execute(text(statement))
                        conn.commit()
                    except Exception as e:
                        if "already exists" in str(e):
                            print(f"Note: {str(e)}")
                        else:
                            print(f"Error executing statement: {e}")
                            raise

            print("\n✅ Graph photos table created successfully!")
            print("\nWhat was added:")
            print("- graph_photos table for caching user photos")
            print("- Indexes for efficient photo lookups")
            print("- Configuration setting for lazy loading")
            print("- Updated cleanup function to remove old photos")
            print("\nPhotos will be cached for 24 hours to improve search performance.")

            # Check if table was created
            result = conn.execute(
                text(
                    "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'graph_photos'"
                )
            )
            if result.scalar() > 0:
                print("\n✅ Verified: graph_photos table exists")
            else:
                print("\n❌ Warning: graph_photos table may not have been created")

            return True

    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        return False


if __name__ == "__main__":
    print("Adding graph_photos table for photo caching...")
    print("=" * 50)

    success = run_migration()

    if success:
        print("\n🎉 Migration completed successfully!")
        print("\nNext steps:")
        print("1. Restart your Flask application")
        print("2. Photos will now be cached automatically")
        print(
            "3. Configure lazy loading in Admin Panel → Configuration → Search Configuration"
        )
    else:
        print("\n❌ Migration failed. Please check the error messages above.")
        sys.exit(1)
