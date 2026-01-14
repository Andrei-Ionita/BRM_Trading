"""
BRM Market Data Viewer using REST API
Shows current market state, contracts, and available data
"""
import asyncio
import logging
import json
import aiohttp
from datetime import datetime
from typing import Dict, Any, List
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


class BRMMarketDataViewer:
    """Market data viewer using REST APIs"""
    
    def __init__(self):
        """Initialize the market data viewer"""
        self.auth = initialize_working_auth()
        
        # API endpoints to try
        self.endpoints = {
            "day_ahead_base": "https://auctions-api.test.brm-power.ro/api/v1",
            "intraday_base": "https://intraday2-api.test.nordpoolgroup.com",
            "nordpool_base": "https://api.nordpoolgroup.com"
        }
        
        logger.info("BRM Market Data Viewer initialized")
    
    async def test_endpoint(self, name: str, url: str, headers: Dict[str, str]) -> Dict[str, Any]:
        """Test an API endpoint"""
        try:
            logger.info(f"🔍 Testing {name}: {url}")
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    logger.info(f"   Status: {response.status}")
                    
                    if response.status == 200:
                        try:
                            data = await response.json()
                            logger.info(f"   ✅ Success! Data type: {type(data)}")
                            if isinstance(data, list):
                                logger.info(f"   📊 List with {len(data)} items")
                            elif isinstance(data, dict):
                                logger.info(f"   📊 Dict with keys: {list(data.keys())[:5]}")
                            return {"success": True, "data": data, "status": response.status}
                        except:
                            text = await response.text()
                            logger.info(f"   📄 Text response: {text[:200]}...")
                            return {"success": True, "data": text, "status": response.status}
                    else:
                        text = await response.text()
                        logger.info(f"   ❌ Error: {text[:200]}...")
                        return {"success": False, "error": text, "status": response.status}
                        
        except Exception as e:
            logger.error(f"   ❌ Exception: {e}")
            return {"success": False, "error": str(e), "status": None}
    
    async def explore_day_ahead_api(self):
        """Explore Day-Ahead API endpoints"""
        logger.info("📊 Exploring Day-Ahead API...")
        
        headers = await self.auth.get_auth_headers_async()
        base_url = self.endpoints["day_ahead_base"]
        
        endpoints_to_try = [
            ("auctions", f"{base_url}/auctions"),
            ("system", f"{base_url}/system"),
            ("system/state", f"{base_url}/system/state"),
            ("portfolios", f"{base_url}/portfolios"),
            ("contracts", f"{base_url}/contracts"),
            ("orders", f"{base_url}/orders"),
            ("positions", f"{base_url}/positions"),
            ("trades", f"{base_url}/trades"),
            ("marketdata", f"{base_url}/marketdata"),
        ]
        
        results = {}
        for name, url in endpoints_to_try:
            result = await self.test_endpoint(f"Day-Ahead {name}", url, headers)
            results[name] = result
            await asyncio.sleep(0.5)  # Be nice to the API
        
        return results
    
    async def explore_intraday_api(self):
        """Explore Intraday API endpoints"""
        logger.info("🌐 Exploring Intraday API...")
        
        headers = await self.auth.get_auth_headers_async()
        base_url = self.endpoints["intraday_base"]
        
        endpoints_to_try = [
            ("root", base_url),
            ("api", f"{base_url}/api"),
            ("v1", f"{base_url}/api/v1"),
            ("contracts", f"{base_url}/api/v1/contracts"),
            ("marketdata", f"{base_url}/api/v1/marketdata"),
            ("orders", f"{base_url}/api/v1/orders"),
            ("portfolios", f"{base_url}/api/v1/portfolios"),
            ("system", f"{base_url}/api/v1/system"),
            ("configuration", f"{base_url}/api/v1/configuration"),
        ]
        
        results = {}
        for name, url in endpoints_to_try:
            result = await self.test_endpoint(f"Intraday {name}", url, headers)
            results[name] = result
            await asyncio.sleep(0.5)  # Be nice to the API
        
        return results
    
    async def try_different_websocket_urls(self):
        """Try different WebSocket URLs to find the working one"""
        logger.info("🌐 Testing different WebSocket URLs...")
        
        token_info = await self.auth.get_token_async()
        headers = {
            "Authorization": token_info.bearer_token,
            "User-Agent": "BRM-Trading-Bot/1.0"
        }
        
        websocket_urls = [
            "wss://intraday-pmd-api-ws-brm.test.nordpoolgroup.com/",
            "wss://intraday-pmd-api-ws-brm.test.nordpoolgroup.com/websocket",
            "wss://intraday-pmd-api-ws-brm.test.nordpoolgroup.com/stomp",
            "wss://intraday2-api.test.nordpoolgroup.com/websocket",
            "wss://intraday2-api.test.nordpoolgroup.com/stomp",
            "wss://api.test.nordpoolgroup.com/websocket",
        ]
        
        for ws_url in websocket_urls:
            try:
                logger.info(f"🔍 Testing WebSocket: {ws_url}")
                
                async with aiohttp.ClientSession() as session:
                    try:
                        async with session.ws_connect(
                            ws_url,
                            headers=headers,
                            timeout=aiohttp.ClientTimeout(total=5)
                        ) as ws:
                            logger.info(f"   ✅ Connection successful!")
                            
                            # Try sending a simple message
                            await ws.send_str("CONNECT\naccept-version:1.0\n\n\x00")
                            
                            # Wait for response
                            try:
                                msg = await asyncio.wait_for(ws.receive(), timeout=3)
                                if msg.type == aiohttp.WSMsgType.TEXT:
                                    logger.info(f"   📥 Response: {msg.data[:100]}...")
                                    return ws_url  # Found working URL!
                            except asyncio.TimeoutError:
                                logger.info("   ⏰ No response received")
                                
                    except Exception as e:
                        logger.info(f"   ❌ Failed: {type(e).__name__}: {e}")
                        
            except Exception as e:
                logger.info(f"   ❌ Connection failed: {e}")
        
        return None
    
    async def show_market_summary(self, day_ahead_results: Dict, intraday_results: Dict):
        """Show a summary of available market data"""
        logger.info("📊 MARKET DATA SUMMARY")
        logger.info("=" * 50)
        
        # Day-Ahead summary
        logger.info("🏛️ Day-Ahead Market:")
        successful_da = [name for name, result in day_ahead_results.items() if result.get("success")]
        failed_da = [name for name, result in day_ahead_results.items() if not result.get("success")]
        
        logger.info(f"   ✅ Working endpoints: {len(successful_da)}")
        for name in successful_da:
            result = day_ahead_results[name]
            data = result.get("data", {})
            if isinstance(data, list):
                logger.info(f"     - {name}: {len(data)} items")
            elif isinstance(data, dict):
                logger.info(f"     - {name}: {len(data)} fields")
            else:
                logger.info(f"     - {name}: available")
        
        logger.info(f"   ❌ Failed endpoints: {len(failed_da)}")
        for name in failed_da:
            status = day_ahead_results[name].get("status", "unknown")
            logger.info(f"     - {name}: HTTP {status}")
        
        # Intraday summary
        logger.info("\n⚡ Intraday Market:")
        successful_id = [name for name, result in intraday_results.items() if result.get("success")]
        failed_id = [name for name, result in intraday_results.items() if not result.get("success")]
        
        logger.info(f"   ✅ Working endpoints: {len(successful_id)}")
        for name in successful_id:
            result = intraday_results[name]
            data = result.get("data", {})
            if isinstance(data, list):
                logger.info(f"     - {name}: {len(data)} items")
            elif isinstance(data, dict):
                logger.info(f"     - {name}: {len(data)} fields")
            else:
                logger.info(f"     - {name}: available")
        
        logger.info(f"   ❌ Failed endpoints: {len(failed_id)}")
        for name in failed_id:
            status = intraday_results[name].get("status", "unknown")
            logger.info(f"     - {name}: HTTP {status}")
        
        # Show sample data from successful endpoints
        logger.info("\n📋 Sample Data:")
        
        # Show Day-Ahead auctions if available
        if "auctions" in day_ahead_results and day_ahead_results["auctions"].get("success"):
            auctions = day_ahead_results["auctions"]["data"]
            if isinstance(auctions, list) and auctions:
                logger.info("   🏛️ Day-Ahead Auctions:")
                for auction in auctions[:3]:
                    if isinstance(auction, dict):
                        logger.info(f"     - ID: {auction.get('id', 'Unknown')}")
                        logger.info(f"       Name: {auction.get('name', 'Unknown')}")
                        logger.info(f"       State: {auction.get('state', 'Unknown')}")
                        logger.info(f"       Delivery: {auction.get('deliveryDate', 'Unknown')}")
        
        # Show any successful intraday data
        for name, result in intraday_results.items():
            if result.get("success") and isinstance(result.get("data"), (list, dict)):
                data = result["data"]
                if isinstance(data, list) and data:
                    logger.info(f"   ⚡ Intraday {name}:")
                    logger.info(f"     - {len(data)} items available")
                    if isinstance(data[0], dict):
                        logger.info(f"     - Sample keys: {list(data[0].keys())[:5]}")
                elif isinstance(data, dict) and data:
                    logger.info(f"   ⚡ Intraday {name}:")
                    logger.info(f"     - Keys: {list(data.keys())[:5]}")
                break
    
    async def run_market_exploration(self):
        """Run complete market data exploration"""
        try:
            logger.info("🚀 Starting BRM Market Data Exploration")
            logger.info("=" * 60)
            
            # Test authentication
            token_info = await self.auth.get_token_async()
            logger.info(f"✅ Authentication successful, token expires at {token_info.expires_at}")
            
            # Explore Day-Ahead API
            day_ahead_results = await self.explore_day_ahead_api()
            
            # Explore Intraday API
            intraday_results = await self.explore_intraday_api()
            
            # Try WebSocket URLs
            working_ws_url = await self.try_different_websocket_urls()
            if working_ws_url:
                logger.info(f"✅ Found working WebSocket URL: {working_ws_url}")
            else:
                logger.info("❌ No working WebSocket URL found")
            
            # Show summary
            await self.show_market_summary(day_ahead_results, intraday_results)
            
            logger.info("\n🎯 CONCLUSION:")
            logger.info("=" * 30)
            
            total_working = sum(1 for r in day_ahead_results.values() if r.get("success")) + \
                           sum(1 for r in intraday_results.values() if r.get("success"))
            
            if total_working > 0:
                logger.info(f"✅ Found {total_working} working API endpoints!")
                logger.info("📊 Market data is accessible through REST APIs")
                if working_ws_url:
                    logger.info("🌐 Real-time WebSocket connection is also available")
                else:
                    logger.info("⚠️ WebSocket connection needs further investigation")
            else:
                logger.info("❌ No working API endpoints found")
                logger.info("🔍 May need different authentication or endpoint URLs")
            
        except Exception as e:
            logger.error(f"❌ Market exploration failed: {e}")


async def main():
    """Main function"""
    logger.info("🇷🇴 BRM MARKET DATA EXPLORATION")
    logger.info("=" * 50)
    logger.info("Discovering available market data and APIs...")
    logger.info("=" * 50)
    
    viewer = BRMMarketDataViewer()
    await viewer.run_market_exploration()
    
    logger.info("\n🎬 Market data exploration completed!")


if __name__ == "__main__":
    # Set test environment
    os.environ["BRM_ENVIRONMENT"] = "test"
    
    # Run the exploration
    asyncio.run(main())
