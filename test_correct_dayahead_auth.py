"""
Test Day-Ahead authentication with the correct password
"""
import requests
import logging
from urllib.parse import quote

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_correct_dayahead_auth():
    """Test Day-Ahead authentication with the correct password"""
    
    logger.info("🔍 Testing Day-Ahead authentication with correct password...")
    
    token_url = "https://sso.test.brm-power.ro/connect/token"
    
    # Correct password from user
    correct_password = "odvM6{=15HW1s%H1Wb"
    
    # From the screenshots
    basic_auth = "Basic Y2xpZW50X2F1Y3Rpb25fYXBpOmNsaWVudF9hdWN0aW9uX2FwaQ=="
    
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": basic_auth
    }
    
    # Test with the correct password
    logger.info(f"🧪 Testing with password: '{correct_password}'")
    
    data = {
        "grant_type": "password",
        "scope": "auction_api",
        "username": "Test_AuctionAPI_ADREM",
        "password": correct_password
    }
    
    try:
        response = requests.post(token_url, headers=headers, data=data, timeout=10)
        
        logger.info(f"📡 Status: {response.status_code}")
        
        if response.status_code == 200:
            token_data = response.json()
            logger.info(f"✅ SUCCESS! Got Day-Ahead access token")
            logger.info(f"🔑 Token type: {token_data.get('token_type')}")
            logger.info(f"⏰ Expires in: {token_data.get('expires_in')} seconds")
            
            # Test the token by calling the API
            test_api_with_token(token_data["access_token"])
            
            return token_data["access_token"]
        else:
            try:
                error_data = response.json()
                logger.info(f"❌ Error: {error_data}")
            except:
                logger.info(f"❌ Error: {response.text}")
    
    except Exception as e:
        logger.info(f"❌ Exception: {e}")
    
    return None

def test_api_with_token(access_token):
    """Test the Day-Ahead API with the access token"""
    
    logger.info("\n🧪 Testing Day-Ahead API with access token...")
    
    api_base_url = "https://auctions-api.test.brm-power.ro"
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "User-Agent": "BRM-Trading-Bot/1.0"
    }
    
    # Test endpoints
    endpoints = [
        "/api/state",
        "/api/v1/auctions",
        "/api/v2/auctions",
    ]
    
    for endpoint in endpoints:
        logger.info(f"📡 Testing {endpoint}...")
        
        try:
            response = requests.get(f"{api_base_url}{endpoint}", headers=headers, timeout=10)
            
            logger.info(f"   📊 Status: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    logger.info(f"   ✅ SUCCESS! Got JSON data")
                    
                    if isinstance(data, list):
                        logger.info(f"   📋 Found {len(data)} items")
                        if data:
                            logger.info(f"   🔍 Sample item keys: {list(data[0].keys())[:5]}")
                    elif isinstance(data, dict):
                        logger.info(f"   🔑 Response keys: {list(data.keys())[:5]}")
                    else:
                        logger.info(f"   📄 Response: {str(data)[:100]}...")
                        
                except:
                    text = response.text
                    logger.info(f"   📄 Text response: {text[:100]}...")
            
            elif response.status_code == 403:
                logger.info(f"   ⚠️ Forbidden - need different permissions")
            elif response.status_code == 404:
                logger.info(f"   ❌ Not Found")
            else:
                logger.info(f"   ❓ Status {response.status_code}: {response.text[:100]}...")
        
        except Exception as e:
            logger.info(f"   ❌ Exception: {e}")

if __name__ == "__main__":
    test_correct_dayahead_auth()
