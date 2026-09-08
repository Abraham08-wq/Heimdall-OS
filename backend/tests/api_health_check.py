#!/usr/bin/env python3
import asyncio
import httpx
from dotenv import load_dotenv
import os as _os

# Load .env.local (project standard); fall back to .env for CI environments.
_root = _os.path.dirname(_os.path.abspath(__file__))
load_dotenv(_os.path.join(_root, ".env.local")) or load_dotenv(_os.path.join(_root, "..", ".env.local"))
load_dotenv(_os.path.join(_root, ".env")) or load_dotenv(_os.path.join(_root, "..", ".env"))

async def check_api(name, url, headers=None, expected_status=200):
    print(f"Checking {name}...", end=" ")
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=headers, timeout=5.0)
            if resp.status_code == expected_status or resp.status_code in [401, 403]:
                if resp.status_code == 200:
                    print("\033[92m[OK - Valid Key]\033[0m")
                else:
                    print("\033[93m[UNAUTHORIZED - Missing or Invalid Key]\033[0m")
            else:
                 print(f"\033[91m[FAILED - Status {resp.status_code}]\033[0m")
    except Exception as e:
        print(f"\033[91m[ERROR - {e}]\033[0m")

async def main():
    print("====================================")
    print("ProjectXY - OSINT API Health Check")
    print("====================================")
    
    shodan_key = os.getenv("SHODAN_API_KEY", "")
    await check_api("Shodan", f"https://api.shodan.io/account/profile?key={shodan_key}")

    alienvault_key = os.getenv("ALIENVAULT_API_KEY", "")
    await check_api("AlienVault OTX", "https://otx.alienvault.com/api/v1/user/me", headers={"X-OTX-API-KEY": alienvault_key})

    intelx_key = os.getenv("INTEL_X_API_KEY", "")
    # IntelX doesn't have a simple user profile GET endpoint via API, we just check access to stats or general info
    await check_api("Intel X", "https://2.intelx.io/intelligent/search/result?id=test", headers={"x-key": intelx_key}, expected_status=404) # 404 is okay as long as not 401

if __name__ == "__main__":
    asyncio.run(main())
