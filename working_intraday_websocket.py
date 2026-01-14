"""
Working Intraday WebSocket Client
Updated to use SockJS protocol for BRM intraday market

SockJS Protocol:
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
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass
import ssl

from intraday_auth import IntradayAuthenticator


def generate_sockjs_server_id() -> str:
    """Generate random 3-digit server ID for SockJS"""
    return str(random.randint(0, 999)).zfill(3)


def generate_sockjs_session_id(length: int = 16) -> str:
    """Generate random session ID for SockJS"""
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class IntradayContract:
    """Intraday contract data"""
    id: str
    name: str
    delivery_start: str
    delivery_end: str
    area_code: str
    status: str

@dataclass
class IntradayTicker:
    """Real-time price ticker"""
    contract_id: str
    last_price: Optional[float] = None
    bid_price: Optional[float] = None
    ask_price: Optional[float] = None
    volume: float = 0.0
    timestamp: str = ""

class WorkingIntradayWebSocket:
    """
    Working WebSocket client for BRM intraday market
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
        self.websocket = None
        self.connected = False
        self.stomp_connected = False
        self.running = False

        # Data storage
        self.contracts: Dict[str, IntradayContract] = {}
        self.tickers: Dict[str, IntradayTicker] = {}
        self.delivery_areas: List[Dict] = []

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
        """Start the WebSocket client"""
        try:
            logger.info("🚀 Starting intraday WebSocket client...")
            
            # Get authentication token
            self.access_token = self.auth.get_access_token()
            if not self.access_token:
                logger.error("❌ Failed to get access token")
                return False
            
            logger.info("✅ Authentication successful")
            
            # Start background thread
            self.running = True
            self.thread = threading.Thread(target=self._run_websocket_loop, daemon=True)
            self.thread.start()
            
            # Give it time to connect
            time.sleep(3)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error starting WebSocket client: {e}")
            return False
    
    def stop(self):
        """Stop the WebSocket client"""
        logger.info("🛑 Stopping WebSocket client...")
        self.running = False
        
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5)
    
    def _run_websocket_loop(self):
        """Run WebSocket in background thread"""
        try:
            # Create new event loop
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            
            # Run WebSocket client
            self.loop.run_until_complete(self._websocket_client())
            
        except Exception as e:
            logger.error(f"❌ Error in WebSocket loop: {e}")
        finally:
            if self.loop:
                self.loop.close()
    
    async def _websocket_client(self):
        """Main WebSocket client logic using SockJS protocol"""
        try:
            # Build SockJS URL
            ws_url = self._build_sockjs_url()
            logger.info(f"Connecting to SockJS: {ws_url}")

            # Create SSL context
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

            async with websockets.connect(
                ws_url,
                ssl=ssl_context,
                max_size=10 * 1024 * 1024,  # 10MB max message size
                ping_interval=20,
                ping_timeout=10
            ) as websocket:

                self.websocket = websocket

                # Wait for SockJS open frame
                open_frame = await asyncio.wait_for(websocket.recv(), timeout=10)
                if open_frame != 'o':
                    logger.error(f"Expected SockJS open frame, got: {open_frame}")
                    return

                self.connected = True
                logger.info("SockJS connection established")

                # Send STOMP CONNECT with X-AUTH-TOKEN
                await self._send_stomp_connect(websocket)

                # Wait for STOMP CONNECTED response
                response = await asyncio.wait_for(websocket.recv(), timeout=10)
                if self._parse_sockjs_stomp_response(response, "CONNECTED"):
                    self.stomp_connected = True
                    logger.info("STOMP handshake successful!")
                else:
                    logger.error(f"STOMP connect failed: {response[:200]}")
                    return

                # Subscribe to topics
                await self._subscribe_to_topics(websocket)

                # Message loop
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
        """Send STOMP CONNECT frame via SockJS"""
        try:
            # Build STOMP CONNECT frame with X-AUTH-TOKEN
            stomp_frame = (
                f"CONNECT\n"
                f"accept-version:1.2\n"
                f"host:intraday-pmd-api-ws-brm.test.nordpoolgroup.com\n"
                f"X-AUTH-TOKEN:{self.access_token}\n"
                f"heart-beat:10000,10000\n"
                f"\n"
                f"\u0000"
            )

            # Wrap in SockJS format
            sockjs_msg = self._wrap_stomp_for_sockjs(stomp_frame)
            await websocket.send(sockjs_msg)
            logger.info("Sent STOMP CONNECT")

        except Exception as e:
            logger.error(f"Error sending STOMP CONNECT: {e}")

    async def _subscribe_to_topics(self, websocket):
        """Subscribe to market data topics using correct topic paths"""
        try:
            # Subscribe to delivery areas
            areas_frame = (
                f"SUBSCRIBE\n"
                f"id:areas-sub-{int(time.time())}\n"
                f"destination:/user/{self.username}/v1/streaming/deliveryAreas\n"
                f"ack:auto\n"
                f"\n"
                f"\u0000"
            )
            await websocket.send(self._wrap_stomp_for_sockjs(areas_frame))
            logger.info("Subscribed to delivery areas")

            # Subscribe to contracts
            contracts_frame = (
                f"SUBSCRIBE\n"
                f"id:contracts-sub-{int(time.time())}\n"
                f"destination:/user/{self.username}/v1/streaming/contracts\n"
                f"ack:auto\n"
                f"\n"
                f"\u0000"
            )
            await websocket.send(self._wrap_stomp_for_sockjs(contracts_frame))
            logger.info("Subscribed to contracts")

            # Subscribe to ticker
            ticker_frame = (
                f"SUBSCRIBE\n"
                f"id:ticker-sub-{int(time.time())}\n"
                f"destination:/user/{self.username}/v1/streaming/ticker\n"
                f"ack:auto\n"
                f"\n"
                f"\u0000"
            )
            await websocket.send(self._wrap_stomp_for_sockjs(ticker_frame))
            logger.info("Subscribed to ticker")

        except Exception as e:
            logger.error(f"Error subscribing: {e}")
    
    async def _message_loop(self, websocket):
        """Process incoming SockJS/STOMP messages"""
        try:
            message_count = 0

            while self.running:
                try:
                    # Wait for message
                    message = await asyncio.wait_for(websocket.recv(), timeout=30)

                    # Handle SockJS frame types
                    if message == 'h':
                        # Heartbeat - ignore
                        continue

                    elif message == 'o':
                        # Open frame (shouldn't happen here)
                        continue

                    elif message.startswith('c['):
                        # Close frame
                        logger.info(f"SockJS close frame: {message}")
                        break

                    elif message.startswith('a['):
                        # Message frame - process STOMP messages
                        message_count += 1
                        await self._process_sockjs_message(message)

                    else:
                        logger.debug(f"Unknown frame: {message[:100]}")

                except asyncio.TimeoutError:
                    # Connection is still alive via websockets ping
                    continue

                except websockets.exceptions.ConnectionClosed:
                    logger.info("Connection closed")
                    break

        except Exception as e:
            logger.error(f"Error in message loop: {e}")

    async def _process_sockjs_message(self, sockjs_msg: str):
        """Process SockJS message frame containing STOMP messages"""
        try:
            # Parse SockJS array (remove 'a' prefix)
            messages = json.loads(sockjs_msg[1:])

            for stomp_msg in messages:
                # Unescape the STOMP message
                stomp_msg = stomp_msg.replace('\\n', '\n').replace('\\u0000', '\x00')

                # Parse STOMP frame
                lines = stomp_msg.strip().split('\n')
                if not lines:
                    continue

                command = lines[0]

                if command == "MESSAGE":
                    # Find body (after empty line)
                    body_start = -1
                    headers = {}
                    for i, line in enumerate(lines[1:], 1):
                        if line == '':
                            body_start = i + 1
                            break
                        if ':' in line:
                            key, value = line.split(':', 1)
                            headers[key] = value

                    if body_start > 0 and body_start < len(lines):
                        body = '\n'.join(lines[body_start:]).rstrip('\x00')
                        if body:
                            try:
                                data = json.loads(body)
                                await self._handle_market_data(headers.get('destination', ''), data)
                            except json.JSONDecodeError:
                                logger.debug(f"Non-JSON body: {body[:100]}")

                elif command == "ERROR":
                    error_msg = stomp_msg[6:].split('\n')[0] if len(stomp_msg) > 6 else stomp_msg
                    logger.error(f"STOMP error: {error_msg}")

        except Exception as e:
            logger.error(f"Error processing SockJS message: {e}")

    async def _handle_market_data(self, destination: str, data):
        """Handle received market data based on destination"""
        try:
            # Handle dict format
            if isinstance(data, dict):
                if 'deliveryAreas' in data:
                    self.delivery_areas = data['deliveryAreas']
                    logger.info(f"Received {len(self.delivery_areas)} delivery areas")
                elif 'contracts' in data:
                    await self._handle_contracts(data.get('contracts', []))
                elif 'tickers' in data:
                    await self._handle_tickers(data.get('tickers', []))
                else:
                    logger.debug(f"Data from {destination}: {list(data.keys())[:5]}")

            # Handle list format (raw array)
            elif isinstance(data, list) and len(data) > 0:
                # Determine type from destination or first item
                if 'deliveryAreas' in destination:
                    self.delivery_areas = data
                    logger.info(f"Received {len(data)} delivery areas")
                elif 'contracts' in destination:
                    await self._handle_contracts(data)
                elif 'ticker' in destination:
                    await self._handle_tickers(data)
                else:
                    # Try to infer from data structure
                    sample = data[0] if data else {}
                    if 'deliveryAreaId' in sample or 'areaCode' in sample:
                        self.delivery_areas = data
                        logger.info(f"Received {len(data)} delivery areas")
                    elif 'contractId' in sample:
                        await self._handle_contracts(data)
                    else:
                        logger.debug(f"Unknown list data from {destination}: {len(data)} items")

        except Exception as e:
            logger.error(f"Error handling market data: {e}")

    async def _process_message(self, message: str):
        """Process received message (legacy method)"""
        try:
            # Try to parse as JSON first
            try:
                data = json.loads(message)
                logger.info(f"📊 JSON message: {list(data.keys()) if isinstance(data, dict) else type(data)}")
                
                # Process JSON data
                if isinstance(data, dict):
                    if 'contracts' in data:
                        await self._handle_contracts(data['contracts'])
                    elif 'tickers' in data:
                        await self._handle_tickers(data['tickers'])
                
                return
                
            except json.JSONDecodeError:
                pass
            
            # Try to parse as STOMP message
            if message.startswith(('CONNECTED', 'MESSAGE', 'ERROR', 'RECEIPT')):
                await self._process_stomp_message(message)
            else:
                logger.info(f"📨 Raw message: {message[:200]}")
                
        except Exception as e:
            logger.error(f"❌ Error processing message: {e}")
    
    async def _process_stomp_message(self, message: str):
        """Process STOMP protocol message"""
        try:
            lines = message.strip().split('\n')
            command = lines[0]
            
            if command == "CONNECTED":
                logger.info("✅ STOMP connected successfully")
                
            elif command == "MESSAGE":
                # Extract body from STOMP message
                body_start = -1
                for i, line in enumerate(lines):
                    if line == '':
                        body_start = i + 1
                        break
                
                if body_start > 0 and body_start < len(lines):
                    body = '\n'.join(lines[body_start:]).rstrip('\x00')
                    if body:
                        try:
                            data = json.loads(body)
                            logger.info(f"📊 STOMP message data: {list(data.keys()) if isinstance(data, dict) else type(data)}")
                        except json.JSONDecodeError:
                            logger.info(f"📊 STOMP message body: {body[:100]}")
                
            elif command == "ERROR":
                logger.error(f"❌ STOMP error: {message}")
                
        except Exception as e:
            logger.error(f"❌ Error processing STOMP: {e}")
    
    async def _handle_contracts(self, contracts_data):
        """Handle contracts data"""
        try:
            logger.info(f"📋 Processing {len(contracts_data)} contracts")
            
            for contract_data in contracts_data:
                contract = IntradayContract(
                    id=contract_data.get('id', ''),
                    name=contract_data.get('name', ''),
                    delivery_start=contract_data.get('deliveryStart', ''),
                    delivery_end=contract_data.get('deliveryEnd', ''),
                    area_code=contract_data.get('areaCode', ''),
                    status=contract_data.get('status', 'Unknown')
                )
                self.contracts[contract.id] = contract
            
            logger.info(f"📋 Updated {len(self.contracts)} total contracts")
            
        except Exception as e:
            logger.error(f"❌ Error handling contracts: {e}")
    
    async def _handle_tickers(self, tickers_data):
        """Handle tickers data"""
        try:
            logger.info(f"📈 Processing {len(tickers_data)} tickers")
            
            for ticker_data in tickers_data:
                contract_id = ticker_data.get('contractId', '')
                ticker = IntradayTicker(
                    contract_id=contract_id,
                    last_price=ticker_data.get('lastPrice'),
                    bid_price=ticker_data.get('bidPrice'),
                    ask_price=ticker_data.get('askPrice'),
                    volume=ticker_data.get('volume', 0.0),
                    timestamp=datetime.now().isoformat()
                )
                self.tickers[contract_id] = ticker
            
            logger.info(f"📈 Updated {len(self.tickers)} total tickers")
            
        except Exception as e:
            logger.error(f"❌ Error handling tickers: {e}")
    
    # Public interface
    def get_contracts(self) -> List[IntradayContract]:
        """Get current contracts"""
        return list(self.contracts.values())
    
    def get_tickers(self) -> List[IntradayTicker]:
        """Get current tickers"""
        return list(self.tickers.values())
    
    def is_connected(self) -> bool:
        """Check connection status"""
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
            'last_update': datetime.now().isoformat()
        }

    def get_delivery_areas(self) -> List[Dict]:
        """Get delivery areas"""
        return self.delivery_areas


def test_working_websocket():
    """Test the working WebSocket client"""
    logger.info("🧪 Testing working intraday WebSocket...")
    
    client = WorkingIntradayWebSocket()
    
    if client.start():
        logger.info("✅ WebSocket client started")
        
        try:
            # Monitor for 60 seconds
            for i in range(60):
                time.sleep(1)
                
                if i % 10 == 0:
                    status = client.get_status()
                    logger.info(f"📊 Status: Connected={status['connected']}, Contracts={status['contracts_count']}, Tickers={status['tickers_count']}")
                    
                    # Show some data if available
                    contracts = client.get_contracts()
                    if contracts:
                        logger.info(f"📋 Sample contracts: {[c.id for c in contracts[:3]]}")
                    
                    tickers = client.get_tickers()
                    if tickers:
                        logger.info(f"📈 Sample tickers: {[(t.contract_id, t.last_price) for t in tickers[:3]]}")
                
        except KeyboardInterrupt:
            logger.info("🛑 Interrupted by user")
        finally:
            client.stop()
            logger.info("🛑 WebSocket client stopped")
    else:
        logger.error("❌ Failed to start WebSocket client")


if __name__ == "__main__":
    test_working_websocket()
