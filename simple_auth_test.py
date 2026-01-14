"""
Simple authentication test script
Easily modifiable to match exact Postman parameters
"""
import requests
import json

def test_auth():
    """Simple authentication test"""
    print("🔐 Simple BRM Authentication Test")
    print("=" * 40)
    
    # URL
    url = "https://sso.test.brm-power.ro/connect/token"
    
    # Headers - modify these to match Postman exactly
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json"
    }
    
    # Data - modify these to match Postman exactly
    data = {
        "grant_type": "password",
        "username": "Test_IntradayAPI_ADREM",
        "password": "nRtB8fDY485Nq4mu", 
        "scope": "intraday_api"
    }
    
    print(f"URL: {url}")
    print(f"Headers: {headers}")
    print(f"Data: {data}")
    print()
    
    try:
        print("Sending request...")
        response = requests.post(url, headers=headers, data=data, timeout=30)
        
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            print("✅ SUCCESS!")
            token_data = response.json()
            access_token = token_data.get('access_token', '')
            print(f"Access token: {access_token[:50]}...")
            return token_data
        else:
            print("❌ FAILED")
            return None
            
    except Exception as e:
        print(f"Error: {e}")
        return None

if __name__ == "__main__":
    test_auth()
