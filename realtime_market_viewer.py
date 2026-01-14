"""
Real-time BRM Intraday Market Viewer
Shows live market data, prices, volumes, and trading activity
"""
import asyncio
import logging
import json
import websockets
import ssl
from datetime import datetime
from typing import Dict, Any, List
from collections import defaultdict
import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from auth_working import initialize_working_auth

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


class BRMMarketViewer:
    """Real-time viewer for BRM Intraday market data"""
    
    def __init__(self):
        """Initialize the market viewer"""
        self.auth = initialize_working_auth()
        self.websocket = None
        self.running = False
        
        # Market data storage
        self.contracts = {}
        self.order_book = defaultdict(lambda: {'bids': [], 'asks': []})
        self.trades = []
        self.portfolios = []
        
        # Statistics
        self.message_count = 0
        self.last_update = None
        
        logger.info("BRM Market Viewer initialized")
    
    async def connect(self):
        """Connect to BRM Intraday WebSocket"""
        try:
            logger.info("🔐 Getting authentication token...")
            token_info = await self.auth.get_token_async()
            logger.info(f"✅ Token acquired, expires at {token_info.expires_at}")
            
            # WebSocket URL for BRM test environment
            ws_url = "wss://intraday-pmd-api-ws-brm.test.nordpoolgroup.com/"
            
            logger.info(f"🌐 Connecting to BRM WebSocket: {ws_url}")
            
            # Create SSL context
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            # Connect with authentication
            extra_headers = {
                "Authorization": token_info.bearer_token,
                "User-Agent": "BRM-Trading-Bot/1.0"
            }
            
            self.websocket = await websockets.connect(
                ws_url,
                ssl=ssl_context,
                extra_headers=extra_headers,
                ping_interval=30,
                ping_timeout=10
            )
            
            logger.info("✅ WebSocket connected successfully!")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to connect to WebSocket: {e}")
            return False
    
    async def send_stomp_message(self, command: str, headers: Dict[str, str] = None, body: str = ""):
        """Send a STOMP protocol message"""
        if not self.websocket:
            raise Exception("WebSocket not connected")
        
        headers = headers or {}
        
        # Build STOMP message
        message_lines = [command]
        
        for key, value in headers.items():
            message_lines.append(f"{key}:{value}")
        
        message_lines.append("")  # Empty line before body
        message_lines.append(body)
        message_lines.append("\x00")  # STOMP null terminator
        
        message = "\n".join(message_lines)
        
        logger.debug(f"Sending STOMP message: {command}")
        await self.websocket.send(message)
    
    async def subscribe_to_market_data(self):
        """Subscribe to all available market data streams"""
        try:
            logger.info("📊 Subscribing to market data streams...")
            
            # Subscribe to configuration (portfolios, contracts, etc.)
            await self.send_stomp_message("SUBSCRIBE", {
                "id": "config-sub",
                "destination": "/user/queue/configuration"
            })
            logger.info("   ✅ Subscribed to configuration")
            
            # Subscribe to market data (prices, volumes)
            await self.send_stomp_message("SUBSCRIBE", {
                "id": "market-sub", 
                "destination": "/topic/marketdata"
            })
            logger.info("   ✅ Subscribed to market data")
            
            # Subscribe to order book updates
            await self.send_stomp_message("SUBSCRIBE", {
                "id": "orderbook-sub",
                "destination": "/topic/orderbook"
            })
            logger.info("   ✅ Subscribed to order book")
            
            # Subscribe to trade executions
            await self.send_stomp_message("SUBSCRIBE", {
                "id": "trades-sub",
                "destination": "/topic/trades"
            })
            logger.info("   ✅ Subscribed to trades")
            
            # Subscribe to system messages
            await self.send_stomp_message("SUBSCRIBE", {
                "id": "system-sub",
                "destination": "/topic/system"
            })
            logger.info("   ✅ Subscribed to system messages")
            
        except Exception as e:
            logger.error(f"❌ Failed to subscribe to market data: {e}")
    
    def parse_stomp_message(self, message: str) -> Dict[str, Any]:
        """Parse a STOMP protocol message"""
        lines = message.split('\n')
        if not lines:
            return {}
        
        command = lines[0]
        headers = {}
        body_start = 1
        
        # Parse headers
        for i, line in enumerate(lines[1:], 1):
            if line == "":
                body_start = i + 1
                break
            if ":" in line:
                key, value = line.split(":", 1)
                headers[key] = value
        
        # Parse body
        body_lines = lines[body_start:]
        body = "\n".join(body_lines).rstrip('\x00')
        
        return {
            "command": command,
            "headers": headers,
            "body": body
        }
    
    def process_configuration(self, data: Dict[str, Any]):
        """Process configuration data"""
        try:
            if isinstance(data, dict):
                # Store portfolios
                portfolios = data.get('portfolios', [])
                self.portfolios = portfolios
                
                logger.info(f"📋 Configuration received:")
                logger.info(f"   Portfolios: {len(portfolios)}")
                
                for portfolio in portfolios[:3]:  # Show first 3
                    logger.info(f"     - {portfolio.get('id', 'Unknown')}: {portfolio.get('name', 'Unknown')}")
                    logger.info(f"       Permission: {portfolio.get('permission', 'Unknown')}")
                
                # Store contracts
                contracts = data.get('contracts', [])
                if contracts:
                    self.contracts = {c.get('id'): c for c in contracts}
                    logger.info(f"   Contracts: {len(contracts)}")
                    
                    # Show some active contracts
                    active_contracts = [c for c in contracts if c.get('status') == 'ACTIVE'][:5]
                    for contract in active_contracts:
                        logger.info(f"     - {contract.get('id', 'Unknown')}: {contract.get('deliveryStart', 'Unknown')}")
                
        except Exception as e:
            logger.error(f"Error processing configuration: {e}")
    
    def process_market_data(self, data: Dict[str, Any]):
        """Process market data updates"""
        try:
            contract_id = data.get('contractId', 'Unknown')
            bid_price = data.get('bidPrice')
            ask_price = data.get('askPrice')
            last_price = data.get('lastPrice')
            volume = data.get('volume', 0)
            
            logger.info(f"📊 Market Data - {contract_id}:")
            if bid_price is not None:
                logger.info(f"   Bid: €{bid_price:.2f}/MWh")
            if ask_price is not None:
                logger.info(f"   Ask: €{ask_price:.2f}/MWh")
            if last_price is not None:
                logger.info(f"   Last: €{last_price:.2f}/MWh")
            if volume > 0:
                logger.info(f"   Volume: {volume} MWh")
                
        except Exception as e:
            logger.error(f"Error processing market data: {e}")
    
    def process_order_book(self, data: Dict[str, Any]):
        """Process order book updates"""
        try:
            contract_id = data.get('contractId', 'Unknown')
            side = data.get('side', 'Unknown')
            price = data.get('price', 0)
            quantity = data.get('quantity', 0)
            
            logger.info(f"📖 Order Book - {contract_id}:")
            logger.info(f"   {side}: {quantity} MWh @ €{price:.2f}/MWh")
            
            # Update internal order book
            if side.upper() == 'BUY':
                self.order_book[contract_id]['bids'].append({'price': price, 'quantity': quantity})
            elif side.upper() == 'SELL':
                self.order_book[contract_id]['asks'].append({'price': price, 'quantity': quantity})
                
        except Exception as e:
            logger.error(f"Error processing order book: {e}")
    
    def process_trade(self, data: Dict[str, Any]):
        """Process trade executions"""
        try:
            contract_id = data.get('contractId', 'Unknown')
            price = data.get('price', 0)
            quantity = data.get('quantity', 0)
            timestamp = data.get('timestamp', datetime.now().isoformat())
            
            logger.info(f"💰 TRADE EXECUTED - {contract_id}:")
            logger.info(f"   Price: €{price:.2f}/MWh")
            logger.info(f"   Quantity: {quantity} MWh")
            logger.info(f"   Time: {timestamp}")
            
            # Store trade
            self.trades.append({
                'contractId': contract_id,
                'price': price,
                'quantity': quantity,
                'timestamp': timestamp
            })
            
            # Keep only last 100 trades
            if len(self.trades) > 100:
                self.trades = self.trades[-100:]
                
        except Exception as e:
            logger.error(f"Error processing trade: {e}")
    
    async def message_handler(self):
        """Handle incoming WebSocket messages"""
        try:
            async for message in self.websocket:
                self.message_count += 1
                self.last_update = datetime.now()
                
                # Parse STOMP message
                parsed = self.parse_stomp_message(message)
                command = parsed.get('command', '')
                body = parsed.get('body', '')
                
                if command == 'CONNECTED':
                    logger.info("✅ STOMP connection established")
                    await self.subscribe_to_market_data()
                
                elif command == 'MESSAGE':
                    destination = parsed.get('headers', {}).get('destination', '')
                    
                    if body:
                        try:
                            data = json.loads(body)
                            
                            if 'configuration' in destination:
                                self.process_configuration(data)
                            elif 'marketdata' in destination:
                                self.process_market_data(data)
                            elif 'orderbook' in destination:
                                self.process_order_book(data)
                            elif 'trades' in destination:
                                self.process_trade(data)
                            else:
                                logger.info(f"📨 Message from {destination}: {body[:200]}...")
                                
                        except json.JSONDecodeError:
                            logger.info(f"📨 Non-JSON message: {body[:200]}...")
                
                elif command == 'ERROR':
                    logger.error(f"❌ STOMP Error: {body}")
                
                # Show periodic statistics
                if self.message_count % 10 == 0:
                    logger.info(f"📊 Statistics: {self.message_count} messages received, last update: {self.last_update}")
                    
        except websockets.exceptions.ConnectionClosed:
            logger.warning("⚠️ WebSocket connection closed")
        except Exception as e:
            logger.error(f"❌ Error in message handler: {e}")
    
    async def start_viewing(self, duration_minutes: int = 10):
        """Start viewing real-time market data"""
        try:
            logger.info("🚀 Starting BRM Real-time Market Viewer")
            logger.info("=" * 60)
            
            # Connect to WebSocket
            if not await self.connect():
                return
            
            # Send STOMP CONNECT
            await self.send_stomp_message("CONNECT", {
                "accept-version": "1.0,1.1,1.2",
                "heart-beat": "10000,10000"
            })
            
            self.running = True
            
            # Start message handler
            handler_task = asyncio.create_task(self.message_handler())
            
            # Run for specified duration
            logger.info(f"📺 Viewing market data for {duration_minutes} minutes...")
            logger.info("   Press Ctrl+C to stop early")
            
            try:
                await asyncio.wait_for(handler_task, timeout=duration_minutes * 60)
            except asyncio.TimeoutError:
                logger.info(f"⏰ Viewing session completed ({duration_minutes} minutes)")
            
        except KeyboardInterrupt:
            logger.info("⏹️ Stopped by user")
        except Exception as e:
            logger.error(f"❌ Error during viewing: {e}")
        finally:
            await self.stop()
    
    async def stop(self):
        """Stop the market viewer"""
        logger.info("🛑 Stopping market viewer...")
        self.running = False
        
        if self.websocket:
            try:
                await self.send_stomp_message("DISCONNECT")
                await self.websocket.close()
            except:
                pass
        
        # Show final statistics
        logger.info("📊 Final Statistics:")
        logger.info(f"   Messages received: {self.message_count}")
        logger.info(f"   Portfolios: {len(self.portfolios)}")
        logger.info(f"   Contracts: {len(self.contracts)}")
        logger.info(f"   Trades seen: {len(self.trades)}")
        logger.info(f"   Last update: {self.last_update}")
        
        if self.trades:
            logger.info("💰 Recent Trades:")
            for trade in self.trades[-5:]:  # Show last 5 trades
                logger.info(f"   {trade['contractId']}: {trade['quantity']} MWh @ €{trade['price']:.2f}/MWh")


async def main():
    """Main function"""
    logger.info("🇷🇴 BRM REAL-TIME INTRADAY MARKET VIEWER")
    logger.info("=" * 60)
    logger.info("Connecting to live Romanian energy market data...")
    logger.info("=" * 60)
    
    viewer = BRMMarketViewer()
    
    try:
        # View market for 5 minutes (you can change this)
        await viewer.start_viewing(duration_minutes=5)
        
    except Exception as e:
        logger.error(f"❌ Viewer failed: {e}")
    
    logger.info("🎬 Market viewing session ended")


if __name__ == "__main__":
    # Set test environment
    os.environ["BRM_ENVIRONMENT"] = "test"
    
    # Run the viewer
    asyncio.run(main())
