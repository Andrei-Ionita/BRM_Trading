"""
Example usage of the BRM Trading Bot
This script shows how to use the trading bot in practice
"""
import asyncio
import logging
import os
from datetime import datetime

from trading_bot import BRMTradingBot, TradingStrategy


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def example_manual_trading():
    """Example of manual trading operations"""
    
    # Initialize the bot with your credentials
    bot = BRMTradingBot(
        client_id=os.getenv("BRM_CLIENT_ID", "your_client_id"),
        client_secret=os.getenv("BRM_CLIENT_SECRET", "your_client_secret"),
        username=os.getenv("BRM_USERNAME", "your_username"),
        portfolio_id=os.getenv("BRM_PORTFOLIO_ID", "your_portfolio_id"),
        strategy=TradingStrategy.MANUAL
    )
    
    try:
        # Start the bot (this connects to APIs and WebSocket)
        await bot.start()
        
        # Wait for configuration to be received
        await asyncio.sleep(2)
        
        # Example 1: Place a Day-Ahead block order
        logger.info("Placing Day-Ahead block order...")
        
        block_order_result = await bot.place_day_ahead_block_order(
            name="Example Block Order",
            price=55.0,  # EUR/MWh
            periods=[
                {
                    "contractId": "NPIDA_1-20241101-08",  # 8-9 AM
                    "volume": 100  # MW
                },
                {
                    "contractId": "NPIDA_1-20241101-09",  # 9-10 AM
                    "volume": 100  # MW
                }
            ],
            minimum_acceptance_ratio=1.0  # Must be 100% filled
        )
        
        logger.info(f"Block order result: {block_order_result}")
        
        # Example 2: Place an Intraday limit order
        logger.info("Placing Intraday limit order...")
        
        order_id = await bot.place_intraday_limit_order(
            contract_id="NX_7650",  # Example contract
            side="BUY",
            quantity=50,  # MW
            price=45.0,   # EUR/MWh
            area_id=1     # Romania area
        )
        
        logger.info(f"Intraday order placed with ID: {order_id}")
        
        # Example 3: Monitor positions and orders
        logger.info("Current positions:")
        positions = bot.get_positions()
        for position_key, position in positions.items():
            logger.info(f"  {position.contract_id}: {position.quantity} MW @ €{position.average_price:.2f}/MWh")
        
        logger.info("Active orders:")
        active_orders = bot.get_active_orders()
        for order_id, order_info in active_orders.items():
            order = order_info["order"]
            logger.info(f"  {order_id}: {order.side} {order.quantity} MW @ €{order.unit_price/100:.2f}/MWh")
        
        # Keep the bot running for a while to receive updates
        logger.info("Bot running... Press Ctrl+C to stop")
        await asyncio.sleep(60)  # Run for 1 minute
        
    except KeyboardInterrupt:
        logger.info("Stopping bot...")
    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        await bot.stop()


async def example_auto_trading():
    """Example of automated trading with custom handlers"""
    
    bot = BRMTradingBot(
        client_id=os.getenv("BRM_CLIENT_ID", "your_client_id"),
        client_secret=os.getenv("BRM_CLIENT_SECRET", "your_client_secret"),
        username=os.getenv("BRM_USERNAME", "your_username"),
        portfolio_id=os.getenv("BRM_PORTFOLIO_ID", "your_portfolio_id"),
        strategy=TradingStrategy.SIMPLE_ARBITRAGE
    )
    
    # Add custom event handlers
    def on_signal(signal):
        logger.info(f"🎯 Trading Signal: {signal.action} {signal.quantity} MW of {signal.contract_id} @ €{signal.price:.2f}/MWh")
        logger.info(f"   Strategy: {signal.strategy.value}, Confidence: {signal.confidence:.2%}")
    
    def on_position_update(position):
        logger.info(f"📈 Position Update: {position.contract_id}")
        logger.info(f"   Quantity: {position.quantity} MW")
        logger.info(f"   Avg Price: €{position.average_price:.2f}/MWh")
        logger.info(f"   Market: {position.market}")
    
    def on_order_update(execution_report):
        logger.info(f"📋 Order Update: {execution_report.get('clientOrderId')}")
        logger.info(f"   Status: {execution_report.get('status')}")
        if execution_report.get('executedQuantity'):
            logger.info(f"   Executed: {execution_report['executedQuantity']} MW @ €{execution_report.get('executionPrice', 0):.2f}/MWh")
    
    # Register handlers
    bot.add_signal_handler(on_signal)
    bot.add_position_handler(on_position_update)
    bot.add_order_handler(on_order_update)
    
    try:
        # Start the bot
        await bot.start()
        
        # Enable auto trading
        bot.enable_auto_trading()
        logger.info("🤖 Auto trading enabled")
        
        # Let it run for a while
        logger.info("Bot running in auto mode... Press Ctrl+C to stop")
        await asyncio.sleep(300)  # Run for 5 minutes
        
    except KeyboardInterrupt:
        logger.info("Stopping bot...")
    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        bot.disable_auto_trading()
        await bot.stop()


async def example_market_monitoring():
    """Example of using the bot just for market monitoring"""
    
    bot = BRMTradingBot(
        client_id=os.getenv("BRM_CLIENT_ID", "your_client_id"),
        client_secret=os.getenv("BRM_CLIENT_SECRET", "your_client_secret"),
        username=os.getenv("BRM_USERNAME", "your_username"),
        portfolio_id=os.getenv("BRM_PORTFOLIO_ID", "your_portfolio_id"),
        strategy=TradingStrategy.MANUAL
    )
    
    try:
        await bot.start()
        
        # Monitor market data
        for i in range(10):  # Check 10 times
            market_data = bot.get_market_data()
            
            logger.info(f"📊 Market Data Update #{i+1}")
            
            if "day_ahead_auctions" in market_data:
                auctions = market_data["day_ahead_auctions"]
                logger.info(f"   Day-Ahead: {len(auctions)} active auctions")
            
            if "local_view" in market_data:
                local_view = market_data["local_view"]
                logger.info(f"   Intraday: Local view data available")
            
            if "system_state" in market_data:
                state = market_data["system_state"]
                logger.info(f"   System State: {state}")
            
            await asyncio.sleep(30)  # Check every 30 seconds
        
    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        await bot.stop()


async def main():
    """Main function to run examples"""
    
    print("BRM Trading Bot Examples")
    print("=" * 40)
    print("1. Manual Trading")
    print("2. Auto Trading")
    print("3. Market Monitoring")
    print("=" * 40)
    
    # For this demo, we'll run the manual trading example
    # In practice, you would choose based on your needs
    
    choice = input("Enter your choice (1-3): ").strip()
    
    if choice == "1":
        logger.info("Running manual trading example...")
        await example_manual_trading()
    elif choice == "2":
        logger.info("Running auto trading example...")
        await example_auto_trading()
    elif choice == "3":
        logger.info("Running market monitoring example...")
        await example_market_monitoring()
    else:
        logger.error("Invalid choice. Please run the script again.")


if __name__ == "__main__":
    # Load environment variables from .env file if it exists
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        logger.warning("python-dotenv not installed. Using environment variables directly.")
    
    # Check if credentials are set
    if not os.getenv("BRM_CLIENT_ID") or os.getenv("BRM_CLIENT_ID") == "your_client_id":
        logger.warning("⚠️  BRM credentials not set!")
        logger.warning("   Set BRM_CLIENT_ID, BRM_CLIENT_SECRET, BRM_USERNAME, and BRM_PORTFOLIO_ID")
        logger.warning("   environment variables or create a .env file")
        logger.warning("   For now, the examples will use placeholder values and may fail")
    
    asyncio.run(main())
