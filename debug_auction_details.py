"""
Debug Auction Details
Examine the structure of auction details to find delivery periods
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

class BRMDebugger:
    """Debug BRM API responses"""
    
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
        
        logger.info("BRMDebugger initialized")
    
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

def debug_auction_details():
    """Debug auction details structure"""
    
    print("🔍 Debugging Auction Details Structure...")
    
    debugger = BRMDebugger()
    
    # Get open auctions
    print("\n📊 Getting open auctions...")
    
    today = datetime.now()
    tomorrow = today + timedelta(days=2)
    
    date_params = {
        "closeBiddingFrom": today.strftime("%Y-%m-%d"),
        "closeBiddingTo": tomorrow.strftime("%Y-%m-%d")
    }
    
    result = debugger.api_request("/api/v1/auctions", params=date_params)
    
    if result and result["success"]:
        auctions = result["data"]
        open_auctions = [a for a in auctions if a.get('state', '').lower() == 'open']
        
        if open_auctions:
            test_auction = open_auctions[0]
            auction_id = test_auction['id']
            
            print(f"✅ Using auction: {auction_id}")
            
            # Get detailed auction information
            print(f"\n🔍 Getting detailed auction information...")
            auction_details = debugger.api_request(f"/api/v1/auctions/{auction_id}")
            
            if auction_details and auction_details["success"]:
                details = auction_details["data"]
                
                print(f"📋 Auction Details Structure:")
                print(f"   Keys: {list(details.keys())}")
                
                # Look for delivery-related fields
                delivery_fields = []
                for key, value in details.items():
                    if any(term in key.lower() for term in ['delivery', 'period', 'contract', 'product']):
                        delivery_fields.append((key, type(value).__name__, len(value) if isinstance(value, (list, dict)) else str(value)[:100]))
                
                if delivery_fields:
                    print(f"\n📋 Delivery-related fields:")
                    for key, value_type, value_info in delivery_fields:
                        print(f"   - {key} ({value_type}): {value_info}")
                        
                        # If it's a list, show first few items
                        if key in details and isinstance(details[key], list) and details[key]:
                            print(f"     Sample items:")
                            for i, item in enumerate(details[key][:3]):
                                print(f"       [{i}]: {json.dumps(item, indent=8)}")
                
                # Show full structure for smaller objects
                print(f"\n📋 Full Auction Details:")
                print(json.dumps(details, indent=2))
                
                # Try to extract contract IDs
                contracts = []
                
                # Check different possible locations for contracts
                if 'deliveryPeriods' in details:
                    contracts = details['deliveryPeriods']
                elif 'periods' in details:
                    contracts = details['periods']
                elif 'contracts' in details:
                    contracts = details['contracts']
                elif 'products' in details:
                    contracts = details['products']
                
                if contracts:
                    print(f"\n✅ Found {len(contracts)} contracts/periods:")
                    for i, contract in enumerate(contracts[:5]):
                        contract_id = contract.get('id', 'Unknown')
                        delivery_start = contract.get('deliveryStart', 'Unknown')
                        delivery_end = contract.get('deliveryEnd', 'Unknown')
                        print(f"   [{i}] {contract_id}: {delivery_start} - {delivery_end}")
                        
                        # Test order placement with this contract
                        if i == 0:  # Test with first contract
                            print(f"\n🧪 Testing order placement with contract: {contract_id}")
                            
                            # Test block order
                            test_block_order = {
                                "auctionId": auction_id,
                                "areaCode": "RO",
                                "portfolio": "TEST_PORTFOLIO",
                                "blocks": [
                                    {
                                        "name": "TestBlock",
                                        "price": 50.0,
                                        "minimumAcceptanceRatio": 1.0,
                                        "linkedTo": None,
                                        "auctionId": auction_id,
                                        "periods": [
                                            {
                                                "contractId": contract_id,
                                                "volume": -1.0  # Sell 1 MW
                                            }
                                        ],
                                        "isSpreadBlock": False
                                    }
                                ]
                            }
                            
                            print(f"📦 Testing block order...")
                            block_result = debugger.api_request("/api/v1/blockorders", method="POST", data=test_block_order)
                            
                            if block_result and block_result["success"]:
                                print(f"   ✅ Block order test successful!")
                                print(f"   📋 Response: {json.dumps(block_result['data'], indent=2)}")
                            else:
                                print(f"   ❌ Block order test failed: {block_result['error']}")
                                
                                # Try to understand the error
                                try:
                                    error_data = json.loads(block_result['error'])
                                    if 'detail' in error_data:
                                        print(f"   📋 Error details: {error_data['detail']}")
                                except:
                                    pass
                else:
                    print(f"\n❌ No contracts found in auction details")
            else:
                print(f"❌ Failed to get auction details")
        else:
            print("❌ No open auctions found")
    else:
        print("❌ Failed to get auctions")

if __name__ == "__main__":
    debug_auction_details()
