"""
Test Intraday Market Data Endpoints
Test the Nord Pool Intraday API endpoints with working authentication
"""

import requests
import json
import logging
from datetime import datetime
from intraday_auth import IntradayAuthenticator

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class IntradayAPITester:
    """Test intraday API endpoints"""
    
    def __init__(self):
        self.auth = IntradayAuthenticator()
        
        # BRM Intraday API URLs (from operator instructions)
        self.base_url_test = "https://intraday2-api.test.nordpoolgroup.com"
        self.base_url_prod = "https://intraday2-api.nordpoolgroup.com"
        
        # Use test environment
        self.base_url = self.base_url_test
        
        # WebSocket URLs for reference
        self.ws_trading_url = "wss://intraday2-ws.test.nordpoolgroup.com:443"
        self.ws_market_url = "wss://intraday-pmd-api-ws-brm.test.nordpoolgroup.com:443"
    
    def test_delivery_areas(self):
        """Test delivery areas endpoint"""
        logger.info("Testing delivery areas endpoint...")
        
        try:
            headers = self.auth.get_auth_headers()
            if not headers:
                logger.error("Failed to get auth headers")
                return None
            
            url = f"{self.base_url}/api/v1/deliveryareas"
            response = requests.get(url, headers=headers, timeout=30)
            
            logger.info(f"Delivery areas response: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"Found {len(data.get('deliveryAreas', []))} delivery areas")
                
                # Show first few areas
                for area in data.get('deliveryAreas', [])[:3]:
                    logger.info(f"  Area: {area.get('code')} - {area.get('name')}")
                
                return data
            else:
                logger.error(f"Failed to get delivery areas: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error testing delivery areas: {e}")
            return None
    
    def test_contracts(self):
        """Test contracts endpoint"""
        logger.info("Testing contracts endpoint...")
        
        try:
            headers = self.auth.get_auth_headers()
            if not headers:
                logger.error("Failed to get auth headers")
                return None
            
            url = f"{self.base_url}/api/v1/contracts"
            response = requests.get(url, headers=headers, timeout=30)
            
            logger.info(f"Contracts response: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                contracts = data.get('contracts', [])
                logger.info(f"Found {len(contracts)} contracts")
                
                # Show first few contracts
                for contract in contracts[:3]:
                    logger.info(f"  Contract: {contract.get('id')} - {contract.get('name')}")
                    logger.info(f"    Delivery: {contract.get('deliveryStart')} to {contract.get('deliveryEnd')}")
                    logger.info(f"    Area: {contract.get('areaCode')}")
                
                return data
            else:
                logger.error(f"Failed to get contracts: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error testing contracts: {e}")
            return None
    
    def test_trades(self):
        """Test trades endpoint"""
        logger.info("Testing trades endpoint...")
        
        try:
            headers = self.auth.get_auth_headers()
            if not headers:
                logger.error("Failed to get auth headers")
                return None
            
            url = f"{self.base_url}/api/v1/trades"
            params = {'limit': 10}
            response = requests.get(url, headers=headers, params=params, timeout=30)
            
            logger.info(f"Trades response: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                trades = data.get('trades', [])
                logger.info(f"Found {len(trades)} recent trades")
                
                # Show first few trades
                for trade in trades[:3]:
                    logger.info(f"  Trade: {trade.get('id')}")
                    logger.info(f"    Contract: {trade.get('contractId')}")
                    logger.info(f"    Price: {trade.get('price')} EUR/MWh")
                    logger.info(f"    Quantity: {trade.get('quantity')} MW")
                    logger.info(f"    Time: {trade.get('timestamp')}")
                
                return data
            else:
                logger.error(f"Failed to get trades: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error testing trades: {e}")
            return None
    
    def test_market_data(self):
        """Test market data endpoint"""
        logger.info("Testing market data endpoint...")
        
        try:
            headers = self.auth.get_auth_headers()
            if not headers:
                logger.error("Failed to get auth headers")
                return None
            
            url = f"{self.base_url}/api/v1/marketdata"
            response = requests.get(url, headers=headers, timeout=30)
            
            logger.info(f"Market data response: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                logger.info("Market data retrieved successfully")
                logger.info(f"Data keys: {list(data.keys())}")
                return data
            else:
                logger.error(f"Failed to get market data: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error testing market data: {e}")
            return None
    
    def test_capacities(self):
        """Test capacities endpoint"""
        logger.info("Testing capacities endpoint...")
        
        try:
            headers = self.auth.get_auth_headers()
            if not headers:
                logger.error("Failed to get auth headers")
                return None
            
            url = f"{self.base_url}/api/v1/capacities"
            response = requests.get(url, headers=headers, timeout=30)
            
            logger.info(f"Capacities response: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                capacities = data.get('capacities', [])
                logger.info(f"Found {len(capacities)} capacity entries")
                
                # Show first few capacities
                for capacity in capacities[:3]:
                    logger.info(f"  Capacity: {capacity.get('fromArea')} -> {capacity.get('toArea')}")
                    logger.info(f"    Available: {capacity.get('available')} MW")
                
                return data
            else:
                logger.error(f"Failed to get capacities: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error testing capacities: {e}")
            return None
    
    def run_all_tests(self):
        """Run all endpoint tests"""
        logger.info("🚀 Starting comprehensive intraday API tests...")
        
        # Test authentication first
        auth_result = self.auth.test_authentication()
        if not auth_result['success']:
            logger.error("❌ Authentication failed, cannot proceed with tests")
            return False
        
        logger.info("✅ Authentication successful, proceeding with endpoint tests...")
        
        results = {}
        
        # Test all endpoints
        results['delivery_areas'] = self.test_delivery_areas()
        results['contracts'] = self.test_contracts()
        results['trades'] = self.test_trades()
        results['market_data'] = self.test_market_data()
        results['capacities'] = self.test_capacities()
        
        # Summary
        successful_tests = sum(1 for result in results.values() if result is not None)
        total_tests = len(results)
        
        logger.info(f"\n📊 Test Results Summary:")
        logger.info(f"✅ Successful tests: {successful_tests}/{total_tests}")
        
        for endpoint, result in results.items():
            status = "✅ PASS" if result is not None else "❌ FAIL"
            logger.info(f"  {endpoint}: {status}")
        
        if successful_tests == total_tests:
            logger.info("🎉 All intraday API tests passed!")
            return True
        else:
            logger.warning(f"⚠️  {total_tests - successful_tests} tests failed")
            return False


def main():
    """Main test function"""
    tester = IntradayAPITester()
    
    logger.info("🔧 BRM Intraday API Comprehensive Test")
    logger.info(f"Base URL: {tester.base_url}")
    logger.info(f"WebSocket Trading: {tester.ws_trading_url}")
    logger.info(f"WebSocket Market Data: {tester.ws_market_url}")
    
    success = tester.run_all_tests()
    
    if success:
        print("\n🎉 Intraday API is fully operational!")
        print("Ready to integrate with the trading dashboard!")
    else:
        print("\n⚠️  Some intraday API tests failed")
        print("Check the logs for details")


if __name__ == "__main__":
    main()
