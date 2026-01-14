"""
Corrected BRM Order Placement Module
Complete implementation with proper API structure for Romanian Day-Ahead energy auctions
"""
import requests
import json
import logging
from datetime import datetime, timedelta
import urllib3
from typing import List, Dict, Optional, Union

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BRMOrderManager:
    """Corrected order management for BRM Day-Ahead auctions"""
    
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
        
        # Default values based on API requirements
        self.area_code = "TEL"  # Romanian delivery area code
        self.portfolio = "ADREM - DA"  # Correct portfolio name from API
        
        logger.info("BRMOrderManager initialized")
    
    def get_access_token(self) -> Optional[str]:
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
    
    def api_request(self, endpoint: str, method: str = "GET", data: Optional[Dict] = None, params: Optional[Dict] = None) -> Dict:
        """Make authenticated API request"""
        
        token = self.get_access_token()
        if not token:
            logger.error("No access token available")
            return {"success": False, "error": "Authentication failed", "status_code": None}
        
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
    
    def get_open_auctions(self) -> List[Dict]:
        """Get list of open auctions"""
        
        today = datetime.now()
        tomorrow = today + timedelta(days=2)
        
        date_params = {
            "closeBiddingFrom": today.strftime("%Y-%m-%d"),
            "closeBiddingTo": tomorrow.strftime("%Y-%m-%d")
        }
        
        result = self.api_request("/api/v1/auctions", params=date_params)
        
        if result and result["success"]:
            auctions = result["data"]
            open_auctions = [a for a in auctions if a.get('state', '').lower() == 'open']
            return open_auctions
        
        return []
    
    def get_auction_details(self, auction_id: str) -> Optional[Dict]:
        """Get detailed information about a specific auction"""
        
        result = self.api_request(f"/api/v1/auctions/{auction_id}")
        
        if result and result["success"]:
            return result["data"]
        
        return None
    
    def get_auction_contracts(self, auction_id: str) -> List[Dict]:
        """Get available contracts (delivery periods) for an auction"""
        
        auction_details = self.get_auction_details(auction_id)
        
        if auction_details:
            # Check for delivery periods in different possible locations
            if 'deliveryPeriods' in auction_details:
                return auction_details['deliveryPeriods']
            elif 'periods' in auction_details:
                return auction_details['periods']
            elif 'contracts' in auction_details:
                return auction_details['contracts']
            elif 'products' in auction_details and isinstance(auction_details['products'], list):
                # Extract delivery periods from products
                all_periods = []
                for product in auction_details['products']:
                    if 'deliveryPeriods' in product:
                        all_periods.extend(product['deliveryPeriods'])
                return all_periods
        
        return []
    
    def place_block_order(self, auction_id: str, blocks: List[Dict], comment: str = "", 
                         area_code: str = None, portfolio: str = None) -> Dict:
        """
        Place a block order using the correct BRM API structure
        
        Args:
            auction_id: ID of the auction
            blocks: List of block specifications with periods
            comment: Optional comment for the order
            area_code: Area code (defaults to "RO")
            portfolio: Portfolio name (defaults to "TEST_PORTFOLIO")
        
        Returns:
            Dict with success status and response data
        """
        
        # Use provided values or defaults
        area_code = area_code or self.area_code
        portfolio = portfolio or self.portfolio
        
        # Construct order data according to BRM API specification
        order_data = {
            "auctionId": auction_id,
            "areaCode": area_code,
            "portfolio": portfolio,
            "blocks": blocks
        }
        
        # Add comment if provided
        if comment:
            order_data["comment"] = comment
        
        logger.info(f"Placing block order in auction {auction_id}")
        logger.info(f"Order data: {json.dumps(order_data, indent=2)}")
        
        # Use the correct endpoint for block orders
        endpoint = f"/api/v1/blockorders"
        
        result = self.api_request(endpoint, method="POST", data=order_data)
        
        return result
    
    def place_curve_order(self, auction_id: str, curves: List[Dict], comment: str = "",
                         area_code: str = None, portfolio: str = None) -> Dict:
        """
        Place a curve order (limit orders) using the correct BRM API structure
        
        Args:
            auction_id: ID of the auction
            curves: List of curve specifications with price-quantity pairs
            comment: Optional comment for the order
            area_code: Area code (defaults to "RO")
            portfolio: Portfolio name (defaults to "TEST_PORTFOLIO")
        
        Returns:
            Dict with success status and response data
        """
        
        # Use provided values or defaults
        area_code = area_code or self.area_code
        portfolio = portfolio or self.portfolio
        
        # Construct order data according to BRM API specification
        order_data = {
            "auctionId": auction_id,
            "areaCode": area_code,
            "portfolio": portfolio,
            "curves": curves
        }
        
        # Add comment if provided
        if comment:
            order_data["comment"] = comment
        
        logger.info(f"Placing curve order in auction {auction_id}")
        logger.info(f"Order data: {json.dumps(order_data, indent=2)}")
        
        # Use the correct endpoint for curve orders
        endpoint = f"/api/v1/curveorders"
        
        result = self.api_request(endpoint, method="POST", data=order_data)
        
        return result
    
    def create_simple_block_order(self, auction_id: str, name: str, price: float, 
                                 contract_volumes: Dict[str, float], 
                                 minimum_acceptance_ratio: float = 1.0,
                                 area_code: str = None, portfolio: str = None) -> Dict:
        """
        Create a simple block order with specified contract volumes
        
        Args:
            auction_id: ID of the auction
            name: Name for the block
            price: Price in EUR/MWh
            contract_volumes: Dict mapping contract IDs to volumes (negative for sell, positive for buy)
            minimum_acceptance_ratio: Minimum acceptance ratio (1.0 = all or nothing)
            area_code: Area code (defaults to "RO")
            portfolio: Portfolio name (defaults to "TEST_PORTFOLIO")
        
        Returns:
            Dict with success status and response data
        """
        
        # Create periods list from contract volumes
        periods = []
        for contract_id, volume in contract_volumes.items():
            periods.append({
                "contractId": contract_id,
                "volume": volume
            })
        
        # Create block specification
        block = {
            "name": name,
            "price": price,
            "minimumAcceptanceRatio": minimum_acceptance_ratio,
            "linkedTo": None,
            "auctionId": auction_id,
            "periods": periods,
            "isSpreadBlock": False
        }
        
        return self.place_block_order(auction_id, [block], area_code=area_code, portfolio=portfolio)
    
    def create_simple_curve_order(self, auction_id: str, contract_id: str, 
                                 price_volume_pairs: List[Dict[str, float]],
                                 area_code: str = None, portfolio: str = None) -> Dict:
        """
        Create a simple curve order (limit order) for a specific contract
        
        Args:
            auction_id: ID of the auction
            contract_id: ID of the contract
            price_volume_pairs: List of dicts with 'price' and 'volume' keys
            area_code: Area code (defaults to "RO")
            portfolio: Portfolio name (defaults to "TEST_PORTFOLIO")
        
        Returns:
            Dict with success status and response data
        """
        
        # Create curve specification
        curve = {
            "contractId": contract_id,
            "auctionId": auction_id,
            "priceVolumePairs": price_volume_pairs
        }
        
        return self.place_curve_order(auction_id, [curve], area_code=area_code, portfolio=portfolio)
    
    def get_my_orders(self, auction_id: str) -> Dict:
        """Get my orders for a specific auction"""
        
        result = self.api_request(f"/api/v1/auctions/{auction_id}/orders")
        
        return result
    
    def get_my_block_orders(self, auction_id: str = None) -> Dict:
        """Get my block orders, optionally filtered by auction"""
        
        endpoint = "/api/v1/blockorders"
        params = {"auctionId": auction_id} if auction_id else None
        
        result = self.api_request(endpoint, params=params)
        
        return result
    
    def get_my_curve_orders(self, auction_id: str = None) -> Dict:
        """Get my curve orders, optionally filtered by auction"""
        
        endpoint = "/api/v1/curveorders"
        params = {"auctionId": auction_id} if auction_id else None
        
        result = self.api_request(endpoint, params=params)
        
        return result
    
    def cancel_block_order(self, order_id: str) -> Dict:
        """Cancel a block order by ID"""
        
        result = self.api_request(f"/api/v1/blockorders/{order_id}", method="DELETE")
        
        return result
    
    def cancel_curve_order(self, order_id: str) -> Dict:
        """Cancel a curve order by ID"""
        
        result = self.api_request(f"/api/v1/curveorders/{order_id}", method="DELETE")
        
        return result
    
    def get_block_order_status(self, order_id: str) -> Dict:
        """Get status of a specific block order"""
        
        result = self.api_request(f"/api/v1/blockorders/{order_id}")
        
        return result
    
    def get_curve_order_status(self, order_id: str) -> Dict:
        """Get status of a specific curve order"""
        
        result = self.api_request(f"/api/v1/curveorders/{order_id}")
        
        return result

def test_corrected_order_placement():
    """Test corrected order placement functionality"""
    
    print("🚀 Testing Corrected BRM Order Placement...")
    
    # Initialize order manager
    order_manager = BRMOrderManager()
    
    # Get open auctions
    print("\n📊 Getting open auctions...")
    open_auctions = order_manager.get_open_auctions()
    
    if not open_auctions:
        print("❌ No open auctions found")
        return
    
    print(f"✅ Found {len(open_auctions)} open auctions:")
    for auction in open_auctions:
        print(f"  - {auction['id']}: {auction.get('name', 'Unknown')} (State: {auction.get('state')})")
    
    # Select first open auction for testing
    test_auction = open_auctions[0]
    auction_id = test_auction['id']
    
    print(f"\n🎯 Testing with auction: {auction_id}")
    
    # Get auction contracts
    print("\n📋 Getting auction contracts...")
    contracts = order_manager.get_auction_contracts(auction_id)
    
    if contracts:
        print(f"✅ Found {len(contracts)} contracts:")
        for contract in contracts[:5]:  # Show first 5 contracts
            print(f"  - {contract.get('id', 'Unknown')}: {contract.get('deliveryStart', 'Unknown')} - {contract.get('deliveryEnd', 'Unknown')}")
    else:
        print("❌ No contracts found")
        return
    
    # Test 1: Place a simple block order
    print("\n📦 Test 1: Placing simple block order...")
    
    # Use first contract for testing
    test_contract = contracts[0]
    contract_id = test_contract.get('id')
    
    if contract_id:
        contract_volumes = {
            contract_id: -5.0  # Sell 5 MW
        }
        
        block_result = order_manager.create_simple_block_order(
            auction_id=auction_id,
            name="TestSellBlock",
            price=55.0,  # 55 EUR/MWh
            contract_volumes=contract_volumes,
            minimum_acceptance_ratio=1.0
        )
        
        if block_result["success"]:
            print("✅ Block order placed successfully!")
            print(f"   Response: {json.dumps(block_result['data'], indent=2)}")
        else:
            print(f"❌ Block order failed: {block_result['error']}")
    
    # Test 2: Place a simple curve order
    print("\n📈 Test 2: Placing simple curve order...")
    
    if len(contracts) > 1:
        test_contract_2 = contracts[1]
        contract_id_2 = test_contract_2.get('id')
        
        if contract_id_2:
            price_volume_pairs = [
                {"price": 50.0, "volume": 2.0},   # Buy 2 MW at 50 EUR/MWh
                {"price": 45.0, "volume": 3.0},   # Buy 3 MW at 45 EUR/MWh
                {"price": 40.0, "volume": 5.0}    # Buy 5 MW at 40 EUR/MWh
            ]
            
            curve_result = order_manager.create_simple_curve_order(
                auction_id=auction_id,
                contract_id=contract_id_2,
                price_volume_pairs=price_volume_pairs
            )
            
            if curve_result["success"]:
                print("✅ Curve order placed successfully!")
                print(f"   Response: {json.dumps(curve_result['data'], indent=2)}")
            else:
                print(f"❌ Curve order failed: {curve_result['error']}")
    
    # Test 3: Get my block orders
    print("\n📦 Test 3: Getting my block orders...")
    block_orders_result = order_manager.get_my_block_orders(auction_id)
    
    if block_orders_result["success"]:
        block_orders = block_orders_result["data"]
        print(f"✅ Retrieved block orders successfully")
        if isinstance(block_orders, list) and block_orders:
            print(f"   Found {len(block_orders)} block orders")
            for order in block_orders[:3]:  # Show first 3 orders
                print(f"   - Block Order ID: {order.get('orderId', 'Unknown')}")
        else:
            print("   No block orders found")
    else:
        print(f"❌ Failed to get block orders: {block_orders_result['error']}")
    
    # Test 4: Get my curve orders
    print("\n📈 Test 4: Getting my curve orders...")
    curve_orders_result = order_manager.get_my_curve_orders(auction_id)
    
    if curve_orders_result["success"]:
        curve_orders = curve_orders_result["data"]
        print(f"✅ Retrieved curve orders successfully")
        if isinstance(curve_orders, list) and curve_orders:
            print(f"   Found {len(curve_orders)} curve orders")
            for order in curve_orders[:3]:  # Show first 3 orders
                print(f"   - Curve Order ID: {order.get('orderId', 'Unknown')}")
        else:
            print("   No curve orders found")
    else:
        print(f"❌ Failed to get curve orders: {curve_orders_result['error']}")
    
    print("\n🏆 Corrected order placement testing completed!")

if __name__ == "__main__":
    test_corrected_order_placement()
