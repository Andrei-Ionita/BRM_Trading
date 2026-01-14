"""
Working BRM Day-Ahead Market Viewer
Uses correct authentication and API parameters
"""
import asyncio
import logging
import json
import sys
import os
from datetime import datetime, timedelta
import aiohttp
import ssl

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class WorkingDayAheadViewer:
    """Working Day-Ahead market viewer with correct authentication"""
    
    def __init__(self):
        # Working Day-Ahead auction API credentials
        self.token_url = "https://sso.test.brm-power.ro/connect/token"
        self.api_base_url = "https://auctions-api.test.brm-power.ro"
        
        # Correct credentials
        self.grant_type = "password"
        self.scope = "auction_api"
        self.username = "Test_AuctionAPI_ADREM"
        self.password = "odvM6{=15HW1s%H1Wb"  # Correct password with {
        self.basic_auth = "Basic Y2xpZW50X2F1Y3Rpb25fYXBpOmNsaWVudF9hdWN0aW9uX2FwaQ=="
        
        self.access_token = None
        self.token_expires_at = None
    
    async def get_access_token(self):
        """Get access token using working Day-Ahead credentials"""
        
        if self.access_token and self.token_expires_at and datetime.now() < self.token_expires_at:
            return self.access_token
        
        logger.info("🔐 Getting Day-Ahead access token...")
        
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": self.basic_auth
        }
        
        data = {
            "grant_type": self.grant_type,
            "scope": self.scope,
            "username": self.username,
            "password": self.password
        }
        
        try:
            connector = aiohttp.TCPConnector(ssl=ssl.create_default_context())
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.post(self.token_url, headers=headers, data=data) as response:
                    
                    if response.status == 200:
                        token_data = await response.json()
                        self.access_token = token_data["access_token"]
                        expires_in = token_data.get("expires_in", 3600)
                        self.token_expires_at = datetime.now() + timedelta(seconds=expires_in - 60)
                        
                        logger.info(f"✅ Token acquired, expires at {self.token_expires_at}")
                        return self.access_token
                    else:
                        error_text = await response.text()
                        logger.error(f"❌ Token request failed: {response.status} - {error_text}")
                        return None
                        
        except Exception as e:
            logger.error(f"❌ Token request error: {e}")
            return None
    
    async def api_request(self, endpoint, params=None):
        """Make authenticated API request"""
        
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
                    
                    if response.status == 200:
                        try:
                            return await response.json()
                        except:
                            return await response.text()
                    else:
                        error_text = await response.text()
                        logger.warning(f"⚠️ {endpoint}: {response.status} - {error_text[:200]}...")
                        return None
                        
        except Exception as e:
            logger.error(f"❌ API request error for {endpoint}: {e}")
            return None
    
    async def view_live_market(self):
        """View live Day-Ahead market data"""
        
        logger.info("🚀 BRM Day-Ahead Market - LIVE DATA")
        logger.info("=" * 60)
        
        # Test system connectivity
        logger.info("🔍 Testing system connectivity...")
        state = await self.api_request("/api/state")
        if state:
            logger.info(f"✅ System state: {state}")
        else:
            logger.error("❌ Cannot connect to system")
            return
        
        logger.info("")
        
        # Try auctions with proper version parameter in URL path
        logger.info("📊 Fetching live auctions...")
        
        for version in [1, 2]:
            logger.info(f"🔍 Trying API version {version}...")
            
            # Use version in URL path (not as parameter)
            auctions = await self.api_request(f"/api/v{version}/auctions")
            
            if auctions and auctions != "Bad Request":
                logger.info(f"✅ SUCCESS! Got auctions from API v{version}")
                await self.display_auctions(auctions, version)
                
                # Get detailed data for active auctions
                await self.get_auction_details(auctions, version)
                break
            else:
                logger.info(f"⚠️ No valid data from API v{version}")
        
        logger.info("")
        
        # Try with date parameters
        logger.info("📅 Fetching auctions with date filters...")
        
        today = datetime.now()
        tomorrow = today + timedelta(days=1)
        
        # Try different date parameter formats
        date_formats = [
            {
                "closeBiddingFrom": today.strftime("%Y-%m-%dT00:00:00Z"),
                "closeBiddingTo": tomorrow.strftime("%Y-%m-%dT23:59:59Z")
            },
            {
                "closeBiddingFrom": today.strftime("%Y-%m-%d"),
                "closeBiddingTo": tomorrow.strftime("%Y-%m-%d")
            },
            {
                "from": today.strftime("%Y-%m-%d"),
                "to": tomorrow.strftime("%Y-%m-%d")
            }
        ]
        
        for i, date_params in enumerate(date_formats, 1):
            logger.info(f"📅 Date format {i}: {date_params}")
            
            for version in [1, 2]:
                auctions = await self.api_request(f"/api/v{version}/auctions", params=date_params)
                
                if auctions and auctions != "Bad Request":
                    logger.info(f"✅ SUCCESS! Got date-filtered auctions")
                    await self.display_auctions(auctions, version)
                    break
        
        logger.info("")
        logger.info("🔄 Starting continuous monitoring (Press Ctrl+C to stop)...")
        
        # Continuous monitoring
        try:
            while True:
                await self.monitor_updates()
                await asyncio.sleep(30)  # Update every 30 seconds
                
        except KeyboardInterrupt:
            logger.info("👋 Market monitoring stopped")
    
    async def display_auctions(self, auctions, version):
        """Display auction information"""
        
        if isinstance(auctions, list):
            logger.info(f"📋 Found {len(auctions)} auctions:")
            
            for auction in auctions:
                auction_id = auction.get('id', 'Unknown')
                name = auction.get('name', 'Unknown')
                state = auction.get('state', 'Unknown')
                close_bidding = auction.get('closeBidding', 'Unknown')
                delivery_date = auction.get('deliveryDate', 'Unknown')
                
                logger.info(f"   🎯 Auction {auction_id}")
                logger.info(f"      📝 Name: {name}")
                logger.info(f"      🔄 State: {state}")
                logger.info(f"      📅 Close Bidding: {close_bidding}")
                logger.info(f"      🚚 Delivery: {delivery_date}")
                logger.info("")
        
        elif isinstance(auctions, dict):
            logger.info("📊 Auction data structure:")
            for key, value in list(auctions.items())[:10]:
                logger.info(f"   🔑 {key}: {value}")
        
        else:
            logger.info(f"📄 Raw data: {str(auctions)[:300]}...")
    
    async def get_auction_details(self, auctions, version):
        """Get detailed data for auctions"""
        
        if not isinstance(auctions, list):
            return
        
        logger.info("🔍 Getting detailed auction data...")
        
        for auction in auctions[:3]:  # Limit to first 3 auctions
            auction_id = auction.get('id')
            if not auction_id:
                continue
            
            logger.info(f"📊 Details for auction {auction_id}:")
            
            # Get orders
            orders = await self.api_request(f"/api/v{version}/auctions/{auction_id}/orders")
            if orders:
                if isinstance(orders, list):
                    logger.info(f"   💰 Orders: {len(orders)} active orders")
                    
                    # Show sample orders
                    for order in orders[:3]:
                        order_id = order.get('id', 'Unknown')
                        order_type = order.get('type', 'Unknown')
                        price = order.get('price', 'Unknown')
                        quantity = order.get('quantity', 'Unknown')
                        side = order.get('side', 'Unknown')
                        logger.info(f"      📝 {order_id}: {side} {order_type} - {price} RON/MWh @ {quantity} MWh")
                else:
                    logger.info(f"   💰 Orders: {orders}")
            
            # Get trades
            trades = await self.api_request(f"/api/v{version}/auctions/{auction_id}/trades")
            if trades:
                if isinstance(trades, list):
                    logger.info(f"   🤝 Trades: {len(trades)} executed trades")
                    
                    # Show recent trades
                    for trade in trades[:3]:
                        trade_id = trade.get('id', 'Unknown')
                        price = trade.get('price', 'Unknown')
                        quantity = trade.get('quantity', 'Unknown')
                        timestamp = trade.get('timestamp', 'Unknown')
                        logger.info(f"      💸 {trade_id}: {price} RON/MWh @ {quantity} MWh at {timestamp}")
                else:
                    logger.info(f"   🤝 Trades: {trades}")
            
            # Get prices
            prices = await self.api_request(f"/api/v{version}/auctions/{auction_id}/prices")
            if prices:
                if isinstance(prices, list):
                    logger.info(f"   💲 Prices: {len(prices)} price points")
                    
                    # Show current prices
                    for price in prices[:3]:
                        area = price.get('area', 'Unknown')
                        value = price.get('price', 'Unknown')
                        currency = price.get('currency', 'RON')
                        logger.info(f"      💰 {area}: {value} {currency}/MWh")
                else:
                    logger.info(f"   💲 Prices: {prices}")
            
            logger.info("")
    
    async def monitor_updates(self):
        """Monitor for market updates"""
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        logger.info(f"🔄 [{timestamp}] Market update check...")
        
        # Quick system check
        state = await self.api_request("/api/state")
        if state:
            logger.info(f"   ✅ System: {state}")
        
        # Check for new auctions
        auctions = await self.api_request("/api/v1/auctions")
        if auctions and isinstance(auctions, list):
            active_auctions = [a for a in auctions if a.get('state', '').lower() in ['active', 'open', 'bidding']]
            logger.info(f"   📊 Active auctions: {len(active_auctions)}")
            
            for auction in active_auctions[:2]:
                auction_id = auction.get('id', 'Unknown')
                name = auction.get('name', 'Unknown')
                close_bidding = auction.get('closeBidding', 'Unknown')
                logger.info(f"      🎯 {auction_id}: {name} (closes: {close_bidding})")


async def main():
    """Main function"""
    
    viewer = WorkingDayAheadViewer()
    
    try:
        await viewer.view_live_market()
    except Exception as e:
        logger.error(f"❌ Market viewer failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())
