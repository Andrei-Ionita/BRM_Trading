"""
Debug Contract Extraction
Fix the contract extraction from auction details
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

class ContractExtractor:
    """Debug contract extraction"""
    
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
        
        logger.info("ContractExtractor initialized")
    
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

def debug_contract_extraction():
    """Debug contract extraction from auction details"""
    
    print("🔍 Debugging Contract Extraction...")
    
    extractor = ContractExtractor()
    
    # Get open auctions
    print("\n📊 Getting open auctions...")
    
    today = datetime.now()
    tomorrow = today + timedelta(days=2)
    
    date_params = {
        "closeBiddingFrom": today.strftime("%Y-%m-%d"),
        "closeBiddingTo": tomorrow.strftime("%Y-%m-%d")
    }
    
    result = extractor.api_request("/api/v1/auctions", params=date_params)
    
    if result and result["success"]:
        auctions = result["data"]
        open_auctions = [a for a in auctions if a.get('state', '').lower() == 'open']
        
        if open_auctions:
            test_auction = open_auctions[0]
            auction_id = test_auction['id']
            
            print(f"✅ Using auction: {auction_id}")
            
            # Get detailed auction information
            print(f"\n🔍 Getting detailed auction information...")
            auction_details = extractor.api_request(f"/api/v1/auctions/{auction_id}")
            
            if auction_details and auction_details["success"]:
                details = auction_details["data"]
                
                print(f"📋 Debugging contract extraction...")
                
                # Method 1: Check products -> deliveryPeriods
                if 'products' in details and isinstance(details['products'], list):
                    print(f"✅ Found products array with {len(details['products'])} items")
                    
                    all_contracts = []
                    for i, product in enumerate(details['products']):
                        print(f"   Product {i}: {list(product.keys())}")
                        
                        if 'deliveryPeriods' in product and isinstance(product['deliveryPeriods'], list):
                            periods = product['deliveryPeriods']
                            print(f"   ✅ Found {len(periods)} delivery periods in product {i}")
                            
                            for j, period in enumerate(periods[:3]):  # Show first 3
                                contract_id = period.get('id', 'NO_ID')
                                delivery_start = period.get('deliveryStart', 'NO_START')
                                delivery_end = period.get('deliveryEnd', 'NO_END')
                                print(f"     [{j}] ID: {contract_id}")
                                print(f"         Start: {delivery_start}")
                                print(f"         End: {delivery_end}")
                                
                                all_contracts.append(period)
                    
                    if all_contracts:
                        print(f"\n✅ Successfully extracted {len(all_contracts)} contracts!")
                        
                        # Test order placement with first contract
                        test_contract = all_contracts[0]
                        contract_id = test_contract.get('id')
                        
                        if contract_id and contract_id != 'NO_ID':
                            print(f"\n🧪 Testing order placement with contract: {contract_id}")
                            
                            # Test block order
                            test_block_order = {
                                "auctionId": auction_id,
                                "areaCode": "TEL",
                                "portfolio": "ADREM - DA",
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
                                                "volume": -0.5  # Sell 0.5 MW (very small test)
                                            }
                                        ],
                                        "isSpreadBlock": False
                                    }
                                ]
                            }
                            
                            print(f"📦 Testing block order...")
                            print(f"   Order data: {json.dumps(test_block_order, indent=2)}")
                            
                            block_result = extractor.api_request("/api/v1/blockorders", method="POST", data=test_block_order)
                            
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
                            print(f"❌ No valid contract ID found")
                    else:
                        print(f"❌ No contracts extracted from products")
                else:
                    print(f"❌ No products found in auction details")
                
                # Method 2: Direct deliveryPeriods check
                if 'deliveryPeriods' in details:
                    print(f"\n🔍 Checking direct deliveryPeriods...")
                    periods = details['deliveryPeriods']
                    if isinstance(periods, list):
                        print(f"   ✅ Found {len(periods)} direct delivery periods")
                        for i, period in enumerate(periods[:3]):
                            print(f"     [{i}] {period}")
                    else:
                        print(f"   ❌ deliveryPeriods is not a list: {type(periods)}")
                else:
                    print(f"   ❌ No direct deliveryPeriods found")
                
            else:
                print(f"❌ Failed to get auction details")
        else:
            print("❌ No open auctions found")
    else:
        print("❌ Failed to get auctions")

if __name__ == "__main__":
    debug_contract_extraction()
