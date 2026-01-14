"""
Script to replicate Postman's exact request
Includes all headers that Postman typically sends
"""
import requests
import json

def test_with_postman_headers():
    """Test with headers that Postman typically sends"""
    print("🔐 Replicating Postman Request with All Headers")
    print("=" * 50)
    
    url = "https://sso.test.brm-power.ro/connect/token"
    
    # Headers that Postman typically sends
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
        "User-Agent": "PostmanRuntime/7.32.3",
        "Postman-Token": "12345678-1234-1234-1234-123456789012",
        "Cache-Control": "no-cache"
    }
    
    # Data exactly as in Postman
    data = {
        "grant_type": "password",
        "username": "Test_IntradayAPI_ADREM",
        "password": "nRtB8fDY485Nq4mu",
        "scope": "intraday_api"
    }
    
    print(f"URL: {url}")
    print(f"Headers: {json.dumps(headers, indent=2)}")
    print(f"Data: {json.dumps(data, indent=2)}")
    print()
    
    try:
        print("Sending request with Postman-like headers...")
        response = requests.post(url, headers=headers, data=data, timeout=30)
        
        print(f"Status: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        print(f"Response Body: {response.text}")
        
        if response.status_code == 200:
            print("✅ SUCCESS! Found the working combination!")
            return response.json()
        else:
            print("❌ Still failed with Postman headers")
            
    except Exception as e:
        print(f"Error: {e}")
    
    return None

def test_minimal_working_headers():
    """Test with minimal headers to find what's actually required"""
    print("\n🧪 Testing Minimal Headers")
    print("=" * 30)
    
    url = "https://sso.test.brm-power.ro/connect/token"
    
    # Try different header combinations
    header_combinations = [
        {
            "name": "Only Content-Type",
            "headers": {
                "Content-Type": "application/x-www-form-urlencoded"
            }
        },
        {
            "name": "Content-Type + Accept",
            "headers": {
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "*/*"
            }
        },
        {
            "name": "Content-Type + User-Agent",
            "headers": {
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "PostmanRuntime/7.32.3"
            }
        },
        {
            "name": "Content-Type + Postman-Token",
            "headers": {
                "Content-Type": "application/x-www-form-urlencoded",
                "Postman-Token": "12345678-1234-1234-1234-123456789012"
            }
        },
        {
            "name": "All Postman essentials",
            "headers": {
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "*/*",
                "User-Agent": "PostmanRuntime/7.32.3",
                "Postman-Token": "12345678-1234-1234-1234-123456789012"
            }
        }
    ]
    
    data = {
        "grant_type": "password",
        "username": "Test_IntradayAPI_ADREM",
        "password": "nRtB8fDY485Nq4mu",
        "scope": "intraday_api"
    }
    
    for combo in header_combinations:
        print(f"\n🔍 Testing: {combo['name']}")
        print(f"Headers: {combo['headers']}")
        
        try:
            response = requests.post(url, headers=combo['headers'], data=data, timeout=30)
            print(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                print("✅ SUCCESS! This combination works!")
                print(f"Response: {response.text[:200]}...")
                return response.json()
            else:
                print(f"Response: {response.text}")
                
        except Exception as e:
            print(f"Error: {e}")
    
    return None

def test_with_session():
    """Test using requests.Session to maintain cookies/state like Postman"""
    print("\n🍪 Testing with Session (like Postman)")
    print("=" * 40)
    
    url = "https://sso.test.brm-power.ro/connect/token"
    
    # Use a session like Postman does
    session = requests.Session()
    
    # Set headers on the session
    session.headers.update({
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "*/*",
        "User-Agent": "PostmanRuntime/7.32.3"
    })
    
    data = {
        "grant_type": "password",
        "username": "Test_IntradayAPI_ADREM",
        "password": "nRtB8fDY485Nq4mu",
        "scope": "intraday_api"
    }
    
    try:
        print("Sending request with session...")
        response = session.post(url, data=data, timeout=30)
        
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            print("✅ SUCCESS with session!")
            return response.json()
        else:
            print("❌ Still failed with session")
            
    except Exception as e:
        print(f"Error: {e}")
    
    return None

def main():
    print("🚀 REPLICATING POSTMAN REQUEST")
    print("=" * 50)
    print("Trying to find the exact combination that works...")
    print()
    
    # Try different approaches
    methods = [
        ("Postman Headers", test_with_postman_headers),
        ("Minimal Headers", test_minimal_working_headers),
        ("Session Approach", test_with_session)
    ]
    
    for method_name, test_func in methods:
        print(f"\n{'='*20} {method_name} {'='*20}")
        result = test_func()
        
        if result:
            print(f"\n🎉 SUCCESS! {method_name} worked!")
            print("This method can now be used in the trading bot!")
            break
    else:
        print("\n❌ All methods failed.")
        print("We need to see the exact headers from your Postman request.")
        print("Please share the 'Headers (10)' tab from Postman.")

if __name__ == "__main__":
    main()
