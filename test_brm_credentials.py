"""
Test script with actual BRM test credentials
Tests both authentication methods with real BRM test environment credentials
"""
import asyncio
import logging
import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from auth_updated import initialize_auth_basic, initialize_auth_password
from config import config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def test_basic_auth_real():
    """Test Basic authentication with real BRM credentials"""
    logger.info("🔐 Testing Basic Authentication with real BRM credentials...")
    
    # From the first image - actual Basic auth header from BRM
    basic_auth_header = "Basic Y2xpZW50X2lkOmNsaWVudF9zZWNyZXQ="
    
    try:
        auth = initialize_auth_basic(basic_auth_header)
        token_info = await auth.get_token_async()
        
        logger.info("✅ Basic authentication successful!")
        logger.info(f"   Token type: {token_info.token_type}")
        logger.info(f"   Expires at: {token_info.expires_at}")
        logger.info(f"   Scope: {token_info.scope}")
        logger.info(f"   Access token (first 20 chars): {token_info.access_token[:20]}...")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Basic authentication failed: {e}")
        return False


async def test_password_auth_real():
    """Test password grant authentication with real BRM credentials"""
    logger.info("🔐 Testing Password Grant Authentication with real BRM credentials...")
    
    # From the second image - actual credentials from BRM
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
        logger.info(f"   Access token (first 20 chars): {token_info.access_token[:20]}...")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Password authentication failed: {e}")
        return False


async def test_day_ahead_api_real():
    """Test Day-Ahead API with real authenticated token"""
    logger.info("📊 Testing Day-Ahead API with real authentication...")
    
    try:
        from day_ahead_client import DayAheadClient
        
        client = DayAheadClient()
        
        # Test getting auctions
        logger.info("   Getting auctions...")
        auctions = await client.get_auctions()
        logger.info(f"✅ Retrieved {len(auctions)} auctions")
        
        if auctions:
            # Show details of first auction
            first_auction = auctions[0]
            logger.info(f"   First auction: {first_auction.get('id', 'Unknown ID')}")
            logger.info(f"   Name: {first_auction.get('name', 'Unknown')}")
            logger.info(f"   State: {first_auction.get('state', 'Unknown')}")
        
        # Test getting system state
        logger.info("   Getting system state...")
        state = await client.get_system_state()
        logger.info(f"✅ System state retrieved")
        logger.info(f"   Current time: {state.get('currentTime', 'Unknown')}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Day-Ahead API test failed: {e}")
        return False


async def test_intraday_connection_real():
    """Test Intraday WebSocket connection with real authentication"""
    logger.info("🌐 Testing Intraday WebSocket connection with real authentication...")
    
    try:
        from intraday_client import IntradayWebSocketClient
        
        # Use the username from the real credentials
        client = IntradayWebSocketClient("Test_IntradayAPI_ADREM")
        
        logger.info("   Attempting WebSocket connection...")
        connected = await client.connect()
        
        if connected:
            logger.info("✅ Intraday WebSocket connected successfully!")
            
            # Wait for configuration and other messages
            logger.info("   Waiting for configuration...")
            await asyncio.sleep(5)
            
            logger.info("   Disconnecting...")
            await client.disconnect()
            return True
        else:
            logger.error("❌ Failed to connect to Intraday WebSocket")
            return False
            
    except Exception as e:
        logger.error(f"❌ Intraday connection test failed: {e}")
        return False


async def test_full_trading_bot():
    """Test the full trading bot with real credentials"""
    logger.info("🤖 Testing full trading bot with real credentials...")
    
    try:
        from trading_bot import BRMTradingBot, TradingStrategy
        
        # Initialize with real credentials
        bot = BRMTradingBot(
            client_id="",  # Not used with our auth method
            client_secret="",  # Not used with our auth method
            username="Test_IntradayAPI_ADREM",
            portfolio_id="TEST-PORTFOLIO",  # You might need to get the real portfolio ID
            strategy=TradingStrategy.MANUAL
        )
        
        logger.info("   Starting trading bot...")
        
        # This will attempt to connect to both Day-Ahead and Intraday
        # We'll run it for a short time to test connectivity
        start_task = asyncio.create_task(bot.start())
        
        # Wait a bit for startup
        await asyncio.sleep(10)
        
        if bot.running:
            logger.info("✅ Trading bot started successfully!")
            
            # Check if we received configuration
            if bot.configuration:
                logger.info("✅ Configuration received from Intraday API")
                logger.info(f"   Portfolios available: {len(bot.configuration.get('portfolios', []))}")
            else:
                logger.warning("⚠️  No configuration received yet")
            
            # Stop the bot
            await bot.stop()
            return True
        else:
            logger.error("❌ Trading bot failed to start")
            return False
            
    except Exception as e:
        logger.error(f"❌ Full trading bot test failed: {e}")
        return False


async def main():
    """Main test function with real BRM credentials"""
    logger.info("🚀 Starting BRM Authentication Tests with REAL BRM Test Credentials")
    logger.info("=" * 70)
    
    results = []
    
    # Test 1: Password authentication (most likely to work)
    success = await test_password_auth_real()
    results.append(("Password Authentication", success))
    
    if success:
        # Test 2: Day-Ahead API
        success = await test_day_ahead_api_real()
        results.append(("Day-Ahead API", success))
        
        # Test 3: Intraday WebSocket
        success = await test_intraday_connection_real()
        results.append(("Intraday WebSocket", success))
        
        # Test 4: Full Trading Bot
        success = await test_full_trading_bot()
        results.append(("Full Trading Bot", success))
    
    # Test 5: Basic authentication (alternative method)
    success = await test_basic_auth_real()
    results.append(("Basic Authentication", success))
    
    # Print results
    logger.info("=" * 70)
    logger.info("🎯 TEST RESULTS WITH REAL BRM CREDENTIALS")
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
        logger.info("🎉 ALL TESTS PASSED! The trading bot is fully functional with BRM!")
        logger.info("🚀 You can now start trading on the BRM test environment!")
    elif passed > 0:
        logger.info("⚠️  Some tests passed. The bot is partially functional.")
        logger.info("   Check the failures above and contact BRM support if needed.")
    else:
        logger.info("❌ All tests failed. Check credentials and network connection.")


if __name__ == "__main__":
    # Set test environment
    os.environ["BRM_ENVIRONMENT"] = "test"
    
    # Run tests
    asyncio.run(main())
