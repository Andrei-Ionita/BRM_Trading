"""
Enhanced BRM Trading Dashboard with Day-Ahead and Intraday Markets
Complete web application for Romanian energy market trading
"""
from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
import json
import logging
import asyncio
import threading
from datetime import datetime
from typing import Dict, List, Optional, Any

# Import existing Day-Ahead components
from working_order_placement import BRMOrderManager
from order_management import OrderTracker

# Import new Intraday components
from intraday_auth import IntradayAuthenticator
# from intraday_market_client import IntradayMarketClient  # Will be implemented with WebSocket

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

class BRMTradingSystem:
    """
    Unified BRM trading system handling both Day-Ahead and Intraday markets
    """
    
    def __init__(self):
        # Day-Ahead components (existing)
        self.da_order_manager = None
        self.da_order_tracker = None
        self.da_available = False
        
        # Intraday components (new)
        self.id_market_client = None
        self.id_available = False
        
        # System status
        self.system_status = {
            'day_ahead': 'Initializing...',
            'intraday': 'Pending credentials...',
            'last_update': datetime.now().isoformat()
        }
        
        # Initialize components
        self._initialize_day_ahead()
        self._initialize_intraday()
    
    def _initialize_day_ahead(self):
        """Initialize Day-Ahead trading components"""
        try:
            self.da_order_manager = BRMOrderManager()
            self.da_order_tracker = OrderTracker()
            self.da_available = True
            self.system_status['day_ahead'] = 'Online'
            logger.info("Day-Ahead trading system initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Day-Ahead system: {e}")
            self.system_status['day_ahead'] = f'Error: {str(e)}'
    
    def _initialize_intraday(self):
        """Initialize Intraday trading components"""
        try:
            # Check if intraday credentials are available
            # This will be updated when credentials are provided
            intraday_token = self._get_intraday_token()
            
            if intraday_token:
                # Store intraday token for WebSocket connections
                self.intraday_token = intraday_token
                
                # TODO: Initialize WebSocket client when ready
                # self.id_market_client = IntradayWebSocketClient(
                #     access_token=intraday_token,
                #     ws_trading_url="wss://intraday2-ws.test.nordpoolgroup.com:443",
                #     ws_market_url="wss://intraday-pmd-api-ws-brm.test.nordpoolgroup.com:443"
                # )
                
                self.id_available = True
                self.system_status['intraday'] = 'Authenticated - WebSocket Ready'
                logger.info("Intraday authentication successful - WebSocket ready")
            else:
                self.system_status['intraday'] = 'Authentication failed'
                logger.info("Intraday authentication failed")
                
        except Exception as e:
            logger.error(f"Failed to initialize Intraday system: {e}")
            self.system_status['intraday'] = f'Error: {str(e)}'
    
    def _get_intraday_token(self) -> Optional[str]:
        """Get intraday access token using working authentication"""
        try:
            auth = IntradayAuthenticator()
            token = auth.get_access_token()
            if token:
                logger.info("Intraday token obtained successfully")
                return token
            else:
                logger.error("Failed to obtain intraday token")
                return None
        except Exception as e:
            logger.error(f"Error getting intraday token: {e}")
            return None
    
    def _start_intraday_client(self):
        """Start intraday WebSocket client (to be implemented)"""
        # TODO: Implement WebSocket client startup
        logger.info("Intraday WebSocket client startup - to be implemented")
        pass
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get overall system status"""
        self.system_status['last_update'] = datetime.now().isoformat()
        return self.system_status
    
    def is_day_ahead_available(self) -> bool:
        """Check if Day-Ahead trading is available"""
        return self.da_available and self.da_order_manager is not None
    
    def is_intraday_available(self) -> bool:
        """Check if Intraday trading is available"""
        return self.id_available and self.id_market_client is not None

# Initialize the trading system
trading_system = BRMTradingSystem()

@app.route('/')
def dashboard():
    """Enhanced dashboard with both Day-Ahead and Intraday markets"""
    return render_template('enhanced_dashboard_with_intraday.html')

# System Status Endpoints
@app.route('/api/system/status')
def get_system_status():
    """Get overall system status"""
    return jsonify({
        'success': True,
        'status': trading_system.get_system_status(),
        'day_ahead_available': trading_system.is_day_ahead_available(),
        'intraday_available': trading_system.is_intraday_available()
    })

# Day-Ahead Market Endpoints (existing functionality)
@app.route('/api/market-data')
def get_day_ahead_market_data():
    """Get Day-Ahead market data"""
    if not trading_system.is_day_ahead_available():
        return jsonify({
            'success': False,
            'error': 'Day-Ahead trading not available'
        }), 503
    
    try:
        # Get auctions
        auctions = trading_system.da_order_manager.get_open_auctions()
        
        # Get detailed auction data
        detailed_auctions = []
        for auction in auctions:
            auction_id = auction['id']
            
            # Get auction details
            details_result = trading_system.da_order_manager.get_auction_details(auction_id)
            auction_details = details_result.get('data', {}) if details_result.get('success') else {}
            
            # Get contracts
            contracts = trading_system.da_order_manager.get_auction_contracts(auction_id)
            
            # Get orders count
            orders_result = trading_system.da_order_manager.get_my_orders(auction_id)
            order_count = 0
            if orders_result.get('success') and orders_result.get('data'):
                orders_data = orders_result['data']
                if isinstance(orders_data, dict):
                    block_orders = orders_data.get('blockLists', [])
                    curve_orders = orders_data.get('curveOrders', [])
                    order_count = len(block_orders) + len(curve_orders)
            
            detailed_auctions.append({
                'id': auction_id,
                'name': auction.get('name', auction_id),
                'state': auction.get('state', 'Unknown'),
                'description': auction_details.get('description', ''),
                'closeForBidding': auction_details.get('closeForBidding'),
                'contracts': len(contracts),
                'orders': order_count,
                'trades': 0,
                'prices': 0
            })
        
        return jsonify({
            'success': True,
            'auctions': detailed_auctions,
            'timestamp': datetime.now().isoformat(),
            'total_auctions': len(auctions),
            'open_auctions': len([a for a in detailed_auctions if a['state'] == 'Open']),
            'completed_auctions': len([a for a in detailed_auctions if a['state'] in ['Closed', 'Completed']])
        })
        
    except Exception as e:
        logger.error(f"Error getting Day-Ahead market data: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/auctions')
def get_day_ahead_auctions():
    """Get Day-Ahead auctions"""
    if not trading_system.is_day_ahead_available():
        return jsonify({'success': False, 'error': 'Day-Ahead not available'}), 503
    
    try:
        auctions = trading_system.da_order_manager.get_open_auctions()
        return jsonify({
            'success': True,
            'auctions': auctions
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/auctions/<auction_id>/contracts')
def get_day_ahead_contracts(auction_id):
    """Get Day-Ahead contracts for specific auction"""
    if not trading_system.is_day_ahead_available():
        return jsonify({'success': False, 'error': 'Day-Ahead not available'}), 503
    
    try:
        contracts = trading_system.da_order_manager.get_auction_contracts(auction_id)
        return jsonify({
            'success': True,
            'contracts': contracts
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/orders/block', methods=['POST'])
def place_day_ahead_block_order():
    """Place Day-Ahead block order"""
    if not trading_system.is_day_ahead_available():
        return jsonify({'success': False, 'error': 'Day-Ahead not available'}), 503
    
    try:
        data = request.get_json()
        
        auction_id = data.get('auction_id')
        name = data.get('name')
        price = float(data.get('price'))
        contract_volumes = data.get('contract_volumes', {})
        minimum_acceptance_ratio = float(data.get('minimum_acceptance_ratio', 1.0))
        
        if not all([auction_id, name, price, contract_volumes]):
            return jsonify({
                'success': False,
                'error': 'Missing required fields'
            }), 400
        
        result = trading_system.da_order_tracker.place_and_track_block_order(
            auction_id=auction_id,
            name=name,
            price=price,
            contract_volumes=contract_volumes,
            minimum_acceptance_ratio=minimum_acceptance_ratio
        )
        
        if result.get('success'):
            return jsonify({
                'success': True,
                'order_id': result['data'].get('orderId'),
                'message': 'Day-Ahead block order placed successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', 'Unknown error')
            }), 400
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# Intraday Market Endpoints (new functionality)
@app.route('/api/intraday/market-data')
def get_intraday_market_data():
    """Get Intraday market data status"""
    try:
        # Test authentication
        auth = IntradayAuthenticator()
        auth_result = auth.test_authentication()
        
        if auth_result['success']:
            # Return mock data showing WebSocket-ready status
            return jsonify({
                'success': True,
                'websocket_status': 'Authenticated - Ready for WebSocket connection',
                'authentication': auth_result,
                'contracts_count': 0,  # Will be populated via WebSocket
                'tickers_count': 0,    # Will be populated via WebSocket
                'trades_count': 0,     # Will be populated via WebSocket
                'api_type': 'WebSocket/STOMP - No REST endpoints available',
                'trading_url': 'wss://intraday2-ws.test.nordpoolgroup.com:443',
                'market_data_url': 'wss://intraday-pmd-api-ws-brm.test.nordpoolgroup.com:443',
                'timestamp': datetime.now().isoformat(),
                'message': 'Intraday authentication successful - WebSocket implementation pending'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Intraday authentication failed',
                'details': auth_result
            }), 503
            
    except Exception as e:
        logger.error(f"Error getting Intraday status: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/intraday/contracts')
def get_intraday_contracts():
    """Get available Intraday contracts (WebSocket implementation pending)"""
    return jsonify({
        'success': True,
        'contracts': [],
        'message': 'Intraday contracts will be available via WebSocket connection',
        'status': 'WebSocket implementation pending'
    })

@app.route('/api/intraday/tickers')
def get_intraday_tickers():
    """Get real-time Intraday price tickers (WebSocket implementation pending)"""
    return jsonify({
        'success': True,
        'tickers': [],
        'message': 'Real-time tickers will be available via WebSocket connection',
        'status': 'WebSocket implementation pending'
    })

@app.route('/api/intraday/orders', methods=['POST'])
def place_intraday_order():
    """Place Intraday order (WebSocket implementation pending)"""
    try:
        data = request.get_json()
        
        # Validate order parameters
        contract_id = data.get('contract_id')
        side = data.get('side')
        order_type = data.get('order_type')
        price = data.get('price')
        quantity = data.get('quantity')
        
        if not all([contract_id, side, order_type, quantity]):
            return jsonify({
                'success': False,
                'error': 'Missing required fields'
            }), 400
        
        # Check authentication
        auth = IntradayAuthenticator()
        if not auth.get_access_token():
            return jsonify({
                'success': False,
                'error': 'Intraday authentication failed'
            }), 401
        
        return jsonify({
            'success': False,
            'error': 'Intraday order placement via WebSocket not yet implemented',
            'status': 'Authentication working - WebSocket client needed',
            'order_data': data
        }), 501
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/intraday/orderbook/<contract_id>')
def get_intraday_orderbook(contract_id):
    """Get Intraday order book for specific contract (WebSocket implementation pending)"""
    return jsonify({
        'success': True,
        'contract_id': contract_id,
        'order_book': {
            'bids': [],
            'asks': [],
            'timestamp': datetime.now().isoformat()
        },
        'message': 'Order book data will be available via WebSocket connection',
        'status': 'WebSocket implementation pending'
    })

# Health and Monitoring Endpoints
@app.route('/health')
def health_check():
    """Comprehensive health check"""
    status = trading_system.get_system_status()
    
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'service': 'BRM Trading Dashboard - Day-Ahead & Intraday',
        'components': {
            'day_ahead': {
                'status': status['day_ahead'],
                'available': trading_system.is_day_ahead_available()
            },
            'intraday': {
                'status': status['intraday'],
                'available': trading_system.is_intraday_available()
            }
        }
    })

@app.route('/api/system/capabilities')
def get_system_capabilities():
    """Get system capabilities and features"""
    return jsonify({
        'success': True,
        'capabilities': {
            'day_ahead_trading': trading_system.is_day_ahead_available(),
            'intraday_trading': trading_system.is_intraday_available(),
            'real_time_data': trading_system.is_intraday_available(),
            'order_tracking': True,
            'multi_market': True,
            'websocket_support': trading_system.is_intraday_available()
        },
        'markets': {
            'day_ahead': {
                'name': 'Romanian Day-Ahead Market',
                'api_url': 'auctions-api.test.brm-power.ro',
                'status': trading_system.system_status['day_ahead']
            },
            'intraday': {
                'name': 'Romanian Intraday Market',
                'api_url': 'intraday2-api.test.nordpoolgroup.com',
                'websocket_url': 'intraday-pmd-api-ws-brm.test.nordpoolgroup.com',
                'status': trading_system.system_status['intraday']
            }
        }
    })

@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'success': False,
        'error': 'Endpoint not found'
    }), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        'success': False,
        'error': 'Internal server error'
    }), 500

if __name__ == '__main__':
    logger.info("Starting Enhanced BRM Trading Dashboard...")
    logger.info("Features: Day-Ahead + Intraday markets, Real-time data, Order placement")
    logger.info(f"Day-Ahead available: {trading_system.is_day_ahead_available()}")
    logger.info(f"Intraday available: {trading_system.is_intraday_available()}")
    
    app.run(host='0.0.0.0', port=5000, debug=False)
