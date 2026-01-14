"""
Intraday Market Data Client for BRM Integration
Handles real-time market data streaming and REST API operations
"""

import asyncio
import aiohttp
import json
import logging
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
import threading
from concurrent.futures import ThreadPoolExecutor

from intraday_websocket_client import IntradayWebSocketClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class IntradayContract:
    """Intraday contract information"""
    id: str
    name: str
    delivery_start: datetime
    delivery_end: datetime
    area_code: str
    status: str
    min_quantity: float = 0.1
    max_quantity: float = 9999.0
    tick_size: float = 0.01

@dataclass
class IntradayTicker:
    """Real-time price ticker information"""
    contract_id: str
    last_price: Optional[float] = None
    bid_price: Optional[float] = None
    ask_price: Optional[float] = None
    volume: float = 0.0
    timestamp: Optional[datetime] = None

@dataclass
class IntradayOrderBook:
    """Order book information"""
    contract_id: str
    bids: List[Dict[str, float]]  # [{"price": 50.0, "quantity": 10.0}]
    asks: List[Dict[str, float]]
    timestamp: Optional[datetime] = None

@dataclass
class IntradayTrade:
    """Trade execution information"""
    id: str
    contract_id: str
    price: float
    quantity: float
    timestamp: datetime
    buyer_area: str
    seller_area: str

class IntradayMarketClient:
    """
    Comprehensive intraday market data client
    Combines WebSocket streaming with REST API operations
    """
    
    def __init__(self, 
                 access_token: str,
                 base_url: str = "https://intraday2-api.test.nordpoolgroup.com",
                 ws_trading_url: str = "wss://intraday2-ws.test.nordpoolgroup.com:443",
                 ws_market_url: str = "wss://intraday-pmd-api-ws-brm.test.nordpoolgroup.com:443"):
        """
        Initialize intraday market client
        
        Args:
            access_token: OAuth2 access token
            base_url: REST API base URL
            ws_trading_url: WebSocket trading URL
            ws_market_url: WebSocket market data URL
        """
        self.access_token = access_token
        self.base_url = base_url
        
        # WebSocket client
        self.ws_client = IntradayWebSocketClient(
            trading_url=ws_trading_url,
            market_data_url=ws_market_url,
            access_token=access_token
        )
        
        # Data storage
        self.contracts: Dict[str, IntradayContract] = {}
        self.tickers: Dict[str, IntradayTicker] = {}
        self.order_books: Dict[str, IntradayOrderBook] = {}
        self.recent_trades: List[IntradayTrade] = []
        
        # Event handlers
        self.contract_handlers: List[Callable] = []
        self.ticker_handlers: List[Callable] = []
        self.trade_handlers: List[Callable] = []
        
        # Threading for async operations
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.running = False
        
        # HTTP session for REST API
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def initialize(self) -> bool:
        """Initialize the market client"""
        try:
            # Create HTTP session
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json'
            }
            self.session = aiohttp.ClientSession(headers=headers)
            
            # Start WebSocket client
            await self.ws_client.start()
            
            # Subscribe to market data topics
            await self._setup_subscriptions()
            
            # Load initial market data
            await self._load_initial_data()
            
            self.running = True
            logger.info("Intraday market client initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize intraday market client: {e}")
            return False
    
    async def _setup_subscriptions(self):
        """Set up WebSocket subscriptions for market data"""
        try:
            # Subscribe to contracts
            await self.ws_client.subscribe_topic(
                "/topic/contracts", 
                self._handle_contracts_update,
                "market_data"
            )
            
            # Subscribe to ticker data
            await self.ws_client.subscribe_topic(
                "/topic/ticker", 
                self._handle_ticker_update,
                "market_data"
            )
            
            # Subscribe to local view (order book)
            await self.ws_client.subscribe_topic(
                "/topic/localView", 
                self._handle_local_view_update,
                "market_data"
            )
            
            # Subscribe to public statistics
            await self.ws_client.subscribe_topic(
                "/topic/publicStatistics", 
                self._handle_statistics_update,
                "market_data"
            )
            
            # Subscribe to capacity information
            await self.ws_client.subscribe_topic(
                "/topic/capacities", 
                self._handle_capacity_update,
                "market_data"
            )
            
            logger.info("WebSocket subscriptions set up successfully")
            
        except Exception as e:
            logger.error(f"Failed to set up subscriptions: {e}")
    
    async def _load_initial_data(self):
        """Load initial market data via REST API"""
        try:
            # Load contracts
            contracts = await self.get_contracts()
            for contract in contracts:
                self.contracts[contract.id] = contract
            
            # Load recent trades
            trades = await self.get_recent_trades(limit=100)
            self.recent_trades = trades[-100:]  # Keep last 100 trades
            
            logger.info(f"Loaded {len(contracts)} contracts and {len(trades)} recent trades")
            
        except Exception as e:
            logger.error(f"Failed to load initial data: {e}")
    
    # WebSocket message handlers
    async def _handle_contracts_update(self, message: Dict[str, Any], headers: Dict[str, str]):
        """Handle contracts update from WebSocket"""
        try:
            if 'contracts' in message:
                for contract_data in message['contracts']:
                    contract = IntradayContract(
                        id=contract_data.get('id', ''),
                        name=contract_data.get('name', ''),
                        delivery_start=datetime.fromisoformat(contract_data.get('deliveryStart', '').replace('Z', '+00:00')),
                        delivery_end=datetime.fromisoformat(contract_data.get('deliveryEnd', '').replace('Z', '+00:00')),
                        area_code=contract_data.get('areaCode', ''),
                        status=contract_data.get('status', 'Unknown'),
                        min_quantity=contract_data.get('minQuantity', 0.1),
                        max_quantity=contract_data.get('maxQuantity', 9999.0),
                        tick_size=contract_data.get('tickSize', 0.01)
                    )
                    self.contracts[contract.id] = contract
                
                # Notify handlers
                for handler in self.contract_handlers:
                    try:
                        await handler(list(self.contracts.values()))
                    except Exception as e:
                        logger.error(f"Error in contract handler: {e}")
                        
        except Exception as e:
            logger.error(f"Error handling contracts update: {e}")
    
    async def _handle_ticker_update(self, message: Dict[str, Any], headers: Dict[str, str]):
        """Handle ticker update from WebSocket"""
        try:
            if 'tickers' in message:
                for ticker_data in message['tickers']:
                    contract_id = ticker_data.get('contractId', '')
                    ticker = IntradayTicker(
                        contract_id=contract_id,
                        last_price=ticker_data.get('lastPrice'),
                        bid_price=ticker_data.get('bidPrice'),
                        ask_price=ticker_data.get('askPrice'),
                        volume=ticker_data.get('volume', 0.0),
                        timestamp=datetime.now()
                    )
                    self.tickers[contract_id] = ticker
                
                # Notify handlers
                for handler in self.ticker_handlers:
                    try:
                        await handler(list(self.tickers.values()))
                    except Exception as e:
                        logger.error(f"Error in ticker handler: {e}")
                        
        except Exception as e:
            logger.error(f"Error handling ticker update: {e}")
    
    async def _handle_local_view_update(self, message: Dict[str, Any], headers: Dict[str, str]):
        """Handle local view (order book) update from WebSocket"""
        try:
            if 'orderBooks' in message:
                for ob_data in message['orderBooks']:
                    contract_id = ob_data.get('contractId', '')
                    order_book = IntradayOrderBook(
                        contract_id=contract_id,
                        bids=ob_data.get('bids', []),
                        asks=ob_data.get('asks', []),
                        timestamp=datetime.now()
                    )
                    self.order_books[contract_id] = order_book
                    
        except Exception as e:
            logger.error(f"Error handling local view update: {e}")
    
    async def _handle_statistics_update(self, message: Dict[str, Any], headers: Dict[str, str]):
        """Handle public statistics update from WebSocket"""
        try:
            # Process public statistics
            logger.debug(f"Statistics update: {message}")
        except Exception as e:
            logger.error(f"Error handling statistics update: {e}")
    
    async def _handle_capacity_update(self, message: Dict[str, Any], headers: Dict[str, str]):
        """Handle capacity update from WebSocket"""
        try:
            # Process capacity information
            logger.debug(f"Capacity update: {message}")
        except Exception as e:
            logger.error(f"Error handling capacity update: {e}")
    
    # REST API methods
    async def get_contracts(self, area_code: Optional[str] = None) -> List[IntradayContract]:
        """Get available contracts via REST API"""
        try:
            url = f"{self.base_url}/api/v1/contracts"
            params = {}
            if area_code:
                params['areaCode'] = area_code
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    contracts = []
                    
                    for contract_data in data.get('contracts', []):
                        contract = IntradayContract(
                            id=contract_data.get('id', ''),
                            name=contract_data.get('name', ''),
                            delivery_start=datetime.fromisoformat(contract_data.get('deliveryStart', '').replace('Z', '+00:00')),
                            delivery_end=datetime.fromisoformat(contract_data.get('deliveryEnd', '').replace('Z', '+00:00')),
                            area_code=contract_data.get('areaCode', ''),
                            status=contract_data.get('status', 'Unknown')
                        )
                        contracts.append(contract)
                    
                    return contracts
                else:
                    logger.error(f"Failed to get contracts: HTTP {response.status}")
                    return []
                    
        except Exception as e:
            logger.error(f"Error getting contracts: {e}")
            return []
    
    async def get_recent_trades(self, limit: int = 100, contract_id: Optional[str] = None) -> List[IntradayTrade]:
        """Get recent trades via REST API"""
        try:
            url = f"{self.base_url}/api/v1/trades"
            params = {'limit': limit}
            if contract_id:
                params['contractId'] = contract_id
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    trades = []
                    
                    for trade_data in data.get('trades', []):
                        trade = IntradayTrade(
                            id=trade_data.get('id', ''),
                            contract_id=trade_data.get('contractId', ''),
                            price=trade_data.get('price', 0.0),
                            quantity=trade_data.get('quantity', 0.0),
                            timestamp=datetime.fromisoformat(trade_data.get('timestamp', '').replace('Z', '+00:00')),
                            buyer_area=trade_data.get('buyerArea', ''),
                            seller_area=trade_data.get('sellerArea', '')
                        )
                        trades.append(trade)
                    
                    return trades
                else:
                    logger.error(f"Failed to get trades: HTTP {response.status}")
                    return []
                    
        except Exception as e:
            logger.error(f"Error getting trades: {e}")
            return []
    
    async def get_delivery_areas(self) -> List[Dict[str, Any]]:
        """Get available delivery areas"""
        try:
            url = f"{self.base_url}/api/v1/deliveryAreas"
            
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get('deliveryAreas', [])
                else:
                    logger.error(f"Failed to get delivery areas: HTTP {response.status}")
                    return []
                    
        except Exception as e:
            logger.error(f"Error getting delivery areas: {e}")
            return []
    
    # Event handler registration
    def add_contract_handler(self, handler: Callable):
        """Add handler for contract updates"""
        self.contract_handlers.append(handler)
    
    def add_ticker_handler(self, handler: Callable):
        """Add handler for ticker updates"""
        self.ticker_handlers.append(handler)
    
    def add_trade_handler(self, handler: Callable):
        """Add handler for trade updates"""
        self.trade_handlers.append(handler)
    
    # Data access methods
    def get_current_contracts(self) -> List[IntradayContract]:
        """Get currently loaded contracts"""
        return list(self.contracts.values())
    
    def get_current_tickers(self) -> List[IntradayTicker]:
        """Get current ticker data"""
        return list(self.tickers.values())
    
    def get_contract_ticker(self, contract_id: str) -> Optional[IntradayTicker]:
        """Get ticker for specific contract"""
        return self.tickers.get(contract_id)
    
    def get_contract_order_book(self, contract_id: str) -> Optional[IntradayOrderBook]:
        """Get order book for specific contract"""
        return self.order_books.get(contract_id)
    
    def get_market_summary(self) -> Dict[str, Any]:
        """Get market summary statistics"""
        return {
            'total_contracts': len(self.contracts),
            'active_contracts': len([c for c in self.contracts.values() if c.status == 'Active']),
            'total_tickers': len(self.tickers),
            'recent_trades_count': len(self.recent_trades),
            'last_update': datetime.now().isoformat(),
            'websocket_status': self.ws_client.get_status()
        }
    
    async def stop(self):
        """Stop the market client"""
        self.running = False
        
        # Stop WebSocket client
        await self.ws_client.stop()
        
        # Close HTTP session
        if self.session:
            await self.session.close()
        
        # Shutdown executor
        self.executor.shutdown(wait=True)
        
        logger.info("Intraday market client stopped")


# Example usage
async def example_contract_handler(contracts: List[IntradayContract]):
    """Example contract update handler"""
    logger.info(f"Contracts updated: {len(contracts)} contracts available")
    for contract in contracts[:3]:  # Show first 3
        logger.info(f"  {contract.id}: {contract.name} ({contract.status})")

async def example_ticker_handler(tickers: List[IntradayTicker]):
    """Example ticker update handler"""
    logger.info(f"Tickers updated: {len(tickers)} tickers available")
    for ticker in tickers[:3]:  # Show first 3
        if ticker.last_price:
            logger.info(f"  {ticker.contract_id}: {ticker.last_price} EUR/MWh")

async def main():
    """Example usage of intraday market client"""
    # Initialize client
    client = IntradayMarketClient(
        access_token="your_access_token_here",
        base_url="https://intraday2-api.test.nordpoolgroup.com"
    )
    
    # Add event handlers
    client.add_contract_handler(example_contract_handler)
    client.add_ticker_handler(example_ticker_handler)
    
    # Initialize and start
    if await client.initialize():
        logger.info("Market client started successfully")
        
        # Keep running and show periodic updates
        try:
            while client.running:
                await asyncio.sleep(30)
                summary = client.get_market_summary()
                logger.info(f"Market Summary: {summary}")
                
        except KeyboardInterrupt:
            logger.info("Shutting down...")
        finally:
            await client.stop()
    else:
        logger.error("Failed to start market client")

if __name__ == "__main__":
    asyncio.run(main())
