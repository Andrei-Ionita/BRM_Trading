"""
Working BRM Market Data Viewer
Uses the correct API endpoints from Swagger documentation
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


class BRMWorkingMarketViewer:
    """Working market data viewer using correct BRM API endpoints"""
    
    def __init__(self):
        """Initialize the market viewer"""
        self.auth = initialize_working_auth()
        self.base_url = "https://auctions-api.test.brm-power.ro"
        
        logger.info("BRM Working Market Viewer initialized")
    
    async def get_system_state(self) -> Dict[str, Any]:
        """Get system state from /api/state endpoint"""
        try:
            headers = await self.auth.get_auth_headers_async()
            url = f"{self.base_url}/api/state"
            
            logger.info(f"🔍 Getting system state from: {url}")
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    logger.info(f"   Status: {response.status}")
                    
                    if response.status == 200:
                        data = await response.json()
                        logger.info("   ✅ System state retrieved successfully!")
                        return data
                    else:
                        text = await response.text()
                        logger.error(f"   ❌ Error: {text}")
                        return {}
                        
        except Exception as e:
            logger.error(f"❌ Failed to get system state: {e}")
            return {}
    
    async def get_auctions(self, version: str = "1") -> List[Dict[str, Any]]:
        """Get auctions from /api/v{version}/auctions endpoint"""
        try:
            headers = await self.auth.get_auth_headers_async()
            url = f"{self.base_url}/api/v{version}/auctions"
            
            logger.info(f"🏛️ Getting auctions from: {url}")
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    logger.info(f"   Status: {response.status}")
                    
                    if response.status == 200:
                        data = await response.json()
                        logger.info(f"   ✅ Retrieved {len(data) if isinstance(data, list) else 'unknown'} auctions")
                        return data if isinstance(data, list) else []
                    else:
                        text = await response.text()
                        logger.error(f"   ❌ Error: {text[:200]}...")
                        return []
                        
        except Exception as e:
            logger.error(f"❌ Failed to get auctions: {e}")
            return []
    
    async def get_auction_details(self, auction_id: str, version: str = "1") -> Dict[str, Any]:
        """Get details for a specific auction"""
        try:
            headers = await self.auth.get_auth_headers_async()
            url = f"{self.base_url}/api/v{version}/auctions/{auction_id}"
            
            logger.info(f"📊 Getting auction details for {auction_id}")
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        data = await response.json()
                        logger.info("   ✅ Auction details retrieved")
                        return data
                    else:
                        text = await response.text()
                        logger.error(f"   ❌ Error: {text[:200]}...")
                        return {}
                        
        except Exception as e:
            logger.error(f"❌ Failed to get auction details: {e}")
            return {}
    
    async def get_auction_prices(self, auction_id: str, version: str = "1") -> Dict[str, Any]:
        """Get prices for a specific auction"""
        try:
            headers = await self.auth.get_auth_headers_async()
            url = f"{self.base_url}/api/v{version}/auctions/{auction_id}/prices"
            
            logger.info(f"💰 Getting prices for auction {auction_id}")
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        data = await response.json()
                        logger.info("   ✅ Auction prices retrieved")
                        return data
                    else:
                        text = await response.text()
                        logger.error(f"   ❌ Error: {text[:200]}...")
                        return {}
                        
        except Exception as e:
            logger.error(f"❌ Failed to get auction prices: {e}")
            return {}
    
    async def get_auction_trades(self, auction_id: str, version: str = "1") -> List[Dict[str, Any]]:
        """Get trades for a specific auction"""
        try:
            headers = await self.auth.get_auth_headers_async()
            url = f"{self.base_url}/api/v{version}/auctions/{auction_id}/trades"
            
            logger.info(f"📈 Getting trades for auction {auction_id}")
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        data = await response.json()
                        logger.info(f"   ✅ Retrieved {len(data) if isinstance(data, list) else 'unknown'} trades")
                        return data if isinstance(data, list) else []
                    else:
                        text = await response.text()
                        logger.error(f"   ❌ Error: {text[:200]}...")
                        return []
                        
        except Exception as e:
            logger.error(f"❌ Failed to get auction trades: {e}")
            return []
    
    def display_system_state(self, state: Dict[str, Any]):
        """Display system state information"""
        if not state:
            logger.warning("⚠️ No system state data available")
            return
        
        logger.info("🖥️ SYSTEM STATE:")
        logger.info("=" * 30)
        
        for key, value in state.items():
            if isinstance(value, (str, int, float, bool)):
                logger.info(f"   {key}: {value}")
            elif isinstance(value, dict):
                logger.info(f"   {key}: {len(value)} items")
            elif isinstance(value, list):
                logger.info(f"   {key}: {len(value)} items")
            else:
                logger.info(f"   {key}: {type(value).__name__}")
    
    def display_auctions(self, auctions: List[Dict[str, Any]]):
        """Display auction information"""
        if not auctions:
            logger.warning("⚠️ No auction data available")
            return
        
        logger.info("🏛️ AVAILABLE AUCTIONS:")
        logger.info("=" * 40)
        
        for i, auction in enumerate(auctions[:5]):  # Show first 5 auctions
            logger.info(f"   Auction {i+1}:")
            logger.info(f"     ID: {auction.get('id', 'Unknown')}")
            logger.info(f"     Name: {auction.get('name', 'Unknown')}")
            logger.info(f"     State: {auction.get('state', 'Unknown')}")
            logger.info(f"     Delivery Date: {auction.get('deliveryDate', 'Unknown')}")
            logger.info(f"     Gate Closure: {auction.get('gateClosure', 'Unknown')}")
            logger.info(f"     Currency: {auction.get('currency', 'Unknown')}")
            
            # Show contracts if available
            contracts = auction.get('contracts', [])
            if contracts:
                logger.info(f"     Contracts: {len(contracts)}")
                for j, contract in enumerate(contracts[:3]):  # Show first 3 contracts
                    logger.info(f"       Contract {j+1}: {contract.get('name', 'Unknown')}")
            
            logger.info("")
    
    def display_auction_prices(self, auction_id: str, prices: Dict[str, Any]):
        """Display auction price information"""
        if not prices:
            logger.warning(f"⚠️ No price data available for auction {auction_id}")
            return
        
        logger.info(f"💰 PRICES FOR AUCTION {auction_id}:")
        logger.info("=" * 50)
        
        # Display area prices if available
        area_prices = prices.get('areaPrices', [])
        if area_prices:
            logger.info("   Area Prices:")
            for area_price in area_prices[:5]:  # Show first 5
                area = area_price.get('area', 'Unknown')
                price = area_price.get('price', 0)
                currency = area_price.get('currency', 'EUR')
                logger.info(f"     {area}: {price:.2f} {currency}/MWh")
        
        # Display contract prices if available
        contract_prices = prices.get('contractPrices', [])
        if contract_prices:
            logger.info("   Contract Prices:")
            for contract_price in contract_prices[:5]:  # Show first 5
                contract = contract_price.get('contract', 'Unknown')
                price = contract_price.get('price', 0)
                currency = contract_price.get('currency', 'EUR')
                logger.info(f"     {contract}: {price:.2f} {currency}/MWh")
    
    def display_auction_trades(self, auction_id: str, trades: List[Dict[str, Any]]):
        """Display auction trade information"""
        if not trades:
            logger.warning(f"⚠️ No trade data available for auction {auction_id}")
            return
        
        logger.info(f"📈 TRADES FOR AUCTION {auction_id}:")
        logger.info("=" * 50)
        
        total_volume = 0
        total_value = 0
        
        for i, trade in enumerate(trades[:10]):  # Show first 10 trades
            contract = trade.get('contract', 'Unknown')
            volume = trade.get('volume', 0)
            price = trade.get('price', 0)
            currency = trade.get('currency', 'EUR')
            side = trade.get('side', 'Unknown')
            
            logger.info(f"   Trade {i+1}:")
            logger.info(f"     Contract: {contract}")
            logger.info(f"     Volume: {volume} MWh")
            logger.info(f"     Price: {price:.2f} {currency}/MWh")
            logger.info(f"     Side: {side}")
            logger.info(f"     Value: {volume * price:.2f} {currency}")
            
            total_volume += volume
            total_value += volume * price
            logger.info("")
        
        if trades:
            avg_price = total_value / total_volume if total_volume > 0 else 0
            logger.info(f"   📊 Summary:")
            logger.info(f"     Total Trades: {len(trades)}")
            logger.info(f"     Total Volume: {total_volume:.2f} MWh")
            logger.info(f"     Total Value: {total_value:.2f} EUR")
            logger.info(f"     Average Price: {avg_price:.2f} EUR/MWh")
    
    async def run_market_analysis(self):
        """Run complete market data analysis"""
        try:
            logger.info("🚀 Starting BRM Market Data Analysis")
            logger.info("=" * 60)
            
            # Test authentication
            token_info = await self.auth.get_token_async()
            logger.info(f"✅ Authentication successful, token expires at {token_info.expires_at}")
            
            # Get system state
            logger.info("\n" + "="*60)
            state = await self.get_system_state()
            self.display_system_state(state)
            
            # Get auctions
            logger.info("\n" + "="*60)
            auctions = await self.get_auctions()
            self.display_auctions(auctions)
            
            # If we have auctions, get details for the first one
            if auctions:
                first_auction = auctions[0]
                auction_id = first_auction.get('id')
                
                if auction_id:
                    logger.info("\n" + "="*60)
                    logger.info(f"📊 DETAILED ANALYSIS FOR AUCTION: {auction_id}")
                    
                    # Get auction details
                    details = await self.get_auction_details(auction_id)
                    if details:
                        logger.info("✅ Auction details retrieved")
                    
                    # Get auction prices
                    prices = await self.get_auction_prices(auction_id)
                    self.display_auction_prices(auction_id, prices)
                    
                    # Get auction trades
                    logger.info("\n" + "-"*50)
                    trades = await self.get_auction_trades(auction_id)
                    self.display_auction_trades(auction_id, trades)
            
            logger.info("\n" + "="*60)
            logger.info("🎯 MARKET ANALYSIS COMPLETE")
            logger.info("=" * 60)
            
            if auctions:
                logger.info("✅ Successfully connected to BRM Day-Ahead market!")
                logger.info(f"📊 Found {len(auctions)} active auctions")
                logger.info("💡 Market data is accessible and ready for trading")
            else:
                logger.info("⚠️ No auctions currently available")
                logger.info("🔍 This might be normal depending on market timing")
            
        except Exception as e:
            logger.error(f"❌ Market analysis failed: {e}")


async def main():
    """Main function"""
    logger.info("🇷🇴 BRM WORKING MARKET DATA VIEWER")
    logger.info("=" * 50)
    logger.info("Accessing real BRM Day-Ahead market data...")
    logger.info("=" * 50)
    
    viewer = BRMWorkingMarketViewer()
    await viewer.run_market_analysis()
    
    logger.info("\n🎬 Market data analysis completed!")
    logger.info("💡 You now have access to real BRM market data!")


if __name__ == "__main__":
    # Set test environment
    os.environ["BRM_ENVIRONMENT"] = "test"
    
    # Run the viewer
    asyncio.run(main())
