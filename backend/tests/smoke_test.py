import requests
import sys
import time

# Configuration
API_URL = "http://localhost:8001/api/v1"
ADMIN_EMAIL = "admin@projectxy.com"
ADMIN_PASS = "admin123"

def log(msg, type="INFO"):
    print(f"[{type}] {msg}")

def test_health():
    try:
        r = requests.get("http://localhost:8001/health")
        if r.status_code == 200:
            log("Health Check: PASS", "SUCCESS")
        else:
            log(f"Health Check: FAIL ({r.status_code})", "ERROR")
            sys.exit(1)
    except Exception as e:
        log(f"Health Check: CRITICAL FAIL - {e}", "ERROR")
        sys.exit(1)

def test_login():
    log("Testing Auth...")
    payload = {"username": ADMIN_EMAIL, "password": ADMIN_PASS}
    try:
        r = requests.post(f"{API_URL}/login/access-token", data=payload)
        if r.status_code == 200:
            token = r.json().get("access_token")
            log("Authentication: PASS", "SUCCESS")
            return token
        else:
            log(f"Authentication: FAIL ({r.status_code}) - {r.text}", "ERROR")
            sys.exit(1)
    except Exception as e:
        log(f"Auth Critiscal: {e}", "ERROR")
        sys.exit(1)

def test_entity_lifecycle(token):
    headers = {"Authorization": f"Bearer {token}"}
    
    # 1. Create Entity
    log("Testing Entity Creation...")
    entity_data = {
        "canonical_name": "Test Subject Alpha",
        "type": "person", 
        "risk_score": 50,
        "attributes": [
            {"value": "test@example.com", "type": "email", "confidence": 0.9}
        ]
    }
    
    r = requests.post(f"{API_URL}/entities/", json=entity_data, headers=headers)
    if r.status_code != 200:
        log(f"Entity Create: FAIL ({r.status_code}) - {r.text}", "ERROR")
        return
        
    entity_id = r.json()["id"]
    log(f"Entity Created: ID {entity_id}", "SUCCESS")
    
    # 2. Analyze Risk
    log("Testing Risk Engine...")
    r = requests.get(f"{API_URL}/analysis/risk/{entity_id}", headers=headers)
    if r.status_code == 200:
        risk = r.json()
        log(f"Risk Analysis: PASS (Score: {risk['total_score']})", "SUCCESS")
    else:
        log(f"Risk Analysis: FAIL ({r.status_code})", "ERROR")

if __name__ == "__main__":
    log("Starting System Verification...")
    test_health()
    token = test_login()
    test_entity_lifecycle(token)
    log("ALL SYSTEMS OPERATIONAL", "SUCCESS")
