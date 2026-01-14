"""
Debug script to show the exact HTTP request being sent
Compares with what Postman sends to identify differences
"""
import requests
import json
import logging
from urllib.parse import urlencode

# Enable detailed HTTP logging
import http.client as http_client
http_client.HTTPConnection.debuglevel = 1

logging.basicConfig()
logging.getLogger().setLevel(logging.DEBUG)
requests_log = logging.getLogger("requests.packages.urllib3")
requests_log.setLevel(logging.DEBUG)
requests_log.propagate = True

def test_exact_postman_request():
    """Send the exact same request as Postman"""
    print("🔍 DEBUGGING EXACT HTTP REQUEST")
    print("=" * 50)
    
    url = "https://sso.test.brm-power.ro/connect/token"
    
    # Exact headers as Postman would send
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "User-Agent": "BRM-Trading-Bot/1.0",  # Add user agent
        "Cache-Control": "no-cache"
    }
    
    # Exact data as in Postman
    data = {
        "grant_type": "password",
        "username": "Test_IntradayAPI_ADREM", 
        "password": "nRtB8fDY485Nq4mu",
        "scope": "intraday_api"
    }
    
    print("📋 REQUEST DETAILS:")
    print(f"URL: {url}")
    print(f"Method: POST")
    print(f"Headers: {json.dumps(headers, indent=2)}")
    print(f"Data: {json.dumps(data, indent=2)}")
    print(f"Data (URL-encoded): {urlencode(data)}")
    print()
    
    print("🌐 SENDING REQUEST...")
    print("-" * 30)
    
    try:
        response = requests.post(
            url,
            headers=headers,
            data=data,  # Let requests handle URL encoding
            timeout=30,
            verify=True  # Ensure SSL verification
        )
        
        print(f"📊 RESPONSE:")
        print(f"Status Code: {response.status_code}")
        print(f"Status Text: {response.reason}")
        print(f"Response Headers:")
        for key, value in response.headers.items():
            print(f"  {key}: {value}")
        
        print(f"\nResponse Body:")
        try:
            response_json = response.json()
            print(json.dumps(response_json, indent=2))
            
            if response.status_code == 200:
                print("\n🎉 SUCCESS! Token received!")
                access_token = response_json.get('access_token', '')
                print(f"Access Token (first 50 chars): {access_token[:50]}...")
                return response_json
            else:
                print(f"\n❌ FAILED with status {response.status_code}")
                
        except json.JSONDecodeError:
            print(f"Raw text: {response.text}")
            
    except Exception as e:
        print(f"❌ REQUEST FAILED: {e}")
    
    return None

def test_alternative_formats():
    """Test alternative request formats"""
    print("\n🧪 TESTING ALTERNATIVE FORMATS")
    print("=" * 40)
    
    url = "https://sso.test.brm-power.ro/connect/token"
    
    # Test 1: Manual URL encoding
    print("\n1️⃣ Testing with manual URL encoding...")
    headers1 = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json"
    }
    
    # Manually URL-encode the data
    data_string = "grant_type=password&username=Test_IntradayAPI_ADREM&password=nRtB8fDY485Nq4mu&scope=intraday_api"
    
    try:
        response = requests.post(url, headers=headers1, data=data_string, timeout=30)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            print("✅ SUCCESS with manual encoding!")
            return response.json()
        else:
            print(f"Response: {response.text}")
    except Exception as e:
        print(f"Error: {e}")
    
    # Test 2: Different Content-Type
    print("\n2️⃣ Testing with different Content-Type...")
    headers2 = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    json_data = {
        "grant_type": "password",
        "username": "Test_IntradayAPI_ADREM",
        "password": "nRtB8fDY485Nq4mu",
        "scope": "intraday_api"
    }
    
    try:
        response = requests.post(url, headers=headers2, json=json_data, timeout=30)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            print("✅ SUCCESS with JSON!")
            return response.json()
        else:
            print(f"Response: {response.text}")
    except Exception as e:
        print(f"Error: {e}")
    
    # Test 3: Minimal headers
    print("\n3️⃣ Testing with minimal headers...")
    headers3 = {
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    data3 = {
        "grant_type": "password",
        "username": "Test_IntradayAPI_ADREM",
        "password": "nRtB8fDY485Nq4mu",
        "scope": "intraday_api"
    }
    
    try:
        response = requests.post(url, headers=headers3, data=data3, timeout=30)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            print("✅ SUCCESS with minimal headers!")
            return response.json()
        else:
            print(f"Response: {response.text}")
    except Exception as e:
        print(f"Error: {e}")
    
    return None

def main():
    print("🚀 BRM AUTHENTICATION HTTP DEBUG SESSION")
    print("=" * 60)
    print("This will show the exact HTTP request being sent")
    print("and help identify differences from Postman")
    print("=" * 60)
    
    # Test the exact request
    token_response = test_exact_postman_request()
    
    if not token_response:
        # Try alternative formats
        token_response = test_alternative_formats()
    
    if token_response:
        print("\n🎉 AUTHENTICATION SUCCESSFUL!")
        print("=" * 40)
        print("The working method can now be used in the trading bot!")
    else:
        print("\n❌ ALL METHODS FAILED")
        print("=" * 30)
        print("Possible reasons:")
        print("1. There might be additional headers Postman sends automatically")
        print("2. The credentials might have expired or been deactivated")
        print("3. There might be IP restrictions or rate limiting")
        print("4. The server might require specific SSL/TLS settings")
        print("\n💡 Try:")
        print("1. Check if your Postman request still works")
        print("2. Compare the exact headers Postman sends")
        print("3. Check for any authentication timeouts")

if __name__ == "__main__":
    main()
