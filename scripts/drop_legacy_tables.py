#!/usr/bin/env python3
"""
Drop Legacy Tables Script
=========================

Drops the legacy graph_photos and data_warehouse_cache tables after
verifying the employee_profiles consolidation is complete.

Usage:
    python scripts/drop_legacy_tables.py [--dry-run]

Options:
    --dry-run    Show what would be executed without making changes

This script connects as the postgres superuser for administrative operations.
"""

import os
import sys
import argparse
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    import psycopg2
    from dotenv import load_dotenv
except ImportError as e:
    print(f"Error: Required dependencies not available: {e}")
    print("Please ensure psycopg2 and python-dotenv are installed")
    sys.exit(1)

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def get_db_connection():
    """Get database connection using postgres superuser."""
    try:
        connection = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST"),
            port=os.getenv("POSTGRES_PORT", 5432),
            database=os.getenv("POSTGRES_DB"),
            user="postgres",  # Use postgres superuser as requested
            password=os.getenv("POSTGRES_PASSWORD"),
        )
        connection.autocommit = False  # We want explicit transaction control
        return connection
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        raise


def check_prerequisites():
    """Check that employee_profiles table exists and has data."""
    logger.info("Checking prerequisites...")

    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        # Check if employee_profiles exists
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'employee_profiles'
            );
        """)

        if not cursor.fetchone()[0]:
            raise RuntimeError(
                "employee_profiles table does not exist. Consolidation not complete."
            )

        # Check if it has data
        cursor.execute("SELECT COUNT(*) FROM employee_profiles;")
        count = cursor.fetchone()[0]

        if count == 0:
            logger.warning("employee_profiles table is empty. Proceeding anyway...")
        else:
            logger.info(f"employee_profiles table has {count} records")

        # Check legacy tables
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name IN ('graph_photos', 'data_warehouse_cache');
        """)

        legacy_tables = [row[0] for row in cursor.fetchall()]
        logger.info(f"Legacy tables found: {legacy_tables}")

        conn.commit()
        return legacy_tables

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def execute_sql_file(sql_file_path, dry_run=False):
    """Execute the SQL file."""
    logger.info(f"{'[DRY RUN] ' if dry_run else ''}Executing SQL file: {sql_file_path}")

    if not os.path.exists(sql_file_path):
        raise FileNotFoundError(f"SQL file not found: {sql_file_path}")

    with open(sql_file_path, "r") as f:
        sql_content = f.read()

    if dry_run:
        logger.info("DRY RUN - SQL content that would be executed:")
        print("=" * 80)
        print(sql_content)
        print("=" * 80)
        return

    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        # Execute the SQL file
        cursor.execute(sql_content)

        # Commit the transaction
        conn.commit()
        logger.info("SQL file executed successfully")

    except Exception as e:
        conn.rollback()
        logger.error(f"Error executing SQL: {e}")
        raise
    finally:
        conn.close()


def verify_cleanup():
    """Verify the tables were dropped successfully."""
    logger.info("Verifying cleanup...")

    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        # Check that legacy tables are gone
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name IN ('graph_photos', 'data_warehouse_cache');
        """)

        remaining_tables = [row[0] for row in cursor.fetchall()]

        if remaining_tables:
            raise RuntimeError(f"Legacy tables still exist: {remaining_tables}")

        # Verify employee_profiles still exists
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'employee_profiles'
            );
        """)

        if not cursor.fetchone()[0]:
            raise RuntimeError("employee_profiles table missing after cleanup!")

        logger.info(
            "Cleanup verification successful - legacy tables dropped, employee_profiles intact"
        )
        conn.commit()

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description="Drop legacy tables after employee_profiles consolidation"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be executed without making changes",
    )

    args = parser.parse_args()

    try:
        logger.info("Starting legacy table cleanup process...")

        # Check prerequisites
        legacy_tables = check_prerequisites()

        if not legacy_tables:
            logger.info("No legacy tables found - cleanup already complete")
            return

        # Execute the SQL file
        sql_file = project_root / "scripts" / "drop_legacy_tables.sql"
        execute_sql_file(sql_file, dry_run=args.dry_run)

        if not args.dry_run:
            # Verify cleanup
            verify_cleanup()
            logger.info("Legacy table cleanup completed successfully!")
        else:
            logger.info("DRY RUN completed - no changes made")

    except Exception as e:
        logger.error(f"Legacy table cleanup failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
