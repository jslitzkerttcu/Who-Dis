#!/usr/bin/env python3
"""
Add timezone configuration to the database.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import create_app
from app.database import db
from sqlalchemy import text


def add_timezone_config():
    """Add timezone configuration to the database."""
    app = create_app()

    with app.app_context():
        try:
            # Check if timezone config already exists
            result = db.session.execute(
                text(
                    "SELECT 1 FROM configuration WHERE category = 'app' AND setting_key = 'timezone'"
                )
            )
            if result.fetchone():
                print("Timezone configuration already exists.")
                return

            # Add timezone configuration
            db.session.execute(
                text("""
                    INSERT INTO configuration (
                        category, setting_key, setting_value, data_type, 
                        description, is_sensitive, default_value, created_at, updated_at
                    ) VALUES (
                        'app', 'timezone', 'US/Central', 'string',
                        'Server timezone for displaying timestamps', false, 'US/Central',
                        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                    )
                """)
            )

            db.session.commit()
            print("Successfully added timezone configuration.")

        except Exception as e:
            db.session.rollback()
            print(f"Error adding timezone configuration: {e}")
            raise


if __name__ == "__main__":
    add_timezone_config()
