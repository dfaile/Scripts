#!/usr/bin/env python3
"""Test authentication with client credentials.

Verifies that client credential or API token authentication works.
Does not print any credential values.
"""
import sys

from examples.common import get_config, StatusPageClient


def main():
    print("Testing Nobl9 Status Page API Authentication")
    print("=" * 60)

    try:
        config = get_config()
        print("✅ Configuration loaded successfully")
    except ValueError as e:
        print(f"❌ Configuration error: {e}")
        sys.exit(1)

    if config.api_token:
        print("ℹ️  Using pre-generated API token")
    elif config.client_id and config.client_secret:
        print("✅ Using client credentials (recommended)")
    else:
        print("❌ No authentication credentials found")
        sys.exit(1)

    print(f"   Organization: {config.organization}")
    print(f"   Base URL: {config.base_url}")

    print("\n📡 Creating API client...")
    client = StatusPageClient(config)

    print("🔑 Testing authentication with API call...")
    try:
        result = client.get("/status-page/status")
        print("✅ Authentication successful!")
        print(f"   Retrieved {len(result.get('components', []))} top-level components")
        if config.client_id and not config.api_token and client.access_token:
            print("✅ Access token generated and cached")
    except Exception as e:
        print(f"❌ Authentication failed: {e}")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("🎉 All authentication tests passed!")
    sys.exit(0)


if __name__ == "__main__":
    main()
