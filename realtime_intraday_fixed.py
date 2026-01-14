"""
Real-time BRM Intraday Market Viewer - Fixed Version
Uses compatible WebSocket implementation
"""
import asyncio
import logging
import json
import sys
import os
from datetime import datetime
import aiohttp
import ssl

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from auth_working import initialize_working_auth

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class IntradayMarketViewer:
    """Real-time viewer for BRM Intraday market data"""
    
    def __init__(self):
        self.auth = initialize_working_auth()
        self.session = None
        self.ws = None
        self.username = "Test_IntradayAPI_ADREM"  # From our working credentials
        self.version = "v1"
        
        # BRM/Romanian area IDs (we'll try to discover these)
        self.romanian_areas = [
            "RO",  # Romania
            "BRM", # BRM specific
            "1",   # Numeric ID
            "10",  # Alternative numeric ID
            "47",  # Romania area code
        ]
        
        # WebSocket URLs from the email
        self.websocket_urls = [
            "wss://intraday-pmd-api-ws-brm.test.nordpoolgroup.com",
            "wss://intraday2-api.test.nordpoolgroup.com",
        ]
    
    async def connect_and_stream(self):
        """Connect to WebSocket and stream real-time market data"""
        
        logger.info("🚀 Starting BRM Intraday Market Viewer")
        logger.info("=" * 60)
        
        try:
            # Get authentication token
            token_info = await self.auth.get_token_async()
            logger.info(f"✅ Authentication successful, token expires at {token_info.expires_at}")
            
            access_token = token_info.access_token
            
            # Create aiohttp session
            connector = aiohttp.TCPConnector(ssl=ssl.create_default_context())
            self.session = aiohttp.ClientSession(connector=connector)
            
            # Try different WebSocket URLs
            for ws_url in self.websocket_urls:
                logger.info(f"🔗 Attempting connection to: {ws_url}")
                
                try:
                    # Create headers for WebSocket connection
                    headers = {
                        "Authorization": f"Bearer {access_token}",
                        "User-Agent": "BRM-Trading-Bot/1.0",
                        "Sec-WebSocket-Protocol": "stomp"
                    }
                    
                    # Connect to WebSocket
                    self.ws = await self.session.ws_connect(
                        ws_url,
                        headers=headers,
                        heartbeat=30
                    )
                    
                    logger.info(f"✅ Connected to {ws_url}")
                    
                    # Send STOMP CONNECT frame
                    await self.send_stomp_connect(access_token)
                    
                    # Subscribe to market data
                    await self.subscribe_to_market_data()
                    
                    # Listen for messages
                    await self.listen_for_messages()
                    
                    break  # If successful, don't try other URLs
                    
                except aiohttp.ClientError as e:
                    logger.warning(f"⚠️ Client error for {ws_url}: {e}")
                except Exception as e:
                    logger.warning(f"⚠️ Failed to connect to {ws_url}: {e}")
                
                logger.info("")
            
            else:
                logger.error("❌ Failed to connect to any WebSocket endpoint")
                
                # Try alternative approach - check if endpoints are accessible via HTTP
                await self.test_http_endpoints(access_token)
            
        except Exception as e:
            logger.error(f"❌ Market viewer failed: {e}")
        
        finally:
            if self.session:
                await self.session.close()
    
    async def test_http_endpoints(self, access_token):
        """Test HTTP endpoints as fallback"""
        
        logger.info("🔍 Testing HTTP endpoints as fallback...")
        
        # Test the intraday API base URLs
        http_urls = [
            "https://intraday2-api.test.nordpoolgroup.com",
            "https://intraday2-api.nordpoolgroup.com",
        ]
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "User-Agent": "BRM-Trading-Bot/1.0"
        }
        
        for base_url in http_urls:
            logger.info(f"🌐 Testing HTTP endpoint: {base_url}")
            
            # Test various endpoints
            endpoints = [
                "/",
                "/api",
                "/health",
                "/status",
            ]
            
            for endpoint in endpoints:
                try:
                    url = f"{base_url}{endpoint}"
                    async with self.session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as response:
                        logger.info(f"   📍 {endpoint}: Status {response.status}")
                        
                        if response.status == 200:
                            try:
                                data = await response.json()
                                logger.info(f"      ✅ Got JSON response: {type(data).__name__}")
                            except:
                                text = await response.text()
                                logger.info(f"      📄 Got text: {text[:100]}...")
                        elif response.status == 401:
                            logger.info(f"      🔐 Unauthorized - token might not be valid for this endpoint")
                        elif response.status == 403:
                            logger.info(f"      ⚠️ Forbidden - need different permissions")
                        elif response.status == 404:
                            logger.info(f"      ❌ Not Found")
                        
                except Exception as e:
                    logger.info(f"   ❌ {endpoint}: {e}")
            
            logger.info("")
    
    async def send_stomp_connect(self, access_token):
        """Send STOMP CONNECT frame"""
        
        connect_frame = f"""CONNECT
accept-version:1.0,1.1,1.2
heart-beat:10000,10000
Authorization:Bearer {access_token}
host:nordpoolgroup.com

\x00"""
        
        logger.info("📤 Sending STOMP CONNECT frame")
        await self.ws.send_str(connect_frame)
        
        # Wait for CONNECTED response
        msg = await self.ws.receive()
        if msg.type == aiohttp.WSMsgType.TEXT:
            response = msg.data
            logger.info(f"📥 STOMP Response: {response[:200]}...")
            
            if "CONNECTED" in response:
                logger.info("✅ STOMP connection established")
                return True
            else:
                logger.warning("⚠️ Unexpected STOMP response")
                return False
        else:
            logger.warning(f"⚠️ Unexpected message type: {msg.type}")
            return False
    
    async def subscribe_to_market_data(self):
        """Subscribe to various market data topics"""
        
        logger.info("📊 Subscribing to market data topics...")
        
        # Topics to subscribe to
        topics = [
            # Delivery areas (to discover Romanian area IDs)
            f"/user/{self.username}/{self.version}/deliveryAreas",
            
            # Contracts (to see available contracts)
            f"/user/{self.username}/{self.version}/contracts",
            
            # Ticker (general market data)
            f"/user/{self.username}/{self.version}/conflated/ticker",
            
            # Heartbeat ping
            f"/user/{self.username}/{self.version}/heartbeatping",
        ]
        
        # Try to subscribe to local views for different Romanian areas
        for area in self.romanian_areas:
            topics.append(f"/user/{self.username}/{self.version}/streaming/localview/{area}")
        
        subscription_id = 1
        
        for topic in topics:
            subscribe_frame = f"""SUBSCRIBE
id:sub-{subscription_id}
destination:{topic}

\x00"""
            
            logger.info(f"📤 Subscribing to: {topic}")
            await self.ws.send_str(subscribe_frame)
            subscription_id += 1
            
            # Small delay between subscriptions
            await asyncio.sleep(0.1)
        
        logger.info(f"✅ Sent {len(topics)} subscription requests")
    
    async def listen_for_messages(self):
        """Listen for incoming WebSocket messages"""
        
        logger.info("👂 Listening for real-time market data...")
        logger.info("=" * 60)
        
        message_count = 0
        
        try:
            async for msg in self.ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    message_count += 1
                    await self.process_message(msg.data, message_count)
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    logger.error(f"❌ WebSocket error: {self.ws.exception()}")
                    break
                elif msg.type == aiohttp.WSMsgType.CLOSE:
                    logger.info("🔌 WebSocket connection closed")
                    break
                    
        except Exception as e:
            logger.error(f"❌ Error listening for messages: {e}")
    
    async def process_message(self, message, count):
        """Process incoming STOMP messages"""
        
        try:
            # Parse STOMP frame
            lines = message.split('\n')
            command = lines[0] if lines else ""
            
            # Extract headers
            headers = {}
            body_start = 1
            for i, line in enumerate(lines[1:], 1):
                if line == "":
                    body_start = i + 1
                    break
                if ":" in line:
                    key, value = line.split(":", 1)
                    headers[key] = value
            
            # Extract body
            body = '\n'.join(lines[body_start:]).rstrip('\x00')
            
            # Log message info
            destination = headers.get("destination", "Unknown")
            timestamp = datetime.now().strftime("%H:%M:%S")
            
            logger.info(f"📨 [{count}] {timestamp} - {command}")
            logger.info(f"   📍 Topic: {destination}")
            
            if body and body.strip():
                try:
                    # Try to parse JSON body
                    data = json.loads(body)
                    await self.process_market_data(destination, data)
                except json.JSONDecodeError:
                    logger.info(f"   📄 Body: {body[:200]}...")
            
            # Show headers for important messages
            if command in ["CONNECTED", "ERROR"] or "localview" in destination:
                for key, value in headers.items():
                    logger.info(f"   🏷️ {key}: {value}")
            
            logger.info("")
            
        except Exception as e:
            logger.error(f"❌ Error processing message: {e}")
    
    async def process_market_data(self, topic, data):
        """Process specific market data types"""
        
        try:
            if "deliveryAreas" in topic:
                await self.process_delivery_areas(data)
            elif "contracts" in topic:
                await self.process_contracts(data)
            elif "localview" in topic:
                await self.process_local_view(data)
            elif "ticker" in topic:
                await self.process_ticker(data)
            elif "heartbeatping" in topic:
                await self.process_heartbeat(data)
            else:
                logger.info(f"   📊 Data type: {type(data).__name__}")
                if isinstance(data, dict):
                    logger.info(f"   📊 Fields: {list(data.keys())[:5]}")
                elif isinstance(data, list):
                    logger.info(f"   📊 Items: {len(data)}")
        
        except Exception as e:
            logger.error(f"❌ Error processing market data: {e}")
    
    async def process_delivery_areas(self, data):
        """Process delivery areas data"""
        if isinstance(data, list):
            logger.info(f"   🌍 Found {len(data)} delivery areas:")
            romanian_areas = []
            for area in data:
                area_id = area.get('id', 'Unknown')
                name = area.get('name', 'Unknown')
                if 'romania' in name.lower() or 'ro' in str(area_id).lower() or 'brm' in name.lower():
                    romanian_areas.append(f"{area_id}: {name}")
                    logger.info(f"      🇷🇴 ROMANIAN AREA: {area_id}: {name}")
            
            if not romanian_areas:
                # Show first few areas
                for area in data[:5]:
                    area_id = area.get('id', 'Unknown')
                    name = area.get('name', 'Unknown')
                    logger.info(f"      📍 {area_id}: {name}")
                if len(data) > 5:
                    logger.info(f"      ... and {len(data) - 5} more areas")
    
    async def process_contracts(self, data):
        """Process contracts data"""
        if isinstance(data, list):
            logger.info(f"   📋 Found {len(data)} contracts:")
            for contract in data[:3]:  # Show first 3
                contract_id = contract.get('contractId', 'Unknown')
                delivery_start = contract.get('deliveryStart', 'Unknown')
                delivery_end = contract.get('deliveryEnd', 'Unknown')
                logger.info(f"      📄 {contract_id}: {delivery_start} - {delivery_end}")
            if len(data) > 3:
                logger.info(f"      ... and {len(data) - 3} more contracts")
    
    async def process_local_view(self, data):
        """Process local view (order book) data"""
        if isinstance(data, list):
            logger.info(f"   📈 🇷🇴 LIVE ROMANIAN ORDER BOOK - {len(data)} contracts:")
            
            for contract in data[:2]:  # Show first 2 contracts
                contract_id = contract.get('contractId', 'Unknown')
                buy_orders = contract.get('buyOrders', [])
                sell_orders = contract.get('sellOrders', [])
                
                logger.info(f"      🎯 Contract: {contract_id}")
                logger.info(f"         💰 Buy Orders: {len(buy_orders)}")
                logger.info(f"         💸 Sell Orders: {len(sell_orders)}")
                
                # Show best buy orders
                if buy_orders:
                    best_buy = buy_orders[0]
                    price = best_buy.get('price', 0)
                    qty = best_buy.get('qty', 0)
                    logger.info(f"         🟢 Best Buy: {price} RON/MWh @ {qty} MWh")
                
                # Show best sell orders
                if sell_orders:
                    best_sell = sell_orders[0]
                    price = best_sell.get('price', 0)
                    qty = best_sell.get('qty', 0)
                    logger.info(f"         🔴 Best Sell: {price} RON/MWh @ {qty} MWh")
            
            if len(data) > 2:
                logger.info(f"      ... and {len(data) - 2} more contracts")
        else:
            logger.info(f"   📈 🇷🇴 LIVE ROMANIAN MARKET DATA:")
            logger.info(f"      📊 Data type: {type(data).__name__}")
    
    async def process_ticker(self, data):
        """Process ticker data"""
        if isinstance(data, dict):
            logger.info(f"   📊 🇷🇴 ROMANIAN MARKET TICKER:")
            for key, value in list(data.items())[:5]:
                logger.info(f"      📈 {key}: {value}")
    
    async def process_heartbeat(self, data):
        """Process heartbeat data"""
        if isinstance(data, dict):
            heartbeat = data.get('heartbeat', [])
            timestamp = data.get('timestamp', 'Unknown')
            logger.info(f"   💓 Heartbeat: {len(heartbeat)} topics active at {timestamp}")


async def main():
    """Main function to run the market viewer"""
    
    # Set test environment
    os.environ["BRM_ENVIRONMENT"] = "test"
    
    viewer = IntradayMarketViewer()
    
    try:
        await viewer.connect_and_stream()
    except KeyboardInterrupt:
        logger.info("👋 Market viewer stopped by user")
    except Exception as e:
        logger.error(f"❌ Market viewer failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())
