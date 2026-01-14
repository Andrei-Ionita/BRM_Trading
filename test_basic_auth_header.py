"""
Test script using the exact Basic auth header from Postman
This combines Basic authentication header with form data
"""
import asyncio
import logging
import sys
import os
import base64

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from auth_updated import initialize_auth_basic
import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def test_exact_postman_basic_auth():
    """Test using the exact Basic auth header from Postman"""
    logger.info("🔐 Testing with EXACT Basic auth header from Postman...")
    
    url = "https://sso.test.brm-power.ro/connect/token"
    
    # Exact headers from your Postman screenshot
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": "Basic Y2xpZW50X2lkOmNsaWVudF9zZWNyZXQ="
    }
    
    # The form data from your Postman body
    data = {
        "grant_type": "password",
        "username": "Test_IntradayAPI_ADREM",
        "password": "nRtB8fDY485Nq4mu",
        "scope": "intraday_api"
    }
    
    logger.info(f"URL: {url}")
    logger.info(f"Headers: {headers}")
    logger.info(f"Data: {data}")
    
    # First, let's see what the Basic auth header decodes to
    try:
        encoded = headers["Authorization"].replace("Basic ", "")
        decoded = base64.b64decode(encoded).decode()
        logger.info(f"Basic auth decodes to: {decoded}")
    except Exception as e:
        logger.error(f"Could not decode Basic auth: {e}")
    
    try:
        logger.info("Sending request with exact Postman configuration...")
        response = requests.post(url, headers=headers, data=data, timeout=30)
        
        logger.info(f"Status Code: {response.status_code}")
        logger.info(f"Response Headers: {dict(response.headers)}")
        logger.info(f"Response Body: {response.text}")
        
        if response.status_code == 200:
            logger.info("🎉 SUCCESS! Basic auth header + form data works!")
            token_data = response.json()
            access_token = token_data.get('access_token', '')
            logger.info(f"Access token (first 50 chars): {access_token[:50]}...")
            return token_data
        else:
            logger.error(f"❌ Failed with status {response.status_code}")
            return None
            
    except Exception as e:
        logger.error(f"❌ Request failed: {e}")
        return None


async def test_with_auth_module():
    """Test using our auth module with the Basic header"""
    logger.info("🔧 Testing with our authentication module...")
    
    try:
        # Use the exact Basic auth header from Postman
        basic_auth_header = "Basic Y2xpZW50X2lkOmNsaWVudF9zZWNyZXQ="
        
        auth = initialize_auth_basic(basic_auth_header)
        token_info = await auth.get_token_async()
        
        logger.info("✅ Authentication module works!")
        logger.info(f"   Token type: {token_info.token_type}")
        logger.info(f"   Expires at: {token_info.expires_at}")
        logger.info(f"   Access token (first 50 chars): {token_info.access_token[:50]}...")
        
        return token_info
        
    except Exception as e:
        logger.error(f"❌ Authentication module failed: {e}")
        return None


def test_different_grant_types():
    """Test different grant types with the Basic auth header"""
    logger.info("🧪 Testing different grant types with Basic auth...")
    
    url = "https://sso.test.brm-power.ro/connect/token"
    
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": "Basic Y2xpZW50X2lkOmNsaWVudF9zZWNyZXQ="
    }
    
    # Test different grant types
    test_cases = [
        {
            "name": "Client Credentials (no username/password)",
            "data": {
                "grant_type": "client_credentials",
                "scope": "intraday_api"
            }
        },
        {
            "name": "Password Grant (with username/password)",
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
        }
    ]
    
    for test_case in test_cases:
        logger.info(f"\n🔍 Testing: {test_case['name']}")
        logger.info(f"Data: {test_case['data']}")
        
        try:
            response = requests.post(url, headers=headers, data=test_case['data'], timeout=30)
            logger.info(f"Status: {response.status_code}")
            logger.info(f"Response: {response.text}")
            
            if response.status_code == 200:
                logger.info("✅ SUCCESS!")
                return response.json()
                
        except Exception as e:
            logger.error(f"Error: {e}")
    
    return None


async def main():
    """Main test function"""
    logger.info("🚀 Testing BRM Authentication with Basic Auth Header")
    logger.info("=" * 60)
    logger.info("Using the exact configuration from your Postman request")
    logger.info("=" * 60)
    
    results = []
    
    # Test 1: Exact Postman configuration
    token_data = test_exact_postman_basic_auth()
    results.append(("Exact Postman Config", token_data is not None))
    
    if token_data:
        # Test 2: Our auth module
        token_info = await test_with_auth_module()
        results.append(("Auth Module", token_info is not None))
        
        if token_info:
            logger.info("🎉 AUTHENTICATION WORKING! Testing APIs...")
            
            # Test Day-Ahead API
            try:
                from day_ahead_client import DayAheadClient
                client = DayAheadClient()
                auctions = await client.get_auctions()
                logger.info(f"✅ Day-Ahead API: Retrieved {len(auctions)} auctions")
                results.append(("Day-Ahead API", True))
            except Exception as e:
                logger.error(f"❌ Day-Ahead API failed: {e}")
                results.append(("Day-Ahead API", False))
    else:
        # If exact config failed, try different grant types
        logger.info("Exact config failed, trying different grant types...")
        token_data = test_different_grant_types()
        results.append(("Alternative Grant Types", token_data is not None))
    
    # Print results
    logger.info("=" * 60)
    logger.info("🎯 FINAL RESULTS")
    logger.info("=" * 60)
    
    passed = 0
    total = len(results)
    
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        logger.info(f"{status} {test_name}")
        if success:
            passed += 1
    
    logger.info("-" * 60)
    logger.info(f"📊 Results: {passed}/{total} tests passed")
    
    if passed > 0:
        logger.info("🎉 SUCCESS! We found a working authentication method!")
        logger.info("🚀 The trading bot can now be activated!")
    else:
        logger.info("❌ Still no success. Need to investigate further.")


if __name__ == "__main__":
    # Set test environment
    os.environ["BRM_ENVIRONMENT"] = "test"
    
    # Run tests
    asyncio.run(main())
