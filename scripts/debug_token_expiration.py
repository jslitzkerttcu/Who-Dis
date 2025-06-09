#!/usr/bin/env python3
"""
Debug script to investigate API token expiration issues in a live system.

This script can be run to check the actual token status and help identify
why tokens might be showing as expired when they shouldn't be.
"""

import os
import sys
from datetime import datetime, timezone

# Add the project root to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)


def debug_token_expiration():
    """Debug API token expiration issues with detailed logging."""
    try:
        from app.app_factory import create_app
        from app.models.api_token import ApiToken

        # Create app context
        app = create_app()

        with app.app_context():
            print("=== API Token Expiration Debug Report ===")
            print(f"Current UTC time: {datetime.now(timezone.utc).isoformat()}")
            print()

            # Get all tokens using the improved status method
            status_list = ApiToken.get_all_tokens_status()

            if not status_list:
                print("No API tokens found in database.")
                return

            for status in status_list:
                print(f"Service: {status['service']}")
                print(f"Stored expires_at: {status['expires_at']}")
                print(f"Expires_at in UTC: {status['expires_at_utc']}")
                print(f"Current time UTC: {status['current_time_utc']}")
                print(f"Timezone info: {status['timezone_info']}")
                print(f"Time difference (seconds): {status['time_diff_seconds']}")
                print(f"Is expired: {status['is_expired']}")
                print(f"Time until expiry: {status['time_until_expiry']}")
                print(f"Last refreshed: {status['last_refreshed']}")

                # Additional analysis
                if status["time_diff_seconds"] > 30:
                    print("✓ Token should be valid (more than 30 seconds until expiry)")
                elif status["time_diff_seconds"] > 0:
                    print("⚠ Token is valid but expires soon (within 30 seconds)")
                else:
                    print("✗ Token is genuinely expired")

                # Test get_token method
                try:
                    retrieved_token = ApiToken.get_token(status["service"])
                    if retrieved_token:
                        print("✓ get_token() returns token (considers it valid)")
                    else:
                        print("✗ get_token() returns None (considers it expired)")
                except Exception as e:
                    print(f"✗ Error calling get_token(): {e}")

                print("-" * 60)

            print("\n=== Debugging Tips ===")
            print("If tokens show as expired but shouldn't be:")
            print("1. Check if timezone_info shows 'naive' - this could cause issues")
            print(
                "2. Look at time_diff_seconds - if positive but small (<30), the buffer is working"
            )
            print(
                "3. Compare 'expires_at' with 'expires_at_utc' for timezone conversion issues"
            )
            print("4. Check if get_token() result matches is_expired status")

    except Exception as e:
        print(f"Error during debug: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    debug_token_expiration()
