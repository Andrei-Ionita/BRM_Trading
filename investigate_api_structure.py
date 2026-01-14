"""
Investigate BRM API Structure
Find the correct endpoints and data structure for order placement
"""
import requests
import json
import logging
from datetime import datetime, timedelta
import urllib3

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BRMAPIInvestigator:
    """Investigate BRM API structure"""
    
    def __init__(self):
        # Working Day-Ahead auction API credentials
        self.token_url = "https://sso.test.brm-power.ro/connect/token"
        self.api_base_url = "https://auctions-api.test.brm-power.ro"
        
        # Correct credentials
        self.grant_type = "password"
        self.scope = "auction_api"
        self.username = "Test_AuctionAPI_ADREM"
        self.password = "odvM6{=15HW1s%H1Wb"
        self.basic_auth = "Basic Y2xpZW50X2F1Y3Rpb25fYXBpOmNsaWVudF9hdWN0aW9uX2FwaQ=="
        
        self.access_token = None
        self.token_expires_at = None
        
        logger.info("BRMAPIInvestigator initialized")
    
    def get_access_token(self):
        """Get access token using requests"""
        
        if self.access_token and self.token_expires_at and datetime.now() < self.token_expires_at:
            logger.info("Using cached access token")
            return self.access_token
        
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
            logger.info("Requesting new access token...")
            
            response = requests.post(
                self.token_url, 
                headers=headers, 
                data=data, 
                verify=False,
                timeout=30
            )
            
            if response.status_code == 200:
                token_data = response.json()
                self.access_token = token_data["access_token"]
                expires_in = token_data.get("expires_in", 3600)
                self.token_expires_at = datetime.now() + timedelta(seconds=expires_in - 60)
                logger.info(f"Access token obtained, expires at {self.token_expires_at}")
                return self.access_token
            else:
                logger.error(f"Token request failed: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Token request error: {e}")
            return None
    
    def api_request(self, endpoint, method="GET", data=None, params=None):
        """Make authenticated API request"""
        
        token = self.get_access_token()
        if not token:
            logger.error("No access token available")
            return None
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": "BRM-Trading-Bot/1.0"
        }
        
        if method in ["POST", "PUT", "PATCH"] and data:
            headers["Content-Type"] = "application/json"
        
        url = f"{self.api_base_url}{endpoint}"
        
        try:
            logger.info(f"Making {method} request to {endpoint}")
            
            if method == "GET":
                response = requests.get(url, headers=headers, params=params, verify=False, timeout=30)
            elif method == "POST":
                response = requests.post(url, headers=headers, json=data, verify=False, timeout=30)
            elif method == "PUT":
                response = requests.put(url, headers=headers, json=data, verify=False, timeout=30)
            elif method == "DELETE":
                response = requests.delete(url, headers=headers, verify=False, timeout=30)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            logger.info(f"{method} {endpoint}: {response.status_code}")
            
            if response.status_code in [200, 201, 202]:
                try:
                    result = response.json()
                    logger.info(f"API request successful: {endpoint}")
                    return {"success": True, "data": result, "status_code": response.status_code}
                except:
                    result = response.text
                    logger.info(f"API request successful (text): {endpoint}")
                    return {"success": True, "data": result, "status_code": response.status_code}
            else:
                logger.warning(f"{endpoint}: {response.status_code} - {response.text}")
                return {"success": False, "error": response.text, "status_code": response.status_code}
                
        except Exception as e:
            logger.error(f"API request error for {endpoint}: {e}")
            return {"success": False, "error": str(e), "status_code": None}

def investigate_api():
    """Investigate the BRM API structure"""
    
    print("🔍 Investigating BRM API Structure...")
    
    investigator = BRMAPIInvestigator()
    
    # Get open auctions
    print("\n📊 Getting open auctions...")
    
    today = datetime.now()
    tomorrow = today + timedelta(days=2)
    
    date_params = {
        "closeBiddingFrom": today.strftime("%Y-%m-%d"),
        "closeBiddingTo": tomorrow.strftime("%Y-%m-%d")
    }
    
    result = investigator.api_request("/api/v1/auctions", params=date_params)
    
    if result and result["success"]:
        auctions = result["data"]
        open_auctions = [a for a in auctions if a.get('state', '').lower() == 'open']
        
        if open_auctions:
            test_auction = open_auctions[0]
            auction_id = test_auction['id']
            
            print(f"✅ Using auction: {auction_id}")
            print(f"   Auction details: {json.dumps(test_auction, indent=2)}")
            
            # Test different endpoints to find contracts
            endpoints_to_test = [
                f"/api/v1/auctions/{auction_id}",
                f"/api/v1/auctions/{auction_id}/contracts",
                f"/api/v1/auctions/{auction_id}/products",
                f"/api/v1/auctions/{auction_id}/periods",
                f"/api/v1/auctions/{auction_id}/deliveryperiods",
                f"/api/v1/contracts",
                f"/api/v1/products",
                f"/api/v1/periods"
            ]
            
            print(f"\n🔍 Testing different endpoints...")
            
            for endpoint in endpoints_to_test:
                print(f"\n📡 Testing: {endpoint}")
                result = investigator.api_request(endpoint)
                
                if result and result["success"]:
                    data = result["data"]
                    if isinstance(data, list):
                        print(f"   ✅ Success: Found {len(data)} items")
                        if data:
                            print(f"   📋 Sample item: {json.dumps(data[0], indent=2)}")
                    elif isinstance(data, dict):
                        print(f"   ✅ Success: Found object with keys: {list(data.keys())}")
                        print(f"   📋 Data: {json.dumps(data, indent=2)}")
                    else:
                        print(f"   ✅ Success: {data}")
                else:
                    print(f"   ❌ Failed: {result['status_code']} - {result['error']}")
            
            # Test order placement endpoints
            print(f"\n🎯 Testing order placement endpoints...")
            
            order_endpoints = [
                "/api/v1/blockorders",
                "/api/v1/curveorders",
                f"/api/v1/auctions/{auction_id}/orders",
                f"/api/v1/auctions/{auction_id}/blockorders",
                f"/api/v1/auctions/{auction_id}/curveorders"
            ]
            
            for endpoint in order_endpoints:
                print(f"\n📡 Testing GET: {endpoint}")
                result = investigator.api_request(endpoint)
                
                if result and result["success"]:
                    data = result["data"]
                    if isinstance(data, list):
                        print(f"   ✅ Success: Found {len(data)} orders")
                        if data:
                            print(f"   📋 Sample order: {json.dumps(data[0], indent=2)}")
                    else:
                        print(f"   ✅ Success: {data}")
                else:
                    print(f"   ❌ Failed: {result['status_code']} - {result['error']}")
            
            # Try to find contract information in auction details
            print(f"\n🔍 Examining auction details for contract information...")
            auction_details = investigator.api_request(f"/api/v1/auctions/{auction_id}")
            
            if auction_details and auction_details["success"]:
                details = auction_details["data"]
                print(f"📋 Full auction details:")
                print(json.dumps(details, indent=2))
                
                # Look for contract-related fields
                contract_fields = []
                for key, value in details.items():
                    if 'contract' in key.lower() or 'period' in key.lower() or 'product' in key.lower():
                        contract_fields.append((key, value))
                
                if contract_fields:
                    print(f"\n📋 Contract-related fields found:")
                    for key, value in contract_fields:
                        print(f"   - {key}: {value}")
                else:
                    print(f"\n❌ No obvious contract-related fields found")
            
            # Test a simple order placement to see what happens
            print(f"\n🧪 Testing simple order placement...")
            
            # Try block order first
            simple_block_order = {
                "blocks": [
                    {
                        "name": "TestBlock",
                        "price": 50.0,
                        "minimumAcceptanceRatio": 1.0,
                        "linkedTo": None,
                        "auctionId": auction_id,
                        "periods": [
                            {
                                "contractId": "TEST_CONTRACT_ID",
                                "volume": -10.0
                            }
                        ],
                        "isSpreadBlock": False
                    }
                ]
            }
            
            print(f"📦 Testing block order placement...")
            block_result = investigator.api_request("/api/v1/blockorders", method="POST", data=simple_block_order)
            
            if block_result and block_result["success"]:
                print(f"   ✅ Block order test successful!")
                print(f"   📋 Response: {json.dumps(block_result['data'], indent=2)}")
            else:
                print(f"   ❌ Block order test failed: {block_result['error']}")
                print(f"   📋 This might give us clues about the correct structure")
        
        else:
            print("❌ No open auctions found")
    else:
        print("❌ Failed to get auctions")

if __name__ == "__main__":
    investigate_api()
