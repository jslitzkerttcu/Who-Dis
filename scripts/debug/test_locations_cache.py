#!/usr/bin/env python3
"""Test script to manually trigger and verify Genesys locations caching."""

import sys
import os
import psycopg2
from psycopg2.extras import RealDictCursor
import json
import requests
from datetime import datetime
from pathlib import Path

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables from .env file in project root
try:
    from dotenv import load_dotenv

    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        print(f"✓ Loaded environment from {env_path}")
    else:
        print(f"⚠ No .env file found at {env_path}")
except ImportError:
    print("⚠ python-dotenv not installed. Install with: pip install python-dotenv")


def get_db_connection():
    """Get direct database connection."""
    # Check for required environment variables
    password = os.getenv("POSTGRES_PASSWORD")
    if not password:
        print("❌ POSTGRES_PASSWORD environment variable is not set!")
        print("\nMake sure you have a .env file in the project root with:")
        print("  POSTGRES_PASSWORD=your-password-here")
        print("\nOr set it manually:")
        print("  export POSTGRES_PASSWORD='your-password-here'")
        print("  python scripts/test_locations_cache.py")
        return None

    try:
        # Show connection details (without password)
        host = os.getenv("POSTGRES_HOST", "localhost")
        port = os.getenv("POSTGRES_PORT", "5432")
        database = os.getenv("POSTGRES_DB", "whodis_db")
        user = os.getenv("POSTGRES_USER", "whodis_user")

        print("\nConnecting to PostgreSQL:")
        print(f"  Host: {host}")
        print(f"  Port: {port}")
        print(f"  Database: {database}")
        print(f"  User: {user}")

        conn = psycopg2.connect(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password,
        )
        print("✓ Connected successfully!\n")
        return conn
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        print("\nPlease check your database connection settings.")
        return None


def get_config_value(cursor, category, key):
    """Get configuration value from database."""
    cursor.execute(
        """
        SELECT setting_value, encrypted_value 
        FROM configuration 
        WHERE category = %s AND setting_key = %s
    """,
        (category, key),
    )

    result = cursor.fetchone()
    if result:
        if result["encrypted_value"]:
            # For this script, we'll skip decryption
            return None
        return result["setting_value"]
    return None


def get_genesys_token(cursor):
    """Get Genesys token from database."""
    cursor.execute("""
        SELECT access_token, expires_at 
        FROM api_tokens 
        WHERE service_name = 'genesys'
        ORDER BY expires_at DESC
        LIMIT 1
    """)

    result = cursor.fetchone()
    if result and result["expires_at"] > datetime.utcnow():
        return result["access_token"]
    return None


def refresh_locations_cache(cursor, token, base_url):
    """Refresh the locations cache."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    try:
        url = f"{base_url}/api/v2/locations"
        print(f"Calling: {url} with pageSize=400")

        response = requests.get(
            url, headers=headers, params={"pageSize": 400}, timeout=30
        )

        if response.status_code != 200:
            print(f"❌ Failed to fetch locations: {response.status_code}")
            print(f"Response: {response.text}")
            return False

        data = response.json()
        locations = data.get("entities", [])
        total_count = data.get("total", 0)

        print(f"✓ Received {len(locations)} locations from API (total: {total_count})")

        # Clear existing locations
        cursor.execute("DELETE FROM genesys_locations")

        # Insert new locations
        inserted = 0
        for location in locations:
            location_id = location.get("id")
            if location_id:
                # Extract emergency number properly
                emergency_number = None
                emergency_obj = location.get("emergencyNumber")
                if emergency_obj and isinstance(emergency_obj, dict):
                    emergency_number = emergency_obj.get("number") or emergency_obj.get(
                        "e164"
                    )

                cursor.execute(
                    """
                    INSERT INTO genesys_locations (id, name, emergency_number, address, raw_data)
                    VALUES (%s, %s, %s, %s, %s)
                """,
                    (
                        location_id,
                        location.get("name", "Unknown"),
                        emergency_number,
                        json.dumps(location.get("address"))
                        if location.get("address")
                        else None,
                        json.dumps(location),
                    ),
                )
                inserted += 1

        print(f"✓ Inserted {inserted} locations into database")
        return True

    except Exception as e:
        print(f"❌ Error refreshing locations: {str(e)}")
        return False


def test_locations_cache():
    """Test the locations caching functionality."""
    conn = get_db_connection()
    if not conn:
        return 1

    cursor = conn.cursor(cursor_factory=RealDictCursor)

    try:
        print("=== Genesys Locations Cache Test ===\n")

        # Check current token status
        token = get_genesys_token(cursor)
        if token:
            print("✓ Genesys token found in database")
        else:
            print("✗ No valid Genesys token found in database")
            print(
                "  Please ensure the application has been run at least once to obtain a token"
            )
            return 1

        # Get Genesys region
        region = get_config_value(cursor, "genesys", "region") or "mypurecloud.com"
        base_url = f"https://api.{region}"
        print(f"Using region: {region}")

        # Check current cache status
        print("\n--- Current Cache Status ---")
        cursor.execute("SELECT COUNT(*) as count FROM genesys_locations")
        count = cursor.fetchone()["count"]
        print(f"Locations cached: {count}")

        if count > 0:
            cursor.execute("""
                SELECT MAX(cached_at) as last_update 
                FROM genesys_locations
            """)
            last_update = cursor.fetchone()["last_update"]
            if last_update:
                print(f"Last update: {last_update}")
                age = datetime.utcnow() - last_update
                print(f"Cache age: {age}")

        # Get sample of current cached locations
        cursor.execute(
            "SELECT id, name, emergency_number FROM genesys_locations LIMIT 5"
        )
        current_locations = cursor.fetchall()

        if current_locations:
            print("\nSample of currently cached locations:")
            for loc in current_locations:
                print(f"  - {loc['name']} (ID: {loc['id'][:8]}...)")
                if loc["emergency_number"]:
                    print(f"    Emergency: {loc['emergency_number']}")

        # Ask to refresh
        print("\n--- Refresh Locations Cache ---")
        response = input("Do you want to refresh the locations cache? (y/n): ")

        if response.lower() == "y":
            print("\nRefreshing locations cache...")

            if refresh_locations_cache(cursor, token, base_url):
                conn.commit()
                print("✓ Locations cache refreshed successfully!")

                # Show new stats
                cursor.execute("SELECT COUNT(*) as count FROM genesys_locations")
                new_count = cursor.fetchone()["count"]
                print(f"\nTotal locations cached: {new_count}")

                # Show sample of new data
                cursor.execute("""
                    SELECT id, name, emergency_number, address 
                    FROM genesys_locations 
                    LIMIT 5
                """)
                new_locations = cursor.fetchall()

                if new_locations:
                    print("\nSample of newly cached locations:")
                    for loc in new_locations:
                        print(f"\n  Location: {loc['name']}")
                        print(f"  ID: {loc['id']}")
                        if loc["emergency_number"]:
                            print(f"  Emergency: {loc['emergency_number']}")
                        if loc["address"]:
                            addr = loc["address"]
                            if isinstance(addr, dict):
                                print(
                                    f"  Address: {addr.get('street1', '')}, {addr.get('city', '')}, {addr.get('state', '')} {addr.get('zipcode', '')}"
                                )
            else:
                conn.rollback()
                print("✗ Failed to refresh locations cache")

        # Test location name resolution
        print("\n--- Test Location Name Resolution ---")
        test_id = input(
            "Enter a location ID to test resolution (or press Enter to skip): "
        )

        if test_id.strip():
            cursor.execute(
                """
                SELECT name FROM genesys_locations WHERE id = %s
            """,
                (test_id.strip(),),
            )

            result = cursor.fetchone()
            if result:
                print(f"✓ Location ID '{test_id}' resolved to: '{result['name']}'")
            else:
                print(f"✗ Location ID '{test_id}' not found in cache")

        return 0

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return 1
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    sys.exit(test_locations_cache())
