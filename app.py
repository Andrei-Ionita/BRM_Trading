"""
BRM Day-Ahead Market Dashboard - Production Version
Real-time web interface for Romanian energy market data
"""
from flask import Flask, render_template, jsonify
from flask_cors import CORS
import asyncio
import logging
import json
from datetime import datetime, timedelta
import aiohttp
import ssl
import threading
import time
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

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
    
    async def get_access_token(self):
        """Get access token"""
        
        if self.access_token and self.token_expires_at and datetime.now() < self.token_expires_at:
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
            connector = aiohttp.TCPConnector(ssl=ssl.create_default_context())
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.post(self.token_url, headers=headers, data=data) as response:
                    
                    if response.status == 200:
                        token_data = await response.json()
                        self.access_token = token_data["access_token"]
                        expires_in = token_data.get("expires_in", 3600)
                        self.token_expires_at = datetime.now() + timedelta(seconds=expires_in - 60)
                        return self.access_token
                    else:
                        logger.error(f"Token request failed: {response.status}")
                        return None
                        
        except Exception as e:
            logger.error(f"Token request error: {e}")
            return None
    
    async def api_request(self, endpoint, params=None):
        """Make authenticated API request"""
        
        token = await self.get_access_token()
        if not token:
            return None
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": "BRM-Market-Dashboard/1.0"
        }
        
        url = f"{self.api_base_url}{endpoint}"
        
        try:
            connector = aiohttp.TCPConnector(ssl=ssl.create_default_context())
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.get(url, headers=headers, params=params) as response:
                    
                    if response.status == 200:
                        try:
                            return await response.json()
                        except:
                            return await response.text()
                    else:
                        logger.warning(f"{endpoint}: {response.status}")
                        return None
                        
        except Exception as e:
            logger.error(f"API request error for {endpoint}: {e}")
            return None
    
    async def collect_market_data(self):
        """Collect comprehensive market data"""
        
        global market_data
        
        try:
            # Get system status
            system_status = await self.api_request("/api/state")
            
            # Get auctions with date filter
            today = datetime.now()
            tomorrow = today + timedelta(days=2)  # Get more data
            
            date_params = {
                "closeBiddingFrom": today.strftime("%Y-%m-%d"),
                "closeBiddingTo": tomorrow.strftime("%Y-%m-%d")
            }
            
            auctions = await self.api_request("/api/v1/auctions", params=date_params)
            
            if auctions and isinstance(auctions, list):
                # Enrich auction data
                enriched_auctions = []
                
                for auction in auctions:
                    auction_id = auction.get('id')
                    
                    # Get additional details for each auction (with error handling)
                    orders = await self.api_request(f"/api/v1/auctions/{auction_id}/orders")
                    trades = await self.api_request(f"/api/v1/auctions/{auction_id}/trades")
                    prices = await self.api_request(f"/api/v1/auctions/{auction_id}/prices")
                    
                    # Enrich auction data
                    enriched_auction = auction.copy()
                    enriched_auction['orders_count'] = len(orders) if isinstance(orders, list) else 0
                    enriched_auction['trades_count'] = len(trades) if isinstance(trades, list) else 0
                    enriched_auction['prices_count'] = len(prices) if isinstance(prices, list) else 0
                    
                    # Add sample data for display
                    enriched_auction['sample_orders'] = orders[:3] if isinstance(orders, list) and orders else []
                    enriched_auction['sample_trades'] = trades[:3] if isinstance(trades, list) and trades else []
                    enriched_auction['sample_prices'] = prices[:3] if isinstance(prices, list) and prices else []
                    
                    # Add formatted delivery date
                    if 'deliveryDate' in auction:
                        try:
                            delivery_date = datetime.fromisoformat(auction['deliveryDate'].replace('Z', '+00:00'))
                            enriched_auction['formatted_delivery'] = delivery_date.strftime("%Y-%m-%d %H:%M")
                        except:
                            enriched_auction['formatted_delivery'] = auction.get('deliveryDate', 'Unknown')
                    else:
                        enriched_auction['formatted_delivery'] = 'Unknown'
                    
                    # Add formatted close bidding date
                    if 'closeBiddingDate' in auction:
                        try:
                            close_date = datetime.fromisoformat(auction['closeBiddingDate'].replace('Z', '+00:00'))
                            enriched_auction['formatted_close_bidding'] = close_date.strftime("%Y-%m-%d %H:%M")
                        except:
                            enriched_auction['formatted_close_bidding'] = auction.get('closeBiddingDate', 'Unknown')
                    else:
                        enriched_auction['formatted_close_bidding'] = 'Unknown'
                    
                    enriched_auctions.append(enriched_auction)
                
                # Calculate statistics
                total_auctions = len(enriched_auctions)
                open_auctions = len([a for a in enriched_auctions if a.get('state', '').lower() == 'open'])
                completed_auctions = len([a for a in enriched_auctions if 'published' in a.get('state', '').lower()])
                
                # Update global market data
                market_data.update({
                    'auctions': enriched_auctions,
                    'system_status': system_status or 'Unknown',
                    'last_update': datetime.now().isoformat(),
                    'error_message': None,
                    'stats': {
                        'total_auctions': total_auctions,
                        'open_auctions': open_auctions,
                        'completed_auctions': completed_auctions
                    }
                })
                
                logger.info(f"Updated market data: {total_auctions} auctions, {open_auctions} open")
            
            else:
                market_data['error_message'] = "No auction data available"
                logger.warning("No auction data received")
        
        except Exception as e:
            market_data['error_message'] = f"Data collection error: {str(e)}"
            logger.error(f"Market data collection failed: {e}")

# Initialize data collector
collector = MarketDataCollector()

def run_data_collection():
    """Run data collection in background thread"""
    
    def collection_loop():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        while True:
            try:
                loop.run_until_complete(collector.collect_market_data())
                time.sleep(30)  # Update every 30 seconds
            except Exception as e:
                logger.error(f"Data collection loop error: {e}")
                time.sleep(60)  # Wait longer on error
    
    thread = threading.Thread(target=collection_loop, daemon=True)
    thread.start()
    logger.info("Started background data collection")

@app.route('/')
def dashboard():
    """Main dashboard page"""
    return render_template('dashboard.html')

@app.route('/api/market-data')
def get_market_data():
    """API endpoint to get current market data"""
    return jsonify(market_data)

@app.route('/api/auction/<auction_id>')
def get_auction_details(auction_id):
    """Get detailed information for a specific auction"""
    
    for auction in market_data.get('auctions', []):
        if auction.get('id') == auction_id:
            return jsonify(auction)
    
    return jsonify({'error': 'Auction not found'}), 404

@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'system_status': market_data.get('system_status', 'Unknown'),
        'last_update': market_data.get('last_update'),
        'auctions_count': len(market_data.get('auctions', []))
    })

if __name__ == '__main__':
    # Start background data collection
    run_data_collection()
    
    # Start Flask app
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"Starting BRM Market Dashboard on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
