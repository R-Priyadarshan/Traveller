"""Test Gemini API directly."""
import requests
import json

api_key = "AQ.Ab8RN6INOKrr1IejyJPN_YiQWxMBCKo62-M9n00TPOeS18w53Q"
url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={api_key}"

data = {
    "contents": [{
        "parts": [{"text": "What is 2+2?"}]
    }]
}

try:
    response = requests.post(url, json=data)
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
except Exception as e:
    print(f"Error: {e}")
