import requests
import json
import sys

BASE_URL = "http://localhost:8000/api/v1"

def print_step(msg):
    print(f"\n[*] {msg}")

def print_success(msg):
    print(f"[+] SUCCESS: {msg}")

def print_error(msg):
    print(f"[-] ERROR: {msg}")

def test_offensive_flow():
    print("=== Starting Offensive Operations Smoke Test ===")
    
    # 1. Login to get Admin Token
    print_step("Authenticating as Admin...")
    login_data = {
        "username": "admin@projectxy.com",
        "password": "admin123"
    }
    
    try:
        # FastAPI OAuth2PasswordRequestForm uses form data
        res = requests.post(f"{BASE_URL}/login/access-token", data=login_data)
        if res.status_code == 200:
            token = res.json().get("access_token")
            print_success("Admin token acquired.")
            headers = {"Authorization": f"Bearer {token}"}
        else:
            print_error(f"Failed to authenticate. Status {res.status_code} - {res.text}")
            sys.exit(1)
    except requests.exceptions.ConnectionError:
        print_error("Backend not running at localhost:8000. Please start server to verify.")
        sys.exit(1)

    # 2. Test Recon Fetch
    print_step("Testing Recon Fetch (`/offensive/recon/fetch`)...")
    recon_data = {"url": "http://example.com"}
    try:
        res = requests.post(f"{BASE_URL}/offensive/recon/fetch", json=recon_data, headers=headers)
        if res.status_code == 200:
            print_success(f"Fetched content preview: {res.json()['content'][:100]}...")
        else:
            print_error(f"Status {res.status_code} - {res.text}")
    except Exception as e:
        print_error(str(e))

    # 3. Test Port Scan
    print_step("Testing Service Port Scan (`/offensive/scan/ports`)...")
    scan_data = {
        "target_ip": "127.0.0.1",
        "ports": [3306, 5432, 80, 443, 8000]
    }
    try:
        res = requests.post(f"{BASE_URL}/offensive/scan/ports", json=scan_data, headers=headers)
        if res.status_code == 200:
            results = res.json()["scan_results"]
            print_success(f"Port scan completed on {res.json()['target_ip']}.")
            for port, status in results.items():
                print(f"    - {port}: {status}")
        else:
            print_error(f"Status {res.status_code} - {res.text}")
    except Exception as e:
        print_error(str(e))

    # 4. Test Exploit Launch
    print_step("Testing Exploit Simulation (`/offensive/exploit/launch`)...")
    exploit_data = {
        "target_ip": "192.168.1.100",
        "exploit_name": "ZeroDay-EternalX"
    }
    try:
        res = requests.post(f"{BASE_URL}/offensive/exploit/launch", json=exploit_data, headers=headers)
        if res.status_code == 200:
            output = res.json()["output"]
            print_success("Exploit launched successfully.")
            print(f"    {output}")
        else:
            print_error(f"Status {res.status_code} - {res.text}")
    except Exception as e:
        print_error(str(e))

if __name__ == "__main__":
    test_offensive_flow()
