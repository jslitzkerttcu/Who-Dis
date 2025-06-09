#!/usr/bin/env python3
"""
Debug script to check if the Graph API token is really expired.
"""

import os
import sys
from datetime import datetime, timezone


def debug_graph_token():
    """Debug the actual Graph API token status."""

    # Set database connection parameters (using same as previous script)
    os.environ["POSTGRES_HOST"] = "172.17.50.245"
    os.environ["POSTGRES_USER"] = "postgres"
    os.environ["POSTGRES_DB"] = "whodis_db"
    os.environ["POSTGRES_PORT"] = "5432"

    # Get password from command line argument
    if len(sys.argv) != 2:
        print("Usage: python debug_graph_token.py <postgres_password>")
        sys.exit(1)

    password = sys.argv[1]
    os.environ["POSTGRES_PASSWORD"] = password

    from app.app_factory import create_app
    from app.models.api_token import ApiToken
    from app.services.graph_service import graph_service

    app = create_app()

    with app.app_context():
        print("=== Graph API Token Debug ===")
        print(f"Current system time (UTC): {datetime.now(timezone.utc)}")
        print(f"Current system time (local): {datetime.now()}")
        print()

        # Get the Graph API token from database
        token = ApiToken.query.filter_by(service_name="microsoft_graph").first()

        if token:
            print("Database Token Info:")
            print(f"  Service: {token.service_name}")
            print(f"  Expires at (raw): {token.expires_at}")
            print(f"  Expires at timezone: {token.expires_at.tzinfo}")
            print(f"  Last refreshed: {token.last_refreshed}")
            print(f"  Is expired (method): {token.is_expired()}")
            print()

            # Check timezone interpretations
            if token.expires_at.tzinfo is None:
                print("Token stored as timezone-naive!")
                print(
                    f"  If interpreted as UTC: {token.expires_at.replace(tzinfo=timezone.utc)}"
                )

                # Check different timezone interpretations
                import pytz

                eastern = pytz.timezone("US/Eastern")
                central = pytz.timezone("US/Central")
                mountain = pytz.timezone("US/Mountain")
                pacific = pytz.timezone("US/Pacific")

                print(
                    f"  If it's actually Eastern time: {eastern.localize(token.expires_at).astimezone(timezone.utc)}"
                )
                print(
                    f"  If it's actually Central time: {central.localize(token.expires_at).astimezone(timezone.utc)}"
                )
                print(
                    f"  If it's actually Mountain time: {mountain.localize(token.expires_at).astimezone(timezone.utc)}"
                )
                print(
                    f"  If it's actually Pacific time: {pacific.localize(token.expires_at).astimezone(timezone.utc)}"
                )
            print()

        else:
            print("No Graph API token found in database!")
            print()

        # Try to test the actual token by making a simple Graph API call
        print("Testing actual Graph API access...")
        try:
            # Try to get a new token
            success = graph_service.refresh_token_if_needed()
            print(f"Token refresh attempt: {'SUCCESS' if success else 'FAILED'}")

            # Check if we can make a simple API call
            from app.services.graph_service import graph_service

            if hasattr(graph_service, "_get_access_token"):
                actual_token = graph_service._get_access_token()
                if actual_token:
                    print("✅ Graph service has a working token")

                    # Try a simple API call to verify it works
                    import requests

                    headers = {"Authorization": f"Bearer {actual_token}"}
                    response = requests.get(
                        "https://graph.microsoft.com/v1.0/users?$top=1",
                        headers=headers,
                        timeout=10,
                    )
                    print(f"Test API call result: {response.status_code}")
                    if response.status_code == 200:
                        print("✅ Token is actually VALID and working!")
                    else:
                        print(f"❌ Token failed API test: {response.text[:200]}")
                else:
                    print("❌ Graph service has no token")

        except Exception as e:
            print(f"❌ Error testing Graph API: {e}")


if __name__ == "__main__":
    debug_graph_token()
