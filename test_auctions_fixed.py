"""
Test BRM Auctions API with correct parameters - Fixed version
"""
import asyncio
import logging
import aiohttp
from datetime import datetime, timedelta
import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from auth_working import initialize_working_auth

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_auctions_with_params():
    """Test auctions API with proper parameters"""
    
    logger.info("🧪 Testing BRM Auctions API with correct parameters")
    logger.info("=" * 70)
    
    # Initialize authentication
    auth = initialize_working_auth()
    
    try:
        # Get authentication token
        token_info = await auth.get_token_async()
        logger.info(f"✅ Authentication successful, token expires at {token_info.expires_at}")
        
        headers = await auth.get_auth_headers_async()
        base_url = "https://auctions-api.test.brm-power.ro"
        
        # Test different versions and parameters
        test_cases = [
            {
                "version": "1",
                "description": "Version 1 - No date filters"
            },
            {
                "version": "2", 
                "description": "Version 2 - No date filters"
            },
            {
                "version": "1",
                "closeBiddingFrom": (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%dT%H:%M:%S'),
                "closeBiddingTo": (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%dT%H:%M:%S'),
                "description": "Version 1 - With date range (last 7 days to tomorrow)"
            }
        ]
        
        async with aiohttp.ClientSession() as session:
            for i, test_case in enumerate(test_cases, 1):
                logger.info(f"🔍 Test {i}/{len(test_cases)}: {test_case['description']}")
                
                # Build URL with version
                version = test_case.pop('version')
                description = test_case.pop('description')
                
                url = f"{base_url}/api/v{version}/auctions"
                
                # Add query parameters if any
                params = {}
                if 'closeBiddingFrom' in test_case:
                    params['closeBiddingFrom'] = test_case['closeBiddingFrom']
                if 'closeBiddingTo' in test_case:
                    params['closeBiddingTo'] = test_case['closeBiddingTo']
                
                logger.info(f"   URL: {url}")
                if params:
                    logger.info(f"   Params: {params}")
                
                try:
                    async with session.get(
                        url,
                        headers=headers,
                        params=params,
                        timeout=aiohttp.ClientTimeout(total=15)
                    ) as response:
                        
                        logger.info(f"   Status: {response.status}")
                        
                        if response.status == 200:
                            data = await response.json()
                            logger.info(f"   ✅ SUCCESS! Got {type(data).__name__}")
                            
                            if isinstance(data, list):
                                logger.info(f"   📊 Found {len(data)} auctions")
                                
                                # Show details of first few auctions
                                for j, auction in enumerate(data[:3], 1):
                                    auction_id = auction.get('id', 'Unknown')
                                    name = auction.get('name', 'Unknown')
                                    state = auction.get('state', 'Unknown')
                                    start_time = auction.get('startTime', 'Unknown')
                                    end_time = auction.get('endTime', 'Unknown')
                                    
                                    logger.info(f"      🎯 Auction {j}: {auction_id}")
                                    logger.info(f"         Name: {name}")
                                    logger.info(f"         State: {state}")
                                    logger.info(f"         Period: {start_time} - {end_time}")
                                
                                if len(data) > 3:
                                    logger.info(f"      ... and {len(data) - 3} more auctions")
                                
                                # If we found auctions, test getting details for the first one
                                if data:
                                    first_auction = data[0]
                                    auction_id = first_auction.get('id')
                                    
                                    if auction_id:
                                        logger.info(f"   🔍 Testing auction details for: {auction_id}")
                                        
                                        # Test auction details
                                        detail_url = f"{base_url}/api/v{version}/auctions/{auction_id}"
                                        async with session.get(detail_url, headers=headers) as detail_response:
                                            logger.info(f"      Details Status: {detail_response.status}")
                                            
                                            if detail_response.status == 200:
                                                detail_data = await detail_response.json()
                                                logger.info(f"      ✅ Got auction details!")
                                                
                                                # Show key details
                                                key_fields = ['name', 'state', 'auctionType', 'marketType', 'currency']
                                                for field in key_fields:
                                                    value = detail_data.get(field, 'Not specified')
                                                    logger.info(f"         {field}: {value}")
                                        
                                        # Test auction orders
                                        orders_url = f"{base_url}/api/v{version}/auctions/{auction_id}/orders"
                                        async with session.get(orders_url, headers=headers) as orders_response:
                                            logger.info(f"      Orders Status: {orders_response.status}")
                                            
                                            if orders_response.status == 200:
                                                orders_data = await orders_response.json()
                                                if isinstance(orders_data, list):
                                                    logger.info(f"      ✅ Found {len(orders_data)} orders!")
                                                else:
                                                    logger.info(f"      ✅ Got orders data!")
                                            elif orders_response.status == 403:
                                                logger.info(f"      ⚠️ Orders access forbidden")
                                            elif orders_response.status == 404:
                                                logger.info(f"      ⚠️ No orders found")
                                        
                                        # Test auction trades
                                        trades_url = f"{base_url}/api/v{version}/auctions/{auction_id}/trades"
                                        async with session.get(trades_url, headers=headers) as trades_response:
                                            logger.info(f"      Trades Status: {trades_response.status}")
                                            
                                            if trades_response.status == 200:
                                                trades_data = await trades_response.json()
                                                if isinstance(trades_data, list):
                                                    logger.info(f"      ✅ Found {len(trades_data)} trades!")
                                                else:
                                                    logger.info(f"      ✅ Got trades data!")
                                            elif trades_response.status == 403:
                                                logger.info(f"      ⚠️ Trades access forbidden")
                                            elif trades_response.status == 404:
                                                logger.info(f"      ⚠️ No trades found")
                                        
                                        # Test auction prices
                                        prices_url = f"{base_url}/api/v{version}/auctions/{auction_id}/prices"
                                        async with session.get(prices_url, headers=headers) as prices_response:
                                            logger.info(f"      Prices Status: {prices_response.status}")
                                            
                                            if prices_response.status == 200:
                                                prices_data = await prices_response.json()
                                                if isinstance(prices_data, list):
                                                    logger.info(f"      ✅ Found {len(prices_data)} price points!")
                                                else:
                                                    logger.info(f"      ✅ Got prices data!")
                                            elif prices_response.status == 403:
                                                logger.info(f"      ⚠️ Prices access forbidden")
                                            elif prices_response.status == 404:
                                                logger.info(f"      ⚠️ No prices found")
                            
                            elif isinstance(data, dict):
                                logger.info(f"   📊 Got dictionary with {len(data)} fields")
                                for key, value in list(data.items())[:5]:
                                    logger.info(f"      {key}: {value}")
                            else:
                                logger.info(f"   📄 Data: {str(data)[:200]}...")
                                
                        elif response.status == 403:
                            logger.info(f"   ⚠️ Forbidden - Access denied")
                        elif response.status == 404:
                            logger.info(f"   ⚠️ Not Found - No auctions match criteria")
                        elif response.status == 400:
                            error_text = await response.text()
                            logger.info(f"   ❌ Bad Request: {error_text[:200]}...")
                        else:
                            error_text = await response.text()
                            logger.info(f"   ❌ Error {response.status}: {error_text[:200]}...")
                            
                except Exception as e:
                    logger.error(f"   ❌ Exception: {e}")
                
                logger.info("")
        
        logger.info("📊 SUMMARY")
        logger.info("=" * 50)
        logger.info("✅ Tested multiple API versions and parameter combinations")
        logger.info("🎯 If any tests succeeded, your BRM market data access is working!")
        logger.info("⚠️ If all tests failed with 403/404, contact BRM about test data availability")
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")


if __name__ == "__main__":
    # Set test environment
    os.environ["BRM_ENVIRONMENT"] = "test"
    
    # Run the test
    asyncio.run(test_auctions_with_params())
