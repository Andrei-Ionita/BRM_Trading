"""
Debug script to understand the exact authentication requirements
"""
import requests
import json
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def test_password_grant_debug():
    """Test password grant with detailed error information"""
    url = "https://sso.test.brm-power.ro/connect/token"
    
    # Method 1: As shown in the image
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json"
    }
    
    data = {
        "grant_type": "password",
        "username": "Test_IntradayAPI_ADREM",
        "password": "nRtB8fDY485Nq4mu",
        "scope": "intraday_api"
    }
    
    print("🔍 Testing Method 1: Password Grant (as shown in image)")
    print(f"URL: {url}")
    print(f"Headers: {headers}")
    print(f"Data: {data}")
    print("-" * 50)
    
    try:
        response = requests.post(url, data=data, headers=headers, timeout=30)
        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        
        try:
            response_json = response.json()
            print(f"Response JSON: {json.dumps(response_json, indent=2)}")
        except:
            print(f"Response Text: {response.text}")
        
        if response.status_code == 200:
            print("✅ Authentication successful!")
            return True
        else:
            print(f"❌ Authentication failed with status {response.status_code}")
            
    except Exception as e:
        print(f"❌ Request failed: {e}")
    
    return False


def test_basic_auth_debug():
    """Test basic auth with detailed error information"""
    url = "https://sso.test.brm-power.ro/connect/token"
    
    # From the first image - we need to extract the actual Basic auth value
    # The image shows: Basic Y2xpZW50X2lkOmNsaWVudF9zZWNyZXQ=
    # But this looks like a placeholder. Let's try creating one from the username/password
    
    import base64
    
    # Try creating Basic auth from the username/password we have
    username = "Test_IntradayAPI_ADREM"
    password = "nRtB8fDY485Nq4mu"
    credentials = f"{username}:{password}"
    encoded_credentials = base64.b64encode(credentials.encode()).decode()
    basic_auth_header = f"Basic {encoded_credentials}"
    
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": basic_auth_header,
        "Accept": "application/json"
    }
    
    # Try different grant types
    for grant_type in ["client_credentials", "password"]:
        print(f"🔍 Testing Method 2: Basic Auth with grant_type={grant_type}")
        print(f"URL: {url}")
        print(f"Headers: {headers}")
        
        if grant_type == "password":
            data = {
                "grant_type": grant_type,
                "username": username,
                "password": password,
                "scope": "intraday_api"
            }
        else:
            data = {
                "grant_type": grant_type,
                "scope": "intraday_api"
            }
        
        print(f"Data: {data}")
        print("-" * 50)
        
        try:
            response = requests.post(url, data=data, headers=headers, timeout=30)
            print(f"Status Code: {response.status_code}")
            print(f"Response Headers: {dict(response.headers)}")
            
            try:
                response_json = response.json()
                print(f"Response JSON: {json.dumps(response_json, indent=2)}")
            except:
                print(f"Response Text: {response.text}")
            
            if response.status_code == 200:
                print("✅ Authentication successful!")
                return True
            else:
                print(f"❌ Authentication failed with status {response.status_code}")
                
        except Exception as e:
            print(f"❌ Request failed: {e}")
        
        print()
    
    return False


def test_alternative_methods():
    """Test alternative authentication methods"""
    url = "https://sso.test.brm-power.ro/connect/token"
    
    # Method 3: Try with client_id and client_secret as form data
    print("🔍 Testing Method 3: Client credentials in form data")
    
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json"
    }
    
    # Maybe the username is actually the client_id?
    data = {
        "grant_type": "client_credentials",
        "client_id": "Test_IntradayAPI_ADREM",
        "client_secret": "nRtB8fDY485Nq4mu",
        "scope": "intraday_api"
    }
    
    print(f"URL: {url}")
    print(f"Headers: {headers}")
    print(f"Data: {data}")
    print("-" * 50)
    
    try:
        response = requests.post(url, data=data, headers=headers, timeout=30)
        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        
        try:
            response_json = response.json()
            print(f"Response JSON: {json.dumps(response_json, indent=2)}")
        except:
            print(f"Response Text: {response.text}")
        
        if response.status_code == 200:
            print("✅ Authentication successful!")
            return True
        else:
            print(f"❌ Authentication failed with status {response.status_code}")
            
    except Exception as e:
        print(f"❌ Request failed: {e}")
    
    return False


def main():
    print("🔍 BRM Authentication Debug Session")
    print("=" * 60)
    print()
    
    # Test all methods
    methods = [
        ("Password Grant", test_password_grant_debug),
        ("Basic Auth", test_basic_auth_debug),
        ("Alternative Methods", test_alternative_methods)
    ]
    
    for method_name, test_func in methods:
        print(f"Testing {method_name}...")
        print("=" * 40)
        success = test_func()
        print()
        
        if success:
            print(f"🎉 {method_name} worked! We can proceed with this method.")
            break
    else:
        print("❌ All authentication methods failed.")
        print("💡 Suggestions:")
        print("   1. Check if the credentials are correct")
        print("   2. Verify the token endpoint URL")
        print("   3. Check if there are additional required parameters")
        print("   4. Contact BRM support for the correct authentication method")


if __name__ == "__main__":
    main()
