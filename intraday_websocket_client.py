"""
Nord Pool Intraday WebSocket Client for BRM Integration
Implements STOMP protocol over WebSocket for real-time intraday trading
"""

import asyncio
import websockets
import json
import logging
import time
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass
from enum import Enum
import uuid
import threading
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ConnectionState(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting" 
    CONNECTED = "connected"
    AUTHENTICATED = "authenticated"
    ERROR = "error"

@dataclass
class STOMPFrame:
    """STOMP protocol frame structure"""
    command: str
    headers: Dict[str, str]
    body: str = ""
    
    def to_bytes(self) -> bytes:
        """Convert frame to STOMP wire format"""
        frame_str = f"{self.command}\n"
        
        for key, value in self.headers.items():
            frame_str += f"{key}:{value}\n"
        
        frame_str += f"\n{self.body}\x00"
        return frame_str.encode('utf-8')
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'STOMPFrame':
        """Parse STOMP frame from wire format"""
        try:
            frame_str = data.decode('utf-8').rstrip('\x00')
            lines = frame_str.split('\n')
            
            command = lines[0]
            headers = {}
            body_start = 1
            
            for i, line in enumerate(lines[1:], 1):
                if line == '':
                    body_start = i + 1
                    break
                if ':' in line:
                    key, value = line.split(':', 1)
                    headers[key] = value
            
            body = '\n'.join(lines[body_start:]) if body_start < len(lines) else ""
            
            return cls(command=command, headers=headers, body=body)
        except Exception as e:
            logger.error(f"Error parsing STOMP frame: {e}")
            return cls(command="ERROR", headers={}, body=str(e))

class IntradayWebSocketClient:
    """
    Nord Pool Intraday WebSocket client with STOMP protocol support
    Handles both Trading API and Public Market Data API connections
    """
    
    def __init__(self, 
                 trading_url: str = "wss://intraday2-ws.test.nordpoolgroup.com:443",
                 market_data_url: str = "wss://intraday-pmd-api-ws-brm.test.nordpoolgroup.com:443",
                 access_token: Optional[str] = None):
        """
        Initialize WebSocket client
        
        Args:
            trading_url: WebSocket URL for trading operations
            market_data_url: WebSocket URL for market data
            access_token: OAuth2 access token for authentication
        """
        self.trading_url = trading_url
        self.market_data_url = market_data_url
        self.access_token = access_token
        
        # Connection management
        self.trading_ws: Optional[websockets.WebSocketServerProtocol] = None
        self.market_data_ws: Optional[websockets.WebSocketServerProtocol] = None
        self.trading_state = ConnectionState.DISCONNECTED
        self.market_data_state = ConnectionState.DISCONNECTED
        
        # STOMP protocol management
        self.receipt_counter = 0
        self.subscription_counter = 0
        self.pending_receipts: Dict[str, asyncio.Future] = {}
        self.subscriptions: Dict[str, Callable] = {}
        
        # Message handlers
        self.message_handlers: Dict[str, Callable] = {
            'CONNECTED': self._handle_connected,
            'MESSAGE': self._handle_message,
            'RECEIPT': self._handle_receipt,
            'ERROR': self._handle_error,
            'HEARTBEAT': self._handle_heartbeat
        }
        
        # Heartbeat management
        self.last_heartbeat = time.time()
        self.heartbeat_interval = 30  # seconds
        self.heartbeat_task: Optional[asyncio.Task] = None
        
        # Event loop and tasks
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.running = False
        
    async def connect_trading(self) -> bool:
        """Connect to trading WebSocket"""
        try:
            logger.info(f"Connecting to trading WebSocket: {self.trading_url}")
            self.trading_state = ConnectionState.CONNECTING
            
            # Add authentication headers
            headers = {}
            if self.access_token:
                headers['Authorization'] = f'Bearer {self.access_token}'
            
            self.trading_ws = await websockets.connect(
                self.trading_url,
                extra_headers=headers,
                ping_interval=20,
                ping_timeout=10
            )
            
            # Send STOMP CONNECT frame
            connect_frame = STOMPFrame(
                command="CONNECT",
                headers={
                    "accept-version": "1.2",
                    "host": "intraday2-ws.test.nordpoolgroup.com",
                    "heart-beat": "10000,10000"
                }
            )
            
            await self.trading_ws.send(connect_frame.to_bytes())
            self.trading_state = ConnectionState.CONNECTED
            
            logger.info("Trading WebSocket connected successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to trading WebSocket: {e}")
            self.trading_state = ConnectionState.ERROR
            return False
    
    async def connect_market_data(self) -> bool:
        """Connect to market data WebSocket"""
        try:
            logger.info(f"Connecting to market data WebSocket: {self.market_data_url}")
            self.market_data_state = ConnectionState.CONNECTING
            
            # Add authentication headers
            headers = {}
            if self.access_token:
                headers['Authorization'] = f'Bearer {self.access_token}'
            
            self.market_data_ws = await websockets.connect(
                self.market_data_url,
                extra_headers=headers,
                ping_interval=20,
                ping_timeout=10
            )
            
            # Send STOMP CONNECT frame
            connect_frame = STOMPFrame(
                command="CONNECT",
                headers={
                    "accept-version": "1.2",
                    "host": "intraday-pmd-api-ws-brm.test.nordpoolgroup.com",
                    "heart-beat": "10000,10000"
                }
            )
            
            await self.market_data_ws.send(connect_frame.to_bytes())
            self.market_data_state = ConnectionState.CONNECTED
            
            logger.info("Market data WebSocket connected successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to market data WebSocket: {e}")
            self.market_data_state = ConnectionState.ERROR
            return False
    
    async def subscribe_topic(self, topic: str, handler: Callable, connection_type: str = "market_data") -> str:
        """
        Subscribe to a STOMP topic
        
        Args:
            topic: Topic to subscribe to (e.g., "/topic/contracts")
            handler: Callback function to handle messages
            connection_type: "trading" or "market_data"
            
        Returns:
            Subscription ID
        """
        subscription_id = f"sub-{self.subscription_counter}"
        self.subscription_counter += 1
        
        # Store handler
        self.subscriptions[subscription_id] = handler
        
        # Create subscription frame
        subscribe_frame = STOMPFrame(
            command="SUBSCRIBE",
            headers={
                "id": subscription_id,
                "destination": topic,
                "ack": "auto"
            }
        )
        
        # Send to appropriate connection
        ws = self.market_data_ws if connection_type == "market_data" else self.trading_ws
        if ws:
            await ws.send(subscribe_frame.to_bytes())
            logger.info(f"Subscribed to {topic} with ID {subscription_id}")
        
        return subscription_id
    
    async def send_order(self, order_data: Dict[str, Any]) -> str:
        """
        Send trading order via WebSocket
        
        Args:
            order_data: Order details
            
        Returns:
            Receipt ID for tracking
        """
        if not self.trading_ws or self.trading_state != ConnectionState.AUTHENTICATED:
            raise Exception("Trading connection not authenticated")
        
        receipt_id = f"receipt-{self.receipt_counter}"
        self.receipt_counter += 1
        
        # Create order frame
        order_frame = STOMPFrame(
            command="SEND",
            headers={
                "destination": "/app/order",
                "receipt": receipt_id,
                "content-type": "application/json"
            },
            body=json.dumps(order_data)
        )
        
        # Create future for receipt tracking
        receipt_future = asyncio.Future()
        self.pending_receipts[receipt_id] = receipt_future
        
        await self.trading_ws.send(order_frame.to_bytes())
        logger.info(f"Order sent with receipt ID: {receipt_id}")
        
        return receipt_id
    
    async def _handle_connected(self, frame: STOMPFrame):
        """Handle STOMP CONNECTED frame"""
        logger.info("STOMP connection established")
        # Update connection state based on which connection sent this
        # This is a simplified approach - in practice you'd track per connection
        if self.trading_state == ConnectionState.CONNECTED:
            self.trading_state = ConnectionState.AUTHENTICATED
        if self.market_data_state == ConnectionState.CONNECTED:
            self.market_data_state = ConnectionState.AUTHENTICATED
    
    async def _handle_message(self, frame: STOMPFrame):
        """Handle STOMP MESSAGE frame"""
        subscription_id = frame.headers.get('subscription')
        if subscription_id and subscription_id in self.subscriptions:
            handler = self.subscriptions[subscription_id]
            try:
                # Parse JSON body if present
                message_data = json.loads(frame.body) if frame.body else {}
                await handler(message_data, frame.headers)
            except Exception as e:
                logger.error(f"Error in message handler for {subscription_id}: {e}")
    
    async def _handle_receipt(self, frame: STOMPFrame):
        """Handle STOMP RECEIPT frame"""
        receipt_id = frame.headers.get('receipt-id')
        if receipt_id and receipt_id in self.pending_receipts:
            future = self.pending_receipts.pop(receipt_id)
            future.set_result(frame)
            logger.info(f"Receipt confirmed: {receipt_id}")
    
    async def _handle_error(self, frame: STOMPFrame):
        """Handle STOMP ERROR frame"""
        error_message = frame.body or "Unknown STOMP error"
        logger.error(f"STOMP Error: {error_message}")
        
        # Set error state
        self.trading_state = ConnectionState.ERROR
        self.market_data_state = ConnectionState.ERROR
    
    async def _handle_heartbeat(self, frame: STOMPFrame):
        """Handle heartbeat frame"""
        self.last_heartbeat = time.time()
        logger.debug("Heartbeat received")
    
    async def _message_loop(self, ws: websockets.WebSocketServerProtocol):
        """Main message processing loop"""
        try:
            async for message in ws:
                if isinstance(message, bytes):
                    frame = STOMPFrame.from_bytes(message)
                    handler = self.message_handlers.get(frame.command)
                    if handler:
                        await handler(frame)
                    else:
                        logger.warning(f"Unhandled STOMP command: {frame.command}")
        except websockets.exceptions.ConnectionClosed:
            logger.info("WebSocket connection closed")
        except Exception as e:
            logger.error(f"Error in message loop: {e}")
    
    async def _heartbeat_loop(self):
        """Send periodic heartbeats"""
        while self.running:
            try:
                # Send heartbeat to both connections if available
                heartbeat_frame = STOMPFrame(command="HEARTBEAT", headers={})
                
                if self.trading_ws and self.trading_state == ConnectionState.AUTHENTICATED:
                    await self.trading_ws.send(heartbeat_frame.to_bytes())
                
                if self.market_data_ws and self.market_data_state == ConnectionState.AUTHENTICATED:
                    await self.market_data_ws.send(heartbeat_frame.to_bytes())
                
                await asyncio.sleep(self.heartbeat_interval)
                
            except Exception as e:
                logger.error(f"Error in heartbeat loop: {e}")
                break
    
    async def start(self):
        """Start the WebSocket client"""
        self.running = True
        self.loop = asyncio.get_event_loop()
        
        # Connect to both WebSockets
        trading_connected = await self.connect_trading()
        market_data_connected = await self.connect_market_data()
        
        if not (trading_connected or market_data_connected):
            logger.error("Failed to connect to any WebSocket")
            return False
        
        # Start message loops
        tasks = []
        
        if self.trading_ws:
            tasks.append(asyncio.create_task(self._message_loop(self.trading_ws)))
        
        if self.market_data_ws:
            tasks.append(asyncio.create_task(self._message_loop(self.market_data_ws)))
        
        # Start heartbeat loop
        self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        tasks.append(self.heartbeat_task)
        
        # Wait for all tasks
        try:
            await asyncio.gather(*tasks)
        except Exception as e:
            logger.error(f"Error in WebSocket client: {e}")
        finally:
            await self.stop()
        
        return True
    
    async def stop(self):
        """Stop the WebSocket client"""
        self.running = False
        
        # Cancel heartbeat task
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
        
        # Close WebSocket connections
        if self.trading_ws:
            await self.trading_ws.close()
        
        if self.market_data_ws:
            await self.market_data_ws.close()
        
        logger.info("WebSocket client stopped")
    
    def is_connected(self) -> bool:
        """Check if at least one connection is authenticated"""
        return (self.trading_state == ConnectionState.AUTHENTICATED or 
                self.market_data_state == ConnectionState.AUTHENTICATED)
    
    def get_status(self) -> Dict[str, str]:
        """Get connection status"""
        return {
            "trading_connection": self.trading_state.value,
            "market_data_connection": self.market_data_state.value,
            "last_heartbeat": datetime.fromtimestamp(self.last_heartbeat).isoformat(),
            "running": self.running
        }


# Example usage and testing
async def example_market_data_handler(message: Dict[str, Any], headers: Dict[str, str]):
    """Example handler for market data messages"""
    logger.info(f"Market data received: {message}")

async def example_order_handler(message: Dict[str, Any], headers: Dict[str, str]):
    """Example handler for order execution reports"""
    logger.info(f"Order update received: {message}")

async def main():
    """Example usage of the WebSocket client"""
    # Initialize client
    client = IntradayWebSocketClient(
        trading_url="wss://intraday2-ws.test.nordpoolgroup.com:443",
        market_data_url="wss://intraday-pmd-api-ws-brm.test.nordpoolgroup.com:443",
        access_token="your_access_token_here"
    )
    
    # Start client
    await client.start()
    
    # Subscribe to topics
    await client.subscribe_topic("/topic/contracts", example_market_data_handler)
    await client.subscribe_topic("/topic/ticker", example_market_data_handler)
    await client.subscribe_topic("/user/queue/orderExecutionReport", example_order_handler, "trading")
    
    # Keep running
    try:
        while client.is_connected():
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        await client.stop()

if __name__ == "__main__":
    asyncio.run(main())
