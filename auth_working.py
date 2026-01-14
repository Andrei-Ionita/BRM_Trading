"""
Working Authentication module for BRM Trading Bot
Uses the verified working credentials and methods
"""
import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

import aiohttp
import requests
from dataclasses import dataclass

from config import config


@dataclass
class TokenInfo:
    """Container for authentication token information"""
    access_token: str
    token_type: str
    expires_in: int
    expires_at: datetime
    scope: Optional[str] = None
    
    @property
    def is_expired(self) -> bool:
        """Check if token is expired or will expire soon"""
        buffer_time = timedelta(minutes=config.token_refresh_buffer_minutes)
        return datetime.now() >= (self.expires_at - buffer_time)
    
    @property
    def bearer_token(self) -> str:
        """Get the token formatted for Authorization header"""
        return f"{self.token_type} {self.access_token}"


class BRMAuthenticator:
    """Handles authentication with BRM SSO service using WORKING credentials"""
    
    def __init__(self):
        """Initialize authenticator with working BRM credentials"""
        self.token_info: Optional[TokenInfo] = None
        self.logger = logging.getLogger(__name__)
        
        # The WORKING credentials from our successful test
        self.basic_auth_header = "Basic Y2xpZW50X2ludHJhZGF5X2FwaToxeEI5SWsxeHNFdTJuYndWYTFCUg=="
        self.username = "Test_IntradayAPI_ADREM"
        self.password = "nR(B8fDY{485Nq4mu"  # Correct password with special characters
        self.scope = "intraday_api"
    
    def get_token_sync(self) -> TokenInfo:
        """Synchronously obtain an access token"""
        if self.token_info and not self.token_info.is_expired:
            return self.token_info
        
        return self._get_token_sync()
    
    async def get_token_async(self) -> TokenInfo:
        """Asynchronously obtain an access token"""
        if self.token_info and not self.token_info.is_expired:
            return self.token_info
        
        return await self._get_token_async()
    
    def _get_token_sync(self) -> TokenInfo:
        """Get token using the working method (sync)"""
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": self.basic_auth_header
        }
        
        # The working form data
        token_data = {
            "grant_type": "password",
            "username": self.username,
            "password": self.password,
            "scope": self.scope
        }
        
        try:
            self.logger.info(f"Requesting token using working method from {config.sso_token_url}")
            response = requests.post(
                config.sso_token_url,
                data=token_data,
                headers=headers,
                timeout=30
            )
            response.raise_for_status()
            
            token_response = response.json()
            return self._create_token_info(token_response)
            
        except requests.RequestException as e:
            self.logger.error(f"Failed to obtain token: {e}")
            raise
    
    async def _get_token_async(self) -> TokenInfo:
        """Get token using the working method (async)"""
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": self.basic_auth_header
        }
        
        token_data = {
            "grant_type": "password",
            "username": self.username,
            "password": self.password,
            "scope": self.scope
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                self.logger.info(f"Requesting token using working method from {config.sso_token_url}")
                async with session.post(
                    config.sso_token_url,
                    data=token_data,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    response.raise_for_status()
                    token_response = await response.json()
            
            return self._create_token_info(token_response)
            
        except aiohttp.ClientError as e:
            self.logger.error(f"Failed to obtain token: {e}")
            raise
    
    def _create_token_info(self, token_response: Dict[str, Any]) -> TokenInfo:
        """Create TokenInfo from API response"""
        try:
            # Calculate expiration time
            expires_at = datetime.now() + timedelta(seconds=token_response["expires_in"])
            
            self.token_info = TokenInfo(
                access_token=token_response["access_token"],
                token_type=token_response.get("token_type", "Bearer"),
                expires_in=token_response["expires_in"],
                expires_at=expires_at,
                scope=token_response.get("scope")
            )
            
            self.logger.info(f"Token acquired successfully, expires at {expires_at}")
            return self.token_info
            
        except KeyError as e:
            self.logger.error(f"Invalid token response format: {e}")
            self.logger.error(f"Response: {token_response}")
            raise
    
    def get_auth_headers(self) -> Dict[str, str]:
        """Get headers with current valid token"""
        if not self.token_info or self.token_info.is_expired:
            self.get_token_sync()
        
        return {
            "Authorization": self.token_info.bearer_token,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
    
    async def get_auth_headers_async(self) -> Dict[str, str]:
        """Get headers with current valid token (async)"""
        if not self.token_info or self.token_info.is_expired:
            await self.get_token_async()
        
        return {
            "Authorization": self.token_info.bearer_token,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }


# Global authenticator instance
authenticator: Optional[BRMAuthenticator] = None


def initialize_working_auth() -> BRMAuthenticator:
    """Initialize authenticator with working BRM credentials"""
    global authenticator
    authenticator = BRMAuthenticator()
    return authenticator


def get_authenticator() -> BRMAuthenticator:
    """Get the global authenticator instance"""
    if authenticator is None:
        # Auto-initialize with working credentials
        initialize_working_auth()
    return authenticator
