"""
Live Intraday WebSocket Client Integration
Real-time intraday market data streaming for BRM trading system

Updated to use SockJS protocol:
- URL format: wss://host/user/{serverId}/{sessionId}/websocket
- Messages wrapped in JSON arrays
- Frames: 'o' (open), 'h' (heartbeat), 'a[...]' (message), 'c[...]' (close)
- Auth via X-AUTH-TOKEN header in STOMP CONNECT
"""

import asyncio
import websockets
import json
import logging
import time
import threading
import random
import string
import ssl
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass
import uuid

from intraday_auth import IntradayAuthenticator

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def generate_sockjs_server_id() -> str:
    """Generate random 3-digit server ID for SockJS"""
    return str(random.randint(0, 999)).zfill(3)


def generate_sockjs_session_id(length: int = 16) -> str:
    """Generate random session ID for SockJS"""
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

@dataclass
class IntradayContract:
    """Intraday contract data"""
    id: str
    name: str
    delivery_start: str
    delivery_end: str
    area_code: str
    status: str
    min_quantity: float = 0.1
    max_quantity: float = 9999.0

@dataclass
class IntradayTicker:
    """Real-time price ticker"""
    contract_id: str
    last_price: Optional[float] = None
    bid_price: Optional[float] = None
    ask_price: Optional[float] = None
    volume: float = 0.0
    timestamp: str = ""

@dataclass
class IntradayTrade:
    """Trade execution data"""
    id: str
    contract_id: str
    price: float
    quantity: float
    timestamp: str
    buyer_area: str
    seller_area: str

class LiveIntradayClient:
    """
    Live WebSocket client for BRM intraday market
    Provides real-time market data and trading capabilities
    Uses SockJS protocol for connection
    """

    def __init__(self):
        # Authentication
        self.auth = IntradayAuthenticator()
        self.access_token = None
        self.username = "Test_IntradayAPI_ADREM"

        # WebSocket base URL (without SockJS path)
        self.base_url = "wss://intraday-pmd-api-ws-brm.test.nordpoolgroup.com"

        # SockJS session identifiers
        self.server_id = ""
        self.session_id = ""

        # Connection state
        self.market_data_ws = None
        self.connected = False
        self.stomp_connected = False
        self.running = False

        # Data storage
        self.contracts: Dict[str, IntradayContract] = {}
        self.tickers: Dict[str, IntradayTicker] = {}
        self.trades: List[IntradayTrade] = []
        self.delivery_areas: List[Dict] = []
        self.order_book: Dict[str, Dict] = {}

        # Event callbacks
        self.on_contract_update: Optional[Callable] = None
        self.on_ticker_update: Optional[Callable] = None
        self.on_trade_update: Optional[Callable] = None
        self.on_delivery_areas_update: Optional[Callable] = None

        # Background thread
        self.thread: Optional[threading.Thread] = None
        self.loop: Optional[asyncio.AbstractEventLoop] = None

    def _build_sockjs_url(self) -> str:
        """Build SockJS WebSocket URL"""
        self.server_id = generate_sockjs_server_id()
        self.session_id = generate_sockjs_session_id()
        return f"{self.base_url}/user/{self.server_id}/{self.session_id}/websocket"

    def _wrap_stomp_for_sockjs(self, stomp_frame: str) -> str:
        """Wrap STOMP frame in SockJS JSON array format"""
        return json.dumps([stomp_frame])
        
    def start(self) -> bool:
        """Start the WebSocket client in background thread"""
        try:
            logger.info("🚀 Starting live intraday WebSocket client...")
            
            # Get authentication token
            self.access_token = self.auth.get_access_token()
            if not self.access_token:
                logger.error("❌ Failed to get intraday access token")
                return False
            
            logger.info("✅ Intraday authentication successful")
            
            # Start background thread
            self.running = True
            self.thread = threading.Thread(target=self._run_websocket_loop, daemon=True)
            self.thread.start()
            
            # Give it a moment to connect
            time.sleep(2)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error starting intraday client: {e}")
            return False
    
    def stop(self):
        """Stop the WebSocket client"""
        logger.info("🛑 Stopping intraday WebSocket client...")
        self.running = False
        
        if self.loop:
            # Schedule shutdown in the event loop
            asyncio.run_coroutine_threadsafe(self._shutdown(), self.loop)
        
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5)
    
    def _run_websocket_loop(self):
        """Run the WebSocket event loop in background thread"""
        try:
            # Create new event loop for this thread
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            
            # Run the WebSocket client
            self.loop.run_until_complete(self._websocket_main())
            
        except Exception as e:
            logger.error(f"❌ Error in WebSocket loop: {e}")
        finally:
            if self.loop:
                self.loop.close()
    
    async def _websocket_main(self):
        """Main WebSocket connection and message handling using SockJS protocol"""
        try:
            # Build SockJS URL
            ws_url = self._build_sockjs_url()
            logger.info(f"Connecting to SockJS: {ws_url}")

            # Create SSL context
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

            # Connect to market data WebSocket
            async with websockets.connect(
                ws_url,
                ssl=ssl_context,
                max_size=10 * 1024 * 1024,  # 10MB max message size
                ping_interval=20,
                ping_timeout=10
            ) as websocket:

                self.market_data_ws = websocket

                # Wait for SockJS open frame
                open_frame = await asyncio.wait_for(websocket.recv(), timeout=10)
                if open_frame != 'o':
                    logger.error(f"Expected SockJS open frame, got: {open_frame}")
                    return

                self.connected = True
                logger.info("SockJS connection established")

                # Send STOMP CONNECT frame
                await self._send_stomp_connect(websocket)

                # Wait for STOMP CONNECTED response
                response = await asyncio.wait_for(websocket.recv(), timeout=10)
                if self._parse_sockjs_stomp_response(response, "CONNECTED"):
                    self.stomp_connected = True
                    logger.info("STOMP handshake successful!")
                else:
                    logger.error(f"STOMP connect failed: {response[:200]}")
                    return

                # Subscribe to market data topics
                await self._subscribe_to_topics(websocket)

                # Message processing loop
                await self._message_loop(websocket)

        except asyncio.TimeoutError:
            logger.error("Connection timeout")
        except websockets.exceptions.ConnectionClosed:
            logger.info("WebSocket connection closed")
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
        finally:
            self.connected = False
            self.stomp_connected = False

    def _parse_sockjs_stomp_response(self, response: str, expected_command: str) -> bool:
        """Parse SockJS response and check for expected STOMP command"""
        if not response.startswith('a['):
            return False
        try:
            messages = json.loads(response[1:])
            for msg in messages:
                if expected_command in msg:
                    return True
        except:
            pass
        return False
    
    async def _send_stomp_connect(self, websocket):
        """Send STOMP CONNECT frame with X-AUTH-TOKEN wrapped in SockJS format"""
        try:
            # Build STOMP CONNECT frame with X-AUTH-TOKEN (not Authorization: Bearer)
            connect_frame = (
                "CONNECT\n"
                "accept-version:1.2\n"
                "host:intraday-pmd-api-ws-brm.test.nordpoolgroup.com\n"
                "heart-beat:10000,10000\n"
                f"X-AUTH-TOKEN:{self.access_token}\n"
                "\n"
                "\x00"
            )

            # Wrap in SockJS format
            sockjs_message = self._wrap_stomp_for_sockjs(connect_frame)
            await websocket.send(sockjs_message)
            logger.info("Sent STOMP CONNECT frame with X-AUTH-TOKEN")

        except Exception as e:
            logger.error(f"Error sending CONNECT frame: {e}")
    
    async def _subscribe_to_topics(self, websocket):
        """Subscribe to market data topics with correct paths and SockJS wrapping"""
        try:
            # Topic format: /user/{username}/v1/streaming/{topic}
            topics = [
                ("sub-delivery-areas", "deliveryAreas"),
                ("sub-contracts", "contracts"),
                ("sub-tickers", "localview"),
                ("sub-public-stats", "publicStatistics"),
            ]

            for sub_id, topic in topics:
                destination = f"/user/{self.username}/v1/streaming/{topic}"
                subscribe_frame = (
                    "SUBSCRIBE\n"
                    f"id:{sub_id}\n"
                    f"destination:{destination}\n"
                    "ack:auto\n"
                    "\n"
                    "\x00"
                )

                sockjs_message = self._wrap_stomp_for_sockjs(subscribe_frame)
                await websocket.send(sockjs_message)
                logger.info(f"Subscribed to {topic}")
                await asyncio.sleep(0.1)  # Small delay between subscriptions

        except Exception as e:
            logger.error(f"Error subscribing to topics: {e}")
    
    async def _message_loop(self, websocket):
        """Process incoming SockJS WebSocket messages"""
        try:
            while self.running:
                try:
                    # Wait for message with timeout
                    message = await asyncio.wait_for(websocket.recv(), timeout=30)

                    if isinstance(message, bytes):
                        message = message.decode('utf-8')

                    # Handle SockJS frame types
                    if message == 'h':
                        # SockJS heartbeat - respond with empty array
                        logger.debug("Received SockJS heartbeat")
                        continue

                    elif message.startswith('a['):
                        # SockJS message array - extract and process STOMP frames
                        await self._process_sockjs_message(message)

                    elif message.startswith('c['):
                        # SockJS close frame
                        try:
                            close_data = json.loads(message[1:])
                            logger.info(f"SockJS close: {close_data}")
                        except:
                            pass
                        break

                    elif message == 'o':
                        # SockJS open (should have been handled already)
                        logger.debug("Received SockJS open frame")

                    else:
                        logger.debug(f"Unknown frame type: {message[:50]}")

                except asyncio.TimeoutError:
                    # Send STOMP heartbeat (empty line wrapped in SockJS)
                    heartbeat = json.dumps(["\n"])
                    await websocket.send(heartbeat)
                    logger.debug("Sent STOMP heartbeat")

                except websockets.exceptions.ConnectionClosed:
                    logger.info("WebSocket connection closed")
                    break

        except Exception as e:
            logger.error(f"Error in message loop: {e}")

    async def _process_sockjs_message(self, sockjs_frame: str):
        """Extract and process STOMP messages from SockJS 'a[...]' frame"""
        try:
            # Parse the JSON array (skip the 'a' prefix)
            messages = json.loads(sockjs_frame[1:])

            for stomp_msg in messages:
                if isinstance(stomp_msg, str) and stomp_msg.strip():
                    await self._process_stomp_message(stomp_msg)

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse SockJS message: {e}")
        except Exception as e:
            logger.error(f"Error processing SockJS message: {e}")

    async def _process_stomp_message(self, message: str):
        """Process STOMP protocol message"""
        try:
            lines = message.strip().split('\n')
            if not lines:
                return
            
            command = lines[0]
            headers = {}
            body = ""
            
            # Parse headers
            body_start = 1
            for i, line in enumerate(lines[1:], 1):
                if line == '':
                    body_start = i + 1
                    break
                if ':' in line:
                    key, value = line.split(':', 1)
                    headers[key] = value
            
            # Parse body
            if body_start < len(lines):
                body = '\n'.join(lines[body_start:]).rstrip('\x00')
            
            # Handle different STOMP commands
            if command == "CONNECTED":
                logger.info("✅ STOMP connection established")
                
            elif command == "MESSAGE":
                await self._handle_stomp_message(headers, body)
                
            elif command == "ERROR":
                logger.error(f"❌ STOMP error: {body}")
                
            elif command == "RECEIPT":
                logger.debug(f"📨 STOMP receipt: {headers.get('receipt-id')}")
                
        except Exception as e:
            logger.error(f"❌ Error processing STOMP message: {e}")
    
    async def _handle_stomp_message(self, headers: Dict[str, str], body: str):
        """Handle STOMP MESSAGE frame"""
        try:
            destination = headers.get('destination', '')

            if not body:
                return

            # Try to parse JSON body
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                logger.warning(f"Non-JSON message body: {body[:100]}")
                return

            # Route message based on destination (using streaming topic paths)
            if 'deliveryAreas' in destination:
                await self._handle_delivery_areas_message(data)

            elif 'contracts' in destination:
                await self._handle_contracts_message(data)

            elif 'localview' in destination:
                await self._handle_ticker_message(data)

            elif 'publicStatistics' in destination:
                await self._handle_statistics_message(data)

            else:
                logger.debug(f"Received message from {destination}")

        except Exception as e:
            logger.error(f"Error handling STOMP message: {e}")

    async def _handle_delivery_areas_message(self, data):
        """Handle delivery areas update message"""
        try:
            # Data can be a list or dict with 'deliveryAreas' key
            if isinstance(data, list):
                self.delivery_areas = data
            elif isinstance(data, dict) and 'deliveryAreas' in data:
                self.delivery_areas = data['deliveryAreas']
            else:
                self.delivery_areas = [data] if data else []

            logger.info(f"Received {len(self.delivery_areas)} delivery areas")

            # Trigger callback
            if self.on_delivery_areas_update:
                self.on_delivery_areas_update(self.delivery_areas)

        except Exception as e:
            logger.error(f"Error handling delivery areas message: {e}")

    async def _handle_contracts_message(self, data):
        """Handle contracts update message"""
        try:
            # Data can be a list of contracts or a dict with 'contracts' key
            contracts_list = []
            if isinstance(data, list):
                contracts_list = data
            elif isinstance(data, dict) and 'contracts' in data:
                contracts_list = data['contracts']

            for contract_data in contracts_list:
                if isinstance(contract_data, dict):
                    contract = IntradayContract(
                        id=str(contract_data.get('id', '')),
                        name=contract_data.get('name', ''),
                        delivery_start=contract_data.get('deliveryStart', ''),
                        delivery_end=contract_data.get('deliveryEnd', ''),
                        area_code=contract_data.get('areaCode', ''),
                        status=contract_data.get('status', 'Unknown')
                    )
                    self.contracts[contract.id] = contract

            if contracts_list:
                logger.info(f"Updated {len(self.contracts)} contracts")

                # Trigger callback
                if self.on_contract_update:
                    self.on_contract_update(list(self.contracts.values()))

        except Exception as e:
            logger.error(f"Error handling contracts message: {e}")
    
    async def _handle_ticker_message(self, data):
        """Handle ticker update message (localview topic)"""
        try:
            # Data can be a list of tickers or a dict with 'tickers' key
            tickers_list = []
            if isinstance(data, list):
                tickers_list = data
            elif isinstance(data, dict) and 'tickers' in data:
                tickers_list = data['tickers']

            for ticker_data in tickers_list:
                if isinstance(ticker_data, dict):
                    contract_id = str(ticker_data.get('contractId', ticker_data.get('id', '')))
                    if contract_id:
                        ticker = IntradayTicker(
                            contract_id=contract_id,
                            last_price=ticker_data.get('lastPrice'),
                            bid_price=ticker_data.get('bidPrice'),
                            ask_price=ticker_data.get('askPrice'),
                            volume=ticker_data.get('volume', 0.0),
                            timestamp=datetime.now().isoformat()
                        )
                        self.tickers[contract_id] = ticker

            if tickers_list:
                logger.info(f"Updated {len(self.tickers)} tickers")

                # Trigger callback
                if self.on_ticker_update:
                    self.on_ticker_update(list(self.tickers.values()))

        except Exception as e:
            logger.error(f"Error handling ticker message: {e}")
    
    async def _handle_statistics_message(self, data: Dict[str, Any]):
        """Handle statistics update message"""
        try:
            logger.debug("📊 Received statistics update")
            # Process statistics data as needed
            
        except Exception as e:
            logger.error(f"❌ Error handling statistics message: {e}")
    
    async def _shutdown(self):
        """Shutdown WebSocket connections"""
        try:
            if self.market_data_ws:
                await self.market_data_ws.close()

        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
    
    # Public interface methods
    def get_delivery_areas(self) -> List[Dict]:
        """Get current delivery areas"""
        return self.delivery_areas

    def get_contracts(self) -> List[IntradayContract]:
        """Get current contracts"""
        return list(self.contracts.values())
    
    def get_tickers(self) -> List[IntradayTicker]:
        """Get current tickers"""
        return list(self.tickers.values())
    
    def get_contract_ticker(self, contract_id: str) -> Optional[IntradayTicker]:
        """Get ticker for specific contract"""
        return self.tickers.get(contract_id)
    
    def is_connected(self) -> bool:
        """Check if WebSocket is connected"""
        return self.connected
    
    def get_status(self) -> Dict[str, Any]:
        """Get client status"""
        return {
            'connected': self.connected,
            'stomp_connected': self.stomp_connected,
            'running': self.running,
            'delivery_areas_count': len(self.delivery_areas),
            'contracts_count': len(self.contracts),
            'tickers_count': len(self.tickers),
            'trades_count': len(self.trades),
            'last_update': datetime.now().isoformat()
        }


# Test function
def test_live_intraday_client():
    """Test the live intraday client"""
    logger.info("🧪 Testing live intraday WebSocket client...")
    
    client = LiveIntradayClient()
    
    # Set up callbacks
    def on_contracts(contracts):
        logger.info(f"📋 Contract callback: {len(contracts)} contracts")
        for contract in contracts[:3]:  # Show first 3
            logger.info(f"  {contract.id}: {contract.name}")
    
    def on_tickers(tickers):
        logger.info(f"📈 Ticker callback: {len(tickers)} tickers")
        for ticker in tickers[:3]:  # Show first 3
            logger.info(f"  {ticker.contract_id}: {ticker.last_price}")
    
    client.on_contract_update = on_contracts
    client.on_ticker_update = on_tickers
    
    # Start client
    if client.start():
        logger.info("✅ Client started successfully")
        
        try:
            # Run for 30 seconds to collect data
            for i in range(30):
                time.sleep(1)
                if i % 10 == 0:
                    status = client.get_status()
                    logger.info(f"📊 Status: {status}")
                    
        except KeyboardInterrupt:
            logger.info("🛑 Interrupted by user")
        finally:
            client.stop()
            logger.info("🛑 Client stopped")
    else:
        logger.error("❌ Failed to start client")


if __name__ == "__main__":
    test_live_intraday_client()
