import time
import urllib.request
import json
import statistics
import os

BASE_URL = "http://localhost:8000/api/v1"

# Endpoints to test
ENDPOINTS = [
    ("/health", "Health Check"),
    ("/stats/", "System Stats"),
    ("/entities/", "List Entities"),
    ("/devices/", "List Devices"),
]

TOKEN = None

def login():
    global TOKEN
    try:
        url = f"{BASE_URL}/login/access-token"
        password = os.getenv("TEST_USER_PASSWORD", "admin123")
        data = f"username=admin@projectxy.com&password={password}".encode()
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        
        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                body = json.loads(response.read().decode())
                TOKEN = body.get("access_token")
                print(f"Logged in. Token: {TOKEN[:10]}...")
                return True
    except Exception as e:
        print(f"Login failed: {e}")
        return False

def make_request(url):
    try:
        req = urllib.request.Request(url)
        if TOKEN:
            req.add_header("Authorization", f"Bearer {TOKEN}")
            
        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                return json.loads(response.read().decode())
            return None
    except Exception as e:
        # print(f"Request failed: {e}")
        return None

def get_valid_entity_id():
    try:
        data = make_request(f"{BASE_URL}/entities/")
        if data and len(data) > 0:
            return data[0]['id']
    except:
        pass
    return None

def benchmark_endpoint(path, name, iterations=10):
    times = []
    print(f"Benchmarking {name} ({path})...")
    
    for i in range(iterations):
        start = time.time()
        try:
            url = f"{BASE_URL}{path}"
            req = urllib.request.Request(url)
            if TOKEN:
                req.add_header("Authorization", f"Bearer {TOKEN}")
                
            with urllib.request.urlopen(req) as response:
                if response.status != 200:
                    print(f"  [Error] {response.status}")
        except Exception as e:
            print(f"  [Exception] {e}")
            
        end = time.time()
        times.append((end - start) * 1000) # ms
        
    if not times:
        return 0.0

    avg_time = statistics.mean(times)
    
    print(f"  Avg: {avg_time:.2f}ms | Max: {max(times):.2f}ms")
    return avg_time

def run_benchmarks():
    print("Starting API Benchmarks...")
    print("-" * 50)
    
    if not login():
        print("Skipping authenticated benchmarks due to login failure.")
        # Proceed anyway for public endpoints
    
    results = {}
    
    # Static endpoints
    for path, name in ENDPOINTS:
        results[name] = benchmark_endpoint(path, name)
        
    # Dynamic endpoints
    entity_id = get_valid_entity_id()
    if entity_id:
        results["Entity Details"] = benchmark_endpoint(f"/entities/{entity_id}", "Entity Details")
        results["Graph Neighbor"] = benchmark_endpoint(f"/analysis/graph/neighborhood/{entity_id}", "Graph Neighborhood")
        results["AI Summary"] = benchmark_endpoint(f"/analysis/ai/summary/{entity_id}", "AI Summary")
    else:
        print("Skipping entity-specific benchmarks (no entities found)")
        
    print("-" * 50)
    print("Summary:")
    for name, duration in results.items():
        status = "FAST" if duration < 100 else ("WARN" if duration < 500 else "SLOW")
        print(f"{name:<20} : {duration:.2f}ms [{status}]")

if __name__ == "__main__":
    # Wait for service to be potentially ready if just started
    time.sleep(1) 
    run_benchmarks()
