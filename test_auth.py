import requests
import time
import os

URL = "http://127.0.0.1:5000/discover"
PWD = "HOLYFUCKJAMESLORDGOTHACK132"

print(f"[*] Testing Auth with password: {PWD}")
start = time.time()
try:
    res = requests.post(URL, json={"password": PWD}, timeout=5)
    latency = (time.time() - start) * 1000
    print(f"[*] Status: {res.status_code}")
    print(f"[*] Response: {res.text}")
    print(f"[*] Latency: {latency:.2f}ms")
except Exception as e:
    print(f"[-] Error: {e}")
