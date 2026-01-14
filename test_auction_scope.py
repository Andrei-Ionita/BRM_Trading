"""
Test BRM API access with different scopes using our working credentials
"""
import asyncio
import logging
import aiohttp
import base64
from datetime import datetime, timedelta
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_different_scopes():
    """Test authentication with different scopes"""
    
    # Our working credentials
    client_id = "client_intraday_api"
    client_secret = "1xB9Ik1xsEu2nbwVa1BR"
    username = "Test_IntradayAPI_ADREM"
    password = "nR(B8fDY{485Nq4mu"
    
    # Create Basic auth header
    credentials = f"{client_id}:{client_secret}"
    basic_auth = base64.b64encode(credentials.encode()).decode()
    
    token_url = "https://sso.test.brm-power.ro/connect/token"
    
    # Test different scopes
    scopes_to_test = [
        "intraday_api",           # Our working scope
        "auction_api",            # Auction API scope
        "intraday_api auction_api",  # Both scopes
        "openid",                 # Basic OpenID scope
        "",                       # No scope
    ]
    
    logger.info("🧪 Testing BRM API with different scopes")
    logger.info("=" * 60)
    
    successful_tokens = {}
    
    for scope in scopes_to_test:
        logger.info(f"🔍 Testing scope: '{scope}'")
        
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {basic_auth}"
        }
        
        data = {
            "grant_type": "password",
            "username": username,
            "password": password
        }
        
        if scope:
            data["scope"] = scope
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    token_url,
                    headers=headers,
                    data=data,
                    timeout=aiohttp.ClientTimeout(total=15)
                ) as response:
                    
                    logger.info(f"   Status: {response.status}")
                    
                    if response.status == 200:
                        token_data = await response.json()
                        logger.info(f"   ✅ SUCCESS!")
                        logger.info(f"   Token type: {token_data.get('token_type', 'Unknown')}")
                        logger.info(f"   Expires in: {token_data.get('expires_in', 'Unknown')} seconds")
                        logger.info(f"   Scope: {token_data.get('scope', 'Unknown')}")
                        
                        successful_tokens[scope] = token_data
                        
                    else:
                        error_text = await response.text()
                        logger.info(f"   ❌ Failed: {error_text}")
                
        except Exception as e:
            logger.error(f"   ❌ Exception: {e}")
        
        logger.info("")
    
    # Now test API access with successful tokens
    logger.info("🚀 Testing API access with successful tokens")
    logger.info("=" * 60)
    
    base_url = "https://auctions-api.test.brm-power.ro"
    
    endpoints_to_test = [
        "/api/state",
        "/api/v1/auctions",
        "/api/v2/auctions",
    ]
    
    for scope, token_data in successful_tokens.items():
        logger.info(f"🔑 Testing with scope: '{scope}'")
        
        bearer_token = f"Bearer {token_data['access_token']}"
        
        for endpoint in endpoints_to_test:
            logger.info(f"   🔍 Testing: {endpoint}")
            
            try:
                headers = {
                    "Authorization": bearer_token,
                    "Accept": "application/json"
                }
                
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        f"{base_url}{endpoint}",
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=15)
                    ) as response:
                        
                        logger.info(f"      Status: {response.status}")
                        
                        if response.status == 200:
                            try:
                                data = await response.json()
                                logger.info(f"      ✅ SUCCESS! Got {type(data).__name__}")
                                
                                if isinstance(data, list):
                                    logger.info(f"      📊 {len(data)} items")
                                elif isinstance(data, dict):
                                    logger.info(f"      📊 {len(data)} fields")
                                else:
                                    logger.info(f"      📄 Data: {str(data)[:100]}...")
                                    
                            except:
                                text = await response.text()
                                logger.info(f"      📄 Text: {text[:100]}...")
                                
                        elif response.status == 403:
                            logger.info(f"      ⚠️ Forbidden - Need permissions")
                        elif response.status == 404:
                            logger.info(f"      ⚠️ Not Found")
                        else:
                            error_text = await response.text()
                            logger.info(f"      ❌ Error: {error_text[:100]}...")
                            
            except Exception as e:
                logger.error(f"      ❌ Exception: {e}")
        
        logger.info("")
    
    # Summary
    logger.info("📊 SUMMARY")
    logger.info("=" * 40)
    logger.info(f"✅ Successful scopes: {len(successful_tokens)}")
    for scope in successful_tokens.keys():
        logger.info(f"   - '{scope}'")
    
    if successful_tokens:
        logger.info("🎯 RECOMMENDATION:")
        logger.info("   Use the working scope(s) above for API access")
        logger.info("   Contact BRM if auction endpoints return 403 Forbidden")
    else:
        logger.info("❌ No scopes worked - check credentials with BRM")


if __name__ == "__main__":
    asyncio.run(test_different_scopes())
