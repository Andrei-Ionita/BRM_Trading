"""
Test with the correct password and proper URL encoding
"""
import requests
import json
import base64
from urllib.parse import quote, urlencode

def test_with_correct_password():
    """Test with the correct password including special characters"""
    print("🔐 Testing with CORRECT Password and URL Encoding")
    print("=" * 60)
    
    url = "https://sso.test.brm-power.ro/connect/token"
    
    # The correct Basic auth header
    correct_basic_header = "Basic Y2xpZW50X2ludHJhZGF5X2FwaToxeEI5SWsxeHNFdTJuYndWYTFCUg=="
    
    # The CORRECT password with special characters
    correct_password = "nR(B8fDY{485Nq4mu"
    
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": correct_basic_header
    }
    
    # Test different approaches for handling special characters
    test_cases = [
        {
            "name": "Raw password (let requests handle encoding)",
            "data": {
                "grant_type": "password",
                "username": "Test_IntradayAPI_ADREM",
                "password": correct_password,
                "scope": "intraday_api"
            },
            "use_raw": True
        },
        {
            "name": "URL-encoded password",
            "data": {
                "grant_type": "password",
                "username": "Test_IntradayAPI_ADREM", 
                "password": quote(correct_password),
                "scope": "intraday_api"
            },
            "use_raw": True
        },
        {
            "name": "Manual URL encoding of entire payload",
            "data": urlencode({
                "grant_type": "password",
                "username": "Test_IntradayAPI_ADREM",
                "password": correct_password,
                "scope": "intraday_api"
            }),
            "use_raw": False
        },
        {
            "name": "Client credentials with correct password",
            "data": {
                "grant_type": "client_credentials",
                "scope": "intraday_api"
            },
            "use_raw": True
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"🧪 Test {i}: {test_case['name']}")
        
        if test_case['use_raw']:
            print(f"Data: {test_case['data']}")
            data_to_send = test_case['data']
        else:
            print(f"Data (URL-encoded): {test_case['data']}")
            data_to_send = test_case['data']
        
        try:
            response = requests.post(url, headers=headers, data=data_to_send, timeout=30)
            
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text}")
            
            if response.status_code == 200:
                print("🎉 SUCCESS! Found the working combination!")
                token_data = response.json()
                access_token = token_data.get('access_token', '')
                print(f"Access Token: {access_token[:50]}...")
                print(f"Token Type: {token_data.get('token_type', 'Unknown')}")
                print(f"Expires In: {token_data.get('expires_in', 'Unknown')} seconds")
                return token_data
            else:
                print("❌ Failed")
                
        except Exception as e:
            print(f"Error: {e}")
        
        print("-" * 50)
    
    return None

def test_without_special_chars():
    """Test if the issue is with special characters by using a simple password"""
    print("\n🔍 Testing Password Character Encoding Issues")
    print("=" * 50)
    
    url = "https://sso.test.brm-power.ro/connect/token"
    correct_basic_header = "Basic Y2xpZW50X2ludHJhZGF5X2FwaToxeEI5SWsxeHNFdTJuYndWYTFCUg=="
    
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": correct_basic_header
    }
    
    # Show what the special characters look like when URL encoded
    correct_password = "nR(B8fDY{485Nq4mu"
    encoded_password = quote(correct_password)
    
    print(f"Original password: {correct_password}")
    print(f"URL-encoded password: {encoded_password}")
    print(f"Character mapping:")
    print(f"  ( -> {quote('(')}")
    print(f"  {{ -> {quote('{')}")
    print()
    
    # Test with explicit character encoding
    data = {
        "grant_type": "password",
        "username": "Test_IntradayAPI_ADREM",
        "password": correct_password,
        "scope": "intraday_api"
    }
    
    print("Testing with correct password and explicit encoding...")
    
    try:
        # Use requests' built-in form encoding
        response = requests.post(url, headers=headers, data=data, timeout=30)
        
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            print("✅ SUCCESS!")
            return response.json()
        else:
            print("❌ Still failed")
            
    except Exception as e:
        print(f"Error: {e}")
    
    return None

def main():
    print("🚀 BRM AUTHENTICATION WITH CORRECT PASSWORD")
    print("=" * 60)
    print("Testing with the correct password: nR(B8fDY{485Nq4mu")
    print("(Notice the special characters: ( and {)")
    print()
    
    # Test with correct password
    token_data = test_with_correct_password()
    
    if not token_data:
        # Test character encoding issues
        token_data = test_without_special_chars()
    
    if token_data:
        print("\n🎉 AUTHENTICATION SUCCESSFUL!")
        print("=" * 40)
        print("We found the working combination!")
        print("The trading bot can now be updated with the correct credentials!")
    else:
        print("\n❌ STILL FAILING")
        print("=" * 20)
        print("Even with the correct password, authentication is failing.")
        print("This suggests there might be:")
        print("1. Additional authentication steps required")
        print("2. Account activation needed")
        print("3. IP restrictions")
        print("4. Time-based restrictions")

if __name__ == "__main__":
    main()
