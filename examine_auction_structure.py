"""
Examine Auction Structure
Look at the exact structure of auction details to find contracts
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

class AuctionExaminer:
    """Examine auction structure"""
    
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
        
        logger.info("AuctionExaminer initialized")
    
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

def examine_auction_structure():
    """Examine the exact auction structure"""
    
    print("🔍 Examining Auction Structure...")
    
    examiner = AuctionExaminer()
    
    # Get open auctions
    print("\n📊 Getting open auctions...")
    
    today = datetime.now()
    tomorrow = today + timedelta(days=2)
    
    date_params = {
        "closeBiddingFrom": today.strftime("%Y-%m-%d"),
        "closeBiddingTo": tomorrow.strftime("%Y-%m-%d")
    }
    
    result = examiner.api_request("/api/v1/auctions", params=date_params)
    
    if result and result["success"]:
        auctions = result["data"]
        open_auctions = [a for a in auctions if a.get('state', '').lower() == 'open']
        
        if open_auctions:
            # Try different auction types
            for auction in open_auctions[:3]:  # Check first 3 auctions
                auction_id = auction['id']
                auction_name = auction.get('name', 'Unknown')
                
                print(f"\n🎯 Examining auction: {auction_id} ({auction_name})")
                
                # Get detailed auction information
                auction_details = examiner.api_request(f"/api/v1/auctions/{auction_id}")
                
                if auction_details and auction_details["success"]:
                    details = auction_details["data"]
                    
                    print(f"📋 Auction Details Keys: {list(details.keys())}")
                    
                    # Look for any field that might contain contracts
                    contract_candidates = []
                    for key, value in details.items():
                        if isinstance(value, list) and value:
                            # Check if list items look like contracts
                            first_item = value[0]
                            if isinstance(first_item, dict):
                                item_keys = list(first_item.keys())
                                if any(term in str(item_keys).lower() for term in ['id', 'contract', 'period', 'delivery']):
                                    contract_candidates.append((key, len(value), item_keys))
                    
                    if contract_candidates:
                        print(f"📋 Potential contract fields:")
                        for key, count, keys in contract_candidates:
                            print(f"   - {key}: {count} items with keys {keys}")
                            
                            # Show sample items
                            items = details[key]
                            for i, item in enumerate(items[:2]):  # Show first 2 items
                                print(f"     [{i}]: {json.dumps(item, indent=6)}")
                    else:
                        print(f"❌ No obvious contract fields found")
                    
                    # Show full structure for smaller objects
                    if len(str(details)) < 5000:  # Only if not too large
                        print(f"\n📋 Full Auction Details for {auction_id}:")
                        print(json.dumps(details, indent=2))
                    else:
                        print(f"\n📋 Auction details too large to display fully")
                        
                        # Show just the structure
                        def show_structure(obj, indent=0):
                            spaces = "  " * indent
                            if isinstance(obj, dict):
                                for key, value in obj.items():
                                    if isinstance(value, (dict, list)):
                                        print(f"{spaces}{key}: {type(value).__name__}({len(value) if hasattr(value, '__len__') else '?'})")
                                        if indent < 2:  # Limit depth
                                            show_structure(value, indent + 1)
                                    else:
                                        print(f"{spaces}{key}: {type(value).__name__}")
                            elif isinstance(obj, list) and obj:
                                print(f"{spaces}[0]: {type(obj[0]).__name__}")
                                if isinstance(obj[0], dict) and indent < 2:
                                    show_structure(obj[0], indent + 1)
                        
                        print(f"📋 Structure overview:")
                        show_structure(details)
                else:
                    print(f"❌ Failed to get details for auction {auction_id}")
        else:
            print("❌ No open auctions found")
    else:
        print("❌ Failed to get auctions")

if __name__ == "__main__":
    examine_auction_structure()
