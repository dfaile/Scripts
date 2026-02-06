#!/usr/bin/env python3
"""Test authentication with client credentials.

This script verifies that client credential authentication works correctly.
"""
import sys

from examples.common import get_config, StatusPageClient


def test_auth():
    """Test authentication flow."""
    print("Testing Nobl9 Status Page API Authentication")
    print("=" * 60)

    # Load config
    try:
        config = get_config()
        print("✅ Configuration loaded successfully")
    except ValueError as e:
        print(f"❌ Configuration error: {e}")
        return False

    # Check auth method
    if config.api_token:
        print("ℹ️  Using pre-generated API token")
        print(f"   Token: {config.api_token[:10]}...")
    elif config.client_id and config.client_secret:
        print("✅ Using client credentials (recommended)")
        print(f"   Client ID: {config.client_id[:10]}...")
        print(f"   Client Secret: {config.client_secret[:10]}...")
    else:
        print("❌ No authentication credentials found")
        return False

    print(f"   Organization: {config.organization}")
    print(f"   Base URL: {config.base_url}")

    # Create client
    print("\n📡 Creating API client...")
    client = StatusPageClient(config)

    # Test API call
    print("🔑 Testing authentication with API call...")
    try:
        result = client.get("/status-page/status")
        print("✅ Authentication successful!")
        print(f"   Retrieved {len(result.get('components', []))} top-level components")

        # If using client credentials, verify token was generated
        if config.client_id and not config.api_token:
            if client.access_token:
                print(f"✅ Access token generated: {client.access_token[:10]}...")
            else:
                print("⚠️  Warning: No access token generated")

        return True

    except Exception as e:
        print(f"❌ Authentication failed: {e}")
        return False


if __name__ == "__main__":
    print()
    success = test_auth()
    print("\n" + "=" * 60)
    if success:
        print("🎉 All authentication tests passed!")
        sys.exit(0)
    else:
        print("❌ Authentication tests failed")
        print("\nTroubleshooting:")
        print("1. Verify your credentials in .env file")
        print("2. Check NOBL9_CLIENT_ID and NOBL9_CLIENT_SECRET are correct")
        print("3. Ensure NOBL9_ORG matches your organization ID")
        sys.exit(1)
