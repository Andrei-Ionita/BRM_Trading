"""
BRM Order Placement Module
Place orders in Romanian Day-Ahead energy auctions
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

class BRMOrderPlacer:
    """Place orders in BRM Day-Ahead auctions"""
    
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
        
        logger.info("BRMOrderPlacer initialized")
    
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
    
    def get_open_auctions(self):
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
    
    def place_limit_order(self, auction_id, side, quantity, price, delivery_start=None, delivery_end=None):
        """
        Place a limit order in an auction
        
        Args:
            auction_id: ID of the auction
            side: "Buy" or "Sell"
            quantity: Quantity in MW
            price: Price in EUR/MWh
            delivery_start: Start time for delivery (optional)
            delivery_end: End time for delivery (optional)
        """
        
        # Basic limit order structure based on BRM API documentation
        order_data = {
            "side": side,
            "quantity": quantity,
            "price": price,
            "orderType": "Limit"
        }
        
        # Add delivery period if specified
        if delivery_start and delivery_end:
            order_data["deliveryStart"] = delivery_start
            order_data["deliveryEnd"] = delivery_end
        
        logger.info(f"Placing limit order in auction {auction_id}: {order_data}")
        
        endpoint = f"/api/v1/auctions/{auction_id}/orders"
        result = self.api_request(endpoint, method="POST", data=order_data)
        
        return result
    
    def place_block_order(self, auction_id, side, blocks):
        """
        Place a block order in an auction
        
        Args:
            auction_id: ID of the auction
            side: "Buy" or "Sell"
            blocks: List of block specifications
        """
        
        order_data = {
            "side": side,
            "orderType": "Block",
            "blocks": blocks
        }
        
        logger.info(f"Placing block order in auction {auction_id}: {order_data}")
        
        endpoint = f"/api/v1/auctions/{auction_id}/blockorders"
        result = self.api_request(endpoint, method="POST", data=order_data)
        
        return result
    
    def get_my_orders(self, auction_id):
        """Get my orders for a specific auction"""
        
        endpoint = f"/api/v1/auctions/{auction_id}/orders"
        result = self.api_request(endpoint)
        
        return result
    
    def cancel_order(self, auction_id, order_id):
        """Cancel an order"""
        
        endpoint = f"/api/v1/auctions/{auction_id}/orders/{order_id}"
        result = self.api_request(endpoint, method="DELETE")
        
        return result

def test_order_placement():
    """Test order placement functionality"""
    
    print("🚀 Testing BRM Order Placement...")
    
    # Initialize order placer
    order_placer = BRMOrderPlacer()
    
    # Get open auctions
    print("\n📊 Getting open auctions...")
    open_auctions = order_placer.get_open_auctions()
    
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
    
    # Test 1: Place a small limit buy order
    print("\n📈 Test 1: Placing limit BUY order...")
    buy_result = order_placer.place_limit_order(
        auction_id=auction_id,
        side="Buy",
        quantity=1.0,  # 1 MW
        price=50.0     # 50 EUR/MWh
    )
    
    if buy_result["success"]:
        print("✅ Buy order placed successfully!")
        print(f"   Response: {buy_result['data']}")
    else:
        print(f"❌ Buy order failed: {buy_result['error']}")
    
    # Test 2: Place a small limit sell order
    print("\n📉 Test 2: Placing limit SELL order...")
    sell_result = order_placer.place_limit_order(
        auction_id=auction_id,
        side="Sell",
        quantity=1.0,  # 1 MW
        price=60.0     # 60 EUR/MWh
    )
    
    if sell_result["success"]:
        print("✅ Sell order placed successfully!")
        print(f"   Response: {sell_result['data']}")
    else:
        print(f"❌ Sell order failed: {sell_result['error']}")
    
    # Test 3: Get my orders
    print("\n📋 Test 3: Getting my orders...")
    orders_result = order_placer.get_my_orders(auction_id)
    
    if orders_result["success"]:
        orders = orders_result["data"]
        print(f"✅ Found {len(orders) if isinstance(orders, list) else 'unknown'} orders")
        if isinstance(orders, list) and orders:
            for order in orders[:3]:  # Show first 3 orders
                print(f"   - Order ID: {order.get('id', 'Unknown')}, Side: {order.get('side', 'Unknown')}, Quantity: {order.get('quantity', 'Unknown')}")
    else:
        print(f"❌ Failed to get orders: {orders_result['error']}")
    
    print("\n🏆 Order placement testing completed!")

if __name__ == "__main__":
    test_order_placement()
