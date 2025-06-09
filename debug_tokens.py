#!/usr/bin/env python3
"""
Debug script to investigate API token expiration issues.
"""

import os
import sys
from datetime import datetime, timezone

# Add the project root to the Python path
sys.path.insert(0, "/home/administrator/Repos/WhoDis")

# Set required environment variables for database connection
os.environ.setdefault("POSTGRES_HOST", "localhost")
os.environ.setdefault("POSTGRES_PORT", "5432")
os.environ.setdefault("POSTGRES_DB", "whodis_db")
os.environ.setdefault("POSTGRES_USER", "whodis_user")
# Note: password should be set separately or via env file


def debug_tokens():
    """Debug API token expiration issues."""
    try:
        from app.app_factory import create_app
        from app.models.api_token import ApiToken

        # Create app context
        app = create_app()

        with app.app_context():
            print("=== API Token Debug Report ===")
            print(f"Current UTC time: {datetime.now(timezone.utc).isoformat()}")
            print()

            # Get all tokens
            tokens = ApiToken.query.all()

            if not tokens:
                print("No API tokens found in database.")
                return

            for token in tokens:
                print(f"Service: {token.service_name}")
                print(
                    f"Stored expires_at: {token.expires_at} (type: {type(token.expires_at)})"
                )
                print(f"Timezone info: {token.expires_at.tzinfo}")

                # Check what the model thinks
                print(f"is_expired property: {token.is_expired}")

                # Manual calculation
                now = datetime.now(timezone.utc)
                expires_at = token.expires_at

                # Handle timezone handling like the model does
                if expires_at.tzinfo is None:
                    expires_at_tz = expires_at.replace(tzinfo=timezone.utc)
                    print(f"Converted naive datetime to UTC: {expires_at_tz}")
                else:
                    expires_at_tz = expires_at

                print(f"Current time (UTC): {now}")
                print(f"Expires at (with timezone): {expires_at_tz}")

                time_diff = expires_at_tz - now
                is_expired_manual = now > expires_at_tz

                print(f"Time difference: {time_diff}")
                print(f"Manual is_expired calculation: {is_expired_manual}")
                print(f"time_until_expiry: {token.time_until_expiry}")

                # Check if there's a mismatch
                if token.is_expired != is_expired_manual:
                    print("*** MISMATCH DETECTED! ***")
                    print(
                        f"Model says: {token.is_expired}, Manual calculation says: {is_expired_manual}"
                    )

                print(f"Last refreshed: {token.last_refreshed}")
                print("-" * 50)

            # Also check using the get_token method
            print("\n=== Testing get_token method ===")
            for token in tokens:
                retrieved_token = ApiToken.get_token(token.service_name)
                if retrieved_token:
                    print(
                        f"{token.service_name}: get_token() returned a token (not expired)"
                    )
                else:
                    print(
                        f"{token.service_name}: get_token() returned None (expired or missing)"
                    )

    except Exception as e:
        print(f"Error during debug: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    debug_tokens()
