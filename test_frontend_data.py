"""Test what the frontend would send."""
import requests
import json

url = "http://localhost:8000/api/plan"
payload = {
    "query": "india for 5 people",
    "preferences": ["adventure"],
    "budget": "medium"
}

print("Sending frontend-style payload...")
print(json.dumps(payload, indent=2))

response = requests.post(url, json=payload)
print(f"\nStatus: {response.status_code}")
print(f"Response: {json.dumps(response.json(), indent=2)[:500]}")
