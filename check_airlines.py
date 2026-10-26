#!/usr/bin/env python3
"""
Verify and switch Duffel API keys for real vs mock airlines.
Usage: python check_airlines.py [set-live <key>] [set-test] [status]
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment
load_dotenv()

def get_env_file():
    """Get path to .env file."""
    return Path(__file__).parent.parent / ".env"

def read_env():
    """Read .env file."""
    env_file = get_env_file()
    env_data = {}
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    if "=" in line:
                        key, val = line.split("=", 1)
                        env_data[key] = val
    return env_data

def write_env(data):
    """Write .env file."""
    env_file = get_env_file()
    with open(env_file, "w") as f:
        for key, val in data.items():
            f.write(f"{key}={val}\n")

def status():
    """Check current API key status."""
    api_key = os.getenv("DUFFEL_API_KEY", "")
    base_url = os.getenv("DUFFEL_BASE_URL", "")

    print("\n" + "=" * 70)
    print("DUFFEL API CONFIGURATION STATUS")
    print("=" * 70)

    if not api_key:
        print("\n❌ DUFFEL_API_KEY not found in environment")
        return False

    # Check key type
    if "duffel_test_" in api_key:
        key_type = "TEST"
        airlines = "❌ Mock airlines (Duffel Airways, etc.)"
        status_icon = "⚠️"
    elif "duffel_live_" in api_key:
        key_type = "LIVE"
        airlines = "✅ Real airlines (BA, LH, AF, etc.)"
        status_icon = "✅"
    else:
        key_type = "UNKNOWN"
        airlines = "❓ Unknown key format"
        status_icon = "❓"

    print(f"\n{status_icon} API Key Type: {key_type}")
    print(f"   Key: {api_key[:30]}...")
    print(f"   Base URL: {base_url}")
    print(f"   Airlines: {airlines}")

    if key_type == "TEST":
        print(f"\n💡 To enable REAL airlines:")
        print(f"   1. Get a live key from https://dashboard.duffel.com")
        print(f"   2. Run: python check_airlines.py set-live <your-live-key>")

    print("\n" + "=" * 70 + "\n")
    return key_type == "LIVE"

def set_live(api_key):
    """Set live Duffel API key."""
    if not api_key.startswith("duffel_live_"):
        print("❌ Error: Live keys should start with 'duffel_live_'")
        print(f"   You provided: {api_key[:20]}...")
        return False

    env_data = read_env()
    env_data["DUFFEL_API_KEY"] = api_key
    env_data["DUFFEL_BASE_URL"] = "https://api.duffel.com"
    write_env(env_data)

    print("\n✅ Updated .env with LIVE Duffel API key")
    print(f"   Key: {api_key[:30]}...")
    print("\n🔄 Restart app to use real airlines:")
    print("   pkill -f 'python app.py'")
    print("   python app.py")
    return True

def set_test():
    """Set test Duffel API key (default)."""
    test_key = "duffel_test_iGY0PYAbebfOHA5X5LeN6NsJmDRfPXmhUTn68mCeTl2"

    env_data = read_env()
    env_data["DUFFEL_API_KEY"] = test_key
    env_data["DUFFEL_BASE_URL"] = "https://api.duffel.com"
    write_env(env_data)

    print("\n⚠️ Switched back to TEST Duffel API key")
    print(f"   Key: {test_key[:30]}...")
    print("   Airlines: Mock data (Duffel Airways, etc.)")
    print("\n🔄 Restart app to use mock airlines:")
    print("   pkill -f 'python app.py'")
    print("   python app.py")
    return True

def main():
    """Main function."""
    if len(sys.argv) < 2:
        status()
        print("Usage:")
        print("  python check_airlines.py status              # Check current API key")
        print("  python check_airlines.py set-live <key>      # Switch to live airlines")
        print("  python check_airlines.py set-test            # Switch to mock airlines")
        return

    command = sys.argv[1]

    if command == "status":
        status()
    elif command == "set-live":
        if len(sys.argv) < 3:
            print("❌ Error: Please provide live API key")
            print("   Usage: python check_airlines.py set-live <your-live-key>")
            sys.exit(1)
        set_live(sys.argv[2])
    elif command == "set-test":
        set_test()
    else:
        print(f"❌ Unknown command: {command}")
        print("   Valid commands: status, set-live <key>, set-test")

if __name__ == "__main__":
    main()
