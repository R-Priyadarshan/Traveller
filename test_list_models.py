"""List available models."""
import requests
import json

api_key = "AQ.Ab8RN6INOKrr1IejyJPN_YiQWxMBCKo62-M9n00TPOeS18w53Q"
url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"

try:
    response = requests.get(url)
    print(f"Status: {response.status_code}")
    data = response.json()
    
    if 'models' in data:
        print("\nAvailable models:")
        for model in data['models']:
            print(f"  - {model.get('name', 'Unknown')}")
    else:
        print(json.dumps(data, indent=2))
except Exception as e:
    print(f"Error: {e}")
