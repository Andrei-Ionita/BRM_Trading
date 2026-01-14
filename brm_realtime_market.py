"""
BRM Real-time Market Data Viewer
Uses the correct BRM API endpoints to show live Romanian energy market data
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


class BRMRealtimeMarketViewer:
    """Real-time market data viewer using BRM API endpoints"""
    
    def __init__(self):
        """Initialize the market viewer"""
        self.auth = initialize_working_auth()
        self.base_url = "https://auctions-api.test.brm-power.ro"
        self.session = None
        
        # Market data storage
        self.auctions = []
        self.current_orders = {}
        self.recent_trades = {}
        self.current_prices = {}
        
        logger.info("BRM Realtime Market Viewer initialized")
    
    async def make_api_call(self, endpoint: str, description: str = "") -> Optional[Any]:
        """Make an API call to the BRM API"""
        try:
            headers = await self.auth.get_auth_headers_async()
            url = f"{self.base_url}{endpoint}"
            
            if not self.session:
                self.session = aiohttp.ClientSession()
            
            logger.info(f"🔍 {description}: {endpoint}")
            
            async with self.session.get(
                url, 
                headers=headers,
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
                        
                elif response.status == 403:
                    logger.info(f"   ⚠️ Forbidden - May need specific permissions for this endpoint")
                    return None
                    
                elif response.status == 404:
                    logger.info(f"   ⚠️ Not Found - Endpoint may not exist or no data available")
                    return None
                    
                else:
                    text = await response.text()
                    logger.info(f"   ❌ Error: {text[:200]}...")
                    return None
                    
        except Exception as e:
            logger.error(f"❌ API call failed for {endpoint}: {e}")
            return None
    
    async def get_all_auctions(self) -> Optional[List[Dict[str, Any]]]:
        """Get all available auctions"""
        # Try different API versions
        for version in [1, 2]:
            endpoint = f"/api/v{version}/auctions"
            result = await self.make_api_call(endpoint, f"Getting auctions (v{version})")
            if result is not None:
                return result
        return None
    
    async def get_auction_orders(self, auction_id: str, version: int = 1) -> Optional[List[Dict[str, Any]]]:
        """Get orders for a specific auction"""
        endpoint = f"/api/v{version}/auctions/{auction_id}/orders"
        return await self.make_api_call(endpoint, f"Getting orders for auction {auction_id}")
    
    async def get_auction_trades(self, auction_id: str, version: int = 1) -> Optional[List[Dict[str, Any]]]:
        """Get trades for a specific auction"""
        endpoint = f"/api/v{version}/auctions/{auction_id}/trades"
        return await self.make_api_call(endpoint, f"Getting trades for auction {auction_id}")
    
    async def get_auction_prices(self, auction_id: str, version: int = 1) -> Optional[List[Dict[str, Any]]]:
        """Get prices for a specific auction"""
        endpoint = f"/api/v{version}/auctions/{auction_id}/prices"
        return await self.make_api_call(endpoint, f"Getting prices for auction {auction_id}")
    
    async def get_auction_details(self, auction_id: str, version: int = 1) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific auction"""
        endpoint = f"/api/v{version}/auctions/{auction_id}"
        return await self.make_api_call(endpoint, f"Getting details for auction {auction_id}")
    
    async def get_system_state(self) -> Optional[Any]:
        """Get system state"""
        endpoint = "/api/state"
        return await self.make_api_call(endpoint, "Getting system state")
    
    def display_auctions(self, auctions: List[Dict[str, Any]]):
        """Display auction information"""
        logger.info("🏛️ AVAILABLE AUCTIONS")
        logger.info("=" * 50)
        
        if not auctions:
            logger.info("   No auctions found")
            return
        
        for auction in auctions[:10]:  # Show first 10 auctions
            auction_id = auction.get('id', 'Unknown')
            name = auction.get('name', 'Unknown')
            state = auction.get('state', 'Unknown')
            start_time = auction.get('startTime', 'Unknown')
            end_time = auction.get('endTime', 'Unknown')
            
            logger.info(f"   🎯 Auction: {auction_id}")
            logger.info(f"      Name: {name}")
            logger.info(f"      State: {state}")
            logger.info(f"      Period: {start_time} - {end_time}")
            logger.info("")
    
    def display_orders(self, auction_id: str, orders: List[Dict[str, Any]]):
        """Display order information"""
        logger.info(f"📋 ORDERS FOR AUCTION {auction_id}")
        logger.info("=" * 60)
        
        if not orders:
            logger.info("   No orders found")
            return
        
        buy_orders = [o for o in orders if o.get('side') == 'BUY']
        sell_orders = [o for o in orders if o.get('side') == 'SELL']
        
        logger.info(f"   📈 BUY ORDERS: {len(buy_orders)}")
        for order in buy_orders[:5]:  # Show first 5 buy orders
            order_id = order.get('id', 'Unknown')
            price = order.get('price', 0)
            quantity = order.get('quantity', 0)
            state = order.get('state', 'Unknown')
            
            logger.info(f"      Order {order_id}: {quantity} MWh @ {price:.2f} EUR/MWh ({state})")
        
        logger.info(f"   📉 SELL ORDERS: {len(sell_orders)}")
        for order in sell_orders[:5]:  # Show first 5 sell orders
            order_id = order.get('id', 'Unknown')
            price = order.get('price', 0)
            quantity = order.get('quantity', 0)
            state = order.get('state', 'Unknown')
            
            logger.info(f"      Order {order_id}: {quantity} MWh @ {price:.2f} EUR/MWh ({state})")
        
        logger.info("")
    
    def display_trades(self, auction_id: str, trades: List[Dict[str, Any]]):
        """Display trade information"""
        logger.info(f"💰 TRADES FOR AUCTION {auction_id}")
        logger.info("=" * 60)
        
        if not trades:
            logger.info("   No trades found")
            return
        
        logger.info(f"   Found {len(trades)} trades")
        
        for trade in trades[:10]:  # Show first 10 trades
            trade_id = trade.get('id', 'Unknown')
            price = trade.get('price', 0)
            quantity = trade.get('quantity', 0)
            trade_time = trade.get('tradeTime', 'Unknown')
            buyer = trade.get('buyerPortfolio', 'Unknown')
            seller = trade.get('sellerPortfolio', 'Unknown')
            
            logger.info(f"   🔄 Trade {trade_id}")
            logger.info(f"      Time: {trade_time}")
            logger.info(f"      Volume: {quantity} MWh @ {price:.2f} EUR/MWh")
            logger.info(f"      Buyer: {buyer}")
            logger.info(f"      Seller: {seller}")
            logger.info("")
    
    def display_prices(self, auction_id: str, prices: List[Dict[str, Any]]):
        """Display price information"""
        logger.info(f"💵 PRICES FOR AUCTION {auction_id}")
        logger.info("=" * 60)
        
        if not prices:
            logger.info("   No prices found")
            return
        
        for price_info in prices[:10]:  # Show first 10 price points
            area = price_info.get('area', 'Unknown')
            period = price_info.get('period', 'Unknown')
            price = price_info.get('price', 0)
            currency = price_info.get('currency', 'EUR')
            
            logger.info(f"   🌍 Area: {area}")
            logger.info(f"      Period: {period}")
            logger.info(f"      Price: {price:.2f} {currency}/MWh")
            logger.info("")
    
    def display_auction_details(self, auction_id: str, details: Dict[str, Any]):
        """Display detailed auction information"""
        logger.info(f"🔍 AUCTION DETAILS: {auction_id}")
        logger.info("=" * 60)
        
        # Show key auction information
        key_fields = [
            'name', 'state', 'startTime', 'endTime', 'deliveryStart', 'deliveryEnd',
            'currency', 'timeZone', 'auctionType', 'marketType'
        ]
        
        for field in key_fields:
            value = details.get(field, 'Not specified')
            logger.info(f"   {field.capitalize()}: {value}")
        
        # Show areas if available
        areas = details.get('areas', [])
        if areas:
            logger.info(f"   Areas: {', '.join(areas)}")
        
        logger.info("")
    
    async def run_realtime_market_view(self):
        """Run real-time market data viewing session"""
        try:
            logger.info("🇷🇴 BRM REAL-TIME MARKET DATA VIEWER")
            logger.info("=" * 70)
            logger.info("Accessing LIVE Romanian energy market data...")
            logger.info("=" * 70)
            
            # Get authentication token
            token_info = await self.auth.get_token_async()
            logger.info(f"✅ Authentication successful, token expires at {token_info.expires_at}")
            logger.info("")
            
            # Get system state first
            logger.info("1️⃣ Getting system state...")
            system_state = await self.get_system_state()
            if system_state:
                logger.info(f"   System state: {system_state}")
            logger.info("")
            
            # Get all auctions
            logger.info("2️⃣ Getting all auctions...")
            auctions = await self.get_all_auctions()
            
            if not auctions:
                logger.warning("⚠️ No auctions found or access denied")
                logger.info("💡 This might be normal if no auctions are currently active")
                return
            
            self.auctions = auctions
            self.display_auctions(auctions)
            
            # Get detailed information for active auctions
            active_auctions = [a for a in auctions if a.get('state') in ['ACTIVE', 'OPEN', 'RUNNING']]
            
            if not active_auctions:
                logger.info("⚠️ No active auctions found")
                # Still try to get data from the first few auctions
                active_auctions = auctions[:3]
            
            logger.info(f"3️⃣ Exploring {len(active_auctions)} auctions in detail...")
            
            for i, auction in enumerate(active_auctions[:3], 1):  # Limit to first 3 auctions
                auction_id = auction.get('id')
                if not auction_id:
                    continue
                
                logger.info(f"   🔍 Auction {i}/{len(active_auctions[:3])}: {auction_id}")
                
                # Get auction details
                details = await self.get_auction_details(auction_id)
                if details:
                    self.display_auction_details(auction_id, details)
                
                # Get orders
                orders = await self.get_auction_orders(auction_id)
                if orders:
                    self.current_orders[auction_id] = orders
                    self.display_orders(auction_id, orders)
                
                # Get trades
                trades = await self.get_auction_trades(auction_id)
                if trades:
                    self.recent_trades[auction_id] = trades
                    self.display_trades(auction_id, trades)
                
                # Get prices
                prices = await self.get_auction_prices(auction_id)
                if prices:
                    self.current_prices[auction_id] = prices
                    self.display_prices(auction_id, prices)
                
                # Small delay between auctions
                await asyncio.sleep(1)
            
            # Show summary
            logger.info("📊 MARKET DATA SUMMARY")
            logger.info("=" * 50)
            logger.info(f"✅ Total auctions found: {len(self.auctions)}")
            logger.info(f"📋 Auctions with orders: {len(self.current_orders)}")
            logger.info(f"💰 Auctions with trades: {len(self.recent_trades)}")
            logger.info(f"💵 Auctions with prices: {len(self.current_prices)}")
            logger.info("")
            logger.info("🎯 CONCLUSION:")
            
            if self.current_orders or self.recent_trades or self.current_prices:
                logger.info("✅ Successfully accessed BRM real-time market data!")
                logger.info("📈 Live market information is available")
                logger.info("🇷🇴 Romanian energy market is accessible")
                logger.info("💰 Ready for live trading operations")
            else:
                logger.info("⚠️ Market data access limited - may need additional permissions")
                logger.info("💡 Contact BRM support to verify market data access")
            
        except Exception as e:
            logger.error(f"❌ Error during real-time market viewing: {e}")
        finally:
            if self.session:
                await self.session.close()
    
    async def continuous_monitoring(self, update_interval_seconds: int = 60):
        """Run continuous market monitoring"""
        logger.info(f"🔄 Starting continuous BRM market monitoring")
        logger.info(f"   Updates every {update_interval_seconds} seconds")
        logger.info("   Press Ctrl+C to stop")
        
        try:
            while True:
                logger.info(f"\n⏰ Market Update - {datetime.now().strftime('%H:%M:%S')}")
                logger.info("-" * 60)
                
                # Quick market snapshot
                auctions = await self.get_all_auctions()
                if auctions:
                    active_count = len([a for a in auctions if a.get('state') in ['ACTIVE', 'OPEN', 'RUNNING']])
                    logger.info(f"🏛️ {len(auctions)} total auctions, {active_count} active")
                    
                    # Check first active auction for quick updates
                    active_auctions = [a for a in auctions if a.get('state') in ['ACTIVE', 'OPEN', 'RUNNING']]
                    if active_auctions:
                        auction_id = active_auctions[0].get('id')
                        
                        # Quick check for new trades
                        trades = await self.get_auction_trades(auction_id)
                        if trades:
                            logger.info(f"💰 {len(trades)} trades in auction {auction_id}")
                
                await asyncio.sleep(update_interval_seconds)
                
        except KeyboardInterrupt:
            logger.info("⏹️ Monitoring stopped by user")
        except Exception as e:
            logger.error(f"❌ Error during monitoring: {e}")


async def main():
    """Main function"""
    viewer = BRMRealtimeMarketViewer()
    
    try:
        # Run real-time market view
        await viewer.run_realtime_market_view()
        
        # Optionally run continuous monitoring
        # Uncomment the next line to enable continuous monitoring
        # await viewer.continuous_monitoring(update_interval_seconds=30)
        
    except Exception as e:
        logger.error(f"❌ Main execution failed: {e}")
    
    logger.info("🎬 BRM real-time market data session completed!")
    logger.info("🇷🇴 Romanian energy market exploration finished! ⚡")


if __name__ == "__main__":
    # Set test environment
    os.environ["BRM_ENVIRONMENT"] = "test"
    
    # Run the BRM real-time market viewer
    asyncio.run(main())
