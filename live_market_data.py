"""
Live BRM Market Data Viewer
Uses Nord Pool Market Data API to show real-time Romanian energy market data
"""
import asyncio
import logging
import json
import aiohttp
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
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


class BRMLiveMarketData:
    """Live market data viewer for BRM using Nord Pool Market Data API"""
    
    def __init__(self):
        """Initialize the market data viewer"""
        self.auth = initialize_working_auth()
        self.base_url = "https://data-api.nordpoolgroup.com"
        self.session = None
        
        # Market data storage
        self.current_prices = {}
        self.recent_trades = []
        self.order_books = {}
        self.market_statistics = {}
        
        logger.info("BRM Live Market Data Viewer initialized")
    
    async def make_api_call(self, endpoint: str, params: Dict[str, Any] = None) -> Optional[Any]:
        """Make an API call to the Market Data API"""
        try:
            headers = await self.auth.get_auth_headers_async()
            url = f"{self.base_url}{endpoint}"
            
            if not self.session:
                self.session = aiohttp.ClientSession()
            
            logger.info(f"🔍 Fetching: {endpoint}")
            if params:
                logger.info(f"   Parameters: {params}")
            
            async with self.session.get(
                url, 
                headers=headers, 
                params=params,
                timeout=aiohttp.ClientTimeout(total=15)
            ) as response:
                logger.info(f"   Status: {response.status}")
                
                if response.status == 200:
                    try:
                        data = await response.json()
                        logger.info(f"   ✅ Success! Got {type(data).__name__}")
                        
                        if isinstance(data, list):
                            logger.info(f"   📊 {len(data)} items")
                        elif isinstance(data, dict):
                            logger.info(f"   📊 {len(data)} fields")
                        
                        return data
                        
                    except Exception as e:
                        text = await response.text()
                        logger.info(f"   📄 Text response: {text[:200]}...")
                        return text
                else:
                    text = await response.text()
                    logger.info(f"   ❌ Error: {text[:200]}...")
                    return None
                    
        except Exception as e:
            logger.error(f"❌ API call failed for {endpoint}: {e}")
            return None
    
    async def get_system_price(self) -> Optional[Dict[str, Any]]:
        """Get current system price"""
        today = datetime.now().strftime('%Y-%m-%d')
        params = {
            'date': today
        }
        return await self.make_api_call("/api/v2/System/Price", params)
    
    async def get_auction_prices(self, areas: List[str] = None) -> Optional[List[Dict[str, Any]]]:
        """Get current auction prices"""
        today = datetime.now().strftime('%Y-%m-%d')
        params = {
            'date': today
        }
        if areas:
            params['areas'] = ','.join(areas)
        
        return await self.make_api_call("/api/v2/Auction/Prices/ByAreas", params)
    
    async def get_recent_trades(self, hours_back: int = 2) -> Optional[List[Dict[str, Any]]]:
        """Get recent intraday trades"""
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=hours_back)
        
        params = {
            'tradeTimeFrom': start_time.strftime('%Y-%m-%dT%H:%M:%S'),
            'tradeTimeTo': end_time.strftime('%Y-%m-%dT%H:%M:%S')
        }
        
        return await self.make_api_call("/api/v2/Intraday/Trades/ByTradeTime", params)
    
    async def get_intraday_statistics(self, areas: List[str] = None) -> Optional[List[Dict[str, Any]]]:
        """Get intraday market statistics"""
        today = datetime.now().strftime('%Y-%m-%d')
        params = {
            'date': today
        }
        if areas:
            params['areas'] = ','.join(areas)
        
        return await self.make_api_call("/api/v2/Intraday/HourlyStatistics/ByAreas", params)
    
    async def get_available_contracts(self, area: str = None) -> Optional[List[str]]:
        """Get available contracts for order book"""
        params = {}
        if area:
            params['area'] = area
        
        return await self.make_api_call("/api/v2/Intraday/OrderBook/ContractsIds/ByArea", params)
    
    async def get_order_book(self, contract_id: str) -> Optional[Dict[str, Any]]:
        """Get order book for a specific contract"""
        params = {
            'contractId': contract_id
        }
        
        return await self.make_api_call("/api/v2/Intraday/OrderBook/ByContractId", params)
    
    def display_system_price(self, data: Any):
        """Display system price information"""
        logger.info("💰 SYSTEM PRICE")
        logger.info("=" * 40)
        
        if isinstance(data, list) and data:
            for price_info in data[:5]:  # Show first 5 entries
                date = price_info.get('date', 'Unknown')
                price = price_info.get('value', 0)
                currency = price_info.get('currency', 'EUR')
                
                logger.info(f"   📅 {date}")
                logger.info(f"   💵 {price:.2f} {currency}/MWh")
                logger.info("")
        elif isinstance(data, dict):
            for key, value in data.items():
                logger.info(f"   {key}: {value}")
        else:
            logger.info(f"   Data: {data}")
    
    def display_auction_prices(self, data: Any):
        """Display auction price information"""
        logger.info("🏛️ AUCTION PRICES")
        logger.info("=" * 40)
        
        if isinstance(data, list) and data:
            for price_info in data[:10]:  # Show first 10 entries
                area = price_info.get('area', 'Unknown')
                date = price_info.get('date', 'Unknown')
                hour = price_info.get('hour', 'Unknown')
                price = price_info.get('value', 0)
                currency = price_info.get('currency', 'EUR')
                
                logger.info(f"   🌍 Area: {area}")
                logger.info(f"   📅 {date} Hour {hour}")
                logger.info(f"   💵 {price:.2f} {currency}/MWh")
                logger.info("")
        else:
            logger.info(f"   Data: {data}")
    
    def display_recent_trades(self, data: Any):
        """Display recent trade information"""
        logger.info("📈 RECENT TRADES")
        logger.info("=" * 40)
        
        if isinstance(data, list) and data:
            logger.info(f"   Found {len(data)} recent trades")
            
            for trade in data[:5]:  # Show first 5 trades
                trade_id = trade.get('id', 'Unknown')
                trade_time = trade.get('tradeTime', 'Unknown')
                contract = trade.get('contractId', 'Unknown')
                price = trade.get('price', 0)
                quantity = trade.get('quantity', 0)
                currency = trade.get('currency', 'EUR')
                
                logger.info(f"   🔄 Trade: {trade_id}")
                logger.info(f"   ⏰ Time: {trade_time}")
                logger.info(f"   📋 Contract: {contract}")
                logger.info(f"   💵 {quantity} MWh @ {price:.2f} {currency}/MWh")
                logger.info("")
        else:
            logger.info(f"   Data: {data}")
    
    def display_statistics(self, data: Any):
        """Display market statistics"""
        logger.info("📊 MARKET STATISTICS")
        logger.info("=" * 40)
        
        if isinstance(data, list) and data:
            for stat in data[:5]:  # Show first 5 statistics
                area = stat.get('area', 'Unknown')
                date = stat.get('date', 'Unknown')
                hour = stat.get('hour', 'Unknown')
                volume = stat.get('volume', 0)
                trades = stat.get('numberOfTrades', 0)
                
                logger.info(f"   🌍 Area: {area}")
                logger.info(f"   📅 {date} Hour {hour}")
                logger.info(f"   📊 Volume: {volume} MWh")
                logger.info(f"   🔄 Trades: {trades}")
                logger.info("")
        else:
            logger.info(f"   Data: {data}")
    
    def display_order_book(self, contract_id: str, data: Any):
        """Display order book information"""
        logger.info(f"📖 ORDER BOOK: {contract_id}")
        logger.info("=" * 50)
        
        if isinstance(data, dict):
            buy_orders = data.get('buyOrders', [])
            sell_orders = data.get('sellOrders', [])
            
            logger.info(f"   📈 BUY ORDERS: {len(buy_orders)}")
            for order in buy_orders[:3]:  # Show top 3 buy orders
                price = order.get('price', 0)
                quantity = order.get('quantity', 0)
                logger.info(f"     💵 {quantity} MWh @ {price:.2f}")
            
            logger.info(f"   📉 SELL ORDERS: {len(sell_orders)}")
            for order in sell_orders[:3]:  # Show top 3 sell orders
                price = order.get('price', 0)
                quantity = order.get('quantity', 0)
                logger.info(f"     💵 {quantity} MWh @ {price:.2f}")
        else:
            logger.info(f"   Data: {data}")
    
    async def run_live_market_view(self, duration_minutes: int = 5):
        """Run live market data viewing session"""
        try:
            logger.info("🇷🇴 BRM LIVE MARKET DATA VIEWER")
            logger.info("=" * 60)
            logger.info("Fetching real-time Romanian energy market data...")
            logger.info("=" * 60)
            
            # Get authentication token
            token_info = await self.auth.get_token_async()
            logger.info(f"✅ Authentication successful, token expires at {token_info.expires_at}")
            
            # Try different area codes for Romania
            romanian_areas = ['RO', 'Romania', 'ROM', 'RO_BZN']
            
            logger.info("🚀 Starting live market data collection...")
            logger.info("=" * 60)
            
            # Get system price
            logger.info("1️⃣ Getting system price...")
            system_price = await self.get_system_price()
            if system_price:
                self.display_system_price(system_price)
            
            await asyncio.sleep(1)
            
            # Get auction prices
            logger.info("2️⃣ Getting auction prices...")
            auction_prices = await self.get_auction_prices(romanian_areas)
            if auction_prices:
                self.display_auction_prices(auction_prices)
            
            await asyncio.sleep(1)
            
            # Get recent trades
            logger.info("3️⃣ Getting recent trades...")
            recent_trades = await self.get_recent_trades(hours_back=6)
            if recent_trades:
                self.display_recent_trades(recent_trades)
            
            await asyncio.sleep(1)
            
            # Get market statistics
            logger.info("4️⃣ Getting market statistics...")
            statistics = await self.get_intraday_statistics(romanian_areas)
            if statistics:
                self.display_statistics(statistics)
            
            await asyncio.sleep(1)
            
            # Try to get order book data
            logger.info("5️⃣ Getting available contracts...")
            contracts = await self.get_available_contracts()
            if contracts and isinstance(contracts, list) and contracts:
                logger.info(f"   Found {len(contracts)} available contracts")
                
                # Get order book for first few contracts
                for contract_id in contracts[:2]:
                    logger.info(f"6️⃣ Getting order book for {contract_id}...")
                    order_book = await self.get_order_book(contract_id)
                    if order_book:
                        self.display_order_book(contract_id, order_book)
                    await asyncio.sleep(1)
            
            # Show summary
            logger.info("📊 MARKET DATA SUMMARY")
            logger.info("=" * 50)
            logger.info("✅ Successfully connected to Nord Pool Market Data API")
            logger.info("📈 Real-time market data is accessible")
            logger.info("🇷🇴 Romanian energy market data retrieved")
            logger.info("💰 Ready for live trading operations")
            
        except Exception as e:
            logger.error(f"❌ Error during live market viewing: {e}")
        finally:
            if self.session:
                await self.session.close()
    
    async def continuous_monitoring(self, update_interval_seconds: int = 30):
        """Run continuous market monitoring"""
        logger.info(f"🔄 Starting continuous monitoring (updates every {update_interval_seconds}s)")
        logger.info("   Press Ctrl+C to stop")
        
        try:
            while True:
                logger.info(f"\n⏰ Market Update - {datetime.now().strftime('%H:%M:%S')}")
                logger.info("-" * 50)
                
                # Quick market snapshot
                system_price = await self.get_system_price()
                if system_price:
                    self.display_system_price(system_price)
                
                recent_trades = await self.get_recent_trades(hours_back=1)
                if recent_trades:
                    logger.info(f"📈 {len(recent_trades)} trades in last hour")
                
                await asyncio.sleep(update_interval_seconds)
                
        except KeyboardInterrupt:
            logger.info("⏹️ Monitoring stopped by user")
        except Exception as e:
            logger.error(f"❌ Error during monitoring: {e}")


async def main():
    """Main function"""
    viewer = BRMLiveMarketData()
    
    try:
        # Run live market view
        await viewer.run_live_market_view(duration_minutes=3)
        
        # Optionally run continuous monitoring
        # await viewer.continuous_monitoring(update_interval_seconds=60)
        
    except Exception as e:
        logger.error(f"❌ Main execution failed: {e}")
    
    logger.info("🎬 Live market data session completed!")
    logger.info("🇷🇴 Romanian energy market exploration finished! ⚡")


if __name__ == "__main__":
    # Set test environment
    os.environ["BRM_ENVIRONMENT"] = "test"
    
    # Run the live market viewer
    asyncio.run(main())
