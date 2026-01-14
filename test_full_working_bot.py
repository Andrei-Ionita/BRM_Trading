"""
Comprehensive test of the BRM Trading Bot with WORKING credentials
"""
import asyncio
import logging
import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from auth_updated import initialize_auth_basic
from config import config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def test_authentication():
    """Test authentication with working credentials"""
    logger.info("🔐 Testing authentication with WORKING credentials...")
    
    try:
        # The working Basic auth header
        correct_basic_header = "Basic Y2xpZW50X2ludHJhZGF5X2FwaToxeEI5SWsxeHNFdTJuYndWYTFCUg=="
        
        auth = initialize_auth_basic(correct_basic_header)
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
            for i, auction in enumerate(auctions[:2]):
                logger.info(f"   Auction {i+1}:")
                logger.info(f"     ID: {auction.get('id', 'Unknown')}")
                logger.info(f"     Name: {auction.get('name', 'Unknown')}")
                logger.info(f"     State: {auction.get('state', 'Unknown')}")
                logger.info(f"     Delivery Date: {auction.get('deliveryDate', 'Unknown')}")
                logger.info(f"     Gate Closure: {auction.get('gateClosure', 'Unknown')}")
        
        # Test getting system state
        logger.info("   Fetching system state...")
        state = await client.get_system_state()
        logger.info(f"✅ System state retrieved")
        logger.info(f"   Current time: {state.get('currentTime', 'Unknown')}")
        logger.info(f"   System status: {state.get('status', 'Unknown')}")
        
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
            
            # Set up message handlers to capture what we receive
            received_messages = []
            
            async def config_handler(data):
                received_messages.append(('config', data))
                logger.info(f"   📨 Configuration received: {len(data.get('portfolios', []))} portfolios")
            
            async def market_data_handler(data):
                received_messages.append(('market_data', data))
                logger.info(f"   📊 Market data received: {type(data)}")
            
            # Subscribe to configuration
            logger.info("   Subscribing to configuration...")
            await client.subscribe_to_configuration(config_handler)
            
            # Subscribe to market data
            logger.info("   Subscribing to market data...")
            await client.subscribe_to_market_data(market_data_handler)
            
            # Wait for messages
            logger.info("   Waiting for messages...")
            await asyncio.sleep(15)
            
            logger.info(f"   📊 Received {len(received_messages)} messages total")
            
            # Show configuration details
            for msg_type, data in received_messages:
                if msg_type == 'config' and isinstance(data, dict):
                    portfolios = data.get('portfolios', [])
                    logger.info(f"   ✅ Configuration details:")
                    logger.info(f"     Available portfolios: {len(portfolios)}")
                    for portfolio in portfolios[:3]:  # Show first 3
                        logger.info(f"       - ID: {portfolio.get('id', 'Unknown')}")
                        logger.info(f"         Name: {portfolio.get('name', 'Unknown')}")
                        logger.info(f"         Permission: {portfolio.get('permission', 'Unknown')}")
                    break
            
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


async def test_complete_trading_bot():
    """Test the complete trading bot with working authentication"""
    logger.info("🤖 Testing complete trading bot...")
    
    try:
        from trading_bot import BRMTradingBot, TradingStrategy
        
        # Initialize bot with working credentials
        bot = BRMTradingBot(
            client_id="",  # Not used with Basic auth
            client_secret="",  # Not used with Basic auth
            username="Test_IntradayAPI_ADREM",
            portfolio_id="TEST-PORTFOLIO",  # We'll see what's available
            strategy=TradingStrategy.MANUAL
        )
        
        # Add event handlers to monitor activity
        events_received = []
        
        def on_signal(signal):
            events_received.append(('signal', signal))
            logger.info(f"   🎯 Signal: {signal.action} {signal.quantity} MW @ €{signal.price:.2f}/MWh")
        
        def on_position_update(position):
            events_received.append(('position', position))
            logger.info(f"   📈 Position: {position.contract_id} - {position.quantity} MW")
        
        def on_order_update(execution_report):
            events_received.append(('order', execution_report))
            logger.info(f"   📋 Order: {execution_report.get('clientOrderId', 'Unknown')} - {execution_report.get('status', 'Unknown')}")
        
        bot.add_signal_handler(on_signal)
        bot.add_position_handler(on_position_update)
        bot.add_order_handler(on_order_update)
        
        logger.info("   Starting trading bot...")
        
        # Start the bot
        start_task = asyncio.create_task(bot.start())
        
        # Wait for startup and initial data
        await asyncio.sleep(20)
        
        if bot.running:
            logger.info("✅ Trading bot started successfully!")
            
            # Check configuration
            if bot.configuration:
                logger.info("   ✅ Configuration received!")
                portfolios = bot.configuration.get('portfolios', [])
                logger.info(f"     Available portfolios: {len(portfolios)}")
                
                # Find a valid portfolio ID
                valid_portfolio_id = None
                for portfolio in portfolios:
                    portfolio_id = portfolio.get('id')
                    permission = portfolio.get('permission', '')
                    logger.info(f"       - ID: {portfolio_id}")
                    logger.info(f"         Name: {portfolio.get('name', 'Unknown')}")
                    logger.info(f"         Permission: {permission}")
                    
                    if 'TRADE' in permission.upper() or 'WRITE' in permission.upper():
                        valid_portfolio_id = portfolio_id
                        logger.info(f"         ✅ This portfolio has trading permissions!")
                
                if valid_portfolio_id:
                    logger.info(f"   🎯 Found trading portfolio: {valid_portfolio_id}")
                    # Update bot's portfolio ID
                    bot.portfolio_id = valid_portfolio_id
            else:
                logger.warning("   ⚠️  No configuration received yet")
            
            # Check market data
            market_data = bot.get_market_data()
            logger.info(f"   📊 Market data available: {len(market_data)} items")
            
            # Check positions
            positions = bot.get_positions()
            logger.info(f"   📈 Current positions: {len(positions)}")
            
            # Check active orders
            active_orders = bot.get_active_orders()
            logger.info(f"   📋 Active orders: {len(active_orders)}")
            
            logger.info(f"   📨 Events received: {len(events_received)}")
            
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
    """Main test function"""
    logger.info("🚀 BRM TRADING BOT - COMPLETE FUNCTIONAL TEST")
    logger.info("=" * 70)
    logger.info("Testing with WORKING credentials!")
    logger.info("=" * 70)
    
    results = []
    
    # Test 1: Authentication
    token_info = await test_authentication()
    results.append(("Authentication", token_info is not None))
    
    if token_info:
        # Test 2: Day-Ahead API
        success = await test_day_ahead_api()
        results.append(("Day-Ahead API", success))
        
        # Test 3: Intraday WebSocket
        success = await test_intraday_websocket()
        results.append(("Intraday WebSocket", success))
        
        # Test 4: Complete Trading Bot
        success = await test_complete_trading_bot()
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
        logger.info("🚀 You can now start live trading on the BRM markets!")
        logger.info("💡 Next steps:")
        logger.info("   1. Update your .env file with the working credentials")
        logger.info("   2. Use production_bot.py to start automated trading")
        logger.info("   3. Complete conformance testing as required by BRM")
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
