import csv
import glob
import os
import subprocess
import sys
import time

def run_locust():
    output_prefix = os.path.join(os.path.dirname(__file__), "capacity_100_results")
    locustfile = os.path.join(os.path.dirname(__file__), "locustfile_capacity_100.py")
    
    cmd = [
        sys.executable,
        "-m", "locust",
        "-f", locustfile,
        "--headless",
        "--users", "100",
        "--spawn-rate", "10",
        "--run-time", "45s",
        "--host", "http://127.0.0.1:8000",
        "--csv", output_prefix,
        "--csv-full-history"
    ]
    
    print(f"Starting Locust Capacity Test: 100 concurrent users for 45s...")
    t0 = time.time()
    res = subprocess.run(cmd, capture_output=True, text=True)
    duration = time.time() - t0
    print(f"Locust finished in {duration:.1f}s, exit code: {res.returncode}")
    if res.stdout:
        # print last 15 lines of stdout
        lines = res.stdout.strip().split("\n")
        print("\n".join(lines[-15:]))

    stats_file = f"{output_prefix}_stats.csv"
    failures_file = f"{output_prefix}_failures.csv"

    if not os.path.exists(stats_file):
        print(f"ERROR: Stats file not found at {stats_file}")
        sys.exit(1)

    total_requests = 0
    total_failures = 0

    with open(stats_file, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("Name") == "Aggregated":
                total_requests = int(row.get("Request Count", 0))
                total_failures = int(row.get("Failure Count", 0))

    failures_detail = []
    if os.path.exists(failures_file):
        with open(failures_file, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                failures_detail.append(row)

    print("\n================ CAPACITY TEST RESULTS ================")
    print(f"Total Requests: {total_requests}")
    print(f"Total Failures: {total_failures}")
    failure_pct = (total_failures / total_requests * 100) if total_requests > 0 else 0
    print(f"Failure Rate:   {failure_pct:.2f}%")
    
    if failures_detail:
        print("Failures breakdown:")
        for fd in failures_detail:
            print(f"  {fd}")

    if total_failures > 0 or total_requests == 0:
        print("TEST FAILED: Non-zero failures or zero requests.")
        sys.exit(1)

    print("TEST PASSED: 100 concurrent users handled with 0.00% failures and 0% 429s!")
    sys.exit(0)

if __name__ == "__main__":
    run_locust()
