"""
Discover Available Intraday API Endpoints
Find what endpoints are actually available on the BRM intraday API
"""

import requests
import json
import logging
from intraday_auth import IntradayAuthenticator

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def discover_endpoints():
    """Discover available endpoints on the intraday API"""
    
    auth = IntradayAuthenticator()
    headers = auth.get_auth_headers()
    
    if not headers:
        logger.error("Failed to get auth headers")
        return
    
    base_url = "https://intraday2-api.test.nordpoolgroup.com"
    
    # Common endpoint patterns to try
    endpoints_to_try = [
        "/",
        "/api",
        "/api/v1",
        "/api/v2",
        "/swagger",
        "/swagger/index.html",
        "/docs",
        "/health",
        "/status",
        "/ping",
        "/info",
        "/version",
        "/openapi.json",
        "/api-docs",
        "/api/swagger.json",
        "/api/v1/swagger.json",
        "/api/v1/health",
        "/api/v1/ping",
        "/api/v1/info",
        "/api/v1/status",
        "/api/v1/version",
        "/api/v1/contracts",
        "/api/v1/deliveryareas",
        "/api/v1/trades",
        "/api/v1/marketdata",
        "/api/v1/capacities",
        "/api/v1/orders",
        "/api/v1/positions",
        "/api/v1/portfolio",
        "/api/v1/tickers",
        "/api/v1/orderbook",
        "/api/v2/contracts",
        "/api/v2/trades",
        "/api/v2/marketdata",
        "/contracts",
        "/trades",
        "/marketdata",
        "/deliveryareas",
        "/capacities",
        "/orders",
        "/tickers",
        "/orderbook"
    ]
    
    found_endpoints = []
    
    logger.info(f"🔍 Discovering endpoints on {base_url}")
    logger.info(f"Testing {len(endpoints_to_try)} potential endpoints...")
    
    for endpoint in endpoints_to_try:
        try:
            url = f"{base_url}{endpoint}"
            response = requests.get(url, headers=headers, timeout=10)
            
            status_code = response.status_code
            
            if status_code == 200:
                logger.info(f"✅ FOUND: {endpoint} (200 OK)")
                found_endpoints.append({
                    'endpoint': endpoint,
                    'status': status_code,
                    'content_type': response.headers.get('content-type', 'unknown'),
                    'content_length': len(response.content)
                })
                
                # Try to parse response
                try:
                    if 'application/json' in response.headers.get('content-type', ''):
                        data = response.json()
                        logger.info(f"    JSON keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
                    else:
                        content_preview = response.text[:200] if response.text else "No content"
                        logger.info(f"    Content preview: {content_preview}")
                except:
                    logger.info(f"    Content length: {len(response.content)} bytes")
                    
            elif status_code in [301, 302, 307, 308]:
                location = response.headers.get('location', 'No location header')
                logger.info(f"🔄 REDIRECT: {endpoint} -> {location}")
                found_endpoints.append({
                    'endpoint': endpoint,
                    'status': status_code,
                    'redirect_to': location
                })
                
            elif status_code == 401:
                logger.info(f"🔐 AUTH REQUIRED: {endpoint} (401 Unauthorized)")
                
            elif status_code == 403:
                logger.info(f"🚫 FORBIDDEN: {endpoint} (403 Forbidden)")
                
            elif status_code == 405:
                logger.info(f"📝 METHOD NOT ALLOWED: {endpoint} (405 - try different HTTP method)")
                
            elif status_code != 404:
                logger.info(f"❓ UNKNOWN: {endpoint} ({status_code})")
                
        except requests.exceptions.Timeout:
            logger.warning(f"⏰ TIMEOUT: {endpoint}")
        except requests.exceptions.ConnectionError:
            logger.warning(f"🔌 CONNECTION ERROR: {endpoint}")
        except Exception as e:
            logger.warning(f"❌ ERROR: {endpoint} - {e}")
    
    # Summary
    logger.info(f"\n📊 Discovery Summary:")
    logger.info(f"Found {len(found_endpoints)} accessible endpoints:")
    
    for endpoint_info in found_endpoints:
        endpoint = endpoint_info['endpoint']
        status = endpoint_info['status']
        logger.info(f"  {endpoint} - HTTP {status}")
    
    return found_endpoints

def test_root_endpoint():
    """Test the root endpoint to see what's available"""
    
    auth = IntradayAuthenticator()
    headers = auth.get_auth_headers()
    
    if not headers:
        logger.error("Failed to get auth headers")
        return
    
    base_url = "https://intraday2-api.test.nordpoolgroup.com"
    
    try:
        logger.info(f"🔍 Testing root endpoint: {base_url}")
        response = requests.get(base_url, headers=headers, timeout=30)
        
        logger.info(f"Status: {response.status_code}")
        logger.info(f"Headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            logger.info("Response content:")
            logger.info(response.text[:1000])  # First 1000 characters
        else:
            logger.info(f"Error response: {response.text}")
            
    except Exception as e:
        logger.error(f"Error testing root endpoint: {e}")

def main():
    """Main discovery function"""
    logger.info("🚀 BRM Intraday API Endpoint Discovery")
    
    # Test authentication first
    auth = IntradayAuthenticator()
    auth_result = auth.test_authentication()
    
    if not auth_result['success']:
        logger.error("❌ Authentication failed")
        return
    
    logger.info("✅ Authentication successful")
    
    # Test root endpoint
    test_root_endpoint()
    
    print("\n" + "="*50)
    
    # Discover endpoints
    found_endpoints = discover_endpoints()
    
    if found_endpoints:
        print(f"\n🎉 Found {len(found_endpoints)} accessible endpoints!")
        print("The intraday API is accessible and we can proceed with integration.")
    else:
        print("\n🤔 No REST endpoints found.")
        print("This suggests the intraday API primarily uses WebSocket/STOMP protocol.")
        print("We should focus on WebSocket implementation for real-time trading.")

if __name__ == "__main__":
    main()
