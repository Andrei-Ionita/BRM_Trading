"""
Real-time BRM Public Market Data Viewer
Connects to public WebSocket endpoints to show live market data
"""
import asyncio
import logging
import json
import aiohttp
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


class BRMPublicMarketViewer:
    """Real-time viewer for BRM public market data"""
    
    def __init__(self):
        """Initialize the market viewer"""
        self.auth = initialize_working_auth()
        self.websocket = None
        self.session = None
        self.running = False
        
        # Market data storage
        self.contracts = {}
        self.delivery_areas = {}
        self.ticker_data = []
        self.local_views = defaultdict(dict)
        
        # Statistics
        self.message_count = 0
        self.last_update = None
        
        logger.info("BRM Public Market Viewer initialized")
    
    async def connect_to_public_websocket(self):
        """Connect to the public market data WebSocket"""
        try:
            logger.info("🔐 Getting authentication token...")
            token_info = await self.auth.get_token_async()
            logger.info(f"✅ Token acquired, expires at {token_info.expires_at}")
            
            # Create aiohttp session
            self.session = aiohttp.ClientSession()
            
            # Try different WebSocket URLs for BRM
            websocket_urls = [
                "wss://intraday-pmd-api-ws-brm.test.nordpoolgroup.com/",
                "wss://intraday2-api.test.nordpoolgroup.com/websocket",
                "wss://api.nordpoolgroup.com/websocket",
            ]
            
            # Headers for authentication
            headers = {
                "Authorization": token_info.bearer_token,
                "User-Agent": "BRM-Trading-Bot/1.0"
            }
            
            # Try each WebSocket URL
            for ws_url in websocket_urls:
                try:
                    logger.info(f"🌐 Trying WebSocket: {ws_url}")
                    
                    # Create SSL context
                    ssl_context = ssl.create_default_context()
                    ssl_context.check_hostname = False
                    ssl_context.verify_mode = ssl.CERT_NONE
                    
                    # Connect to WebSocket
                    self.websocket = await self.session.ws_connect(
                        ws_url,
                        headers=headers,
                        ssl=ssl_context,
                        heartbeat=30,
                        timeout=aiohttp.ClientTimeout(total=10)
                    )
                    
                    logger.info(f"✅ Connected to {ws_url}")
                    return True
                    
                except Exception as e:
                    logger.info(f"   ❌ Failed: {e}")
                    continue
            
            logger.error("❌ Could not connect to any WebSocket URL")
            return False
            
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
        
        logger.debug(f"📤 Sending STOMP: {command}")
        await self.websocket.send_str(message)
    
    async def subscribe_to_public_data(self):
        """Subscribe to public market data streams"""
        try:
            logger.info("📊 Subscribing to public market data...")
            
            # Get username from token (we'll use a placeholder for now)
            username = "Test_IntradayAPI_ADREM"  # From our credentials
            version = "v1"
            
            # Subscribe to contracts
            await self.send_stomp_message("SUBSCRIBE", {
                "id": "contracts-sub",
                "destination": f"/user/{username}/{version}/conflated/contracts"
            })
            logger.info("   ✅ Subscribed to contracts")
            
            # Subscribe to delivery areas
            await self.send_stomp_message("SUBSCRIBE", {
                "id": "areas-sub",
                "destination": f"/user/{username}/{version}/conflated/deliveryAreas"
            })
            logger.info("   ✅ Subscribed to delivery areas")
            
            # Subscribe to ticker (public trades)
            await self.send_stomp_message("SUBSCRIBE", {
                "id": "ticker-sub",
                "destination": f"/user/{username}/{version}/conflated/ticker"
            })
            logger.info("   ✅ Subscribed to ticker")
            
            # Subscribe to public statistics
            await self.send_stomp_message("SUBSCRIBE", {
                "id": "stats-sub",
                "destination": f"/user/{username}/{version}/conflated/publicStatistics"
            })
            logger.info("   ✅ Subscribed to public statistics")
            
            # Subscribe to heartbeat
            await self.send_stomp_message("SUBSCRIBE", {
                "id": "heartbeat-sub",
                "destination": f"/user/{username}/{version}/heartbeatping"
            })
            logger.info("   ✅ Subscribed to heartbeat")
            
        except Exception as e:
            logger.error(f"❌ Failed to subscribe to public data: {e}")
    
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
    
    def process_contracts(self, data: List[Dict[str, Any]]):
        """Process contracts data"""
        try:
            if isinstance(data, list):
                self.contracts = {c.get('id'): c for c in data}
                logger.info(f"📋 Contracts updated: {len(data)} contracts")
                
                # Show some active contracts
                active_contracts = [c for c in data if c.get('state') == 'ACTIVE'][:5]
                for contract in active_contracts:
                    logger.info(f"   - {contract.get('id', 'Unknown')}: {contract.get('displayName', 'Unknown')}")
                    logger.info(f"     Delivery: {contract.get('deliveryStart', 'Unknown')} - {contract.get('deliveryEnd', 'Unknown')}")
                
        except Exception as e:
            logger.error(f"Error processing contracts: {e}")
    
    def process_delivery_areas(self, data: List[Dict[str, Any]]):
        """Process delivery areas data"""
        try:
            if isinstance(data, list):
                self.delivery_areas = {a.get('id'): a for a in data}
                logger.info(f"🌍 Delivery areas updated: {len(data)} areas")
                
                for area in data[:5]:  # Show first 5 areas
                    logger.info(f"   - {area.get('id', 'Unknown')}: {area.get('displayName', 'Unknown')}")
                
        except Exception as e:
            logger.error(f"Error processing delivery areas: {e}")
    
    def process_ticker(self, data: Dict[str, Any]):
        """Process ticker (public trades) data"""
        try:
            trade_id = data.get('tradeId', 'Unknown')
            trade_time = data.get('tradeTime', 'Unknown')
            state = data.get('state', 'Unknown')
            currency = data.get('currency', 'EUR')
            
            logger.info(f"💰 TRADE: {trade_id}")
            logger.info(f"   Time: {trade_time}")
            logger.info(f"   State: {state}")
            logger.info(f"   Currency: {currency}")
            
            # Process trade legs
            legs = data.get('legs', [])
            for leg in legs:
                side = leg.get('side', 'Unknown')
                price = leg.get('unitPrice', 0)
                quantity = leg.get('quantity', 0)
                contract_id = leg.get('contractId', 'Unknown')
                
                logger.info(f"   {side}: {quantity} MWh @ {price/100:.2f} {currency}/MWh")
                logger.info(f"   Contract: {contract_id}")
            
            # Store trade
            self.ticker_data.append(data)
            if len(self.ticker_data) > 100:  # Keep last 100 trades
                self.ticker_data = self.ticker_data[-100:]
                
        except Exception as e:
            logger.error(f"Error processing ticker: {e}")
    
    def process_public_statistics(self, data: Dict[str, Any]):
        """Process public statistics data"""
        try:
            logger.info(f"📊 PUBLIC STATISTICS:")
            
            # Show key statistics
            for key, value in data.items():
                if isinstance(value, (str, int, float)):
                    logger.info(f"   {key}: {value}")
                elif isinstance(value, dict):
                    logger.info(f"   {key}: {len(value)} items")
                elif isinstance(value, list):
                    logger.info(f"   {key}: {len(value)} items")
                
        except Exception as e:
            logger.error(f"Error processing public statistics: {e}")
    
    def process_heartbeat(self, data: Dict[str, Any]):
        """Process heartbeat data"""
        try:
            heartbeat = data.get('heartbeat', [])
            timestamp = data.get('timestamp', 0)
            
            logger.info(f"💓 Heartbeat: {len(heartbeat)} subscriptions active")
            logger.info(f"   Timestamp: {datetime.fromtimestamp(timestamp/1000)}")
            
            for topic_info in heartbeat[:3]:  # Show first 3 topics
                topic = topic_info.get('topic', 'Unknown')
                seq_no = topic_info.get('lastSequenceNumber', 0)
                logger.info(f"   {topic}: seq {seq_no}")
                
        except Exception as e:
            logger.error(f"Error processing heartbeat: {e}")
    
    async def message_handler(self):
        """Handle incoming WebSocket messages"""
        try:
            async for msg in self.websocket:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    self.message_count += 1
                    self.last_update = datetime.now()
                    
                    message = msg.data
                    
                    # Parse STOMP message
                    parsed = self.parse_stomp_message(message)
                    command = parsed.get('command', '')
                    body = parsed.get('body', '')
                    headers = parsed.get('headers', {})
                    
                    if command == 'CONNECTED':
                        logger.info("✅ STOMP connection established")
                        await self.subscribe_to_public_data()
                    
                    elif command == 'MESSAGE':
                        destination = headers.get('destination', '')
                        
                        if body:
                            try:
                                data = json.loads(body)
                                
                                if 'contracts' in destination:
                                    self.process_contracts(data)
                                elif 'deliveryAreas' in destination:
                                    self.process_delivery_areas(data)
                                elif 'ticker' in destination:
                                    self.process_ticker(data)
                                elif 'publicStatistics' in destination:
                                    self.process_public_statistics(data)
                                elif 'heartbeatping' in destination:
                                    self.process_heartbeat(data)
                                else:
                                    logger.info(f"📨 Message from {destination}: {body[:200]}...")
                                    
                            except json.JSONDecodeError:
                                logger.info(f"📨 Non-JSON message: {body[:200]}...")
                    
                    elif command == 'ERROR':
                        logger.error(f"❌ STOMP Error: {body}")
                    
                    # Show periodic statistics
                    if self.message_count % 10 == 0:
                        logger.info(f"📊 Statistics: {self.message_count} messages, {len(self.ticker_data)} trades")
                        
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    logger.error(f"❌ WebSocket error: {self.websocket.exception()}")
                    break
                    
                elif msg.type == aiohttp.WSMsgType.CLOSE:
                    logger.warning("⚠️ WebSocket connection closed")
                    break
                    
        except Exception as e:
            logger.error(f"❌ Error in message handler: {e}")
    
    async def start_viewing(self, duration_minutes: int = 5):
        """Start viewing real-time market data"""
        try:
            logger.info("🚀 Starting BRM Real-time Public Market Viewer")
            logger.info("=" * 60)
            
            # Connect to WebSocket
            if not await self.connect_to_public_websocket():
                # If WebSocket fails, try REST API approach
                logger.info("🔄 WebSocket failed, trying REST API approach...")
                await self.try_rest_api_approach()
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
    
    async def try_rest_api_approach(self):
        """Try to get market data via REST API"""
        try:
            logger.info("🔍 Trying REST API approach for market data...")
            
            headers = await self.auth.get_auth_headers_async()
            
            # Try different REST endpoints
            rest_endpoints = [
                "https://data-api.nordpoolgroup.com/api/Auction",
                "https://data-api.nordpoolgroup.com/api/PriceCurves",
                "https://api.nordpoolgroup.com/api/marketdata",
                "https://intraday2-api.test.nordpoolgroup.com/api/v1/marketdata",
            ]
            
            async with aiohttp.ClientSession() as session:
                for endpoint in rest_endpoints:
                    try:
                        logger.info(f"🔍 Trying: {endpoint}")
                        
                        async with session.get(
                            endpoint, 
                            headers=headers, 
                            timeout=aiohttp.ClientTimeout(total=10)
                        ) as response:
                            logger.info(f"   Status: {response.status}")
                            
                            if response.status == 200:
                                try:
                                    data = await response.json()
                                    logger.info(f"   ✅ Success! Got {type(data).__name__} data")
                                    
                                    if isinstance(data, list):
                                        logger.info(f"   📊 {len(data)} items")
                                        # Show sample data
                                        for i, item in enumerate(data[:3]):
                                            logger.info(f"   Item {i+1}: {item}")
                                    elif isinstance(data, dict):
                                        logger.info(f"   📊 {len(data)} fields")
                                        for key, value in list(data.items())[:5]:
                                            logger.info(f"   {key}: {value}")
                                    
                                    return data
                                    
                                except:
                                    text = await response.text()
                                    logger.info(f"   📄 Text response: {text[:200]}...")
                                    return text
                            else:
                                text = await response.text()
                                logger.info(f"   ❌ Error: {text[:200]}...")
                                
                    except Exception as e:
                        logger.info(f"   ❌ Failed: {e}")
            
            logger.info("⚠️ No working REST endpoints found")
            
        except Exception as e:
            logger.error(f"❌ REST API approach failed: {e}")
    
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
        
        if self.session:
            await self.session.close()
        
        # Show final statistics
        logger.info("📊 Final Statistics:")
        logger.info(f"   Messages received: {self.message_count}")
        logger.info(f"   Contracts: {len(self.contracts)}")
        logger.info(f"   Delivery areas: {len(self.delivery_areas)}")
        logger.info(f"   Trades seen: {len(self.ticker_data)}")
        logger.info(f"   Last update: {self.last_update}")


async def main():
    """Main function"""
    logger.info("🇷🇴 BRM REAL-TIME PUBLIC MARKET VIEWER")
    logger.info("=" * 60)
    logger.info("Connecting to live Romanian energy market data...")
    logger.info("=" * 60)
    
    viewer = BRMPublicMarketViewer()
    
    try:
        # View market for 3 minutes
        await viewer.start_viewing(duration_minutes=3)
        
    except Exception as e:
        logger.error(f"❌ Viewer failed: {e}")
    
    logger.info("🎬 Real-time market viewing session ended")
    logger.info("🇷🇴 Romanian energy market data exploration complete! ⚡")


if __name__ == "__main__":
    # Set test environment
    os.environ["BRM_ENVIRONMENT"] = "test"
    
    # Run the viewer
    asyncio.run(main())
