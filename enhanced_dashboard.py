"""
Enhanced BRM Trading Dashboard
Real-time market data with order placement functionality
"""
from flask import Flask, render_template, jsonify, request
import asyncio
import logging
import json
from datetime import datetime, timedelta
import aiohttp
import ssl
import threading
import time
from working_order_placement import BRMOrderManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Global market data storage
market_data = {
    'auctions': [],
    'system_status': 'Unknown',
    'last_update': None,
    'error_message': None,
    'stats': {
        'total_auctions': 0,
        'open_auctions': 0,
        'completed_auctions': 0
    }
}

# Global order manager
order_manager = BRMOrderManager()

class MarketDataCollector:
    """Collects real-time market data from BRM API"""
    
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
        
        logger.info("MarketDataCollector initialized")
    
    async def get_access_token(self):
        """Get access token using aiohttp"""
        
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
            
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.post(self.token_url, headers=headers, data=data) as response:
                    if response.status == 200:
                        token_data = await response.json()
                        self.access_token = token_data["access_token"]
                        expires_in = token_data.get("expires_in", 3600)
                        self.token_expires_at = datetime.now() + timedelta(seconds=expires_in - 60)
                        logger.info(f"Access token obtained, expires at {self.token_expires_at}")
                        return self.access_token
                    else:
                        error_text = await response.text()
                        logger.error(f"Token request failed: {response.status} - {error_text}")
                        return None
                        
        except Exception as e:
            logger.error(f"Token request error: {e}")
            return None
    
    async def api_request(self, endpoint, params=None):
        """Make authenticated API request"""
        
        token = await self.get_access_token()
        if not token:
            logger.error("No access token available")
            return None
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": "BRM-Trading-Bot/1.0"
        }
        
        url = f"{self.api_base_url}{endpoint}"
        
        try:
            logger.info(f"Making request to {endpoint}")
            
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.get(url, headers=headers, params=params) as response:
                    logger.info(f"GET {endpoint}: {response.status}")
                    
                    if response.status == 200:
                        result = await response.json()
                        logger.info(f"API request successful: {endpoint}")
                        return result
                    else:
                        error_text = await response.text()
                        logger.warning(f"{endpoint}: {response.status} - {error_text}")
                        return None
                        
        except Exception as e:
            logger.error(f"API request error for {endpoint}: {e}")
            return None
    
    async def collect_market_data(self):
        """Collect market data from BRM API"""
        
        try:
            logger.info("Collecting market data...")
            
            # Get auctions for today and tomorrow
            today = datetime.now()
            tomorrow = today + timedelta(days=2)
            
            date_params = {
                "closeBiddingFrom": today.strftime("%Y-%m-%d"),
                "closeBiddingTo": tomorrow.strftime("%Y-%m-%d")
            }
            
            auctions = await self.api_request("/api/v1/auctions", params=date_params)
            
            if auctions:
                # Update global market data
                market_data['auctions'] = auctions
                market_data['last_update'] = datetime.now().isoformat()
                market_data['system_status'] = 'Connected'
                market_data['error_message'] = None
                
                # Calculate stats
                total_auctions = len(auctions)
                open_auctions = len([a for a in auctions if a.get('state', '').lower() == 'open'])
                completed_auctions = len([a for a in auctions if a.get('state', '').lower() == 'completed'])
                
                market_data['stats'] = {
                    'total_auctions': total_auctions,
                    'open_auctions': open_auctions,
                    'completed_auctions': completed_auctions
                }
                
                logger.info(f"Market data updated: {total_auctions} auctions ({open_auctions} open)")
            else:
                market_data['system_status'] = 'Error'
                market_data['error_message'] = 'Failed to fetch auction data'
                logger.error("Failed to collect market data")
                
        except Exception as e:
            market_data['system_status'] = 'Error'
            market_data['error_message'] = str(e)
            logger.error(f"Error collecting market data: {e}")

# Initialize market data collector
collector = MarketDataCollector()

def run_data_collection():
    """Run data collection in background thread"""
    
    async def collection_loop():
        while True:
            try:
                await collector.collect_market_data()
                await asyncio.sleep(30)  # Update every 30 seconds
            except Exception as e:
                logger.error(f"Data collection loop error: {e}")
                await asyncio.sleep(60)  # Wait longer on error
    
    # Run the async loop in a thread
    def run_loop():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(collection_loop())
    
    thread = threading.Thread(target=run_loop, daemon=True)
    thread.start()
    logger.info("Background data collection started")

@app.route('/')
def dashboard():
    """Main dashboard page"""
    return render_template('enhanced_dashboard.html')

@app.route('/api/market-data')
def get_market_data():
    """API endpoint for market data"""
    return jsonify(market_data)

@app.route('/api/auction/<auction_id>/contracts')
def get_auction_contracts(auction_id):
    """Get contracts for a specific auction"""
    try:
        contracts = order_manager.get_auction_contracts(auction_id)
        return jsonify({
            'success': True,
            'contracts': contracts
        })
    except Exception as e:
        logger.error(f"Error getting contracts for auction {auction_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/place-block-order', methods=['POST'])
def place_block_order():
    """Place a block order"""
    try:
        data = request.get_json()
        
        auction_id = data.get('auctionId')
        name = data.get('name')
        price = float(data.get('price'))
        contract_volumes = data.get('contractVolumes', {})
        minimum_acceptance_ratio = float(data.get('minimumAcceptanceRatio', 1.0))
        
        # Convert contract volumes to proper format
        contract_volumes_dict = {}
        for contract_id, volume in contract_volumes.items():
            contract_volumes_dict[contract_id] = float(volume)
        
        result = order_manager.create_simple_block_order(
            auction_id=auction_id,
            name=name,
            price=price,
            contract_volumes=contract_volumes_dict,
            minimum_acceptance_ratio=minimum_acceptance_ratio
        )
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error placing block order: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/place-curve-order', methods=['POST'])
def place_curve_order():
    """Place a curve order"""
    try:
        data = request.get_json()
        
        auction_id = data.get('auctionId')
        contract_id = data.get('contractId')
        curve_points = data.get('curvePoints', [])
        
        # Convert curve points to proper format
        price_volume_pairs = []
        for point in curve_points:
            price_volume_pairs.append({
                'price': float(point['price']),
                'volume': float(point['volume'])
            })
        
        result = order_manager.create_simple_curve_order(
            auction_id=auction_id,
            contract_id=contract_id,
            price_volume_pairs=price_volume_pairs
        )
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error placing curve order: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/auction/<auction_id>/orders')
def get_auction_orders(auction_id):
    """Get orders for a specific auction"""
    try:
        result = order_manager.get_my_orders(auction_id)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error getting orders for auction {auction_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/cancel-block-order/<order_id>', methods=['DELETE'])
def cancel_block_order(order_id):
    """Cancel a block order"""
    try:
        result = order_manager.cancel_block_order(order_id)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error canceling block order {order_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/cancel-curve-order/<order_id>', methods=['DELETE'])
def cancel_curve_order(order_id):
    """Cancel a curve order"""
    try:
        result = order_manager.cancel_curve_order(order_id)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error canceling curve order {order_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

if __name__ == '__main__':
    # Start background data collection
    run_data_collection()
    
    # Give some time for initial data collection
    time.sleep(5)
    
    print("🚀 Enhanced BRM Trading Dashboard starting...")
    print("📊 Real-time market data collection active")
    print("💼 Order placement functionality enabled")
    print("🌐 Dashboard available at: http://localhost:5000")
    
    # Run Flask app
    app.run(host='0.0.0.0', port=5000, debug=False)
