"""
Test with the CORRECT Basic auth header provided by the user
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


def test_correct_basic_auth():
    """Test with the correct Basic auth header"""
    logger.info("🔐 Testing with CORRECT Basic auth header...")
    
    url = "https://sso.test.brm-power.ro/connect/token"
    
    # The CORRECT Basic auth header provided by the user
    correct_basic_header = "Basic Y2xpZW50X2ludHJhZGF5X2FwaToxeEI5SWsxeHNFdTJuYndWYTFCUg=="
    
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": correct_basic_header
    }
    
    # The form data
    data = {
        "grant_type": "password",
        "username": "Test_IntradayAPI_ADREM",
        "password": "nRtB8fDY485Nq4mu",
        "scope": "intraday_api"
    }
    
    logger.info(f"URL: {url}")
    logger.info(f"Headers: {headers}")
    logger.info(f"Data: {data}")
    
    # Decode the Basic auth header to see what it contains
    try:
        encoded = correct_basic_header.replace("Basic ", "")
        decoded = base64.b64decode(encoded).decode()
        logger.info(f"Basic auth decodes to: {decoded}")
    except Exception as e:
        logger.error(f"Could not decode Basic auth: {e}")
    
    try:
        logger.info("Sending request with CORRECT Basic auth header...")
        response = requests.post(url, headers=headers, data=data, timeout=30)
        
        logger.info(f"Status Code: {response.status_code}")
        logger.info(f"Response Headers: {dict(response.headers)}")
        logger.info(f"Response Body: {response.text}")
        
        if response.status_code == 200:
            logger.info("🎉 SUCCESS! Correct Basic auth header works!")
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
    """Test using our auth module with the correct Basic header"""
    logger.info("🔧 Testing with our authentication module...")
    
    try:
        # Use the correct Basic auth header
        correct_basic_header = "Basic Y2xpZW50X2ludHJhZGF5X2FwaToxeEI5SWsxeHNFdTJuYndWYTFCUg=="
        
        auth = initialize_auth_basic(correct_basic_header)
        token_info = await auth.get_token_async()
        
        logger.info("✅ Authentication module works!")
        logger.info(f"   Token type: {token_info.token_type}")
        logger.info(f"   Expires in: {token_info.expires_in} seconds")
        logger.info(f"   Expires at: {token_info.expires_at}")
        logger.info(f"   Scope: {token_info.scope}")
        logger.info(f"   Access token (first 50 chars): {token_info.access_token[:50]}...")
        
        return token_info
        
    except Exception as e:
        logger.error(f"❌ Authentication module failed: {e}")
        return None


async def test_day_ahead_api():
    """Test Day-Ahead API with working authentication"""
    logger.info("📊 Testing Day-Ahead API...")
    
    try:
        from day_ahead_client import DayAheadClient
        
        client = DayAheadClient()
        
        # Test getting auctions
        logger.info("   Fetching auctions...")
        auctions = await client.get_auctions()
        logger.info(f"✅ Retrieved {len(auctions)} auctions")
        
        if auctions:
            # Show details of first few auctions
            for i, auction in enumerate(auctions[:3]):
                logger.info(f"   Auction {i+1}:")
                logger.info(f"     ID: {auction.get('id', 'Unknown')}")
                logger.info(f"     Name: {auction.get('name', 'Unknown')}")
                logger.info(f"     State: {auction.get('state', 'Unknown')}")
                logger.info(f"     Delivery Date: {auction.get('deliveryDate', 'Unknown')}")
        
        # Test getting system state
        logger.info("   Fetching system state...")
        state = await client.get_system_state()
        logger.info(f"✅ System state retrieved")
        logger.info(f"   Current time: {state.get('currentTime', 'Unknown')}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Day-Ahead API test failed: {e}")
        return False


async def test_intraday_websocket():
    """Test Intraday WebSocket with working authentication"""
    logger.info("🌐 Testing Intraday WebSocket...")
    
    try:
        from intraday_client import IntradayWebSocketClient
        
        client = IntradayWebSocketClient("Test_IntradayAPI_ADREM")
        
        logger.info("   Connecting to WebSocket...")
        connected = await client.connect()
        
        if connected:
            logger.info("✅ WebSocket connected successfully!")
            
            # Wait for configuration
            logger.info("   Waiting for configuration...")
            await asyncio.sleep(10)
            
            logger.info("   Disconnecting...")
            await client.disconnect()
            return True
        else:
            logger.error("❌ Failed to connect to WebSocket")
            return False
            
    except Exception as e:
        logger.error(f"❌ WebSocket test failed: {e}")
        return False


async def test_full_trading_bot():
    """Test the complete trading bot"""
    logger.info("🤖 Testing complete trading bot...")
    
    try:
        from trading_bot import BRMTradingBot, TradingStrategy
        
        # Initialize bot
        bot = BRMTradingBot(
            client_id="",
            client_secret="",
            username="Test_IntradayAPI_ADREM",
            portfolio_id="TEST-PORTFOLIO",
            strategy=TradingStrategy.MANUAL
        )
        
        logger.info("   Starting trading bot...")
        
        # Start the bot
        start_task = asyncio.create_task(bot.start())
        
        # Wait for startup
        await asyncio.sleep(15)
        
        if bot.running:
            logger.info("✅ Trading bot started successfully!")
            
            # Check configuration
            if bot.configuration:
                logger.info("   ✅ Configuration received!")
                portfolios = bot.configuration.get('portfolios', [])
                logger.info(f"     Available portfolios: {len(portfolios)}")
                for portfolio in portfolios:
                    logger.info(f"       - {portfolio.get('id', 'Unknown')}: {portfolio.get('name', 'Unknown')}")
            
            # Stop the bot
            await bot.stop()
            return True
        else:
            logger.error("❌ Trading bot failed to start")
            return False
            
    except Exception as e:
        logger.error(f"❌ Trading bot test failed: {e}")
        return False


async def main():
    """Main test function"""
    logger.info("🚀 BRM AUTHENTICATION TEST WITH CORRECT CREDENTIALS")
    logger.info("=" * 70)
    logger.info("Using the correct Basic auth header provided by the user")
    logger.info("=" * 70)
    
    results = []
    
    # Test 1: Direct HTTP request with correct auth
    token_data = test_correct_basic_auth()
    results.append(("Direct HTTP Request", token_data is not None))
    
    if token_data:
        # Test 2: Our auth module
        token_info = await test_with_auth_module()
        results.append(("Auth Module", token_info is not None))
        
        if token_info:
            # Test 3: Day-Ahead API
            success = await test_day_ahead_api()
            results.append(("Day-Ahead API", success))
            
            # Test 4: Intraday WebSocket
            success = await test_intraday_websocket()
            results.append(("Intraday WebSocket", success))
            
            # Test 5: Complete Trading Bot
            success = await test_full_trading_bot()
            results.append(("Complete Trading Bot", success))
    
    # Print results
    logger.info("=" * 70)
    logger.info("🎯 FINAL TEST RESULTS")
    logger.info("=" * 70)
    
    passed = 0
    total = len(results)
    
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        logger.info(f"{status} {test_name}")
        if success:
            passed += 1
    
    logger.info("-" * 70)
    logger.info(f"📊 Results: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("🎉 ALL TESTS PASSED! BRM Trading Bot is FULLY FUNCTIONAL!")
        logger.info("🚀 You can now start trading on the BRM markets!")
    elif passed > 0:
        logger.info("⚠️  Some tests passed. The bot is partially functional.")
    else:
        logger.info("❌ Tests failed. Check the error messages above.")


if __name__ == "__main__":
    # Set test environment
    os.environ["BRM_ENVIRONMENT"] = "test"
    
    # Run tests
    asyncio.run(main())
