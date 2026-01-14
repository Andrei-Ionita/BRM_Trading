"""
Production-ready BRM Trading Bot
Ready to use with real credentials from BRM operator
"""
import asyncio
import logging
import os
from datetime import datetime
from typing import Dict, Any

from auth_updated import initialize_auth_password, initialize_auth_basic, create_basic_auth_header
from trading_bot import BRMTradingBot, TradingStrategy
from config import config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('brm_trading_bot.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


class ProductionBRMBot:
    """Production wrapper for the BRM Trading Bot"""
    
    def __init__(self):
        self.bot: BRMTradingBot = None
        self.running = False
    
    def initialize_from_env(self) -> bool:
        """Initialize bot from environment variables"""
        try:
            # Get credentials from environment
            auth_method = os.getenv("BRM_AUTH_METHOD", "password")  # "password" or "basic"
            username = os.getenv("BRM_USERNAME")
            password = os.getenv("BRM_PASSWORD")
            portfolio_id = os.getenv("BRM_PORTFOLIO_ID")
            strategy = os.getenv("BRM_STRATEGY", "manual")
            
            if not username or not password or not portfolio_id:
                logger.error("Missing required environment variables:")
                logger.error("  BRM_USERNAME, BRM_PASSWORD, BRM_PORTFOLIO_ID")
                return False
            
            # Initialize authentication
            if auth_method == "basic":
                # For basic auth, create the header from username:password
                basic_header = create_basic_auth_header(username, password)
                initialize_auth_basic(basic_header)
            else:
                # Default to password grant
                scope = os.getenv("BRM_SCOPE", "intraday_api")
                initialize_auth_password(username, password, scope)
            
            # Map strategy string to enum
            strategy_map = {
                "manual": TradingStrategy.MANUAL,
                "arbitrage": TradingStrategy.SIMPLE_ARBITRAGE,
                "mean_reversion": TradingStrategy.MEAN_REVERSION,
                "momentum": TradingStrategy.MOMENTUM
            }
            
            strategy_enum = strategy_map.get(strategy.lower(), TradingStrategy.MANUAL)
            
            # Initialize the bot
            self.bot = BRMTradingBot(
                client_id="",  # Not used with our auth method
                client_secret="",  # Not used with our auth method
                username=username,
                portfolio_id=portfolio_id,
                strategy=strategy_enum
            )
            
            # Add event handlers
            self.setup_event_handlers()
            
            logger.info(f"✅ Bot initialized successfully")
            logger.info(f"   Username: {username}")
            logger.info(f"   Portfolio: {portfolio_id}")
            logger.info(f"   Strategy: {strategy}")
            logger.info(f"   Environment: {config.environment}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize bot: {e}")
            return False
    
    def setup_event_handlers(self):
        """Setup event handlers for the bot"""
        
        def on_signal(signal):
            logger.info(f"🎯 SIGNAL: {signal.action} {signal.quantity} MW of {signal.contract_id}")
            logger.info(f"   Price: €{signal.price:.2f}/MWh | Confidence: {signal.confidence:.1%}")
            logger.info(f"   Strategy: {signal.strategy.value}")
        
        def on_position_update(position):
            logger.info(f"📈 POSITION: {position.contract_id}")
            logger.info(f"   Quantity: {position.quantity} MW")
            logger.info(f"   Avg Price: €{position.average_price:.2f}/MWh")
            logger.info(f"   Market: {position.market}")
            
            # Log P&L if we have market data
            # This is where you'd calculate unrealized P&L
        
        def on_order_update(execution_report):
            client_order_id = execution_report.get('clientOrderId', 'Unknown')
            status = execution_report.get('status', 'Unknown')
            
            logger.info(f"📋 ORDER: {client_order_id} - {status}")
            
            if execution_report.get('executedQuantity'):
                executed_qty = execution_report['executedQuantity']
                exec_price = execution_report.get('executionPrice', 0)
                logger.info(f"   Executed: {executed_qty} MW @ €{exec_price:.2f}/MWh")
            
            if execution_report.get('remainingQuantity'):
                remaining = execution_report['remainingQuantity']
                logger.info(f"   Remaining: {remaining} MW")
        
        # Register handlers
        self.bot.add_signal_handler(on_signal)
        self.bot.add_position_handler(on_position_update)
        self.bot.add_order_handler(on_order_update)
    
    async def start(self):
        """Start the production bot"""
        if not self.bot:
            logger.error("Bot not initialized. Call initialize_from_env() first.")
            return False
        
        try:
            logger.info("🚀 Starting BRM Trading Bot...")
            
            # Start the bot
            await self.bot.start()
            self.running = True
            
            logger.info("✅ Bot started successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start bot: {e}")
            return False
    
    async def stop(self):
        """Stop the production bot"""
        if self.bot and self.running:
            logger.info("🛑 Stopping BRM Trading Bot...")
            await self.bot.stop()
            self.running = False
            logger.info("✅ Bot stopped")
    
    async def run_forever(self):
        """Run the bot until interrupted"""
        if not await self.start():
            return
        
        try:
            logger.info("🤖 Bot running... Press Ctrl+C to stop")
            
            # Keep running until interrupted
            while self.running:
                await asyncio.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("👋 Shutdown requested by user")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
        finally:
            await self.stop()
    
    def enable_auto_trading(self):
        """Enable automatic trading"""
        if self.bot:
            self.bot.enable_auto_trading()
            logger.info("🤖 Auto trading enabled")
    
    def disable_auto_trading(self):
        """Disable automatic trading"""
        if self.bot:
            self.bot.disable_auto_trading()
            logger.info("✋ Auto trading disabled")
    
    async def place_manual_order(
        self, 
        contract_id: str, 
        side: str, 
        quantity: int, 
        price: float
    ) -> str:
        """Place a manual order"""
        if not self.bot:
            raise ValueError("Bot not initialized")
        
        logger.info(f"📝 Placing manual order: {side} {quantity} MW of {contract_id} @ €{price:.2f}/MWh")
        
        order_id = await self.bot.place_intraday_limit_order(
            contract_id=contract_id,
            side=side,
            quantity=quantity,
            price=price
        )
        
        logger.info(f"✅ Order placed with ID: {order_id}")
        return order_id
    
    def get_status(self) -> Dict[str, Any]:
        """Get current bot status"""
        if not self.bot:
            return {"status": "not_initialized"}
        
        positions = self.bot.get_positions()
        active_orders = self.bot.get_active_orders()
        market_data = self.bot.get_market_data()
        
        return {
            "status": "running" if self.running else "stopped",
            "auto_trading": self.bot.auto_trading_enabled,
            "positions_count": len(positions),
            "active_orders_count": len(active_orders),
            "market_data_available": bool(market_data),
            "last_update": datetime.now().isoformat()
        }


async def main():
    """Main function for production bot"""
    print("🏛️  BRM Trading Bot - Production Version")
    print("=" * 50)
    
    # Load environment variables from .env file if available
    try:
        from dotenv import load_dotenv
        load_dotenv()
        logger.info("📄 Loaded environment variables from .env file")
    except ImportError:
        logger.info("📄 Using system environment variables")
    
    # Initialize and run the bot
    bot = ProductionBRMBot()
    
    if not bot.initialize_from_env():
        logger.error("❌ Failed to initialize bot. Check your environment variables.")
        return
    
    # Check if auto trading should be enabled
    auto_trading = os.getenv("BRM_AUTO_TRADING", "false").lower() == "true"
    if auto_trading:
        bot.enable_auto_trading()
    
    # Run the bot
    await bot.run_forever()


if __name__ == "__main__":
    asyncio.run(main())
