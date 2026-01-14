"""
Debug Day-Ahead authentication with exact parameters from Postman
"""
import requests
import logging
from urllib.parse import quote, unquote

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_dayahead_auth():
    """Test Day-Ahead authentication with various parameter combinations"""
    
    logger.info("🔍 Testing Day-Ahead authentication parameters...")
    
    token_url = "https://sso.test.brm-power.ro/connect/token"
    
    # From the screenshots
    basic_auth = "Basic Y2xpZW50X2F1Y3Rpb25fYXBpOmNsaWVudF9hdWN0aW9uX2FwaQ=="
    
    # Test different password variations
    password_variations = [
        "odvM6f=15HW1s%H1Wb",  # As shown in screenshot
        "odvM6f=15HW1s%H1Wb",  # URL decoded version
        quote("odvM6f=15HW1s%H1Wb"),  # URL encoded
        "odvM6f=15HW1s%H1Wb",  # Raw version
    ]
    
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": basic_auth
    }
    
    for i, password in enumerate(password_variations, 1):
        logger.info(f"\n🧪 Test {i}: Password = '{password}'")
        
        # Test with form data (like Postman)
        data = {
            "grant_type": "password",
            "scope": "auction_api",
            "username": "Test_AuctionAPI_ADREM",
            "password": password
        }
        
        try:
            response = requests.post(token_url, headers=headers, data=data, timeout=10)
            
            logger.info(f"   📡 Status: {response.status_code}")
            
            if response.status_code == 200:
                token_data = response.json()
                logger.info(f"   ✅ SUCCESS! Got access token")
                logger.info(f"   🔑 Token type: {token_data.get('token_type')}")
                logger.info(f"   ⏰ Expires in: {token_data.get('expires_in')} seconds")
                return token_data["access_token"]
            else:
                try:
                    error_data = response.json()
                    logger.info(f"   ❌ Error: {error_data}")
                except:
                    logger.info(f"   ❌ Error: {response.text}")
        
        except Exception as e:
            logger.info(f"   ❌ Exception: {e}")
    
    # Test with raw form string (exactly like Postman)
    logger.info(f"\n🧪 Test with raw form string:")
    
    raw_data = "grant_type=password&scope=auction_api&username=Test_AuctionAPI_ADREM&password=odvM6f%3D15HW1s%25H1Wb"
    
    try:
        response = requests.post(
            token_url, 
            headers=headers, 
            data=raw_data,
            timeout=10
        )
        
        logger.info(f"   📡 Status: {response.status_code}")
        
        if response.status_code == 200:
            token_data = response.json()
            logger.info(f"   ✅ SUCCESS! Got access token")
            return token_data["access_token"]
        else:
            try:
                error_data = response.json()
                logger.info(f"   ❌ Error: {error_data}")
            except:
                logger.info(f"   ❌ Error: {response.text}")
    
    except Exception as e:
        logger.info(f"   ❌ Exception: {e}")
    
    # Decode the Basic auth to see what client credentials we're using
    import base64
    try:
        decoded_auth = base64.b64decode(basic_auth.replace("Basic ", "")).decode()
        logger.info(f"\n🔍 Basic auth decodes to: {decoded_auth}")
    except:
        logger.info(f"\n❌ Could not decode Basic auth")
    
    return None

if __name__ == "__main__":
    test_dayahead_auth()
