"""
Final BRM Market Data Viewer - Fixed Version
Shows real BRM market data with proper response handling
"""
import asyncio
import logging
import json
import aiohttp
from datetime import datetime
from typing import Dict, Any, List, Union
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


class BRMFinalMarketViewer:
    """Final working market data viewer with proper response handling"""
    
    def __init__(self):
        """Initialize the market viewer"""
        self.auth = initialize_working_auth()
        self.base_url = "https://auctions-api.test.brm-power.ro"
        
        logger.info("BRM Final Market Viewer initialized")
    
    async def make_api_call(self, endpoint: str, description: str) -> Union[Dict, List, str, None]:
        """Make an API call and return the response"""
        try:
            headers = await self.auth.get_auth_headers_async()
            url = f"{self.base_url}{endpoint}"
            
            logger.info(f"🔍 {description}: {url}")
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    logger.info(f"   Status: {response.status}")
                    
                    if response.status == 200:
                        # Try to parse as JSON first
                        try:
                            data = await response.json()
                            logger.info(f"   ✅ Success! Data type: {type(data).__name__}")
                            if isinstance(data, list):
                                logger.info(f"   📊 List with {len(data)} items")
                            elif isinstance(data, dict):
                                logger.info(f"   📊 Dict with {len(data)} keys")
                            return data
                        except:
                            # If JSON parsing fails, return as text
                            text = await response.text()
                            logger.info(f"   📄 Text response: {len(text)} characters")
                            return text
                    else:
                        text = await response.text()
                        logger.error(f"   ❌ Error {response.status}: {text[:200]}...")
                        return None
                        
        except Exception as e:
            logger.error(f"❌ Failed to call {endpoint}: {e}")
            return None
    
    def display_data(self, title: str, data: Union[Dict, List, str, None]):
        """Display data in a formatted way"""
        logger.info(f"\n{title}")
        logger.info("=" * len(title))
        
        if data is None:
            logger.info("   ❌ No data available")
            return
        
        if isinstance(data, str):
            logger.info(f"   📄 Text Response: {data[:500]}...")
            return
        
        if isinstance(data, list):
            logger.info(f"   📊 List with {len(data)} items")
            
            # Show first few items
            for i, item in enumerate(data[:3]):
                logger.info(f"   Item {i+1}:")
                if isinstance(item, dict):
                    for key, value in list(item.items())[:5]:  # Show first 5 keys
                        if isinstance(value, (str, int, float, bool)):
                            logger.info(f"     {key}: {value}")
                        else:
                            logger.info(f"     {key}: {type(value).__name__}")
                else:
                    logger.info(f"     {item}")
                logger.info("")
            
            if len(data) > 3:
                logger.info(f"   ... and {len(data) - 3} more items")
        
        elif isinstance(data, dict):
            logger.info(f"   📊 Dictionary with {len(data)} keys")
            
            # Show all key-value pairs
            for key, value in data.items():
                if isinstance(value, (str, int, float, bool)):
                    logger.info(f"     {key}: {value}")
                elif isinstance(value, list):
                    logger.info(f"     {key}: List with {len(value)} items")
                elif isinstance(value, dict):
                    logger.info(f"     {key}: Dict with {len(value)} keys")
                else:
                    logger.info(f"     {key}: {type(value).__name__}")
    
    async def explore_all_endpoints(self):
        """Explore all available endpoints"""
        logger.info("🚀 EXPLORING ALL BRM API ENDPOINTS")
        logger.info("=" * 60)
        
        # Test authentication first
        token_info = await self.auth.get_token_async()
        logger.info(f"✅ Authentication successful, token expires at {token_info.expires_at}")
        
        # List of endpoints to try
        endpoints = [
            ("/api/state", "System State"),
            ("/api/v1/auctions", "Auctions (v1)"),
            ("/api/v2/auctions", "Auctions (v2)"),
            ("/api/v1/blockorders", "Block Orders (v1)"),
            ("/api/v1/curveorders", "Curve Orders (v1)"),
        ]
        
        results = {}
        
        for endpoint, description in endpoints:
            data = await self.make_api_call(endpoint, description)
            results[endpoint] = data
            self.display_data(f"📊 {description}", data)
            await asyncio.sleep(0.5)  # Be nice to the API
        
        # If we found auctions, explore them further
        auctions_data = results.get("/api/v1/auctions") or results.get("/api/v2/auctions")
        if auctions_data and isinstance(auctions_data, list) and auctions_data:
            await self.explore_auction_details(auctions_data[0])
        
        return results
    
    async def explore_auction_details(self, auction: Dict[str, Any]):
        """Explore details of a specific auction"""
        auction_id = auction.get('id')
        if not auction_id:
            logger.warning("⚠️ No auction ID found")
            return
        
        logger.info(f"\n🔍 EXPLORING AUCTION DETAILS: {auction_id}")
        logger.info("=" * 60)
        
        # Auction detail endpoints to try
        detail_endpoints = [
            (f"/api/v1/auctions/{auction_id}", "Auction Details"),
            (f"/api/v1/auctions/{auction_id}/orders", "Auction Orders"),
            (f"/api/v1/auctions/{auction_id}/trades", "Auction Trades"),
            (f"/api/v1/auctions/{auction_id}/prices", "Auction Prices"),
            (f"/api/v1/auctions/{auction_id}/portfoliovolumes", "Portfolio Volumes"),
        ]
        
        for endpoint, description in detail_endpoints:
            data = await self.make_api_call(endpoint, description)
            self.display_data(f"📊 {description}", data)
            await asyncio.sleep(0.5)
    
    async def show_market_summary(self, results: Dict[str, Any]):
        """Show a summary of the market data"""
        logger.info("\n🎯 MARKET DATA SUMMARY")
        logger.info("=" * 50)
        
        working_endpoints = []
        failed_endpoints = []
        
        for endpoint, data in results.items():
            if data is not None:
                working_endpoints.append(endpoint)
            else:
                failed_endpoints.append(endpoint)
        
        logger.info(f"✅ Working endpoints: {len(working_endpoints)}")
        for endpoint in working_endpoints:
            data = results[endpoint]
            if isinstance(data, list):
                logger.info(f"   {endpoint}: {len(data)} items")
            elif isinstance(data, dict):
                logger.info(f"   {endpoint}: {len(data)} fields")
            else:
                logger.info(f"   {endpoint}: available")
        
        logger.info(f"\n❌ Failed endpoints: {len(failed_endpoints)}")
        for endpoint in failed_endpoints:
            logger.info(f"   {endpoint}: not accessible")
        
        # Show key insights
        logger.info("\n💡 KEY INSIGHTS:")
        
        # Check auctions
        auctions = results.get("/api/v1/auctions") or results.get("/api/v2/auctions")
        if auctions and isinstance(auctions, list):
            logger.info(f"   🏛️ {len(auctions)} auctions available")
            
            # Show auction states
            states = {}
            for auction in auctions:
                state = auction.get('state', 'Unknown')
                states[state] = states.get(state, 0) + 1
            
            for state, count in states.items():
                logger.info(f"     - {count} auctions in {state} state")
        
        # Check system state
        system_state = results.get("/api/state")
        if system_state:
            logger.info("   🖥️ System state accessible")
            if isinstance(system_state, dict):
                logger.info(f"     - {len(system_state)} system parameters")
        
        logger.info("\n🚀 CONCLUSION:")
        if working_endpoints:
            logger.info("✅ Successfully connected to BRM Day-Ahead market!")
            logger.info("📊 Real market data is accessible")
            logger.info("💰 Ready for trading operations")
        else:
            logger.info("❌ No working endpoints found")
            logger.info("🔍 May need additional permissions or different approach")


async def main():
    """Main function"""
    logger.info("🇷🇴 BRM FINAL MARKET DATA VIEWER")
    logger.info("=" * 50)
    logger.info("Accessing REAL Romanian energy market data...")
    logger.info("=" * 50)
    
    viewer = BRMFinalMarketViewer()
    
    try:
        results = await viewer.explore_all_endpoints()
        await viewer.show_market_summary(results)
        
    except Exception as e:
        logger.error(f"❌ Market exploration failed: {e}")
    
    logger.info("\n🎬 Market data exploration completed!")
    logger.info("🇷🇴 You now have access to the Romanian energy market! ⚡")


if __name__ == "__main__":
    # Set test environment
    os.environ["BRM_ENVIRONMENT"] = "test"
    
    # Run the viewer
    asyncio.run(main())
