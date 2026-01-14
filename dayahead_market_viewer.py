"""
Real-time BRM Day-Ahead Market Viewer
Uses the correct auction API credentials from Postman screenshots
"""
import asyncio
import logging
import json
import sys
import os
from datetime import datetime, timedelta
import aiohttp
import ssl
from urllib.parse import quote

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class DayAheadMarketViewer:
    """Real-time viewer for BRM Day-Ahead auction market data"""
    
    def __init__(self):
        # Day-Ahead auction API credentials from Postman screenshots
        self.token_url = "https://sso.test.brm-power.ro/connect/token"
        self.api_base_url = "https://auctions-api.test.brm-power.ro"
        
        # Credentials from the screenshots
        self.grant_type = "password"
        self.scope = "auction_api"
        self.username = "Test_AuctionAPI_ADREM"
        self.password = "odvM6f=15HW1s%H1Wb"
        self.basic_auth = "Basic Y2xpZW50X2F1Y3Rpb25fYXBpOmNsaWVudF9hdWN0aW9uX2FwaQ=="
        
        self.access_token = None
        self.token_expires_at = None
    
    async def get_access_token(self):
        """Get access token using the Day-Ahead auction API credentials"""
        
        if self.access_token and self.token_expires_at and datetime.now() < self.token_expires_at:
            return self.access_token
        
        logger.info("🔐 Getting Day-Ahead auction API access token...")
        
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": self.basic_auth
        }
        
        # URL encode the password to handle special characters
        encoded_password = quote(self.password)
        
        data = {
            "grant_type": self.grant_type,
            "scope": self.scope,
            "username": self.username,
            "password": encoded_password
        }
        
        # Convert to form data
        form_data = "&".join([f"{k}={v}" for k, v in data.items()])
        
        try:
            connector = aiohttp.TCPConnector(ssl=ssl.create_default_context())
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.post(self.token_url, headers=headers, data=form_data) as response:
                    
                    if response.status == 200:
                        token_data = await response.json()
                        self.access_token = token_data["access_token"]
                        expires_in = token_data.get("expires_in", 3600)
                        self.token_expires_at = datetime.now() + timedelta(seconds=expires_in - 60)  # 1 minute buffer
                        
                        logger.info(f"✅ Day-Ahead token acquired, expires at {self.token_expires_at}")
                        return self.access_token
                    else:
                        error_text = await response.text()
                        logger.error(f"❌ Token request failed: {response.status} - {error_text}")
                        return None
                        
        except Exception as e:
            logger.error(f"❌ Token request error: {e}")
            return None
    
    async def get_api_data(self, endpoint, params=None):
        """Get data from the Day-Ahead auction API"""
        
        token = await self.get_access_token()
        if not token:
            return None
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": "BRM-Trading-Bot/1.0"
        }
        
        url = f"{self.api_base_url}{endpoint}"
        
        try:
            connector = aiohttp.TCPConnector(ssl=ssl.create_default_context())
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.get(url, headers=headers, params=params) as response:
                    
                    logger.info(f"📡 {endpoint}: Status {response.status}")
                    
                    if response.status == 200:
                        try:
                            data = await response.json()
                            return data
                        except:
                            text = await response.text()
                            return text
                    else:
                        error_text = await response.text()
                        logger.warning(f"⚠️ {endpoint}: {response.status} - {error_text}")
                        return None
                        
        except Exception as e:
            logger.error(f"❌ API request error for {endpoint}: {e}")
            return None
    
    async def view_market_data(self):
        """View real-time Day-Ahead market data"""
        
        logger.info("🚀 Starting BRM Day-Ahead Market Viewer")
        logger.info("=" * 60)
        
        # Test system state first
        logger.info("🔍 Testing system connectivity...")
        state = await self.get_api_data("/api/state")
        if state:
            logger.info(f"✅ System state: {state}")
        else:
            logger.error("❌ Cannot connect to system")
            return
        
        logger.info("")
        
        # Get current auctions
        logger.info("📊 Fetching current auctions...")
        
        # Try different API versions
        for version in [1, 2]:
            logger.info(f"🔍 Trying API version {version}...")
            
            auctions = await self.get_api_data(f"/api/v{version}/auctions")
            
            if auctions:
                logger.info(f"✅ Found auctions data with API v{version}!")
                await self.process_auctions(auctions, version)
                break
            else:
                logger.info(f"⚠️ No data from API v{version}")
        
        logger.info("")
        
        # Try to get auctions with date filters
        logger.info("📅 Fetching auctions with date filters...")
        
        # Get auctions for today and tomorrow
        today = datetime.now()
        tomorrow = today + timedelta(days=1)
        
        date_params = {
            "closeBiddingFrom": today.strftime("%Y-%m-%dT00:00:00Z"),
            "closeBiddingTo": tomorrow.strftime("%Y-%m-%dT23:59:59Z")
        }
        
        for version in [1, 2]:
            auctions = await self.get_api_data(f"/api/v{version}/auctions", params=date_params)
            
            if auctions:
                logger.info(f"✅ Found date-filtered auctions with API v{version}!")
                await self.process_auctions(auctions, version)
                break
        
        logger.info("")
        logger.info("🔄 Starting continuous monitoring...")
        
        # Continuous monitoring loop
        try:
            while True:
                await self.monitor_market_updates()
                await asyncio.sleep(30)  # Update every 30 seconds
                
        except KeyboardInterrupt:
            logger.info("👋 Market viewer stopped by user")
    
    async def process_auctions(self, auctions, version):
        """Process and display auction data"""
        
        if isinstance(auctions, list):
            logger.info(f"📋 Found {len(auctions)} auctions:")
            
            for auction in auctions[:5]:  # Show first 5 auctions
                auction_id = auction.get('id', 'Unknown')
                name = auction.get('name', 'Unknown')
                state = auction.get('state', 'Unknown')
                close_bidding = auction.get('closeBidding', 'Unknown')
                
                logger.info(f"   🎯 Auction {auction_id}: {name}")
                logger.info(f"      📅 Close Bidding: {close_bidding}")
                logger.info(f"      🔄 State: {state}")
                
                # Get detailed auction data
                await self.get_auction_details(auction_id, version)
                logger.info("")
            
            if len(auctions) > 5:
                logger.info(f"   ... and {len(auctions) - 5} more auctions")
        
        elif isinstance(auctions, dict):
            logger.info("📊 Auction data structure:")
            for key, value in list(auctions.items())[:10]:
                logger.info(f"   🔑 {key}: {value}")
        
        else:
            logger.info(f"📄 Raw auction data: {str(auctions)[:200]}...")
    
    async def get_auction_details(self, auction_id, version):
        """Get detailed information for a specific auction"""
        
        # Get orders for this auction
        orders = await self.get_api_data(f"/api/v{version}/auctions/{auction_id}/orders")
        if orders:
            if isinstance(orders, list):
                logger.info(f"      💰 Orders: {len(orders)} active orders")
                
                # Show sample orders
                for order in orders[:2]:
                    order_id = order.get('id', 'Unknown')
                    order_type = order.get('type', 'Unknown')
                    price = order.get('price', 'Unknown')
                    quantity = order.get('quantity', 'Unknown')
                    logger.info(f"         📝 Order {order_id}: {order_type} - {price} @ {quantity} MWh")
            else:
                logger.info(f"      💰 Orders: {orders}")
        
        # Get trades for this auction
        trades = await self.get_api_data(f"/api/v{version}/auctions/{auction_id}/trades")
        if trades:
            if isinstance(trades, list):
                logger.info(f"      🤝 Trades: {len(trades)} executed trades")
                
                # Show sample trades
                for trade in trades[:2]:
                    trade_id = trade.get('id', 'Unknown')
                    price = trade.get('price', 'Unknown')
                    quantity = trade.get('quantity', 'Unknown')
                    timestamp = trade.get('timestamp', 'Unknown')
                    logger.info(f"         💸 Trade {trade_id}: {price} @ {quantity} MWh at {timestamp}")
            else:
                logger.info(f"      🤝 Trades: {trades}")
        
        # Get prices for this auction
        prices = await self.get_api_data(f"/api/v{version}/auctions/{auction_id}/prices")
        if prices:
            if isinstance(prices, list):
                logger.info(f"      💲 Prices: {len(prices)} price points")
                
                # Show sample prices
                for price in prices[:2]:
                    area = price.get('area', 'Unknown')
                    value = price.get('price', 'Unknown')
                    currency = price.get('currency', 'RON')
                    logger.info(f"         💰 {area}: {value} {currency}/MWh")
            else:
                logger.info(f"      💲 Prices: {prices}")
    
    async def monitor_market_updates(self):
        """Monitor for market updates"""
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        logger.info(f"🔄 [{timestamp}] Checking for market updates...")
        
        # Get current system state
        state = await self.get_api_data("/api/state")
        if state:
            logger.info(f"   ✅ System: {state}")
        
        # Get latest auctions
        auctions = await self.get_api_data("/api/v1/auctions")
        if auctions and isinstance(auctions, list):
            active_auctions = [a for a in auctions if a.get('state') == 'Active']
            logger.info(f"   📊 Active auctions: {len(active_auctions)}")
            
            # Show any new or updated auctions
            for auction in active_auctions[:3]:
                auction_id = auction.get('id', 'Unknown')
                name = auction.get('name', 'Unknown')
                logger.info(f"      🎯 {auction_id}: {name}")


async def main():
    """Main function to run the Day-Ahead market viewer"""
    
    # Set test environment
    os.environ["BRM_ENVIRONMENT"] = "test"
    
    viewer = DayAheadMarketViewer()
    
    try:
        await viewer.view_market_data()
    except KeyboardInterrupt:
        logger.info("👋 Day-Ahead market viewer stopped by user")
    except Exception as e:
        logger.error(f"❌ Market viewer failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())
