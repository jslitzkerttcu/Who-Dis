#!/usr/bin/env python3
"""Test script to verify Genesys locations API endpoint and response format."""

import os
import requests
import json

# Configuration - update these as needed
GENESYS_REGION = os.getenv("GENESYS_REGION", "mypurecloud.com")
GENESYS_CLIENT_ID = os.getenv("GENESYS_CLIENT_ID")
GENESYS_CLIENT_SECRET = os.getenv("GENESYS_CLIENT_SECRET")


def get_access_token():
    """Get access token from Genesys OAuth."""
    token_url = f"https://login.{GENESYS_REGION}/oauth/token"

    data = {
        "grant_type": "client_credentials",
        "client_id": GENESYS_CLIENT_ID,
        "client_secret": GENESYS_CLIENT_SECRET,
    }

    response = requests.post(token_url, data=data)

    if response.status_code == 200:
        token_data = response.json()
        return token_data.get("access_token")
    else:
        print(f"Failed to get token: {response.status_code} - {response.text}")
        return None


def test_locations_api(token):
    """Test the locations API endpoint."""
    base_url = f"https://api.{GENESYS_REGION}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # Test the exact endpoint that should be used
    url = f"{base_url}/api/v2/locations?pageSize=400"

    print(f"\nTesting endpoint: {url}")

    try:
        response = requests.get(url, headers=headers, timeout=30)

        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()

            print("\nResponse structure:")
            print(f"- Total locations: {data.get('total', 0)}")
            print(f"- Page size: {data.get('pageSize', 0)}")
            print(f"- Page number: {data.get('pageNumber', 0)}")
            print(f"- Entities count: {len(data.get('entities', []))}")

            locations = data.get("entities", [])

            if locations:
                print("\nFirst 3 locations:")
                for i, loc in enumerate(locations[:3]):
                    print(f"\n  Location {i + 1}:")
                    print(f"  - ID: {loc.get('id')}")
                    print(f"  - Name: {loc.get('name')}")
                    print(f"  - State: {loc.get('state')}")

                    if loc.get("address"):
                        addr = loc["address"]
                        print(
                            f"  - Address: {addr.get('street1', '')}, {addr.get('city', '')}, {addr.get('state', '')} {addr.get('zipcode', '')}"
                        )

                    if loc.get("emergencyNumber"):
                        em = loc["emergencyNumber"]
                        print(
                            f"  - Emergency Number: {em.get('number', em.get('e164', ''))}"
                        )

            # Save full response for analysis
            with open("locations_response.json", "w") as f:
                json.dump(data, f, indent=2)
            print("\nFull response saved to locations_response.json")

            return True
        else:
            print(f"Error response: {response.text}")
            return False

    except Exception as e:
        print(f"Error testing locations API: {str(e)}")
        return False


def main():
    """Main test function."""
    print("Genesys Locations API Test")
    print("=" * 40)

    if not GENESYS_CLIENT_ID or not GENESYS_CLIENT_SECRET:
        print("ERROR: GENESYS_CLIENT_ID and GENESYS_CLIENT_SECRET must be set")
        return

    print(f"Region: {GENESYS_REGION}")
    print(f"Client ID: {GENESYS_CLIENT_ID[:10]}...")

    # Get token
    print("\nGetting access token...")
    token = get_access_token()

    if not token:
        print("Failed to get access token")
        return

    print("Successfully obtained access token")

    # Test locations API
    if test_locations_api(token):
        print("\nLocations API test successful!")
    else:
        print("\nLocations API test failed!")


if __name__ == "__main__":
    main()
