"""
Intraday Market WebSocket Client for BRM Trading Bot
Handles SockJS + STOMP protocol WebSocket connections for real-time trading

SockJS Protocol Notes:
- URL format: wss://host/user/{serverId}/{sessionId}/websocket
- serverId: random 3-digit number (000-999)
- sessionId: random 10-20 character alphanumeric string
- Messages wrapped in JSON arrays for sending
- Incoming frames: 'o' (open), 'h' (heartbeat), 'a[...]' (messages)
- Auth via X-AUTH-TOKEN header in STOMP CONNECT frame
"""
import asyncio
import json
import logging
import uuid
import random
import string
import ssl
from datetime import datetime
from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass
from enum import Enum

import websockets
from websockets.exceptions import ConnectionClosed, WebSocketException

from intraday_auth import IntradayAuthenticator
from config import config


def generate_sockjs_server_id() -> str:
    """Generate random 3-digit server ID for SockJS"""
    return str(random.randint(0, 999)).zfill(3)


def generate_sockjs_session_id(length: int = 16) -> str:
    """Generate random session ID for SockJS (10-20 chars)"""
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))


class OrderType(Enum):
    """Intraday order types"""
    LIMIT = "LIMIT"
    ICEBERG = "ICEBERG"
    USER_DEFINED_BLOCK = "USER_DEFINED_BLOCK"


class TimeInForce(Enum):
    """Time in force options"""
    FOK = "FOK"  # Fill or Kill
    IOC = "IOC"  # Immediate or Cancel
    GFS = "GFS"  # Good for Session
    GTD = "GTD"  # Good Till Date


class ExecutionRestriction(Enum):
    """Execution restriction options"""
    AON = "AON"  # All or None
    NON = "NON"  # No restrictions


class OrderModificationType(Enum):
    """Order modification types"""
    ACTIVATE = "ACTI"
    DEACTIVATE = "DEAC"
    MODIFY = "MODI"
    DELETE = "DELE"


@dataclass
class IntradayOrder:
    """Intraday order structure"""
    portfolio_id: str
    contract_ids: List[str]
    delivery_area_id: int
    side: str  # "BUY" or "SELL"
    order_type: OrderType
    unit_price: int  # Price in cents
    quantity: int  # Quantity in kW
    time_in_force: TimeInForce
    execution_restriction: ExecutionRestriction
    state: str = "ACTI"
    client_order_id: Optional[str] = None
    clip_size: Optional[int] = None
    clip_price_change: Optional[int] = None
    expire_time: Optional[str] = None
    text: Optional[str] = None
    
    def __post_init__(self):
        if self.client_order_id is None:
            self.client_order_id = str(uuid.uuid4())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API request"""
        order_dict = {
            "portfolioId": self.portfolio_id,
            "contractIds": self.contract_ids,
            "deliveryAreaId": self.delivery_area_id,
            "side": self.side,
            "orderType": self.order_type.value,
            "unitPrice": self.unit_price,
            "quantity": self.quantity,
            "timeInForce": self.time_in_force.value,
            "executionRestriction": self.execution_restriction.value,
            "state": self.state,
            "clientOrderId": self.client_order_id
        }
        
        # Add optional fields if present
        if self.clip_size is not None:
            order_dict["clipSize"] = self.clip_size
        if self.clip_price_change is not None:
            order_dict["clipPriceChange"] = self.clip_price_change
        if self.expire_time is not None:
            order_dict["expireTime"] = self.expire_time
        if self.text is not None:
            order_dict["text"] = self.text
        
        return order_dict


class STOMPFrame:
    """STOMP protocol frame with SockJS support"""

    def __init__(self, command: str, headers: Dict[str, str] = None, body: str = ""):
        self.command = command
        self.headers = headers or {}
        self.body = body

    def to_string(self) -> str:
        """Convert frame to STOMP protocol string"""
        frame_str = self.command + "\n"

        for key, value in self.headers.items():
            frame_str += f"{key}:{value}\n"

        frame_str += "\n" + self.body + "\x00"
        return frame_str

    def to_sockjs(self) -> str:
        """Convert frame to SockJS format (JSON array with escaped STOMP)"""
        # Create STOMP frame with actual newlines - json.dumps will escape them
        frame_str = self.command + "\n"

        for key, value in self.headers.items():
            frame_str += f"{key}:{value}\n"

        # Double newline to separate headers from body (STOMP spec), then null terminator
        frame_str += "\n" + self.body + "\u0000"

        # Wrap in JSON array for SockJS - json.dumps handles escaping
        return json.dumps([frame_str])

    @classmethod
    def from_string(cls, frame_str: str) -> 'STOMPFrame':
        """Parse STOMP frame from string"""
        lines = frame_str.split('\n')
        command = lines[0]

        headers = {}
        body_start = 1

        for i, line in enumerate(lines[1:], 1):
            if line == "":
                body_start = i + 1
                break
            if ":" in line:
                key, value = line.split(":", 1)
                headers[key] = value

        body = "\n".join(lines[body_start:]).rstrip('\x00')
        return cls(command, headers, body)

    @classmethod
    def from_sockjs(cls, sockjs_msg: str) -> List['STOMPFrame']:
        """Parse STOMP frames from SockJS message format"""
        frames = []

        if not sockjs_msg.startswith('a['):
            return frames

        try:
            # Parse SockJS array (remove 'a' prefix)
            messages = json.loads(sockjs_msg[1:])

            for msg in messages:
                # Unescape the STOMP message
                msg = msg.replace('\\n', '\n').replace('\\u0000', '\x00')

                # Parse as STOMP frame
                frames.append(cls.from_string(msg))

        except json.JSONDecodeError:
            pass

        return frames


class IntradayWebSocketClient:
    """WebSocket client for Intraday market using SockJS + STOMP protocol"""

    def __init__(self, username: str):
        self.username = username
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.connected = False
        self.stomp_connected = False
        self.subscriptions: Dict[str, str] = {}  # topic -> subscription_id
        self.message_handlers: Dict[str, Callable] = {}
        self.logger = logging.getLogger(__name__)
        self.heartbeat_task: Optional[asyncio.Task] = None
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = config.max_reconnection_attempts
        self.access_token: Optional[str] = None

        # SockJS session identifiers
        self.server_id: str = ""
        self.session_id: str = ""

    def _build_sockjs_url(self) -> str:
        """Build the SockJS WebSocket URL"""
        self.server_id = generate_sockjs_server_id()
        self.session_id = generate_sockjs_session_id()

        base_url = config.websocket_url.rstrip('/')
        return f"{base_url}/user/{self.server_id}/{self.session_id}/websocket"

    async def connect(self) -> bool:
        """
        Connect to the WebSocket server using SockJS protocol and perform STOMP handshake
        """
        try:
            auth = IntradayAuthenticator()
            self.access_token = auth.get_access_token()

            if not self.access_token:
                self.logger.error("Failed to obtain access token")
                return False

            # Build SockJS URL
            ws_url = self._build_sockjs_url()
            self.logger.info(f"Connecting to SockJS endpoint: {ws_url}")

            # Create SSL context
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

            # Connect to WebSocket
            self.websocket = await websockets.connect(
                ws_url,
                ssl=ssl_context,
                max_size=10 * 1024 * 1024,  # 10MB max message size
                ping_interval=20,
                ping_timeout=10
            )

            # Wait for SockJS open frame ('o')
            open_frame = await asyncio.wait_for(self.websocket.recv(), timeout=10)
            if open_frame != 'o':
                self.logger.error(f"Expected SockJS open frame, got: {open_frame}")
                return False

            self.connected = True
            self.logger.info("SockJS connection established")

            # Extract host from URL for STOMP
            host = config.websocket_url.split("//")[1].split("/")[0].split(":")[0]

            # Send STOMP CONNECT frame (wrapped in SockJS format)
            connect_frame = STOMPFrame(
                "CONNECT",
                {
                    "accept-version": "1.2",
                    "host": host,
                    "X-AUTH-TOKEN": self.access_token,
                    "heart-beat": "10000,10000"
                }
            )

            await self.websocket.send(connect_frame.to_sockjs())

            # Wait for STOMP CONNECTED frame
            response = await asyncio.wait_for(self.websocket.recv(), timeout=10)

            # Parse SockJS response
            if response.startswith('a['):
                frames = STOMPFrame.from_sockjs(response)
                if frames and frames[0].command == "CONNECTED":
                    self.stomp_connected = True
                    self.reconnect_attempts = 0
                    self.logger.info("STOMP handshake successful - fully connected!")

                    # Start heartbeat task
                    self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())

                    # Start message listening task
                    asyncio.create_task(self._listen_for_messages())

                    return True
                else:
                    cmd = frames[0].command if frames else "UNKNOWN"
                    body = frames[0].body if frames else response
                    self.logger.error(f"STOMP connection failed: {cmd} - {body}")
                    return False
            else:
                self.logger.error(f"Unexpected response: {response[:200]}")
                return False

        except asyncio.TimeoutError:
            self.logger.error("Connection timeout")
            return False
        except Exception as e:
            self.logger.error(f"Failed to connect: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from the WebSocket server"""
        if self.connected and self.websocket:
            try:
                # Send STOMP DISCONNECT frame (wrapped in SockJS format)
                disconnect_frame = STOMPFrame("DISCONNECT")
                await self.websocket.send(disconnect_frame.to_sockjs())

                # Cancel heartbeat task
                if self.heartbeat_task:
                    self.heartbeat_task.cancel()

                await self.websocket.close()
                self.connected = False
                self.stomp_connected = False
                self.logger.info("Disconnected from Intraday WebSocket")

            except Exception as e:
                self.logger.error(f"Error during disconnect: {e}")

    async def subscribe(self, topic: str, handler: Callable[[Dict[str, Any]], None]) -> str:
        """
        Subscribe to a topic and register a message handler

        Args:
            topic: The topic to subscribe to
            handler: Function to handle incoming messages

        Returns:
            Subscription ID
        """
        if not self.stomp_connected:
            raise ConnectionError("Not connected to WebSocket (STOMP not established)")

        subscription_id = str(uuid.uuid4())

        subscribe_frame = STOMPFrame(
            "SUBSCRIBE",
            {
                "id": subscription_id,
                "destination": topic,
                "ack": "auto"
            }
        )

        await self.websocket.send(subscribe_frame.to_sockjs())

        self.subscriptions[topic] = subscription_id
        self.message_handlers[subscription_id] = handler

        self.logger.info(f"Subscribed to {topic} with ID {subscription_id}")
        return subscription_id

    async def unsubscribe(self, topic: str):
        """Unsubscribe from a topic"""
        if topic not in self.subscriptions:
            return

        subscription_id = self.subscriptions[topic]

        unsubscribe_frame = STOMPFrame(
            "UNSUBSCRIBE",
            {"id": subscription_id}
        )

        await self.websocket.send(unsubscribe_frame.to_sockjs())

        del self.subscriptions[topic]
        del self.message_handlers[subscription_id]

        self.logger.info(f"Unsubscribed from {topic}")
    
    async def send_order(self, order: IntradayOrder, reject_partially: bool = False) -> str:
        """
        Send an order to the market

        Args:
            order: The order to send
            reject_partially: Whether to reject partially if there are errors

        Returns:
            Request ID
        """
        if not self.stomp_connected:
            raise ConnectionError("Not connected to WebSocket (STOMP not established)")

        request_id = str(uuid.uuid4())

        order_request = {
            "requestId": request_id,
            "rejectPartially": reject_partially,
            "linkedBasket": False,
            "orders": [order.to_dict()]
        }

        send_frame = STOMPFrame(
            "SEND",
            {
                "destination": f"/{config.api_version}/orderEntryRequest",
                "content-type": "application/json"
            },
            json.dumps(order_request)
        )

        await self.websocket.send(send_frame.to_sockjs())

        self.logger.info(f"Sent order {order.client_order_id} with request ID {request_id}")
        return request_id

    async def modify_order(
        self,
        order_id: str,
        modification_type: OrderModificationType,
        modifications: Optional[Dict[str, Any]] = None,
        revision_no: int = 1
    ) -> str:
        """
        Modify an existing order

        Args:
            order_id: The order ID to modify
            modification_type: Type of modification
            modifications: Dictionary of fields to modify
            revision_no: Revision number for the modification

        Returns:
            Request ID
        """
        if not self.stomp_connected:
            raise ConnectionError("Not connected to WebSocket (STOMP not established)")

        request_id = str(uuid.uuid4())

        modification_request = {
            "requestId": request_id,
            "orders": [{
                "orderId": order_id,
                "orderModificationType": modification_type.value,
                "revisionNo": revision_no,
                **(modifications or {})
            }]
        }

        send_frame = STOMPFrame(
            "SEND",
            {
                "destination": f"/{config.api_version}/orderModificationRequest",
                "content-type": "application/json"
            },
            json.dumps(modification_request)
        )

        await self.websocket.send(send_frame.to_sockjs())

        self.logger.info(f"Sent modification for order {order_id} with request ID {request_id}")
        return request_id

    async def refresh_token(self, new_token: str, old_token: str):
        """
        Refresh the authentication token

        Args:
            new_token: The new authentication token
            old_token: The old authentication token
        """
        if not self.stomp_connected:
            raise ConnectionError("Not connected to WebSocket (STOMP not established)")

        token_refresh = {
            "type": "TOKEN_REFRESH",
            "oldToken": old_token,
            "newToken": new_token
        }

        send_frame = STOMPFrame(
            "SEND",
            {
                "destination": f"/{config.api_version}/command",
                "content-type": "application/json"
            },
            json.dumps(token_refresh)
        )

        await self.websocket.send(send_frame.to_sockjs())
        self.access_token = new_token
        self.logger.info("Token refresh request sent")
    
    async def _heartbeat_loop(self):
        """Send heartbeat messages to keep connection alive"""
        try:
            while self.connected and self.stomp_connected:
                await asyncio.sleep(config.websocket_heartbeat_interval)
                if self.connected and self.websocket:
                    # WebSocket ping (handled by library), STOMP uses heart-beat negotiated in CONNECT
                    pass
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.logger.error(f"Heartbeat error: {e}")

    async def _listen_for_messages(self):
        """Listen for incoming SockJS/STOMP messages and dispatch to handlers"""
        try:
            while self.connected and self.websocket:
                try:
                    message = await self.websocket.recv()

                    # Handle SockJS frame types
                    if message == 'h':
                        # Heartbeat frame - ignore
                        continue

                    elif message == 'o':
                        # Open frame (shouldn't happen after connect)
                        self.logger.debug("Received SockJS open frame")
                        continue

                    elif message.startswith('c['):
                        # Close frame
                        self.logger.warning(f"SockJS close frame: {message}")
                        self.connected = False
                        self.stomp_connected = False
                        break

                    elif message.startswith('a['):
                        # Message frame - parse STOMP frames
                        frames = STOMPFrame.from_sockjs(message)

                        for frame in frames:
                            if frame.command == "MESSAGE":
                                subscription_id = frame.headers.get("subscription")
                                if subscription_id in self.message_handlers:
                                    try:
                                        if frame.body:
                                            data = json.loads(frame.body)
                                            await self._safe_call_handler(
                                                self.message_handlers[subscription_id],
                                                data
                                            )
                                    except json.JSONDecodeError as e:
                                        self.logger.error(f"Failed to parse message JSON: {e}")

                            elif frame.command == "ERROR":
                                error_msg = frame.headers.get("message", frame.body)
                                self.logger.error(f"STOMP error: {error_msg}")

                            elif frame.command == "RECEIPT":
                                receipt_id = frame.headers.get("receipt-id")
                                self.logger.debug(f"Received STOMP receipt: {receipt_id}")

                    else:
                        self.logger.debug(f"Unknown SockJS frame: {message[:100]}")

                except ConnectionClosed:
                    self.logger.warning("WebSocket connection closed")
                    self.connected = False
                    self.stomp_connected = False
                    await self._attempt_reconnect()
                    break

        except Exception as e:
            self.logger.error(f"Message listening error: {e}")
            self.connected = False
            self.stomp_connected = False
    
    async def _safe_call_handler(self, handler: Callable, data: Dict[str, Any]):
        """Safely call a message handler"""
        try:
            if asyncio.iscoroutinefunction(handler):
                await handler(data)
            else:
                handler(data)
        except Exception as e:
            self.logger.error(f"Error in message handler: {e}")
    
    async def _attempt_reconnect(self):
        """Attempt to reconnect to the WebSocket"""
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            self.logger.error("Max reconnection attempts reached")
            return

        self.reconnect_attempts += 1
        wait_time = min(2 ** self.reconnect_attempts, 60)  # Exponential backoff, max 60s

        self.logger.info(f"Attempting reconnection {self.reconnect_attempts}/{self.max_reconnect_attempts} in {wait_time}s")
        await asyncio.sleep(wait_time)

        # Store current subscriptions before reconnecting
        old_subscriptions = dict(self.subscriptions)
        old_handlers = dict(self.message_handlers)

        # Clear current state
        self.subscriptions.clear()
        self.message_handlers.clear()

        if await self.connect():
            # Re-subscribe to all previous topics
            for topic, subscription_id in old_subscriptions.items():
                handler = old_handlers.get(subscription_id)
                if handler:
                    try:
                        await self.subscribe(topic, handler)
                    except Exception as e:
                        self.logger.error(f"Failed to re-subscribe to {topic}: {e}")

    async def subscribe_to_configuration(self, handler: Callable[[Dict[str, Any]], None]) -> str:
        """Subscribe to configuration updates (portfolios, areas, throttling limits)"""
        # Note: configuration does NOT use /streaming/ in the path
        topic = f"/user/{self.username}/{config.api_version}/configuration"
        return await self.subscribe(topic, handler)

    async def subscribe_to_order_execution_reports(self, handler: Callable[[Dict[str, Any]], None]) -> str:
        """Subscribe to order execution reports"""
        topic = f"/user/{self.username}/{config.api_version}/streaming/orderExecutionReport"
        return await self.subscribe(topic, handler)

    async def subscribe_to_private_trades(self, handler: Callable[[Dict[str, Any]], None]) -> str:
        """Subscribe to private trade updates"""
        topic = f"/user/{self.username}/{config.api_version}/streaming/privateTrade"
        return await self.subscribe(topic, handler)

    async def subscribe_to_local_view(self, area_id: int, handler: Callable[[Dict[str, Any]], None]) -> str:
        """Subscribe to local market view for a specific area"""
        topic = f"/user/{self.username}/{config.api_version}/streaming/localview/{area_id}"
        return await self.subscribe(topic, handler)

    async def subscribe_to_delivery_areas(self, handler: Callable[[Dict[str, Any]], None]) -> str:
        """Subscribe to delivery areas updates"""
        topic = f"/user/{self.username}/{config.api_version}/streaming/deliveryAreas"
        return await self.subscribe(topic, handler)

    async def subscribe_to_contracts(self, handler: Callable[[Dict[str, Any]], None]) -> str:
        """Subscribe to contracts updates"""
        topic = f"/user/{self.username}/{config.api_version}/streaming/contracts"
        return await self.subscribe(topic, handler)

    async def subscribe_to_ticker(self, handler: Callable[[Dict[str, Any]], None]) -> str:
        """Subscribe to ticker/price updates"""
        topic = f"/user/{self.username}/{config.api_version}/streaming/ticker"
        return await self.subscribe(topic, handler)

    async def subscribe_to_public_statistics(self, handler: Callable[[Dict[str, Any]], None]) -> str:
        """Subscribe to public market statistics"""
        topic = f"/user/{self.username}/{config.api_version}/streaming/publicStatistics"
        return await self.subscribe(topic, handler)
