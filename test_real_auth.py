"""
Test script with real BRM credentials
Tests both authentication methods shown in the images
"""
import asyncio
import logging
import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from auth_updated import initialize_auth_basic, initialize_auth_password, create_basic_auth_header
from config import config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def test_basic_auth():
    """Test Basic authentication method"""
    logger.info("🔐 Testing Basic Authentication...")
    
    # From the first image - Basic auth header
    basic_auth_header = "Basic Y2xpZW50X2lkOmNsaWVudF9zZWNyZXQ="  # This appears to be a placeholder
    
    # The actual header from your image
    actual_basic_header = "Basic Y2xpZW50X2lkOmNsaWVudF9zZWNyZXQ="  # Replace with actual from image
    
    try:
        auth = initialize_auth_basic(actual_basic_header)
        token_info = await auth.get_token_async()
        
        logger.info("✅ Basic authentication successful!")
        logger.info(f"   Token type: {token_info.token_type}")
        logger.info(f"   Expires at: {token_info.expires_at}")
        logger.info(f"   Scope: {token_info.scope}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Basic authentication failed: {e}")
        return False


async def test_password_auth():
    """Test password grant authentication method"""
    logger.info("🔐 Testing Password Grant Authentication...")
    
    # From the second image
    username = "Test_IntradayAPI_ADREM"
    password = "nRtB8fDY485Nq4mu"
    scope = "intraday_api"
    
    try:
        auth = initialize_auth_password(username, password, scope)
        token_info = await auth.get_token_async()
        
        logger.info("✅ Password authentication successful!")
        logger.info(f"   Token type: {token_info.token_type}")
        logger.info(f"   Expires at: {token_info.expires_at}")
        logger.info(f"   Scope: {token_info.scope}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Password authentication failed: {e}")
        return False


async def test_day_ahead_api():
    """Test Day-Ahead API with authenticated token"""
    logger.info("📊 Testing Day-Ahead API...")
    
    try:
        from day_ahead_client import DayAheadClient
        
        client = DayAheadClient()
        
        # Test getting auctions
        auctions = await client.get_auctions()
        logger.info(f"✅ Retrieved {len(auctions)} auctions")
        
        # Test getting system state
        state = await client.get_system_state()
        logger.info(f"✅ System state: {state}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Day-Ahead API test failed: {e}")
        return False


async def test_intraday_connection():
    """Test Intraday WebSocket connection"""
    logger.info("🌐 Testing Intraday WebSocket connection...")
    
    try:
        from intraday_client import IntradayWebSocketClient
        
        # Use the username from the credentials
        client = IntradayWebSocketClient("Test_IntradayAPI_ADREM")
        
        connected = await client.connect()
        
        if connected:
            logger.info("✅ Intraday WebSocket connected successfully")
            
            # Wait a bit for configuration
            await asyncio.sleep(3)
            
            # Disconnect
            await client.disconnect()
            return True
        else:
            logger.error("❌ Failed to connect to Intraday WebSocket")
            return False
            
    except Exception as e:
        logger.error(f"❌ Intraday connection test failed: {e}")
        return False


async def main():
    """Main test function"""
    logger.info("🚀 Starting BRM Authentication Tests with Real Credentials")
    logger.info("=" * 60)
    
    results = []
    
    # Test 1: Password authentication (most likely to work)
    success = await test_password_auth()
    results.append(("Password Authentication", success))
    
    if success:
        # Test 2: Day-Ahead API
        success = await test_day_ahead_api()
        results.append(("Day-Ahead API", success))
        
        # Test 3: Intraday WebSocket
        success = await test_intraday_connection()
        results.append(("Intraday WebSocket", success))
    
    # Test 4: Basic authentication (if password worked, this might too)
    # Note: We'd need the actual Basic auth header from your image
    # success = await test_basic_auth()
    # results.append(("Basic Authentication", success))
    
    # Print results
    logger.info("=" * 60)
    logger.info("🎯 TEST RESULTS")
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
    
    if passed == total:
        logger.info("🎉 All tests passed! The trading bot is ready to use.")
    elif passed > 0:
        logger.info("⚠️  Some tests passed. Check the failures above.")
    else:
        logger.info("❌ All tests failed. Check your credentials and network connection.")


if __name__ == "__main__":
    # Set test environment
    os.environ["BRM_ENVIRONMENT"] = "test"
    
    # Run tests
    asyncio.run(main())
