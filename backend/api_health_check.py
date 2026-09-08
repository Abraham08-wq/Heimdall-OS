import asyncio
import os
import httpx
from dotenv import load_dotenv
import os as _os
# Load .env.local (project standard); fall back to .env for CI environments.
_root = _os.path.dirname(_os.path.abspath(__file__))
load_dotenv(_os.path.join(_root, ".env.local")) or load_dotenv(_os.path.join(_root, "..", ".env.local"))
load_dotenv(_os.path.join(_root, ".env")) or load_dotenv(_os.path.join(_root, "..", ".env"))

async def check_api(name, url, headers=None, params=None):
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=headers, params=params, timeout=5.0)
            if resp.status_code in [200, 201]:
                print(f"✅ {name}: CONNECTED (Status: {resp.status_code})")
            elif resp.status_code == 401:
                print(f"❌ {name}: UNAUTHORIZED (Status: {resp.status_code}) - Check your API key!")
            elif resp.status_code == 403:
                print(f"❌ {name}: FORBIDDEN (Status: {resp.status_code}) - Key lacks permissions or quotas exceeded.")
            else:
                print(f"⚠️ {name}: UNKNOWN RESPONSE (Status: {resp.status_code})")
    except Exception as e:
        print(f"🛑 {name}: CONNECTION FAILED ({str(e)})")

async def main():
    print("====================================")
    print(" OMNI-PROBE: LIVE OSINT LINK CHECK  ")
    print("====================================\n")

    # Shodan
    shodan_key = os.getenv("SHODAN_API_KEY")
    if shodan_key:
        await check_api("Shodan", "https://api.shodan.io/api-info", params={"key": shodan_key})
    else:
        print("⏭️ Shodan: SKIPPED (No API key found)")

    # AlienVault
    otx_key = os.getenv("ALIENVAULT_API_KEY")
    if otx_key:
        await check_api("AlienVault OTX", "https://otx.alienvault.com/api/v1/users/me", headers={"X-OTX-API-KEY": otx_key})
    else:
        print("⏭️ AlienVault OTX: SKIPPED (No API key found)")

    # Intel X
    intelx_key = os.getenv("INTEL_X_API_KEY")
    if intelx_key:
        await check_api("IntelX", "https://2.intelx.io/authenticate/info", headers={"x-key": intelx_key})
    else:
        print("⏭️ IntelX: SKIPPED (No API key found)")

    print("\n====================================")
    print(" Link check complete.")

if __name__ == "__main__":
    asyncio.run(main())
