"""
Detailed debug script to understand BRM authentication requirements
"""
import requests
import json
import base64
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def decode_basic_auth(basic_header):
    """Decode a Basic auth header to see what credentials it contains"""
    try:
        # Remove "Basic " prefix
        encoded = basic_header.replace("Basic ", "")
        # Decode base64
        decoded = base64.b64decode(encoded).decode()
        return decoded
    except Exception as e:
        return f"Error decoding: {e}"

def test_all_auth_combinations():
    """Test all possible authentication combinations"""
    url = "https://sso.test.brm-power.ro/connect/token"
    
    # The credentials from the images
    username = "Test_IntradayAPI_ADREM"
    password = "nRtB8fDY485Nq4mu"
    scope = "intraday_api"
    
    # The Basic auth header from the image (might be placeholder)
    basic_header_from_image = "Basic Y2xpZW50X2lkOmNsaWVudF9zZWNyZXQ="
    
    print("🔍 DETAILED BRM AUTHENTICATION DEBUG")
    print("=" * 60)
    print()
    
    # First, let's see what the Basic header from the image contains
    print("📋 Analyzing Basic Auth Header from Image:")
    decoded = decode_basic_auth(basic_header_from_image)
    print(f"   Header: {basic_header_from_image}")
    print(f"   Decoded: {decoded}")
    print()
    
    # Test combinations
    test_cases = [
        {
            "name": "Method 1: Password Grant (standard)",
            "headers": {
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json"
            },
            "data": {
                "grant_type": "password",
                "username": username,
                "password": password,
                "scope": scope
            }
        },
        {
            "name": "Method 2: Client Credentials with username/password as client_id/secret",
            "headers": {
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json"
            },
            "data": {
                "grant_type": "client_credentials",
                "client_id": username,
                "client_secret": password,
                "scope": scope
            }
        },
        {
            "name": "Method 3: Basic Auth with username:password",
            "headers": {
                "Content-Type": "application/x-www-form-urlencoded",
                "Authorization": f"Basic {base64.b64encode(f'{username}:{password}'.encode()).decode()}",
                "Accept": "application/json"
            },
            "data": {
                "grant_type": "client_credentials",
                "scope": scope
            }
        },
        {
            "name": "Method 4: Basic Auth from image (if different)",
            "headers": {
                "Content-Type": "application/x-www-form-urlencoded",
                "Authorization": basic_header_from_image,
                "Accept": "application/json"
            },
            "data": {
                "grant_type": "client_credentials",
                "scope": scope
            }
        },
        {
            "name": "Method 5: Password Grant with Basic Auth",
            "headers": {
                "Content-Type": "application/x-www-form-urlencoded",
                "Authorization": f"Basic {base64.b64encode(f'{username}:{password}'.encode()).decode()}",
                "Accept": "application/json"
            },
            "data": {
                "grant_type": "password",
                "username": username,
                "password": password,
                "scope": scope
            }
        },
        {
            "name": "Method 6: Try without scope",
            "headers": {
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json"
            },
            "data": {
                "grant_type": "password",
                "username": username,
                "password": password
            }
        },
        {
            "name": "Method 7: Try with different scope",
            "headers": {
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json"
            },
            "data": {
                "grant_type": "password",
                "username": username,
                "password": password,
                "scope": "api"
            }
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"🧪 {test_case['name']}")
        print("-" * 50)
        print(f"Headers: {test_case['headers']}")
        print(f"Data: {test_case['data']}")
        
        try:
            response = requests.post(
                url, 
                headers=test_case['headers'], 
                data=test_case['data'], 
                timeout=30
            )
            
            print(f"Status: {response.status_code}")
            print(f"Response Headers: {dict(response.headers)}")
            
            try:
                response_json = response.json()
                print(f"Response: {json.dumps(response_json, indent=2)}")
                
                if response.status_code == 200:
                    print("🎉 SUCCESS! This method works!")
                    print(f"Access Token: {response_json.get('access_token', 'N/A')[:50]}...")
                    return test_case, response_json
                    
            except json.JSONDecodeError:
                print(f"Response Text: {response.text}")
                
        except Exception as e:
            print(f"Request Error: {e}")
        
        print()
    
    print("❌ All authentication methods failed.")
    return None, None

def test_token_endpoint_discovery():
    """Try to discover the correct token endpoint or parameters"""
    print("🔍 TESTING TOKEN ENDPOINT DISCOVERY")
    print("=" * 50)
    
    # Try to get OpenID Connect discovery document
    discovery_urls = [
        "https://sso.test.brm-power.ro/.well-known/openid_configuration",
        "https://sso.test.brm-power.ro/.well-known/oauth-authorization-server",
        "https://sso.test.brm-power.ro/connect/.well-known/openid_configuration"
    ]
    
    for url in discovery_urls:
        print(f"Trying discovery URL: {url}")
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                print("✅ Discovery document found!")
                discovery = response.json()
                print(f"Token Endpoint: {discovery.get('token_endpoint', 'Not found')}")
                print(f"Supported Grant Types: {discovery.get('grant_types_supported', 'Not found')}")
                print(f"Supported Scopes: {discovery.get('scopes_supported', 'Not found')}")
                return discovery
            else:
                print(f"   Status: {response.status_code}")
        except Exception as e:
            print(f"   Error: {e}")
    
    print("❌ No discovery document found")
    return None

def main():
    print("🚀 BRM AUTHENTICATION DETAILED DEBUG SESSION")
    print("=" * 60)
    print()
    
    # First try to discover the correct endpoint configuration
    discovery = test_token_endpoint_discovery()
    print()
    
    # Then test all authentication methods
    working_method, token_response = test_all_auth_combinations()
    
    if working_method:
        print("🎉 AUTHENTICATION SUCCESS!")
        print("=" * 40)
        print(f"Working method: {working_method['name']}")
        print("You can now use this method in the trading bot!")
    else:
        print("❌ AUTHENTICATION FAILED")
        print("=" * 40)
        print("Possible issues:")
        print("1. Credentials might be for a different environment")
        print("2. Additional parameters might be required")
        print("3. The endpoint might be different")
        print("4. Account might need activation")
        print()
        print("💡 Next steps:")
        print("1. Contact BRM support to verify credentials")
        print("2. Ask for the exact authentication method")
        print("3. Verify the token endpoint URL")
        print("4. Check if account needs activation")

if __name__ == "__main__":
    main()
