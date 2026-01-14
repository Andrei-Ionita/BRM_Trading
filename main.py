"""
BRM Day-Ahead Market Dashboard - Simplified Production Version
Real-time web interface for Romanian energy market data
"""
from flask import Flask, render_template, jsonify
from flask_cors import CORS
import requests
import logging
import json
from datetime import datetime, timedelta
import sys
import urllib3

# Disable SSL warnings for production
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configure logging for production
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

class BRMMarketData:
    """Simplified BRM market data collector using requests"""
    
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
        
        logger.info("BRMMarketData initialized")
    
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
                verify=False,  # Disable SSL verification for production
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
    
    def api_request(self, endpoint, params=None):
        """Make authenticated API request using requests"""
        
        token = self.get_access_token()
        if not token:
            logger.error("No access token available")
            return None
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": "BRM-Market-Dashboard/1.0"
        }
        
        url = f"{self.api_base_url}{endpoint}"
        
        try:
            logger.info(f"Making API request to {endpoint}")
            
            response = requests.get(
                url, 
                headers=headers, 
                params=params,
                verify=False,  # Disable SSL verification for production
                timeout=30
            )
            
            if response.status_code == 200:
                try:
                    result = response.json()
                    logger.info(f"API request successful: {endpoint}")
                    return result
                except:
                    result = response.text
                    logger.info(f"API request successful (text): {endpoint}")
                    return result
            else:
                logger.warning(f"{endpoint}: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"API request error for {endpoint}: {e}")
            return None
    
    def get_market_data(self):
        """Get comprehensive market data"""
        
        try:
            logger.info("Starting market data collection...")
            
            # Get system status
            logger.info("Checking system status...")
            system_status = self.api_request("/api/state")
            logger.info(f"System status response: {system_status}")
            
            # Get auctions with date filter
            today = datetime.now()
            tomorrow = today + timedelta(days=2)  # Get more data
            
            date_params = {
                "closeBiddingFrom": today.strftime("%Y-%m-%d"),
                "closeBiddingTo": tomorrow.strftime("%Y-%m-%d")
            }
            
            logger.info(f"Requesting auctions with params: {date_params}")
            auctions = self.api_request("/api/v1/auctions", params=date_params)
            logger.info(f"Auctions response: {len(auctions) if isinstance(auctions, list) else 'Not a list'}")
            
            if auctions and isinstance(auctions, list):
                # Enrich auction data
                enriched_auctions = []
                
                for auction in auctions[:10]:  # Limit to first 10 for performance
                    auction_id = auction.get('id')
                    logger.info(f"Processing auction: {auction_id}")
                    
                    # Get additional details for each auction (with error handling)
                    orders = self.api_request(f"/api/v1/auctions/{auction_id}/orders")
                    trades = self.api_request(f"/api/v1/auctions/{auction_id}/trades")
                    prices = self.api_request(f"/api/v1/auctions/{auction_id}/prices")
                    
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
                
                result = {
                    'auctions': enriched_auctions,
                    'system_status': system_status or 'Ok',
                    'last_update': datetime.now().isoformat(),
                    'error_message': None,
                    'stats': {
                        'total_auctions': total_auctions,
                        'open_auctions': open_auctions,
                        'completed_auctions': completed_auctions
                    },
                    'success': True
                }
                
                logger.info(f"Successfully collected market data: {total_auctions} auctions, {open_auctions} open")
                return result
            
            else:
                error_msg = "No auction data available"
                logger.warning(error_msg)
                return {
                    'auctions': [],
                    'system_status': system_status or 'Unknown',
                    'last_update': datetime.now().isoformat(),
                    'error_message': error_msg,
                    'stats': {'total_auctions': 0, 'open_auctions': 0, 'completed_auctions': 0},
                    'success': False
                }
        
        except Exception as e:
            error_msg = f"Data collection error: {str(e)}"
            logger.error(f"Market data collection failed: {e}", exc_info=True)
            return {
                'auctions': [],
                'system_status': 'Error',
                'last_update': datetime.now().isoformat(),
                'error_message': error_msg,
                'stats': {'total_auctions': 0, 'open_auctions': 0, 'completed_auctions': 0},
                'success': False
            }

# Initialize data collector
brm_data = BRMMarketData()

@app.route('/')
def dashboard():
    """Main dashboard page"""
    logger.info("Dashboard page requested")
    return render_template('dashboard.html')

@app.route('/api/market-data')
def get_market_data():
    """API endpoint to get current market data - triggers fresh data collection"""
    logger.info("Market data API requested - collecting fresh data...")
    
    try:
        market_data = brm_data.get_market_data()
        logger.info(f"Returning market data: {len(market_data.get('auctions', []))} auctions")
        return jsonify(market_data)
    except Exception as e:
        logger.error(f"Error in get_market_data endpoint: {e}")
        return jsonify({
            'auctions': [],
            'system_status': 'Error',
            'last_update': datetime.now().isoformat(),
            'error_message': f"API error: {str(e)}",
            'stats': {'total_auctions': 0, 'open_auctions': 0, 'completed_auctions': 0},
            'success': False
        })

@app.route('/api/auction/<auction_id>')
def get_auction_details(auction_id):
    """Get detailed information for a specific auction"""
    
    try:
        market_data = brm_data.get_market_data()
        
        for auction in market_data.get('auctions', []):
            if auction.get('id') == auction_id:
                return jsonify(auction)
        
        return jsonify({'error': 'Auction not found'}), 404
    except Exception as e:
        logger.error(f"Error getting auction details: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'version': '2.0-simplified',
        'data_collection': 'on-demand'
    })

@app.route('/debug')
def debug_info():
    """Debug endpoint to see detailed information"""
    return jsonify({
        'collector_info': {
            'token_url': brm_data.token_url,
            'api_base_url': brm_data.api_base_url,
            'has_token': brm_data.access_token is not None,
            'token_expires_at': brm_data.token_expires_at.isoformat() if brm_data.token_expires_at else None,
            'username': brm_data.username,
            'scope': brm_data.scope
        },
        'test_connection': 'Use /api/market-data to test live connection'
    })

@app.route('/test')
def test_connection():
    """Test endpoint to verify BRM API connection"""
    logger.info("Testing BRM API connection...")
    
    try:
        # Test authentication
        token = brm_data.get_access_token()
        if not token:
            return jsonify({
                'success': False,
                'error': 'Authentication failed',
                'timestamp': datetime.now().isoformat()
            })
        
        # Test system status
        system_status = brm_data.api_request("/api/state")
        
        return jsonify({
            'success': True,
            'authentication': 'OK',
            'system_status': system_status,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Test connection failed: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        })

if __name__ == '__main__':
    logger.info("Starting BRM Market Dashboard (Simplified Version)...")
    
    # Start Flask app
    import os
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"Starting Flask app on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
