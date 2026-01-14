"""
BRM Order Management and Tracking System
Complete order lifecycle management for Romanian energy market
"""
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from working_order_placement import BRMOrderManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class OrderTracker:
    """Advanced order tracking and management system"""
    
    def __init__(self):
        self.order_manager = BRMOrderManager()
        self.order_history = []
        logger.info("OrderTracker initialized")
    
    def place_and_track_block_order(self, auction_id: str, name: str, price: float, 
                                   contract_volumes: Dict[str, float], 
                                   minimum_acceptance_ratio: float = 1.0) -> Dict:
        """Place a block order and add it to tracking"""
        
        # Place the order
        result = self.order_manager.create_simple_block_order(
            auction_id=auction_id,
            name=name,
            price=price,
            contract_volumes=contract_volumes,
            minimum_acceptance_ratio=minimum_acceptance_ratio
        )
        
        # Add to tracking if successful
        if result.get('success'):
            order_record = {
                'order_id': result['data'].get('orderId'),
                'type': 'block',
                'auction_id': auction_id,
                'name': name,
                'price': price,
                'contract_volumes': contract_volumes,
                'minimum_acceptance_ratio': minimum_acceptance_ratio,
                'placed_at': datetime.now().isoformat(),
                'status': 'placed',
                'result': result['data']
            }
            self.order_history.append(order_record)
            logger.info(f"Block order tracked: {order_record['order_id']}")
        
        return result
    
    def place_and_track_curve_order(self, auction_id: str, contract_id: str, 
                                   price_volume_pairs: List[Dict]) -> Dict:
        """Place a curve order and add it to tracking"""
        
        # Place the order
        result = self.order_manager.create_simple_curve_order(
            auction_id=auction_id,
            contract_id=contract_id,
            price_volume_pairs=price_volume_pairs
        )
        
        # Add to tracking if successful
        if result.get('success'):
            order_record = {
                'order_id': result['data'].get('orderId'),
                'type': 'curve',
                'auction_id': auction_id,
                'contract_id': contract_id,
                'price_volume_pairs': price_volume_pairs,
                'placed_at': datetime.now().isoformat(),
                'status': 'placed',
                'result': result['data']
            }
            self.order_history.append(order_record)
            logger.info(f"Curve order tracked: {order_record['order_id']}")
        
        return result
    
    def get_order_status(self, order_id: str, auction_id: str) -> Dict:
        """Get current status of a specific order"""
        
        # Get all orders for the auction
        orders_result = self.order_manager.get_my_orders(auction_id)
        
        if orders_result.get('success') and orders_result.get('data'):
            orders = orders_result['data']
            
            # Find the specific order
            for order in orders:
                if order.get('id') == order_id or order.get('orderId') == order_id:
                    return {
                        'success': True,
                        'order': order,
                        'status': order.get('status', order.get('state', 'unknown'))
                    }
        
        return {
            'success': False,
            'error': 'Order not found',
            'order_id': order_id
        }
    
    def update_order_statuses(self) -> Dict:
        """Update status for all tracked orders"""
        
        updated_count = 0
        errors = []
        
        for order_record in self.order_history:
            order_id = order_record.get('order_id')
            auction_id = order_record.get('auction_id')
            
            if order_id and auction_id:
                try:
                    status_result = self.get_order_status(order_id, auction_id)
                    
                    if status_result.get('success'):
                        # Update the order record
                        order_record['last_updated'] = datetime.now().isoformat()
                        order_record['current_status'] = status_result['status']
                        order_record['current_data'] = status_result['order']
                        updated_count += 1
                    else:
                        errors.append(f"Failed to update {order_id}: {status_result.get('error')}")
                        
                except Exception as e:
                    errors.append(f"Error updating {order_id}: {str(e)}")
        
        return {
            'success': True,
            'updated_count': updated_count,
            'total_orders': len(self.order_history),
            'errors': errors
        }
    
    def cancel_order(self, order_id: str, order_type: str) -> Dict:
        """Cancel an order and update tracking"""
        
        # Cancel the order
        if order_type.lower() == 'block':
            result = self.order_manager.cancel_block_order(order_id)
        elif order_type.lower() == 'curve':
            result = self.order_manager.cancel_curve_order(order_id)
        else:
            return {
                'success': False,
                'error': f'Unknown order type: {order_type}'
            }
        
        # Update tracking if successful
        if result.get('success'):
            for order_record in self.order_history:
                if order_record.get('order_id') == order_id:
                    order_record['cancelled_at'] = datetime.now().isoformat()
                    order_record['status'] = 'cancelled'
                    break
            
            logger.info(f"Order cancelled and tracked: {order_id}")
        
        return result
    
    def get_order_summary(self) -> Dict:
        """Get summary of all tracked orders"""
        
        total_orders = len(self.order_history)
        block_orders = len([o for o in self.order_history if o.get('type') == 'block'])
        curve_orders = len([o for o in self.order_history if o.get('type') == 'curve'])
        cancelled_orders = len([o for o in self.order_history if o.get('status') == 'cancelled'])
        
        # Calculate total volumes and values
        total_volume = 0
        total_value = 0
        
        for order in self.order_history:
            if order.get('type') == 'block' and order.get('contract_volumes'):
                for volume in order['contract_volumes'].values():
                    total_volume += abs(volume)
                    total_value += abs(volume) * order.get('price', 0)
            elif order.get('type') == 'curve' and order.get('price_volume_pairs'):
                for pair in order['price_volume_pairs']:
                    volume = abs(pair.get('volume', 0))
                    price = pair.get('price', 0)
                    total_volume += volume
                    total_value += volume * price
        
        return {
            'total_orders': total_orders,
            'block_orders': block_orders,
            'curve_orders': curve_orders,
            'cancelled_orders': cancelled_orders,
            'active_orders': total_orders - cancelled_orders,
            'total_volume_mw': round(total_volume, 1),
            'total_value_eur': round(total_value, 2),
            'orders': self.order_history
        }
    
    def get_orders_by_auction(self, auction_id: str) -> List[Dict]:
        """Get all tracked orders for a specific auction"""
        
        return [order for order in self.order_history 
                if order.get('auction_id') == auction_id]
    
    def get_recent_orders(self, hours: int = 24) -> List[Dict]:
        """Get orders placed in the last N hours"""
        
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_orders = []
        
        for order in self.order_history:
            placed_at_str = order.get('placed_at')
            if placed_at_str:
                try:
                    placed_at = datetime.fromisoformat(placed_at_str)
                    if placed_at > cutoff_time:
                        recent_orders.append(order)
                except:
                    pass  # Skip orders with invalid timestamps
        
        return recent_orders
    
    def export_order_history(self, filename: str = None) -> str:
        """Export order history to JSON file"""
        
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"brm_order_history_{timestamp}.json"
        
        export_data = {
            'export_timestamp': datetime.now().isoformat(),
            'summary': self.get_order_summary(),
            'orders': self.order_history
        }
        
        with open(filename, 'w') as f:
            json.dump(export_data, f, indent=2)
        
        logger.info(f"Order history exported to {filename}")
        return filename

class AutomatedTrader:
    """Automated trading strategies for BRM market"""
    
    def __init__(self):
        self.order_tracker = OrderTracker()
        self.strategies = {}
        logger.info("AutomatedTrader initialized")
    
    def add_strategy(self, name: str, strategy_func, params: Dict = None):
        """Add a trading strategy"""
        
        self.strategies[name] = {
            'function': strategy_func,
            'params': params or {},
            'added_at': datetime.now().isoformat(),
            'executions': 0
        }
        
        logger.info(f"Strategy added: {name}")
    
    def execute_strategy(self, strategy_name: str, auction_id: str) -> Dict:
        """Execute a specific trading strategy"""
        
        if strategy_name not in self.strategies:
            return {
                'success': False,
                'error': f'Strategy not found: {strategy_name}'
            }
        
        strategy = self.strategies[strategy_name]
        
        try:
            # Execute the strategy function
            result = strategy['function'](
                order_tracker=self.order_tracker,
                auction_id=auction_id,
                **strategy['params']
            )
            
            # Update execution count
            strategy['executions'] += 1
            strategy['last_executed'] = datetime.now().isoformat()
            
            logger.info(f"Strategy executed: {strategy_name}")
            return result
            
        except Exception as e:
            logger.error(f"Strategy execution failed: {strategy_name} - {e}")
            return {
                'success': False,
                'error': f'Strategy execution failed: {str(e)}'
            }
    
    def simple_arbitrage_strategy(self, order_tracker: OrderTracker, auction_id: str, 
                                 target_price: float = 45.0, volume: float = 0.5) -> Dict:
        """Simple arbitrage strategy - buy low, sell high"""
        
        # Get auction contracts
        contracts = order_tracker.order_manager.get_auction_contracts(auction_id)
        
        if not contracts:
            return {
                'success': False,
                'error': 'No contracts available for arbitrage'
            }
        
        # Select first available contract
        contract = contracts[0]
        contract_id = contract['id']
        
        # Place a buy order at target price
        result = order_tracker.place_and_track_curve_order(
            auction_id=auction_id,
            contract_id=contract_id,
            price_volume_pairs=[
                {'price': target_price, 'volume': volume}
            ]
        )
        
        return result
    
    def volume_scaling_strategy(self, order_tracker: OrderTracker, auction_id: str,
                               base_price: float = 50.0, volumes: List[float] = None) -> Dict:
        """Volume scaling strategy - multiple orders at different volumes"""
        
        if not volumes:
            volumes = [0.1, 0.2, 0.3]
        
        contracts = order_tracker.order_manager.get_auction_contracts(auction_id)
        
        if not contracts:
            return {
                'success': False,
                'error': 'No contracts available'
            }
        
        results = []
        
        for i, volume in enumerate(volumes):
            contract = contracts[min(i, len(contracts) - 1)]
            
            # Create block order with scaled pricing
            price = base_price + (i * 2.0)  # Increase price for larger volumes
            
            result = order_tracker.place_and_track_block_order(
                auction_id=auction_id,
                name=f"ScaledOrder_{i+1}",
                price=price,
                contract_volumes={contract['id']: -volume},  # Sell orders
                minimum_acceptance_ratio=1.0
            )
            
            results.append(result)
        
        return {
            'success': True,
            'strategy': 'volume_scaling',
            'orders_placed': len([r for r in results if r.get('success')]),
            'results': results
        }

def test_order_management():
    """Test the order management and tracking system"""
    
    print("🚀 Testing BRM Order Management System...")
    
    # Initialize tracker
    tracker = OrderTracker()
    
    # Get live auctions
    auctions = tracker.order_manager.get_open_auctions()
    
    if not auctions:
        print("❌ No open auctions available")
        return
    
    auction_id = auctions[0]['id']
    print(f"🎯 Testing with auction: {auction_id}")
    
    # Get contracts
    contracts = tracker.order_manager.get_auction_contracts(auction_id)
    
    if not contracts:
        print("❌ No contracts available")
        return
    
    contract_id = contracts[0]['id']
    print(f"💼 Using contract: {contract_id}")
    
    # Test 1: Place and track a block order
    print("\n📦 Test 1: Placing tracked block order...")
    
    block_result = tracker.place_and_track_block_order(
        auction_id=auction_id,
        name="TrackedTestOrder",
        price=52.0,
        contract_volumes={contract_id: -0.1}
    )
    
    if block_result.get('success'):
        order_id = block_result['data'].get('orderId')
        print(f"✅ Block order placed and tracked: {order_id}")
        
        # Test order status tracking
        print("\n📊 Test 2: Checking order status...")
        status_result = tracker.get_order_status(order_id, auction_id)
        
        if status_result.get('success'):
            print(f"✅ Order status retrieved: {status_result['status']}")
        else:
            print(f"❌ Failed to get order status: {status_result.get('error')}")
    else:
        print(f"❌ Block order failed: {block_result.get('error')}")
    
    # Test 3: Order summary
    print("\n📋 Test 3: Order summary...")
    summary = tracker.get_order_summary()
    
    print(f"✅ Order Summary:")
    print(f"   - Total Orders: {summary['total_orders']}")
    print(f"   - Block Orders: {summary['block_orders']}")
    print(f"   - Curve Orders: {summary['curve_orders']}")
    print(f"   - Active Orders: {summary['active_orders']}")
    print(f"   - Total Volume: {summary['total_volume_mw']} MW")
    print(f"   - Total Value: {summary['total_value_eur']} EUR")
    
    # Test 4: Automated trading
    print("\n🤖 Test 4: Automated trading strategies...")
    
    auto_trader = AutomatedTrader()
    
    # Add simple arbitrage strategy
    auto_trader.add_strategy(
        'simple_arbitrage',
        auto_trader.simple_arbitrage_strategy,
        {'target_price': 48.0, 'volume': 0.2}
    )
    
    # Execute strategy
    strategy_result = auto_trader.execute_strategy('simple_arbitrage', auction_id)
    
    if strategy_result.get('success'):
        print("✅ Automated strategy executed successfully")
    else:
        print(f"❌ Strategy failed: {strategy_result.get('error')}")
    
    # Test 5: Export order history
    print("\n💾 Test 5: Exporting order history...")
    
    filename = tracker.export_order_history()
    print(f"✅ Order history exported to: {filename}")
    
    print("\n🏆 Order Management System Testing Complete!")
    
    return tracker, auto_trader

if __name__ == "__main__":
    test_order_management()
