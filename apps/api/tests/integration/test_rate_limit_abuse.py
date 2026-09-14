import sys
import requests

API_BASE = "http://127.0.0.1:8000/api/v1"

print("--- Running Rate Limit Abuse / Security Test ---")

got_429 = False
retry_after_val = None
consecutive_ok = 0

for i in range(1, 25):
    resp = requests.post(f"{API_BASE}/auth/login", json={"email": f"fake_{i}@chemistry.com", "password": "wrong"})
    if resp.status_code == 429:
        got_429 = True
        retry_after_val = resp.headers.get("Retry-After")
        print(f"Request {i} correctly rejected with HTTP 429! Retry-After: {retry_after_val}")
        break
    else:
        consecutive_ok += 1

if not got_429:
    print("FAILED: Did not trigger HTTP 429 after 25 requests.")
    sys.exit(1)

if not retry_after_val or int(retry_after_val) <= 0:
    print(f"FAILED: Invalid or missing Retry-After header: {retry_after_val}")
    sys.exit(1)

print(f"SUCCESS: Rate limiter blocked abuse at request {consecutive_ok + 1} with Retry-After={retry_after_val}s.")
