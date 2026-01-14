"""
Test different grant types with the correct Basic auth header
"""
import requests
import json
import base64

def test_grant_types():
    """Test different grant types with the correct Basic auth"""
    print("🔐 Testing Different Grant Types with Correct Basic Auth")
    print("=" * 60)
    
    url = "https://sso.test.brm-power.ro/connect/token"
    
    # The correct Basic auth header
    correct_basic_header = "Basic Y2xpZW50X2ludHJhZGF5X2FwaToxeEI5SWsxeHNFdTJuYndWYTFCUg=="
    
    # Decode to see what it contains
    encoded = correct_basic_header.replace("Basic ", "")
    decoded = base64.b64decode(encoded).decode()
    print(f"Basic auth decodes to: {decoded}")
    print()
    
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": correct_basic_header
    }
    
    # Test different grant type combinations
    test_cases = [
        {
            "name": "Client Credentials (no user credentials)",
            "data": {
                "grant_type": "client_credentials",
                "scope": "intraday_api"
            }
        },
        {
            "name": "Client Credentials (no scope)",
            "data": {
                "grant_type": "client_credentials"
            }
        },
        {
            "name": "Password Grant (original)",
            "data": {
                "grant_type": "password",
                "username": "Test_IntradayAPI_ADREM",
                "password": "nRtB8fDY485Nq4mu",
                "scope": "intraday_api"
            }
        },
        {
            "name": "Password Grant (no scope)",
            "data": {
                "grant_type": "password",
                "username": "Test_IntradayAPI_ADREM",
                "password": "nRtB8fDY485Nq4mu"
            }
        },
        {
            "name": "Client Credentials with different scope",
            "data": {
                "grant_type": "client_credentials",
                "scope": "api"
            }
        },
        {
            "name": "Client Credentials with multiple scopes",
            "data": {
                "grant_type": "client_credentials",
                "scope": "intraday_api dayahead_api"
            }
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"🧪 Test {i}: {test_case['name']}")
        print(f"Data: {test_case['data']}")
        
        try:
            response = requests.post(url, headers=headers, data=test_case['data'], timeout=30)
            
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text}")
            
            if response.status_code == 200:
                print("🎉 SUCCESS! This combination works!")
                token_data = response.json()
                access_token = token_data.get('access_token', '')
                print(f"Access Token: {access_token[:50]}...")
                print(f"Token Type: {token_data.get('token_type', 'Unknown')}")
                print(f"Expires In: {token_data.get('expires_in', 'Unknown')} seconds")
                print(f"Scope: {token_data.get('scope', 'Unknown')}")
                return token_data
            else:
                print("❌ Failed")
                
        except Exception as e:
            print(f"Error: {e}")
        
        print("-" * 50)
    
    print("❌ All grant type combinations failed")
    return None

def test_without_basic_auth():
    """Test without Basic auth header to see if that's the issue"""
    print("\n🔍 Testing WITHOUT Basic Auth Header")
    print("=" * 40)
    
    url = "https://sso.test.brm-power.ro/connect/token"
    
    # No Authorization header
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    # Try with the client credentials from the Basic auth
    data = {
        "grant_type": "client_credentials",
        "client_id": "client_intraday_api",
        "client_secret": "1xB9Ik1xsEu2nbwVa1BR",
        "scope": "intraday_api"
    }
    
    print(f"Headers: {headers}")
    print(f"Data: {data}")
    
    try:
        response = requests.post(url, headers=headers, data=data, timeout=30)
        
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            print("✅ SUCCESS without Basic auth!")
            return response.json()
        else:
            print("❌ Failed without Basic auth too")
            
    except Exception as e:
        print(f"Error: {e}")
    
    return None

def main():
    print("🚀 BRM GRANT TYPE TESTING")
    print("=" * 50)
    print("Testing different OAuth2 grant types with correct credentials")
    print()
    
    # Test with Basic auth header
    token_data = test_grant_types()
    
    if not token_data:
        # Test without Basic auth header
        token_data = test_without_basic_auth()
    
    if token_data:
        print("\n🎉 AUTHENTICATION SUCCESSFUL!")
        print("=" * 40)
        print("The working method can now be used in the trading bot!")
    else:
        print("\n❌ ALL METHODS FAILED")
        print("=" * 30)
        print("This suggests there might be additional requirements or")
        print("the credentials might need to be activated differently.")

if __name__ == "__main__":
    main()
