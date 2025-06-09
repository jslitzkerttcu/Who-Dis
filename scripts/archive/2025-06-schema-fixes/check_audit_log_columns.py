#!/usr/bin/env python3
"""Check audit_log table columns in the database."""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import db
from app import create_app
from sqlalchemy import text


def check_audit_log_columns():
    """Check columns in audit_log table."""
    app = create_app()

    with app.app_context():
        try:
            # Query to get column information
            query = text("""
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns
                WHERE table_name = 'audit_log'
                ORDER BY ordinal_position;
            """)

            result = db.session.execute(query)
            columns = result.fetchall()

            print("Columns in audit_log table:")
            print("-" * 80)
            print(f"{'Column Name':<30} {'Data Type':<20} {'Nullable':<10} {'Default'}")
            print("-" * 80)

            for col in columns:
                print(
                    f"{col.column_name:<30} {col.data_type:<20} {col.is_nullable:<10} {col.column_default or 'None'}"
                )

            # Check specifically for message column
            message_exists = any(col.column_name == "message" for col in columns)
            print("\n" + "=" * 80)
            print(f"Message column exists: {message_exists}")

        except Exception as e:
            print(f"Error checking columns: {e}")
            db.session.rollback()


if __name__ == "__main__":
    check_audit_log_columns()
