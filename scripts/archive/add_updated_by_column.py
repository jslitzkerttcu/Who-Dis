#!/usr/bin/env python3
"""
Add updated_by column to users table.
"""

import os
import sys
import psycopg2

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def add_updated_by_column():
    """Add updated_by column to users table if it doesn't exist."""
    # Get database configuration from environment
    db_config = {
        "host": os.getenv("POSTGRES_HOST", "localhost"),
        "port": os.getenv("POSTGRES_PORT", "5432"),
        "database": os.getenv("POSTGRES_DB", "whodis_db"),
        "user": os.getenv("POSTGRES_USER", "whodis_user"),
        "password": os.getenv("POSTGRES_PASSWORD", ""),
    }

    conn = None
    cursor = None

    try:
        conn = psycopg2.connect(**db_config)
        cursor = conn.cursor()

        # Check if column already exists
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'users' 
            AND column_name = 'updated_by'
        """)

        if cursor.fetchone():
            print("Column 'updated_by' already exists in users table")
            return

        # Add the column
        print("Adding 'updated_by' column to users table...")
        cursor.execute("""
            ALTER TABLE users 
            ADD COLUMN updated_by VARCHAR(255)
        """)

        conn.commit()
        print("Successfully added 'updated_by' column to users table")

    except Exception as e:
        print(f"Error adding column: {e}")
        if conn:
            conn.rollback()
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


if __name__ == "__main__":
    add_updated_by_column()
