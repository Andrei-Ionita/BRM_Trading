"""
Enhanced BRM Trading Dashboard with Order Placement
Complete web application for Romanian energy market trading
"""
from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
import json
import logging
from datetime import datetime
from working_order_placement import BRMOrderManager
from order_management import OrderTracker

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Initialize trading components
order_manager = BRMOrderManager()
order_tracker = OrderTracker()

@app.route('/')
def dashboard():
    """Main dashboard with order placement functionality"""
    return render_template('enhanced_dashboard.html')

@app.route('/api/market-data')
def get_market_data():
    """Get live market data from BRM API"""
    try:
        # Get auctions
        auctions = order_manager.get_open_auctions()
        
        # Get detailed auction data
        detailed_auctions = []
        for auction in auctions:
            auction_id = auction['id']
            
            # Get auction details
            details_result = order_manager.get_auction_details(auction_id)
            if details_result.get('success'):
                auction_details = details_result['data']
                
                # Get contracts
                contracts = order_manager.get_auction_contracts(auction_id)
                
                # Get orders
                orders_result = order_manager.get_my_orders(auction_id)
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
                    'trades': 0,  # Not available in current API
                    'prices': 0   # Not available in current API
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
        logger.error(f"Error getting market data: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/auctions')
def get_auctions():
    """Get list of available auctions"""
    try:
        auctions = order_manager.get_open_auctions()
        return jsonify({
            'success': True,
            'auctions': auctions
        })
    except Exception as e:
        logger.error(f"Error getting auctions: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/auctions/<auction_id>/contracts')
def get_auction_contracts(auction_id):
    """Get contracts for a specific auction"""
    try:
        contracts = order_manager.get_auction_contracts(auction_id)
        return jsonify({
            'success': True,
            'contracts': contracts
        })
    except Exception as e:
        logger.error(f"Error getting contracts for {auction_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/orders/block', methods=['POST'])
def place_block_order():
    """Place a block order"""
    try:
        data = request.get_json()
        
        # Extract order parameters
        auction_id = data.get('auction_id')
        name = data.get('name')
        price = float(data.get('price'))
        contract_volumes = data.get('contract_volumes', {})
        minimum_acceptance_ratio = float(data.get('minimum_acceptance_ratio', 1.0))
        
        # Validate required fields
        if not all([auction_id, name, price, contract_volumes]):
            return jsonify({
                'success': False,
                'error': 'Missing required fields: auction_id, name, price, contract_volumes'
            }), 400
        
        # Place the order using order tracker
        result = order_tracker.place_and_track_block_order(
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
                'message': 'Block order placed successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', 'Unknown error')
            }), 400
            
    except Exception as e:
        logger.error(f"Error placing block order: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/orders/curve', methods=['POST'])
def place_curve_order():
    """Place a curve order"""
    try:
        data = request.get_json()
        
        # Extract order parameters
        auction_id = data.get('auction_id')
        contract_id = data.get('contract_id')
        price_volume_pairs = data.get('price_volume_pairs', [])
        
        # Validate required fields
        if not all([auction_id, contract_id, price_volume_pairs]):
            return jsonify({
                'success': False,
                'error': 'Missing required fields: auction_id, contract_id, price_volume_pairs'
            }), 400
        
        # Place the order using order tracker
        result = order_tracker.place_and_track_curve_order(
            auction_id=auction_id,
            contract_id=contract_id,
            price_volume_pairs=price_volume_pairs
        )
        
        if result.get('success'):
            return jsonify({
                'success': True,
                'order_id': result['data'].get('orderId'),
                'message': 'Curve order placed successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', 'Unknown error')
            }), 400
            
    except Exception as e:
        logger.error(f"Error placing curve order: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/orders/<auction_id>')
def get_orders(auction_id):
    """Get orders for a specific auction"""
    try:
        result = order_manager.get_my_orders(auction_id)
        
        if result.get('success'):
            return jsonify({
                'success': True,
                'orders': result['data']
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', 'Failed to get orders')
            }), 400
            
    except Exception as e:
        logger.error(f"Error getting orders for {auction_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/orders/summary')
def get_order_summary():
    """Get summary of all tracked orders"""
    try:
        summary = order_tracker.get_order_summary()
        return jsonify({
            'success': True,
            'summary': summary
        })
    except Exception as e:
        logger.error(f"Error getting order summary: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/orders/cancel/<order_id>', methods=['POST'])
def cancel_order(order_id):
    """Cancel an order"""
    try:
        data = request.get_json()
        order_type = data.get('order_type', 'block')
        
        result = order_tracker.cancel_order(order_id, order_type)
        
        if result.get('success'):
            return jsonify({
                'success': True,
                'message': f'Order {order_id} cancelled successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', 'Failed to cancel order')
            }), 400
            
    except Exception as e:
        logger.error(f"Error cancelling order {order_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'service': 'BRM Trading Dashboard Enhanced'
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
    logger.info("Features: Live market data, Order placement, Order tracking")
    app.run(host='0.0.0.0', port=5000, debug=False)
