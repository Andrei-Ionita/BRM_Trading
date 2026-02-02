"""
Day-Ahead Market API Client for BRM Trading Bot
Handles REST API interactions with the Day-Ahead auction system
"""
import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass
from enum import Enum

import aiohttp
import requests

from auction_auth import BRMAuctionAuth
from config import config

# Global auction auth instance
_auction_auth = None

def get_auction_auth() -> BRMAuctionAuth:
    """Get or create auction auth instance"""
    global _auction_auth
    if _auction_auth is None:
        _auction_auth = BRMAuctionAuth()
    return _auction_auth


class OrderSide(Enum):
    """Order side enumeration"""
    BUY = "BUY"
    SELL = "SELL"


class OrderState(Enum):
    """Order state enumeration"""
    ACTIVE = "ACTI"
    INACTIVE = "IACT"
    HIBERNATED = "HIBE"
    PENDING = "PENDING"


@dataclass
class BlockOrderRequest:
    """Block order request structure"""
    name: str
    price: float
    minimum_acceptance_ratio: float
    linked_to: Optional[str]
    exclusive_group: Optional[str]
    periods: List[Dict[str, Any]]
    is_spread_block: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API request"""
        return {
            "blocks": [{
                "name": self.name,
                "price": self.price,
                "minimumAcceptanceRatio": self.minimum_acceptance_ratio,
                "linkedTo": self.linked_to,
                "exclusiveGroup": self.exclusive_group,
                "periods": self.periods,
                "isSpreadBlock": self.is_spread_block
            }]
        }


@dataclass
class CurveOrderRequest:
    """Curve order request structure"""
    name: str
    contract_id: str
    side: OrderSide
    curve_points: List[Dict[str, Any]]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API request"""
        return {
            "name": self.name,
            "contractId": self.contract_id,
            "side": self.side.value,
            "curvePoints": self.curve_points
        }


class DayAheadClient:
    """Client for interacting with the Day-Ahead market API"""
    
    def __init__(self):
        self.base_url = config.day_ahead_base_url
        self.api_version = config.api_version
        self.logger = logging.getLogger(__name__)
    
    def _get_url(self, endpoint: str) -> str:
        """Construct full URL for API endpoint"""
        return f"{self.base_url}/api/v{self.api_version}/{endpoint}"
    
    async def get_auctions(
        self,
        close_bidding_from: Optional[datetime] = None,
        close_bidding_to: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Get list of auctions with optional date filtering

        Args:
            close_bidding_from: Start date for auction filtering
            close_bidding_to: End date for auction filtering

        Returns:
            List of auction objects
        """
        url = self._get_url("auctions")
        params = {}

        # Use simple YYYY-MM-DD format as expected by BRM API
        if close_bidding_from:
            params["closeBiddingFrom"] = close_bidding_from.strftime("%Y-%m-%d")
        if close_bidding_to:
            params["closeBiddingTo"] = close_bidding_to.strftime("%Y-%m-%d")

        auth = get_auction_auth()
        headers = await auth.get_auth_headers_async()

        self.logger.info(f"Fetching auctions with params: {params}")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params) as response:
                    if response.status == 200:
                        auctions = await response.json()
                        self.logger.info(f"Retrieved {len(auctions)} auctions")
                        return auctions
                    else:
                        error_text = await response.text()
                        self.logger.error(f"Failed to get auctions: {response.status}, message='{error_text}', url='{url}'")
                        return []
        except aiohttp.ClientError as e:
            self.logger.error(f"Failed to get auctions: {e}")
            return []
    
    async def get_auction(self, auction_id: str) -> Dict[str, Any]:
        """
        Get details of a specific auction
        
        Args:
            auction_id: The auction identifier
            
        Returns:
            Auction details
        """
        url = self._get_url(f"auctions/{auction_id}")
        auth = get_auction_auth()
        headers = await auth.get_auth_headers_async()
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    response.raise_for_status()
                    auction = await response.json()
                    self.logger.info(f"Retrieved auction {auction_id}")
                    return auction
        except aiohttp.ClientError as e:
            self.logger.error(f"Failed to get auction {auction_id}: {e}")
            raise
    
    async def get_auction_orders(
        self, 
        auction_id: str,
        portfolios: Optional[List[str]] = None,
        area_codes: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Get orders for a specific auction
        
        Args:
            auction_id: The auction identifier
            portfolios: List of portfolio IDs to filter by
            area_codes: List of area codes to filter by
            
        Returns:
            Combined orders response
        """
        url = self._get_url(f"auctions/{auction_id}/orders")
        params = {}
        
        if portfolios:
            params["portfolios"] = portfolios
        if area_codes:
            params["areaCodes"] = area_codes
        
        auth = get_auction_auth()
        headers = await auth.get_auth_headers_async()
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params) as response:
                    response.raise_for_status()
                    orders = await response.json()
                    self.logger.info(f"Retrieved orders for auction {auction_id}")
                    return orders
        except aiohttp.ClientError as e:
            self.logger.error(f"Failed to get orders for auction {auction_id}: {e}")
            raise
    
    async def get_auction_trades(
        self, 
        auction_id: str,
        portfolios: Optional[List[str]] = None,
        area_codes: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Get trades for a specific auction
        
        Args:
            auction_id: The auction identifier
            portfolios: List of portfolio IDs to filter by
            area_codes: List of area codes to filter by
            
        Returns:
            List of trade results
        """
        url = self._get_url(f"auctions/{auction_id}/trades")
        params = {}
        
        if portfolios:
            params["portfolios"] = portfolios
        if area_codes:
            params["areaCodes"] = area_codes
        
        auth = get_auction_auth()
        headers = await auth.get_auth_headers_async()
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params) as response:
                    response.raise_for_status()
                    trades = await response.json()
                    self.logger.info(f"Retrieved trades for auction {auction_id}")
                    return trades
        except aiohttp.ClientError as e:
            self.logger.error(f"Failed to get trades for auction {auction_id}: {e}")
            raise
    
    async def get_auction_prices(self, auction_id: str) -> List[Dict[str, Any]]:
        """
        Get prices for a specific auction
        
        Args:
            auction_id: The auction identifier
            
        Returns:
            List of auction prices
        """
        url = self._get_url(f"auctions/{auction_id}/prices")
        auth = get_auction_auth()
        headers = await auth.get_auth_headers_async()
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    response.raise_for_status()
                    prices = await response.json()
                    self.logger.info(f"Retrieved prices for auction {auction_id}")
                    return prices
        except aiohttp.ClientError as e:
            self.logger.error(f"Failed to get prices for auction {auction_id}: {e}")
            raise
    
    async def submit_block_order(self, order: BlockOrderRequest) -> Dict[str, Any]:
        """
        Submit a new block order
        
        Args:
            order: Block order request object
            
        Returns:
            Order submission response
        """
        url = self._get_url("blockorders")
        auth = get_auction_auth()
        headers = await auth.get_auth_headers_async()
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url, 
                    headers=headers, 
                    json=order.to_dict()
                ) as response:
                    response.raise_for_status()
                    result = await response.json()
                    self.logger.info(f"Block order submitted successfully: {order.name}")
                    return result
        except aiohttp.ClientError as e:
            self.logger.error(f"Failed to submit block order {order.name}: {e}")
            raise
    
    async def get_block_order(self, order_id: str) -> Dict[str, Any]:
        """
        Get details of a specific block order
        
        Args:
            order_id: The order identifier
            
        Returns:
            Block order details
        """
        url = self._get_url(f"blockorders/{order_id}")
        auth = get_auction_auth()
        headers = await auth.get_auth_headers_async()
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    response.raise_for_status()
                    order = await response.json()
                    self.logger.info(f"Retrieved block order {order_id}")
                    return order
        except aiohttp.ClientError as e:
            self.logger.error(f"Failed to get block order {order_id}: {e}")
            raise
    
    async def modify_block_order(
        self, 
        order_id: str, 
        modifications: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Modify an existing block order
        
        Args:
            order_id: The order identifier
            modifications: Dictionary of fields to modify
            
        Returns:
            Order modification response
        """
        url = self._get_url(f"blockorders/{order_id}")
        auth = get_auction_auth()
        headers = await auth.get_auth_headers_async()
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.patch(
                    url, 
                    headers=headers, 
                    json=modifications
                ) as response:
                    response.raise_for_status()
                    result = await response.json()
                    self.logger.info(f"Block order {order_id} modified successfully")
                    return result
        except aiohttp.ClientError as e:
            self.logger.error(f"Failed to modify block order {order_id}: {e}")
            raise
    
    async def submit_curve_order(self, order: CurveOrderRequest) -> Dict[str, Any]:
        """
        Submit a new curve order (legacy method - use submit_da_curves instead)
        """
        url = self._get_url("curveorders")
        auth = get_auction_auth()
        headers = await auth.get_auth_headers_async()

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    headers=headers,
                    json=order.to_dict()
                ) as response:
                    response.raise_for_status()
                    result = await response.json()
                    self.logger.info(f"Curve order submitted successfully: {order.name}")
                    return result
        except aiohttp.ClientError as e:
            self.logger.error(f"Failed to submit curve order {order.name}: {e}")
            raise

    async def get_open_auction_for_date(self, delivery_date: str) -> Optional[Dict[str, Any]]:
        """
        Get the open auction for a specific delivery date.

        Args:
            delivery_date: Delivery date in YYYY-MM-DD format

        Returns:
            Auction dict or None if not found
        """
        import re
        from datetime import datetime, timedelta

        # Get auctions with date filter (required by API)
        target_date = datetime.strptime(delivery_date, "%Y-%m-%d")
        from_date = target_date - timedelta(days=1)
        to_date = target_date + timedelta(days=2)

        # Convert delivery_date to compact format for ID matching (YYYYMMDD)
        target_date_compact = delivery_date.replace("-", "")

        try:
            auctions = await self.get_auctions(
                close_bidding_from=from_date,
                close_bidding_to=to_date
            )

            # Find auction for the target delivery date that is open
            for auction in auctions:
                auction_id = auction.get('id', '')
                auction_delivery = auction.get('deliveryDate', '') or ''
                auction_state = auction.get('state', '').lower()

                self.logger.debug(f"Auction {auction_id}: delivery={auction_delivery}, state={auction_state}")

                # Check if delivery date matches (either in deliveryDate field or auction ID)
                # Auction IDs like "BRM_QH_DA_1-20260203" contain the date as YYYYMMDD
                date_matches = False
                if auction_delivery and delivery_date in auction_delivery:
                    date_matches = True
                elif target_date_compact in auction_id:
                    date_matches = True

                # Skip test auctions (prefer production auctions)
                is_test = 'test' in auction_id.lower()

                if date_matches and auction_state == 'open' and not is_test:
                    self.logger.info(f"Found open auction {auction_id} for {delivery_date}")
                    return auction

            # Second pass: accept test auctions if no production auction found
            for auction in auctions:
                auction_id = auction.get('id', '')
                auction_delivery = auction.get('deliveryDate', '') or ''
                auction_state = auction.get('state', '').lower()

                date_matches = False
                if auction_delivery and delivery_date in auction_delivery:
                    date_matches = True
                elif target_date_compact in auction_id:
                    date_matches = True

                if date_matches and auction_state == 'open':
                    self.logger.info(f"Found open test auction {auction_id} for {delivery_date}")
                    return auction

            # If no open auction, show available auctions
            self.logger.warning(f"No open auction found for {delivery_date}")
            for auction in auctions[:5]:
                self.logger.info(f"  Available: {auction.get('id')} - {auction.get('deliveryDate')} - {auction.get('state')}")

            return None

        except Exception as e:
            self.logger.error(f"Error finding auction for {delivery_date}: {e}")
            return None

    async def get_auction_contracts(self, auction_id: str) -> List[Dict[str, Any]]:
        """
        Get available contracts (delivery periods) for an auction.

        Args:
            auction_id: The auction ID

        Returns:
            List of contract dicts with 'id', 'deliveryStart', 'deliveryEnd'
        """
        try:
            # First, try the dedicated contracts endpoint
            contracts_from_api = await self._fetch_contracts_endpoint(auction_id)
            if contracts_from_api and len(contracts_from_api) >= 90:
                self.logger.info(f"Found {len(contracts_from_api)} contracts from API for auction {auction_id}")
                if contracts_from_api:
                    self.logger.info(f"Sample contract: {contracts_from_api[0]}")
                return contracts_from_api

            # Fall back to auction details
            auction_details = await self.get_auction(auction_id)

            if not auction_details:
                return self._generate_qh_contracts_if_needed(auction_id)

            # Log full structure for debugging
            self.logger.info(f"Auction details keys: {list(auction_details.keys())}")
            # Log a summary of the auction
            import json
            self.logger.info(f"Auction summary: id={auction_details.get('id')}, state={auction_details.get('state')}")
            # Dump full auction details to see structure
            self.logger.info(f"Full auction JSON: {json.dumps(auction_details, indent=2, default=str)[:3000]}")

            # Extract contracts from nested structure
            # Structure: auction_details['contracts'] = [{"areaCode": "TEL", "contracts": [...]}]
            all_periods = []

            if 'contracts' in auction_details and isinstance(auction_details['contracts'], list):
                for area_contracts in auction_details['contracts']:
                    if isinstance(area_contracts, dict):
                        area_code = area_contracts.get('areaCode', '')
                        nested_contracts = area_contracts.get('contracts', [])
                        if nested_contracts:
                            self.logger.info(f"Found {len(nested_contracts)} contracts for area {area_code}")
                            # Filter for QH (quarter-hourly) contracts only
                            qh_contracts = [c for c in nested_contracts if c.get('id', '').endswith('_QH')]
                            self.logger.info(f"Found {len(qh_contracts)} quarter-hourly contracts")
                            all_periods.extend(qh_contracts)

            # Fallback to products if contracts not found
            if not all_periods:
                if 'products' in auction_details and isinstance(auction_details['products'], list):
                    for product in auction_details['products']:
                        if isinstance(product, dict):
                            if 'deliveryPeriods' in product:
                                all_periods.extend(product['deliveryPeriods'])
                            if 'contracts' in product:
                                all_periods.extend(product['contracts'])

            # Add interval numbers to contracts for easier matching
            import re
            for contract in all_periods:
                contract_id = contract.get('id', '')
                # Extract interval from contract ID like BRM_QH_DA_1-20260204-35_QH
                match = re.search(r'-(\d+)_QH$', contract_id)
                if match:
                    contract['interval'] = int(match.group(1))

            # Log sample if found
            if all_periods:
                self.logger.info(f"Sample contract: {all_periods[0]}")

            # If still no contracts found for QH auction, generate them
            if not all_periods or len(all_periods) < 90:
                self.logger.warning(f"Only found {len(all_periods)} contracts, generating QH contracts")
                all_periods = self._generate_qh_contracts_if_needed(auction_id)

            self.logger.info(f"Found {len(all_periods)} contracts for auction {auction_id}")
            return all_periods

        except Exception as e:
            self.logger.error(f"Error getting contracts for auction {auction_id}: {e}")
            return self._generate_qh_contracts_if_needed(auction_id)

    async def _fetch_contracts_endpoint(self, auction_id: str) -> List[Dict[str, Any]]:
        """Try to fetch contracts from dedicated API endpoint."""
        auth = get_auction_auth()
        headers = await auth.get_auth_headers_async()

        # Try multiple possible endpoints
        endpoints = [
            f"auctions/{auction_id}/contracts",
            f"auctions/{auction_id}/deliveryperiods",
            f"contracts?auctionId={auction_id}",
        ]

        for endpoint in endpoints:
            url = self._get_url(endpoint)
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=headers) as response:
                        if response.status == 200:
                            data = await response.json()
                            contracts = data if isinstance(data, list) else data.get('items', data.get('contracts', []))
                            if contracts:
                                self.logger.info(f"Endpoint '{endpoint}' returned {len(contracts)} contracts")
                                # Filter contracts to only those matching our auction
                                matching = [c for c in contracts if auction_id in str(c.get('id', '')) or auction_id in str(c.get('auctionId', ''))]
                                self.logger.info(f"Contracts matching auction {auction_id}: {len(matching)}")
                                if matching:
                                    self.logger.info(f"First matching contract: {matching[0]}")
                                    return matching
                                elif contracts:
                                    self.logger.info(f"No exact match. First contract: {contracts[0]}")
                        else:
                            self.logger.debug(f"Endpoint '{endpoint}' returned {response.status}")
            except Exception as e:
                self.logger.debug(f"Endpoint '{endpoint}' failed: {e}")

        return []

    def _generate_qh_contracts_if_needed(self, auction_id: str) -> List[Dict[str, Any]]:
        """Generate QH contracts if this is a QH auction."""
        import re
        if '_QH_' in auction_id or 'QH' in auction_id:
            date_match = re.search(r'(\d{8})$', auction_id)
            if date_match:
                date_str = date_match.group(1)
                self.logger.info(f"Generating 96 QH contracts for auction {auction_id}")
                return self._generate_qh_contracts(auction_id, date_str)
        return []

    def _generate_qh_contracts(self, auction_id: str, date_str: str) -> List[Dict[str, Any]]:
        """
        Generate 96 quarter-hourly contract definitions for a QH auction.

        Args:
            auction_id: The auction ID (e.g., BRM_QH_DA_1-20260203)
            date_str: Date in YYYYMMDD format

        Returns:
            List of 96 contract dicts
        """
        from datetime import datetime, timedelta

        contracts = []
        base_date = datetime.strptime(date_str, "%Y%m%d")

        for interval in range(1, 97):
            # Calculate start time for this interval
            minutes_offset = (interval - 1) * 15
            start_time = base_date + timedelta(minutes=minutes_offset)
            end_time = start_time + timedelta(minutes=15)

            # BRM contract ID format variations to try
            # The API showed: BRM_QH_DA_1-20260204-96_QH
            contract_id = f"{auction_id}-{interval}_QH"

            contract = {
                'id': contract_id,
                'interval': interval,
                'deliveryStart': start_time.isoformat(),
                'deliveryEnd': end_time.isoformat(),
                'auctionId': auction_id
            }
            contracts.append(contract)

        return contracts

    async def submit_da_curves(
        self,
        auction_id: str,
        curves: List[Dict[str, Any]],
        area_code: str = "TEL",
        portfolio: str = "ADREM - DA"
    ) -> Dict[str, Any]:
        """
        Submit DA curve orders using the correct BRM API format.

        Args:
            auction_id: The auction ID
            curves: List of curve dicts with contractId, auctionId, priceVolumePairs
            area_code: Delivery area code (default "TEL" for Romania)
            portfolio: Portfolio name (default "ADREM - DA")

        Returns:
            API response dict
        """
        url = self._get_url("curveorders")
        auth = get_auction_auth()
        headers = await auth.get_auth_headers_async()

        # Construct order data according to BRM API specification (PascalCase)
        order_data = {
            "AuctionId": auction_id,
            "AreaCode": area_code,
            "Portfolio": portfolio,
            "Curves": curves
        }

        self.logger.info(f"Submitting {len(curves)} curves to auction {auction_id}")

        # First try PUT to replace existing orders, fall back to POST
        try:
            async with aiohttp.ClientSession() as session:
                # Try PUT first (replace existing)
                async with session.put(
                    url,
                    headers=headers,
                    json=order_data
                ) as response:
                    if response.status in [200, 201, 202]:
                        result = await response.json()
                        self.logger.info(f"DA curves updated successfully via PUT")
                        return {"success": True, "data": result}
                    elif response.status == 405:
                        # PUT not allowed, will try POST below
                        self.logger.debug("PUT not allowed, trying POST")
                    else:
                        error_text = await response.text()
                        self.logger.debug(f"PUT failed: {response.status} - {error_text}")
        except Exception as e:
            self.logger.debug(f"PUT request failed: {e}")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    headers=headers,
                    json=order_data
                ) as response:
                    if response.status in [200, 201, 202]:
                        result = await response.json()
                        self.logger.info(f"DA curves submitted successfully")
                        return {"success": True, "data": result}
                    else:
                        error_text = await response.text()
                        self.logger.error(f"DA curves submission failed: {response.status} - {error_text}")
                        return {"success": False, "error": error_text, "status": response.status}

        except Exception as e:
            self.logger.error(f"Error submitting DA curves: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_curve_order(self, order_id: str) -> Dict[str, Any]:
        """
        Get details of a specific curve order
        
        Args:
            order_id: The order identifier
            
        Returns:
            Curve order details
        """
        url = self._get_url(f"curveorders/{order_id}")
        auth = get_auction_auth()
        headers = await auth.get_auth_headers_async()
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    response.raise_for_status()
                    order = await response.json()
                    self.logger.info(f"Retrieved curve order {order_id}")
                    return order
        except aiohttp.ClientError as e:
            self.logger.error(f"Failed to get curve order {order_id}: {e}")
            raise
    
    async def modify_curve_order(
        self, 
        order_id: str, 
        modifications: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Modify an existing curve order
        
        Args:
            order_id: The order identifier
            modifications: Dictionary of fields to modify
            
        Returns:
            Order modification response
        """
        url = self._get_url(f"curveorders/{order_id}")
        auth = get_auction_auth()
        headers = await auth.get_auth_headers_async()
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.patch(
                    url, 
                    headers=headers, 
                    json=modifications
                ) as response:
                    response.raise_for_status()
                    result = await response.json()
                    self.logger.info(f"Curve order {order_id} modified successfully")
                    return result
        except aiohttp.ClientError as e:
            self.logger.error(f"Failed to modify curve order {order_id}: {e}")
            raise
    
    async def update_da_curves(
        self,
        order_id: str,
        auction_id: str,
        curves: List[Dict[str, Any]],
        area_code: str = "TEL",
        portfolio: str = "ADREM - DA"
    ) -> Dict[str, Any]:
        """
        Update existing DA curve orders via PATCH.

        Args:
            order_id: Existing order ID to update
            auction_id: The auction ID
            curves: List of curve dicts
            area_code: Delivery area code
            portfolio: Portfolio name

        Returns:
            API response dict
        """
        url = self._get_url(f"curveorders/{order_id}")
        auth = get_auction_auth()
        headers = await auth.get_auth_headers_async()

        # Construct update data
        update_data = {
            "AuctionId": auction_id,
            "AreaCode": area_code,
            "Portfolio": portfolio,
            "Curves": curves
        }

        self.logger.info(f"Updating existing curve order {order_id} with {len(curves)} curves")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.patch(
                    url,
                    headers=headers,
                    json=update_data
                ) as response:
                    if response.status in [200, 201, 202, 204]:
                        try:
                            result = await response.json()
                        except:
                            result = {}
                        self.logger.info(f"DA curves updated successfully via PATCH")
                        return {"success": True, "data": result}
                    else:
                        error_text = await response.text()
                        self.logger.error(f"DA curves update failed: {response.status} - {error_text}")
                        return {"success": False, "error": error_text, "status": response.status}

        except Exception as e:
            self.logger.error(f"Error updating DA curves: {e}")
            return {"success": False, "error": str(e)}

    async def delete_curve_order(self, order_id: str) -> bool:
        """
        Delete an existing curve order.

        Args:
            order_id: The order identifier

        Returns:
            True if deleted successfully
        """
        url = self._get_url(f"curveorders/{order_id}")
        auth = get_auction_auth()
        headers = await auth.get_auth_headers_async()

        try:
            async with aiohttp.ClientSession() as session:
                async with session.delete(url, headers=headers) as response:
                    if response.status in [200, 204]:
                        self.logger.info(f"Curve order {order_id} deleted successfully")
                        return True
                    else:
                        error_text = await response.text()
                        self.logger.error(f"Failed to delete curve order {order_id}: {response.status} - {error_text}")
                        return False
        except aiohttp.ClientError as e:
            self.logger.error(f"Failed to delete curve order {order_id}: {e}")
            return False

    async def get_existing_curve_orders(
        self,
        auction_id: str,
        portfolio: str = "ADREM - DA",
        area_code: str = "TEL"
    ) -> List[Dict[str, Any]]:
        """
        Get existing curve orders for an auction.

        Args:
            auction_id: The auction ID
            portfolio: Portfolio name
            area_code: Area code

        Returns:
            List of existing curve orders
        """
        try:
            orders_data = await self.get_auction_orders(auction_id)

            # Extract curve orders from response
            curve_orders = []
            if isinstance(orders_data, dict):
                # Check various possible structures
                if 'curveOrders' in orders_data:
                    curve_orders = orders_data['curveOrders']
                elif 'curves' in orders_data:
                    curve_orders = orders_data['curves']
                elif 'orders' in orders_data:
                    curve_orders = [o for o in orders_data['orders'] if o.get('type') == 'curve']
            elif isinstance(orders_data, list):
                curve_orders = orders_data

            self.logger.info(f"Found {len(curve_orders)} existing curve orders for auction {auction_id}")
            return curve_orders

        except Exception as e:
            self.logger.warning(f"Could not fetch existing orders: {e}")
            return []

    async def delete_existing_curve_orders(
        self,
        auction_id: str,
        portfolio: str = "ADREM - DA",
        area_code: str = "TEL"
    ) -> int:
        """
        Delete all existing curve orders for an auction/portfolio.

        Args:
            auction_id: The auction ID
            portfolio: Portfolio name
            area_code: Area code

        Returns:
            Number of orders deleted
        """
        existing_orders = await self.get_existing_curve_orders(auction_id, portfolio, area_code)

        deleted_count = 0
        for order in existing_orders:
            order_id = order.get('id') or order.get('orderId')
            if order_id:
                if await self.delete_curve_order(order_id):
                    deleted_count += 1

        self.logger.info(f"Deleted {deleted_count} existing curve orders")
        return deleted_count

    async def get_system_state(self) -> Dict[str, Any]:
        """
        Get current system state

        Returns:
            System state information
        """
        url = self._get_url("state")
        auth = get_auction_auth()
        headers = await auth.get_auth_headers_async()

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    response.raise_for_status()
                    state = await response.json()
                    self.logger.info("Retrieved system state")
                    return state
        except aiohttp.ClientError as e:
            self.logger.error(f"Failed to get system state: {e}")
            raise
