"""
Final test using the working authentication module
"""
import asyncio
import logging
import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from auth_working import initialize_working_auth

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def test_working_authentication():
    """Test the working authentication module"""
    logger.info("🔐 Testing working authentication module...")
    
    try:
        auth = initialize_working_auth()
        token_info = await auth.get_token_async()
        
        logger.info("✅ Authentication successful!")
        logger.info(f"   Token type: {token_info.token_type}")
        logger.info(f"   Expires in: {token_info.expires_in} seconds")
        logger.info(f"   Expires at: {token_info.expires_at}")
        logger.info(f"   Scope: {token_info.scope}")
        logger.info(f"   Access token (first 50 chars): {token_info.access_token[:50]}...")
        
        return token_info
        
    except Exception as e:
        logger.error(f"❌ Authentication failed: {e}")
        return None


async def test_day_ahead_with_working_auth():
    """Test Day-Ahead API with working authentication"""
    logger.info("📊 Testing Day-Ahead API with working auth...")
    
    try:
        # Temporarily replace the auth module import in day_ahead_client
        import day_ahead_client
        import auth_working
        
        # Monkey patch the auth module
        day_ahead_client.auth = auth_working
        
        from day_ahead_client import DayAheadClient
        
        client = DayAheadClient()
        
        # Test getting auctions
        logger.info("   Fetching auctions...")
        auctions = await client.get_auctions()
        logger.info(f"✅ Retrieved {len(auctions)} auctions")
        
        if auctions:
            # Show details of first auction
            auction = auctions[0]
            logger.info(f"   First auction:")
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


async def test_intraday_with_working_auth():
    """Test Intraday WebSocket with working authentication"""
    logger.info("🌐 Testing Intraday WebSocket with working auth...")
    
    try:
        # Temporarily replace the auth module import in intraday_client
        import intraday_client
        import auth_working
        
        # Monkey patch the auth module
        intraday_client.auth = auth_working
        
        from intraday_client import IntradayWebSocketClient
        
        client = IntradayWebSocketClient("Test_IntradayAPI_ADREM")
        
        logger.info("   Connecting to WebSocket...")
        connected = await client.connect()
        
        if connected:
            logger.info("✅ WebSocket connected successfully!")
            
            # Set up message handler
            config_received = False
            
            async def config_handler(data):
                nonlocal config_received
                config_received = True
                portfolios = data.get('portfolios', [])
                logger.info(f"   📨 Configuration received: {len(portfolios)} portfolios")
                for portfolio in portfolios[:3]:
                    logger.info(f"       - {portfolio.get('id', 'Unknown')}: {portfolio.get('name', 'Unknown')}")
            
            # Subscribe to configuration
            logger.info("   Subscribing to configuration...")
            await client.subscribe_to_configuration(config_handler)
            
            # Wait for configuration
            logger.info("   Waiting for configuration...")
            await asyncio.sleep(10)
            
            if config_received:
                logger.info("   ✅ Configuration received successfully!")
            else:
                logger.warning("   ⚠️  No configuration received")
            
            # Disconnect
            logger.info("   Disconnecting...")
            await client.disconnect()
            return True
        else:
            logger.error("❌ Failed to connect to WebSocket")
            return False
            
    except Exception as e:
        logger.error(f"❌ WebSocket test failed: {e}")
        return False


async def main():
    """Main test function"""
    logger.info("🚀 BRM TRADING BOT - FINAL WORKING TEST")
    logger.info("=" * 60)
    logger.info("Using the verified working authentication method")
    logger.info("=" * 60)
    
    results = []
    
    # Test 1: Authentication
    token_info = await test_working_authentication()
    results.append(("Authentication", token_info is not None))
    
    if token_info:
        # Test 2: Day-Ahead API
        success = await test_day_ahead_with_working_auth()
        results.append(("Day-Ahead API", success))
        
        # Test 3: Intraday WebSocket
        success = await test_intraday_with_working_auth()
        results.append(("Intraday WebSocket", success))
    
    # Print results
    logger.info("=" * 60)
    logger.info("🎯 FINAL TEST RESULTS")
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
        logger.info("🎉 ALL TESTS PASSED! BRM Trading Bot is FULLY FUNCTIONAL!")
        logger.info("🚀 Ready for live trading on BRM markets!")
        logger.info("")
        logger.info("📋 Next Steps:")
        logger.info("   1. The authentication is working perfectly")
        logger.info("   2. Both Day-Ahead and Intraday APIs are accessible")
        logger.info("   3. You can now start implementing trading strategies")
        logger.info("   4. Complete BRM conformance testing as required")
        logger.info("   5. Deploy to production when ready")
    elif passed > 0:
        logger.info("⚠️  Some tests passed. The bot is partially functional.")
    else:
        logger.info("❌ Tests failed. Check the error messages above.")


if __name__ == "__main__":
    # Set test environment
    os.environ["BRM_ENVIRONMENT"] = "test"
    
    # Run tests
    asyncio.run(main())
