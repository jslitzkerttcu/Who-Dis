#!/usr/bin/env python3
"""
Test timezone configuration functionality.
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timezone

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_timezone_config():
    """Test timezone configuration and display examples."""
    try:
        from app.utils.timezone import (
            get_configured_timezone,
            convert_to_configured_timezone,
            format_timestamp,
            format_timestamp_long,
            get_timezone_abbreviation,
        )

        # Create a test UTC timestamp
        utc_now = datetime.now(timezone.utc)
        print(f"UTC Time: {utc_now.strftime('%Y-%m-%d %H:%M:%S %Z')}")

        # Get configured timezone
        tz = get_configured_timezone()
        print(f"\nConfigured Timezone: {tz}")
        print(f"Timezone Abbreviation: {get_timezone_abbreviation()}")

        # Convert to configured timezone
        local_time = convert_to_configured_timezone(utc_now)
        print(f"\nLocal Time: {local_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")

        # Test formatting functions
        print(f"\nformat_timestamp(): {format_timestamp(utc_now)}")
        print(f"format_timestamp_long(): {format_timestamp_long(utc_now)}")

        # Test with different formats
        print(
            f"\nCustom format: {format_timestamp(utc_now, '%A, %B %d, %Y at %I:%M %p %Z')}"
        )

        # Test with naive datetime
        naive_dt = datetime.now()
        print(f"\nNaive datetime: {naive_dt}")
        print(f"Formatted: {format_timestamp(naive_dt)}")

        print("\nTimezone configuration test completed successfully!")

    except Exception as e:
        print(f"Error testing timezone configuration: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    # Set minimal environment for testing
    os.environ.setdefault("WHODIS_ENCRYPTION_KEY", "test-key-not-for-production")

    test_timezone_config()
