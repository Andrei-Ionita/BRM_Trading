"""
Comprehensive search for BRM Intraday API endpoints
"""
import asyncio
import logging
import aiohttp
import sys
import os
from urllib.parse import urljoin

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from auth_working import initialize_working_auth

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def find_intraday_endpoints():
    """Comprehensive search for intraday API endpoints"""
    
    logger.info("🔍 Comprehensive BRM Intraday API Endpoint Discovery")
    logger.info("=" * 70)
    
    # Initialize authentication
    auth = initialize_working_auth()
    
    try:
        # Get authentication token
        token_info = await auth.get_token_async()
        logger.info(f"✅ Authentication successful, token expires at {token_info.expires_at}")
        
        headers = {
            "Authorization": f"Bearer {token_info.access_token}",
            "Accept": "application/json",
            "User-Agent": "BRM-Trading-Bot/1.0"
        }
        
        # Base URLs to test (from the email and variations)
        base_urls = [
            # From the email
            "https://intraday2-api.test.nordpoolgroup.com",
            "https://intraday2-api.nordpoolgroup.com",
            
            # BRM specific variations
            "https://intraday-api.test.brm-power.ro",
            "https://intraday-api.brm-power.ro",
            "https://intraday2-api.test.brm-power.ro",
            "https://intraday2-api.brm-power.ro",
            
            # Alternative patterns
            "https://api.test.brm-power.ro/intraday",
            "https://api.brm-power.ro/intraday",
            "https://test.brm-power.ro/intraday-api",
            "https://brm-power.ro/intraday-api",
            
            # Nord Pool variations
            "https://intraday-api.test.nordpoolgroup.com",
            "https://intraday-api.nordpoolgroup.com",
        ]
        
        # Common API paths to test
        api_paths = [
            "/",
            "/api",
            "/swagger",
            "/swagger/index.html",
            "/swagger/v1/swagger.json",
            "/health",
            "/status",
            "/ping",
            "/version",
            "/info",
            "/docs",
            "/openapi.json",
            "/v1",
            "/v2",
            "/api/v1",
            "/api/v2",
            "/api/state",
            "/api/orders",
            "/api/trades",
            "/api/contracts",
            "/api/areas",
            "/api/portfolios",
        ]
        
        connector = aiohttp.TCPConnector(ssl=False)  # Disable SSL verification for testing
        timeout = aiohttp.ClientTimeout(total=10)
        
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            
            for base_url in base_urls:
                logger.info(f"🌐 Testing base URL: {base_url}")
                
                successful_endpoints = []
                
                for path in api_paths:
                    url = urljoin(base_url, path)
                    
                    try:
                        async with session.get(url, headers=headers) as response:
                            status = response.status
                            
                            if status == 200:
                                logger.info(f"   ✅ {path}: Status {status}")
                                successful_endpoints.append((path, status))
                                
                                try:
                                    # Try to get content
                                    content_type = response.headers.get('content-type', '')
                                    if 'json' in content_type:
                                        data = await response.json()
                                        logger.info(f"      📊 JSON response: {type(data).__name__}")
                                        if isinstance(data, dict):
                                            logger.info(f"      🔑 Keys: {list(data.keys())[:5]}")
                                        elif isinstance(data, list):
                                            logger.info(f"      📋 Items: {len(data)}")
                                    else:
                                        text = await response.text()
                                        if 'swagger' in text.lower() or 'openapi' in text.lower():
                                            logger.info(f"      📖 Found Swagger/OpenAPI documentation!")
                                        elif len(text) < 200:
                                            logger.info(f"      📄 Text: {text}")
                                        else:
                                            logger.info(f"      📄 Text length: {len(text)} chars")
                                            
                                except Exception as e:
                                    logger.info(f"      ⚠️ Could not parse response: {e}")
                            
                            elif status == 401:
                                logger.info(f"   🔐 {path}: Status {status} (Unauthorized - token issue)")
                                successful_endpoints.append((path, status))
                            
                            elif status == 403:
                                logger.info(f"   ⚠️ {path}: Status {status} (Forbidden - need permissions)")
                                successful_endpoints.append((path, status))
                            
                            elif status == 404:
                                # Don't log 404s to reduce noise
                                pass
                            
                            elif status in [301, 302, 307, 308]:
                                location = response.headers.get('location', 'Unknown')
                                logger.info(f"   🔄 {path}: Status {status} (Redirect to {location})")
                                successful_endpoints.append((path, status))
                            
                            else:
                                logger.info(f"   ❓ {path}: Status {status}")
                                successful_endpoints.append((path, status))
                    
                    except aiohttp.ClientError as e:
                        if "SSL" not in str(e) and "timeout" not in str(e).lower():
                            logger.info(f"   ❌ {path}: {type(e).__name__}")
                    except Exception as e:
                        if "SSL" not in str(e) and "timeout" not in str(e).lower():
                            logger.info(f"   ❌ {path}: {e}")
                
                if successful_endpoints:
                    logger.info(f"   🎯 Found {len(successful_endpoints)} accessible endpoints!")
                    for path, status in successful_endpoints:
                        logger.info(f"      ✅ {path} -> {status}")
                else:
                    logger.info(f"   ❌ No accessible endpoints found")
                
                logger.info("")
        
        # Test WebSocket endpoints
        logger.info("🔌 Testing WebSocket endpoints...")
        
        websocket_urls = [
            "wss://intraday-pmd-api-ws-brm.test.nordpoolgroup.com",
            "wss://intraday-pmd-api-ws-brm.nordpoolgroup.com",
            "wss://intraday2-api.test.nordpoolgroup.com",
            "wss://intraday2-api.nordpoolgroup.com",
            "wss://ws.test.brm-power.ro",
            "wss://ws.brm-power.ro",
            "wss://intraday-ws.test.brm-power.ro",
            "wss://intraday-ws.brm-power.ro",
        ]
        
        for ws_url in websocket_urls:
            logger.info(f"🔌 Testing WebSocket: {ws_url}")
            
            try:
                ws_headers = {
                    "Authorization": f"Bearer {token_info.access_token}",
                    "User-Agent": "BRM-Trading-Bot/1.0"
                }
                
                async with session.ws_connect(ws_url, headers=ws_headers, timeout=5) as ws:
                    logger.info(f"   ✅ WebSocket connection successful!")
                    
                    # Try to send a simple message
                    await ws.send_str("CONNECT\naccept-version:1.0\n\n\x00")
                    
                    # Wait for response
                    try:
                        msg = await asyncio.wait_for(ws.receive(), timeout=5)
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            logger.info(f"   📨 Received: {msg.data[:100]}...")
                        else:
                            logger.info(f"   📨 Received message type: {msg.type}")
                    except asyncio.TimeoutError:
                        logger.info(f"   ⏰ No response within 5 seconds")
                    
                    break  # If successful, don't test other URLs
                    
            except aiohttp.ClientError as e:
                logger.info(f"   ❌ WebSocket failed: {type(e).__name__}: {e}")
            except Exception as e:
                logger.info(f"   ❌ WebSocket error: {e}")
        
        logger.info("")
        logger.info("📊 SUMMARY")
        logger.info("=" * 50)
        logger.info("✅ Tested comprehensive list of potential BRM Intraday API endpoints")
        logger.info("🎯 Any successful endpoints above are candidates for real-time market data")
        logger.info("📞 If no endpoints worked, contact BRM for correct intraday API URLs")
        
    except Exception as e:
        logger.error(f"❌ Endpoint discovery failed: {e}")


if __name__ == "__main__":
    # Set test environment
    os.environ["BRM_ENVIRONMENT"] = "test"
    
    # Run the endpoint discovery
    asyncio.run(find_intraday_endpoints())
