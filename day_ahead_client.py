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

from auth import get_authenticator
from config import config


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
        
        if close_bidding_from:
            params["closeBiddingFrom"] = close_bidding_from.isoformat()
        if close_bidding_to:
            params["closeBiddingTo"] = close_bidding_to.isoformat()
        
        auth = get_authenticator()
        headers = await auth.get_auth_headers_async()
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params) as response:
                    response.raise_for_status()
                    auctions = await response.json()
                    self.logger.info(f"Retrieved {len(auctions)} auctions")
                    return auctions
        except aiohttp.ClientError as e:
            self.logger.error(f"Failed to get auctions: {e}")
            raise
    
    async def get_auction(self, auction_id: str) -> Dict[str, Any]:
        """
        Get details of a specific auction
        
        Args:
            auction_id: The auction identifier
            
        Returns:
            Auction details
        """
        url = self._get_url(f"auctions/{auction_id}")
        auth = get_authenticator()
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
        
        auth = get_authenticator()
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
        
        auth = get_authenticator()
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
        auth = get_authenticator()
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
        auth = get_authenticator()
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
        auth = get_authenticator()
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
        auth = get_authenticator()
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
        Submit a new curve order
        
        Args:
            order: Curve order request object
            
        Returns:
            Order submission response
        """
        url = self._get_url("curveorders")
        auth = get_authenticator()
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
    
    async def get_curve_order(self, order_id: str) -> Dict[str, Any]:
        """
        Get details of a specific curve order
        
        Args:
            order_id: The order identifier
            
        Returns:
            Curve order details
        """
        url = self._get_url(f"curveorders/{order_id}")
        auth = get_authenticator()
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
        auth = get_authenticator()
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
    
    async def get_system_state(self) -> Dict[str, Any]:
        """
        Get current system state
        
        Returns:
            System state information
        """
        url = self._get_url("state")
        auth = get_authenticator()
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
