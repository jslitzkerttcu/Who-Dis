#!/usr/bin/env python3
"""
Quick test script to manually create and test token expiration scenarios.
This can be run without database to verify the logic works correctly.
"""

from datetime import datetime, timezone, timedelta
import sys

# Add project root to path
sys.path.insert(0, "/home/administrator/Repos/WhoDis")


# Mock database objects for testing
class MockToken:
    def __init__(self, service_name, expires_at, access_token="test_token"):
        self.service_name = service_name
        self.expires_at = expires_at
        self.access_token = access_token
        self.last_refreshed = datetime.now(timezone.utc)

    def is_expired(self) -> bool:
        """
        Implement the fixed is_expired logic.
        """
        now = datetime.now(timezone.utc)
        expires_at = self.expires_at

        # Ensure both datetimes are timezone-aware and in UTC
        if expires_at.tzinfo is None:
            # If stored as naive datetime, assume it's UTC
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        else:
            # Convert to UTC if it's in a different timezone
            expires_at = expires_at.astimezone(timezone.utc)

        # Add a small buffer (30 seconds) to account for clock skew and processing time
        buffer = timedelta(seconds=30)
        return now > (expires_at - buffer)

    @property
    def time_until_expiry(self):
        """Get time remaining until token expires."""
        now = datetime.now(timezone.utc)
        expires_at = self.expires_at

        # Handle timezone-naive vs timezone-aware comparison using same logic as is_expired
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        else:
            expires_at = expires_at.astimezone(timezone.utc)

        delta = expires_at - now
        return delta if delta.total_seconds() > 0 else timedelta(0)


def test_token_scenarios():
    """Test various token expiration scenarios."""

    print("=== Quick Token Test ===")

    now = datetime.now(timezone.utc)

    # Create test tokens with different expiration scenarios
    test_tokens = [
        MockToken("test_valid", now + timedelta(hours=1)),  # Valid for 1 hour
        MockToken("test_expired", now - timedelta(hours=1)),  # Expired 1 hour ago
        MockToken(
            "test_soon", now + timedelta(seconds=15)
        ),  # Expires in 15 seconds (should be expired due to buffer)
        MockToken(
            "test_buffer", now + timedelta(seconds=45)
        ),  # Expires in 45 seconds (should be valid)
        MockToken(
            "test_naive", (now + timedelta(hours=1)).replace(tzinfo=None)
        ),  # Naive datetime
    ]

    for token in test_tokens:
        print(f"\nToken: {token.service_name}")
        print(f"Expires at: {token.expires_at}")
        print(f"Is expired: {token.is_expired()}")
        print(f"Time until expiry: {token.time_until_expiry}")

        # Simulate get_token logic
        if not token.is_expired():
            print("✓ get_token() would return this token")
        else:
            print("✗ get_token() would return None")


def simulate_issue():
    """Simulate the reported issue scenario."""

    print("\n=== Simulating Reported Issue ===")
    print("Creating a token that should be valid but might show as expired...")

    now = datetime.now(timezone.utc)

    # Create a token that expires in 30 minutes (should definitely be valid)
    valid_token = MockToken("simulation", now + timedelta(minutes=30))

    print(f"Created token expiring at: {valid_token.expires_at}")
    print(f"Current time: {now}")
    print(f"Time until expiry: {valid_token.time_until_expiry}")
    print(f"Is expired (fixed logic): {valid_token.is_expired()}")

    # Test old logic for comparison
    old_logic_expired = now > valid_token.expires_at
    print(f"Is expired (old simple logic): {old_logic_expired}")

    if valid_token.is_expired() != old_logic_expired:
        print("⚠ Different results between old and new logic!")
    else:
        print("✓ Both logics agree")


if __name__ == "__main__":
    test_token_scenarios()
    simulate_issue()

    print("\n=== Summary ===")
    print("The fixed logic includes:")
    print("1. Proper timezone handling for both naive and aware datetimes")
    print("2. 30-second buffer to prevent edge cases")
    print("3. Better logging for debugging")
    print("4. Consistent UTC conversion")
    print("\nTo apply these fixes:")
    print("1. The ApiToken model has been updated with the fixes")
    print("2. Use scripts/debug_token_expiration.py to test in live system")
    print("3. Monitor logs for 'Found token for...' debug messages")
