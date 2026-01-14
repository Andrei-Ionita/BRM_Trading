"""
Demo script for BRM Trading Bot
Demonstrates the bot's functionality without requiring real API credentials
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


class MockBRMTradingBot:
    """Mock version of the trading bot for demonstration purposes"""
    
    def __init__(self, username: str, portfolio_id: str):
        self.username = username
        self.portfolio_id = portfolio_id
        self.positions = {}
        self.active_orders = {}
        self.market_data = {}
        self.running = False
        self.auto_trading_enabled = False
        
        # Event handlers
        self.signal_handlers = []
        self.position_handlers = []
        self.order_handlers = []
        
        logger.info(f"Initialized mock trading bot for user: {username}")
    
    async def start(self):
        """Start the mock trading bot"""
        logger.info("🚀 Starting BRM Trading Bot Demo")
        self.running = True
        
        # Simulate successful connection
        await asyncio.sleep(1)
        logger.info("✅ Connected to Day-Ahead API")
        
        await asyncio.sleep(0.5)
        logger.info("✅ Connected to Intraday WebSocket")
        
        # Simulate receiving configuration
        await self._simulate_configuration()
        
        # Simulate market data updates
        await self._simulate_market_data()
        
        # Demonstrate order placement
        await self._demonstrate_orders()
        
        # Demonstrate position management
        await self._demonstrate_positions()
        
        logger.info("🎯 Demo completed successfully!")
    
    async def _simulate_configuration(self):
        """Simulate receiving configuration from the API"""
        logger.info("📋 Receiving configuration...")
        
        config = {
            "portfolios": [
                {
                    "id": self.portfolio_id,
                    "name": "Demo Portfolio",
                    "shortName": "DEMO",
                    "companyId": "DEMO001",
                    "permission": "WRITE",
                    "validFrom": "2024-01-01T00:00:00.000Z",
                    "validTo": "2024-12-31T23:59:59.999Z",
                    "deleted": False,
                    "state": "ACTI",
                    "currency": "EUR",
                    "areas": [
                        {
                            "areaId": 1,
                            "validFrom": "2024-01-01T00:00:00.000Z",
                            "validTo": "2024-12-31T23:59:59.999Z"
                        }
                    ],
                    "markets": [
                        {"marketId": "N_1"},  # Nord Pool Continuous
                        {"marketId": "N_2"}   # XBID Continuous
                    ]
                }
            ],
            "throttlingLimit": [10, 100],
            "companyUsers": {
                "demo-user-uuid": self.username
            }
        }
        
        logger.info(f"✅ Configuration received - Portfolio: {config['portfolios'][0]['name']}")
        logger.info(f"   Areas: {len(config['portfolios'][0]['areas'])}")
        logger.info(f"   Markets: {len(config['portfolios'][0]['markets'])}")
    
    async def _simulate_market_data(self):
        """Simulate receiving market data"""
        logger.info("📊 Receiving market data...")
        
        # Simulate Day-Ahead auction data
        auctions = [
            {
                "id": "DA_2024_11_01",
                "name": "Day-Ahead Auction 2024-11-01",
                "closeBiddingTime": "2024-10-31T12:00:00Z",
                "deliveryDate": "2024-11-01",
                "state": "OPEN"
            }
        ]
        
        logger.info(f"📈 Day-Ahead: {len(auctions)} active auctions")
        
        # Simulate Intraday market data
        market_data = {
            "contracts": [
                {
                    "contractId": "NX_7650",
                    "deliveryStart": "2024-11-01T07:00:00Z",
                    "deliveryEnd": "2024-11-01T08:00:00Z",
                    "lastPrice": 45.50,
                    "bidPrice": 45.00,
                    "askPrice": 46.00,
                    "volume": 1250
                },
                {
                    "contractId": "NX_7651",
                    "deliveryStart": "2024-11-01T08:00:00Z",
                    "deliveryEnd": "2024-11-01T09:00:00Z",
                    "lastPrice": 48.75,
                    "bidPrice": 48.25,
                    "askPrice": 49.25,
                    "volume": 980
                }
            ]
        }
        
        logger.info(f"⚡ Intraday: {len(market_data['contracts'])} active contracts")
        for contract in market_data['contracts']:
            logger.info(f"   {contract['contractId']}: €{contract['lastPrice']}/MWh (Vol: {contract['volume']} MW)")
    
    async def _demonstrate_orders(self):
        """Demonstrate order placement"""
        logger.info("📝 Demonstrating order placement...")
        
        # Day-Ahead Block Order
        logger.info("🔲 Placing Day-Ahead block order...")
        await asyncio.sleep(0.5)
        
        block_order = {
            "orderId": "BLOCK_001",
            "name": "Morning Peak Block",
            "price": 55.0,
            "periods": [
                {"contractId": "NPIDA_1-20241101-07", "volume": 200},
                {"contractId": "NPIDA_1-20241101-08", "volume": 200},
                {"contractId": "NPIDA_1-20241101-09", "volume": 200}
            ],
            "status": "SUBMITTED"
        }
        
        logger.info(f"✅ Block order placed: {block_order['name']} @ €{block_order['price']}/MWh")
        logger.info(f"   Total volume: {sum(p['volume'] for p in block_order['periods'])} MW")
        
        # Intraday Limit Order
        logger.info("⚡ Placing Intraday limit order...")
        await asyncio.sleep(0.5)
        
        limit_order = {
            "orderId": "LIMIT_001",
            "clientOrderId": "demo-order-001",
            "contractId": "NX_7650",
            "side": "BUY",
            "quantity": 100,
            "price": 45.0,
            "timeInForce": "GFS",
            "status": "ACTIVE"
        }
        
        self.active_orders[limit_order['clientOrderId']] = limit_order
        
        logger.info(f"✅ Limit order placed: {limit_order['side']} {limit_order['quantity']} MW @ €{limit_order['price']}/MWh")
        logger.info(f"   Contract: {limit_order['contractId']}")
        
        # Simulate order execution
        await asyncio.sleep(1)
        await self._simulate_order_execution(limit_order)
    
    async def _simulate_order_execution(self, order: Dict[str, Any]):
        """Simulate order execution"""
        logger.info("🎯 Order execution simulation...")
        
        # Simulate partial fill
        executed_quantity = order['quantity'] // 2
        remaining_quantity = order['quantity'] - executed_quantity
        execution_price = order['price'] + 0.25  # Slight price improvement
        
        execution_report = {
            "orderId": order['orderId'],
            "clientOrderId": order['clientOrderId'],
            "executedQuantity": executed_quantity,
            "remainingQuantity": remaining_quantity,
            "executionPrice": execution_price,
            "timestamp": datetime.now().isoformat(),
            "status": "PARTIALLY_FILLED" if remaining_quantity > 0 else "FILLED"
        }
        
        logger.info(f"📊 Order execution: {executed_quantity} MW @ €{execution_price}/MWh")
        logger.info(f"   Remaining: {remaining_quantity} MW")
        
        # Update position
        await self._update_position(order['contractId'], executed_quantity, execution_price, order['side'])
        
        # Notify handlers
        for handler in self.order_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(execution_report)
                else:
                    handler(execution_report)
            except Exception as e:
                logger.error(f"Error in order handler: {e}")
    
    async def _update_position(self, contract_id: str, quantity: int, price: float, side: str):
        """Update position based on execution"""
        if side == "SELL":
            quantity = -quantity
        
        if contract_id in self.positions:
            position = self.positions[contract_id]
            total_quantity = position['quantity'] + quantity
            
            if total_quantity != 0:
                # Calculate new average price
                total_value = (position['quantity'] * position['averagePrice']) + (quantity * price)
                position['averagePrice'] = total_value / total_quantity
                position['quantity'] = total_quantity
            else:
                # Position closed
                del self.positions[contract_id]
                logger.info(f"🔄 Position closed: {contract_id}")
                return
        else:
            # New position
            self.positions[contract_id] = {
                'contractId': contract_id,
                'quantity': quantity,
                'averagePrice': price,
                'timestamp': datetime.now().isoformat()
            }
        
        position = self.positions[contract_id]
        logger.info(f"📈 Position updated: {contract_id}")
        logger.info(f"   Quantity: {position['quantity']} MW")
        logger.info(f"   Avg Price: €{position['averagePrice']:.2f}/MWh")
        
        # Notify handlers
        for handler in self.position_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(position)
                else:
                    handler(position)
            except Exception as e:
                logger.error(f"Error in position handler: {e}")
    
    async def _demonstrate_positions(self):
        """Demonstrate position management"""
        logger.info("💼 Position management demonstration...")
        
        if self.positions:
            total_exposure = 0
            for contract_id, position in self.positions.items():
                exposure = abs(position['quantity'] * position['averagePrice'])
                total_exposure += exposure
                
                logger.info(f"📊 {contract_id}: {position['quantity']} MW @ €{position['averagePrice']:.2f}/MWh")
                logger.info(f"   Exposure: €{exposure:.2f}")
            
            logger.info(f"💰 Total exposure: €{total_exposure:.2f}")
        else:
            logger.info("📊 No open positions")
    
    def add_signal_handler(self, handler):
        """Add signal handler"""
        self.signal_handlers.append(handler)
    
    def add_position_handler(self, handler):
        """Add position handler"""
        self.position_handlers.append(handler)
    
    def add_order_handler(self, handler):
        """Add order handler"""
        self.order_handlers.append(handler)


async def demo_with_handlers():
    """Demonstrate the bot with custom event handlers"""
    logger.info("🎭 Starting demo with custom handlers...")
    
    bot = MockBRMTradingBot("demo_user", "DEMO-001")
    
    # Add custom handlers
    def signal_handler(signal):
        logger.info(f"🎯 Signal Handler: {signal}")
    
    def position_handler(position):
        logger.info(f"📈 Position Handler: Updated {position['contractId']}")
    
    def order_handler(execution_report):
        logger.info(f"📋 Order Handler: Execution report for {execution_report['clientOrderId']}")
    
    bot.add_signal_handler(signal_handler)
    bot.add_position_handler(position_handler)
    bot.add_order_handler(order_handler)
    
    await bot.start()


async def main():
    """Main demo function"""
    print("=" * 80)
    print("🏛️  BRM TRADING BOT DEMONSTRATION")
    print("=" * 80)
    print()
    print("This demo shows how the BRM Trading Bot works without requiring")
    print("real API credentials. It simulates all the key functionality:")
    print()
    print("• Authentication and connection to BRM APIs")
    print("• Day-Ahead and Intraday market data")
    print("• Order placement and execution")
    print("• Position management")
    print("• Event-driven architecture")
    print()
    print("=" * 80)
    print()
    
    await demo_with_handlers()
    
    print()
    print("=" * 80)
    print("✨ Demo completed! The trading bot is ready for real deployment.")
    print("   To use with real credentials:")
    print("   1. Set your BRM_CLIENT_ID and BRM_CLIENT_SECRET")
    print("   2. Configure your portfolio and username")
    print("   3. Run the actual trading bot")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
