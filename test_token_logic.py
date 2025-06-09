#!/usr/bin/env python3
"""
Test script to verify token expiration logic without database.
"""

from datetime import datetime, timezone, timedelta


def test_timezone_handling():
    """Test various timezone scenarios that could cause expiration issues."""

    print("=== Testing Token Expiration Logic ===")

    # Current time
    now = datetime.now(timezone.utc)
    print(f"Current UTC time: {now}")

    # Test scenarios
    scenarios = [
        {
            "name": "Valid token (1 hour future)",
            "expires_at": now + timedelta(hours=1),
            "expected_expired": False,
        },
        {
            "name": "Expired token (1 hour past)",
            "expires_at": now - timedelta(hours=1),
            "expected_expired": True,
        },
        {
            "name": "Token expiring soon (1 minute future)",
            "expires_at": now + timedelta(minutes=1),
            "expected_expired": False,  # Should not be expired yet
        },
        {
            "name": "Token expiring very soon (10 seconds future)",
            "expires_at": now + timedelta(seconds=10),
            "expected_expired": True,  # Should be expired due to 30-second buffer
        },
        {
            "name": "Naive datetime (stored without timezone)",
            "expires_at": (now + timedelta(hours=1)).replace(tzinfo=None),
            "expected_expired": False,
        },
        {
            "name": "Naive datetime expired",
            "expires_at": (now - timedelta(hours=1)).replace(tzinfo=None),
            "expected_expired": True,
        },
    ]

    print()

    for scenario in scenarios:
        print(f"Scenario: {scenario['name']}")
        expires_at = scenario["expires_at"]

        # Simulate the fixed is_expired logic
        test_now = datetime.now(timezone.utc)

        # Handle timezone conversion like our fixed code
        if expires_at.tzinfo is None:
            expires_at_utc = expires_at.replace(tzinfo=timezone.utc)
        else:
            expires_at_utc = expires_at.astimezone(timezone.utc)

        # Apply 30-second buffer
        buffer = timedelta(seconds=30)
        is_expired = test_now > (expires_at_utc - buffer)

        # Calculate time difference
        time_diff = expires_at_utc - test_now

        print(f"  Expires at: {expires_at}")
        print(f"  Expires at UTC: {expires_at_utc}")
        print(f"  Time difference: {time_diff}")
        print(f"  Is expired (with buffer): {is_expired}")
        print(f"  Expected: {scenario['expected_expired']}")

        if is_expired == scenario["expected_expired"]:
            print("  ✓ PASS")
        else:
            print(
                f"  ✗ FAIL - Expected {scenario['expected_expired']}, got {is_expired}"
            )

        print()


def test_old_logic():
    """Test the old logic to see what might be wrong."""

    print("=== Testing Old Logic ===")

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=30)  # Valid token

    print(f"Current time: {now}")
    print(f"Expires at: {expires_at}")

    # Old logic from base.py
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    is_expired_old = now > expires_at
    print(f"Old logic result: {is_expired_old}")
    print(f"Should be False for valid token: {not is_expired_old}")

    # Test with naive datetime
    print("\n--- Testing with naive datetime ---")
    expires_at_naive = (now + timedelta(minutes=30)).replace(tzinfo=None)
    print(f"Naive expires_at: {expires_at_naive}")

    test_now = datetime.now(timezone.utc)
    if expires_at_naive.tzinfo is None:
        expires_at_converted = expires_at_naive.replace(tzinfo=timezone.utc)

    is_expired_naive = test_now > expires_at_converted
    print(f"Result with naive datetime: {is_expired_naive}")


if __name__ == "__main__":
    test_timezone_handling()
    test_old_logic()
