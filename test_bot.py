"""
Test script for BRM Trading Bot
Demonstrates how to use the trading bot and test its functionality
"""
import asyncio
import logging
import os
from datetime import datetime, timedelta

from trading_bot import BRMTradingBot, TradingStrategy, TradingSignal, TradingPosition
from config import config


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


class TestTradingBot:
    """Test harness for the BRM Trading Bot"""
    
    def __init__(self):
        self.bot: BRMTradingBot = None
        self.test_results = []
    
    async def run_tests(self):
        """Run all tests"""
        logger.info("Starting BRM Trading Bot Tests")
        
        # Test 1: Authentication
        await self.test_authentication()
        
        # Test 2: Day-Ahead API
        await self.test_day_ahead_api()
        
        # Test 3: Intraday WebSocket Connection
        await self.test_intraday_connection()
        
        # Test 4: Manual Order Placement
        await self.test_manual_orders()
        
        # Test 5: Auto Trading (if enabled)
        await self.test_auto_trading()
        
        # Print test results
        self.print_test_results()
    
    async def test_authentication(self):
        """Test authentication functionality"""
        logger.info("Testing authentication...")
        
        try:
            # Use environment variables or default test values
            client_id = os.getenv("BRM_CLIENT_ID", "test_client_id")
            client_secret = os.getenv("BRM_CLIENT_SECRET", "test_client_secret")
            username = os.getenv("BRM_USERNAME", "test_user")
            portfolio_id = os.getenv("BRM_PORTFOLIO_ID", "TEST-001")
            
            if client_id == "test_client_id":
                logger.warning("Using default test credentials - set BRM_CLIENT_ID and BRM_CLIENT_SECRET environment variables for real testing")
            
            # Initialize the bot
            self.bot = BRMTradingBot(
                client_id=client_id,
                client_secret=client_secret,
                username=username,
                portfolio_id=portfolio_id,
                strategy=TradingStrategy.MANUAL
            )
            
            # Test token acquisition
            from auth import get_authenticator
            auth = get_authenticator()
            
            try:
                token_info = await auth.get_token_async()
                logger.info(f"Authentication successful - Token expires at: {token_info.expires_at}")
                self.test_results.append(("Authentication", "PASS", "Token acquired successfully"))
            except Exception as e:
                logger.error(f"Authentication failed: {e}")
                self.test_results.append(("Authentication", "FAIL", str(e)))
                return False
            
        except Exception as e:
            logger.error(f"Authentication test failed: {e}")
            self.test_results.append(("Authentication", "FAIL", str(e)))
            return False
        
        return True
    
    async def test_day_ahead_api(self):
        """Test Day-Ahead API functionality"""
        logger.info("Testing Day-Ahead API...")
        
        if not self.bot:
            self.test_results.append(("Day-Ahead API", "SKIP", "Bot not initialized"))
            return
        
        try:
            # Test getting auctions
            auctions = await self.bot.day_ahead_client.get_auctions()
            logger.info(f"Retrieved {len(auctions)} auctions")
            self.test_results.append(("Day-Ahead API - Get Auctions", "PASS", f"Retrieved {len(auctions)} auctions"))
            
            # Test getting system state
            state = await self.bot.day_ahead_client.get_system_state()
            logger.info(f"System state retrieved: {state}")
            self.test_results.append(("Day-Ahead API - System State", "PASS", "State retrieved successfully"))
            
            # If there are auctions, test getting auction details
            if auctions:
                auction_id = auctions[0].get("id")
                if auction_id:
                    auction_details = await self.bot.day_ahead_client.get_auction(auction_id)
                    logger.info(f"Auction details retrieved for {auction_id}")
                    self.test_results.append(("Day-Ahead API - Auction Details", "PASS", f"Details for auction {auction_id}"))
            
        except Exception as e:
            logger.error(f"Day-Ahead API test failed: {e}")
            self.test_results.append(("Day-Ahead API", "FAIL", str(e)))
    
    async def test_intraday_connection(self):
        """Test Intraday WebSocket connection"""
        logger.info("Testing Intraday WebSocket connection...")
        
        if not self.bot:
            self.test_results.append(("Intraday Connection", "SKIP", "Bot not initialized"))
            return
        
        try:
            # Test WebSocket connection
            connected = await self.bot.intraday_client.connect()
            
            if connected:
                logger.info("Intraday WebSocket connected successfully")
                self.test_results.append(("Intraday Connection", "PASS", "WebSocket connected"))
                
                # Wait a bit for configuration to be received
                await asyncio.sleep(2)
                
                if self.bot.configuration:
                    logger.info("Configuration received")
                    self.test_results.append(("Intraday Configuration", "PASS", "Configuration received"))
                else:
                    logger.warning("No configuration received")
                    self.test_results.append(("Intraday Configuration", "WARN", "No configuration received"))
                
            else:
                logger.error("Failed to connect to Intraday WebSocket")
                self.test_results.append(("Intraday Connection", "FAIL", "WebSocket connection failed"))
                
        except Exception as e:
            logger.error(f"Intraday connection test failed: {e}")
            self.test_results.append(("Intraday Connection", "FAIL", str(e)))
    
    async def test_manual_orders(self):
        """Test manual order placement (simulation)"""
        logger.info("Testing manual order placement...")
        
        if not self.bot or not self.bot.intraday_client.connected:
            self.test_results.append(("Manual Orders", "SKIP", "Bot not connected"))
            return
        
        try:
            # This is a simulation - we won't actually place real orders in test
            logger.info("Simulating manual order placement...")
            
            # Test order creation (without sending)
            from intraday_client import IntradayOrder, OrderType, TimeInForce, ExecutionRestriction
            
            test_order = IntradayOrder(
                portfolio_id=self.bot.portfolio_id,
                contract_ids=["TEST_CONTRACT"],
                delivery_area_id=1,
                side="BUY",
                order_type=OrderType.LIMIT,
                unit_price=5000,  # 50 EUR/MWh in cents
                quantity=100,  # 100 kW
                time_in_force=TimeInForce.GFS,
                execution_restriction=ExecutionRestriction.NON,
                text="Test order"
            )
            
            # Validate order structure
            order_dict = test_order.to_dict()
            required_fields = ["portfolioId", "contractIds", "deliveryAreaId", "side", "orderType", "unitPrice", "quantity"]
            
            for field in required_fields:
                if field not in order_dict:
                    raise ValueError(f"Missing required field: {field}")
            
            logger.info("Order structure validation passed")
            self.test_results.append(("Manual Orders - Validation", "PASS", "Order structure valid"))
            
            # Note: In a real test with valid credentials, you would uncomment the following:
            # request_id = await self.bot.place_intraday_limit_order(
            #     contract_id="TEST_CONTRACT",
            #     side="BUY",
            #     quantity=100,
            #     price=50.0
            # )
            # logger.info(f"Order placed with request ID: {request_id}")
            
        except Exception as e:
            logger.error(f"Manual order test failed: {e}")
            self.test_results.append(("Manual Orders", "FAIL", str(e)))
    
    async def test_auto_trading(self):
        """Test auto trading functionality"""
        logger.info("Testing auto trading...")
        
        if not self.bot:
            self.test_results.append(("Auto Trading", "SKIP", "Bot not initialized"))
            return
        
        try:
            # Test signal generation
            from trading_bot import TradingSignal, TradingStrategy
            
            test_signal = TradingSignal(
                action="BUY",
                contract_id="TEST_CONTRACT",
                area_id=1,
                quantity=100,
                price=50.0,
                confidence=0.8,
                strategy=TradingStrategy.MANUAL
            )
            
            # Test signal handler
            signals_received = []
            
            def signal_handler(signal):
                signals_received.append(signal)
                logger.info(f"Signal received: {signal.action} {signal.quantity} @ {signal.price}")
            
            self.bot.add_signal_handler(signal_handler)
            
            # Simulate signal execution (without actually trading)
            await self.bot._execute_signal(test_signal)
            
            if signals_received:
                logger.info("Signal handling test passed")
                self.test_results.append(("Auto Trading - Signals", "PASS", "Signal handling works"))
            else:
                logger.warning("No signals received")
                self.test_results.append(("Auto Trading - Signals", "WARN", "No signals received"))
            
        except Exception as e:
            logger.error(f"Auto trading test failed: {e}")
            self.test_results.append(("Auto Trading", "FAIL", str(e)))
    
    def print_test_results(self):
        """Print test results summary"""
        logger.info("\n" + "="*60)
        logger.info("BRM TRADING BOT TEST RESULTS")
        logger.info("="*60)
        
        passed = 0
        failed = 0
        warnings = 0
        skipped = 0
        
        for test_name, result, details in self.test_results:
            status_symbol = {
                "PASS": "✓",
                "FAIL": "✗",
                "WARN": "⚠",
                "SKIP": "○"
            }.get(result, "?")
            
            logger.info(f"{status_symbol} {test_name}: {result} - {details}")
            
            if result == "PASS":
                passed += 1
            elif result == "FAIL":
                failed += 1
            elif result == "WARN":
                warnings += 1
            elif result == "SKIP":
                skipped += 1
        
        logger.info("-"*60)
        logger.info(f"Total: {len(self.test_results)} | Passed: {passed} | Failed: {failed} | Warnings: {warnings} | Skipped: {skipped}")
        logger.info("="*60)
        
        if failed == 0:
            logger.info("🎉 All tests passed successfully!")
        else:
            logger.warning(f"⚠️  {failed} test(s) failed. Check the logs above for details.")
    
    async def cleanup(self):
        """Cleanup after tests"""
        if self.bot:
            await self.bot.stop()


async def main():
    """Main test function"""
    test_harness = TestTradingBot()
    
    try:
        await test_harness.run_tests()
    finally:
        await test_harness.cleanup()


if __name__ == "__main__":
    # Set test environment
    os.environ.setdefault("BRM_ENVIRONMENT", "test")
    
    # Run tests
    asyncio.run(main())
