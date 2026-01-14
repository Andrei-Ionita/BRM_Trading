"""
Test script that exactly matches the successful Postman request
Uses the same parameters that worked in Postman to get the Bearer token
"""
import asyncio
import logging
import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from auth_updated import initialize_auth_password
from config import config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def test_exact_postman_auth():
    """Test authentication using exact same parameters as successful Postman request"""
    logger.info("🔐 Testing authentication with EXACT Postman parameters...")
    
    # Exact parameters from your successful Postman request
    username = "Test_IntradayAPI_ADREM"
    password = "nRtB8fDY485Nq4mu"
    scope = "intraday_api"
    
    try:
        # Initialize authentication exactly as Postman did
        auth = initialize_auth_password(username, password, scope)
        
        # Get token
        token_info = await auth.get_token_async()
        
        logger.info("🎉 AUTHENTICATION SUCCESSFUL!")
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
    logger.info("📊 Testing Day-Ahead API with working authentication...")
    
    try:
        from day_ahead_client import DayAheadClient
        
        client = DayAheadClient()
        
        # Test getting auctions
        logger.info("   Fetching auctions...")
        auctions = await client.get_auctions()
        logger.info(f"✅ Successfully retrieved {len(auctions)} auctions")
        
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
        logger.info(f"✅ System state retrieved successfully")
        logger.info(f"   Current time: {state.get('currentTime', 'Unknown')}")
        logger.info(f"   System status: {state.get('status', 'Unknown')}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Day-Ahead API test failed: {e}")
        return False


async def test_intraday_with_working_auth():
    """Test Intraday WebSocket with working authentication"""
    logger.info("🌐 Testing Intraday WebSocket with working authentication...")
    
    try:
        from intraday_client import IntradayWebSocketClient
        
        # Create WebSocket client
        client = IntradayWebSocketClient("Test_IntradayAPI_ADREM")
        
        logger.info("   Attempting WebSocket connection...")
        connected = await client.connect()
        
        if connected:
            logger.info("✅ Intraday WebSocket connected successfully!")
            
            # Set up a simple message handler to see what we receive
            received_messages = []
            
            async def message_handler(data):
                received_messages.append(data)
                logger.info(f"   📨 Received message: {type(data)} with keys: {list(data.keys()) if isinstance(data, dict) else 'N/A'}")
            
            # Subscribe to configuration
            logger.info("   Subscribing to configuration...")
            await client.subscribe_to_configuration(message_handler)
            
            # Wait for messages
            logger.info("   Waiting for configuration and other messages...")
            await asyncio.sleep(10)
            
            logger.info(f"   📊 Received {len(received_messages)} messages total")
            
            # Show configuration if received
            for msg in received_messages:
                if isinstance(msg, dict) and 'portfolios' in msg:
                    logger.info("   ✅ Configuration received!")
                    portfolios = msg.get('portfolios', [])
                    logger.info(f"     Available portfolios: {len(portfolios)}")
                    for portfolio in portfolios[:3]:  # Show first 3
                        logger.info(f"       - {portfolio.get('id', 'Unknown')}: {portfolio.get('name', 'Unknown')}")
                    break
            
            # Disconnect
            logger.info("   Disconnecting...")
            await client.disconnect()
            return True
        else:
            logger.error("❌ Failed to connect to Intraday WebSocket")
            return False
            
    except Exception as e:
        logger.error(f"❌ Intraday WebSocket test failed: {e}")
        return False


async def test_full_bot_with_working_auth():
    """Test the complete trading bot with working authentication"""
    logger.info("🤖 Testing complete trading bot with working authentication...")
    
    try:
        from trading_bot import BRMTradingBot, TradingStrategy
        
        # Initialize bot with working credentials
        bot = BRMTradingBot(
            client_id="",  # Not used with our auth method
            client_secret="",  # Not used with our auth method
            username="Test_IntradayAPI_ADREM",
            portfolio_id="TEST-PORTFOLIO",  # We'll see what portfolios are available
            strategy=TradingStrategy.MANUAL
        )
        
        # Add event handlers to see what happens
        def on_signal(signal):
            logger.info(f"   🎯 Signal: {signal.action} {signal.quantity} MW @ €{signal.price:.2f}/MWh")
        
        def on_position_update(position):
            logger.info(f"   📈 Position: {position.contract_id} - {position.quantity} MW")
        
        def on_order_update(execution_report):
            logger.info(f"   📋 Order: {execution_report.get('clientOrderId', 'Unknown')} - {execution_report.get('status', 'Unknown')}")
        
        bot.add_signal_handler(on_signal)
        bot.add_position_handler(on_position_update)
        bot.add_order_handler(on_order_update)
        
        logger.info("   Starting trading bot...")
        
        # Start the bot
        start_task = asyncio.create_task(bot.start())
        
        # Wait for startup and initial data
        await asyncio.sleep(15)
        
        if bot.running:
            logger.info("✅ Trading bot started successfully!")
            
            # Check what we received
            if bot.configuration:
                logger.info("   ✅ Configuration received!")
                portfolios = bot.configuration.get('portfolios', [])
                logger.info(f"     Available portfolios: {len(portfolios)}")
                for portfolio in portfolios:
                    logger.info(f"       - ID: {portfolio.get('id', 'Unknown')}")
                    logger.info(f"         Name: {portfolio.get('name', 'Unknown')}")
                    logger.info(f"         Permission: {portfolio.get('permission', 'Unknown')}")
            
            # Check market data
            market_data = bot.get_market_data()
            logger.info(f"   📊 Market data keys: {list(market_data.keys())}")
            
            # Stop the bot
            logger.info("   Stopping trading bot...")
            await bot.stop()
            return True
        else:
            logger.error("❌ Trading bot failed to start")
            return False
            
    except Exception as e:
        logger.error(f"❌ Trading bot test failed: {e}")
        return False


async def main():
    """Main test function with working BRM authentication"""
    logger.info("🚀 BRM Trading Bot - WORKING AUTHENTICATION TESTS")
    logger.info("=" * 70)
    logger.info("Using the same parameters that worked in your Postman request!")
    logger.info("=" * 70)
    
    results = []
    
    # Test 1: Authentication (should work now!)
    token_info = await test_exact_postman_auth()
    results.append(("Authentication", token_info is not None))
    
    if token_info:
        # Test 2: Day-Ahead API
        success = await test_day_ahead_with_working_auth()
        results.append(("Day-Ahead API", success))
        
        # Test 3: Intraday WebSocket
        success = await test_intraday_with_working_auth()
        results.append(("Intraday WebSocket", success))
        
        # Test 4: Complete Trading Bot
        success = await test_full_bot_with_working_auth()
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
        logger.info("🎉 ALL TESTS PASSED! Your BRM Trading Bot is FULLY FUNCTIONAL!")
        logger.info("🚀 You can now start trading on the BRM markets!")
        logger.info("💡 Next: Use production_bot.py to start automated trading")
    elif passed > 0:
        logger.info("⚠️  Some tests passed. The bot is partially functional.")
        logger.info("   Check the failures above for any remaining issues.")
    else:
        logger.info("❌ Tests failed. Check the error messages above.")


if __name__ == "__main__":
    # Set test environment
    os.environ["BRM_ENVIRONMENT"] = "test"
    
    # Run tests
    asyncio.run(main())
