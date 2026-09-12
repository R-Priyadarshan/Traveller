"""Quick test of the API."""
import requests
import json

url = "http://localhost:8000/plan"
payload = {
    "query": "3 days in Paris with friends, we like museums and food",
    "preferences": ["art", "food"],
    "budget": "medium"
}

print("Sending request to /plan endpoint...")
print(f"Payload: {json.dumps(payload, indent=2)}\n")

try:
    response = requests.post(url, json=payload, timeout=60)
    print(f"Status: {response.status_code}")
    print(f"Response:\n{json.dumps(response.json(), indent=2)}")
except Exception as e:
    print(f"Error: {e}")
