import requests
import base64
import os
import urllib3
import json

urllib3.disable_warnings()

def test_api_login():
    paths = [
        os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Riot Games', 'Riot Client', 'Config', 'lockfile'),
        r"C:\Riot Games\Riot Client\lockfile"
    ]
    
    lockfile_data = None
    for p in paths:
        if os.path.exists(p):
            with open(p, 'r') as f:
                lockfile_data = f.read().split(':')
                print(f"Found lockfile at {p}")
                break
                
    if not lockfile_data:
        print("Could not find lockfile.")
        return
        
    port = lockfile_data[2]
    password = lockfile_data[3]
    
    auth_string = f"riot:{password}"
    b64_auth = base64.b64encode(auth_string.encode()).decode()
    
    headers = {
        "Authorization": f"Basic {b64_auth}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    # We will try to get the auth status first
    url_base = f"https://127.0.0.1:{port}"
    try:
        r = requests.get(f"{url_base}/rso-auth/v1/session", headers=headers, verify=False)
        print("GET /rso-auth/v1/session:", r.status_code, r.text)
        
        # Test auth endpoint but with dummy credentials to see what it returns
        payload = {
            "username": "testuser123",
            "password": "testpassword123",
            "persistLogin": False,
            "language": "en_US"
        }
        r2 = requests.put(f"{url_base}/rso-authenticator/v1/authentication", headers=headers, json=payload, verify=False)
        print("PUT /rso-authenticator/v1/authentication:", r2.status_code, json.dumps(r2.json(), indent=2))
        
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    test_api_login()
