import requests
import uuid
import json

BASE_URL = "http://localhost:8000/api/v1"

def print_step(msg):
    print(f"\n[+] {msg}")

def test_redteam_flow():
    print("=== Starting Red Team Operations Smoke Test ===")

    # 1. Test Payload Generation
    print_step("Testing Payload Generator (Windows)...")
    payload = {
        "target_os": "windows",
        "lhost": "192.168.1.50",
        "lport": 1337
    }
    # Note: Requires running backend. Since we are in an agent environment without the server running,
    # allows mocking the request or assuming success if we could run it.
    # This script is for the user to run.
    try:
        res = requests.post(f"{BASE_URL}/redteam/payload/generate", json=payload)
        if res.status_code == 200:
            print(f"SUCCESS: Generated payload: {res.json()['command']}")
        else:
            print(f"FAIL: Status {res.status_code} - {res.text}")
    except requests.exceptions.ConnectionError:
        print("SKIP: Backend not running at localhost:8000. Please start server to verify.")

    # 2. Test Device Creation
    print_step("Testing Device Creation...")
    device_data = {
        "name": f"Test_Device_{uuid.uuid4().hex[:8]}",
        "type": "android",
        "latitude": 0.0,
        "longitude": 0.0
    }
    device_id = None
    try:
        res = requests.post(f"{BASE_URL}/devices/", json=device_data)
        if res.status_code == 200:
            device = res.json()
            device_id = device['id']
            print(f"SUCCESS: Created device {device_id}")
        else:
            print(f"FAIL: Status {res.status_code} - {res.text}")
    except requests.exceptions.ConnectionError:
        print("SKIP: Backend not running.")

    # 3. Test GPS Update
    if device_id:
        print_step(f"Testing GPS Update for {device_id}...")
        loc_data = {
            "latitude": 40.7128,
            "longitude": -74.0060,
            "accuracy_radius": 5.0
        }
        try:
            res = requests.post(f"{BASE_URL}/devices/{device_id}/gps-update", json=loc_data)
            if res.status_code == 200:
                print("SUCCESS: GPS Updated (and Graph synced if Neo4j active)")
            else:
                print(f"FAIL: Status {res.status_code} - {res.text}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    test_redteam_flow()
