"""
Updated Authentication module for BRM Trading Bot
Supports both Basic Authentication and Password Grant methods
"""
import asyncio
import logging
import time
import base64
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
    """Handles authentication with BRM SSO service"""
    
    def __init__(self, auth_method: str = "password", **kwargs):
        """
        Initialize authenticator
        
        Args:
            auth_method: "basic" or "password"
            **kwargs: Authentication parameters based on method
        """
        self.auth_method = auth_method
        self.token_info: Optional[TokenInfo] = None
        self.logger = logging.getLogger(__name__)
        
        if auth_method == "basic":
            # Basic authentication using encoded credentials
            self.basic_auth_header = kwargs.get("basic_auth_header")
            if not self.basic_auth_header:
                raise ValueError("basic_auth_header required for basic authentication")
        
        elif auth_method == "password":
            # Password grant using username/password
            self.username = kwargs.get("username")
            self.password = kwargs.get("password")
            self.scope = kwargs.get("scope", "intraday_api")
            
            if not self.username or not self.password:
                raise ValueError("username and password required for password grant")
        
        else:
            raise ValueError("auth_method must be 'basic' or 'password'")
    
    def get_token_sync(self) -> TokenInfo:
        """
        Synchronously obtain an access token
        """
        if self.token_info and not self.token_info.is_expired:
            return self.token_info
        
        if self.auth_method == "basic":
            return self._get_token_basic_sync()
        elif self.auth_method == "password":
            return self._get_token_password_sync()
    
    async def get_token_async(self) -> TokenInfo:
        """
        Asynchronously obtain an access token
        """
        if self.token_info and not self.token_info.is_expired:
            return self.token_info
        
        if self.auth_method == "basic":
            return await self._get_token_basic_async()
        elif self.auth_method == "password":
            return await self._get_token_password_async()
    
    def _get_token_basic_sync(self) -> TokenInfo:
        """Get token using Basic authentication (sync)"""
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": self.basic_auth_header,
            "Accept": "application/json"
        }
        
        # For Basic auth, we typically still need to send grant_type
        token_data = {
            "grant_type": "client_credentials"
        }
        
        try:
            self.logger.info(f"Requesting token using Basic auth from {config.sso_token_url}")
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
            self.logger.error(f"Failed to obtain token with Basic auth: {e}")
            raise
    
    def _get_token_password_sync(self) -> TokenInfo:
        """Get token using password grant (sync)"""
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json"
        }
        
        token_data = {
            "grant_type": "password",
            "username": self.username,
            "password": self.password,
            "scope": self.scope
        }
        
        try:
            self.logger.info(f"Requesting token using password grant from {config.sso_token_url}")
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
            self.logger.error(f"Failed to obtain token with password grant: {e}")
            raise
    
    async def _get_token_basic_async(self) -> TokenInfo:
        """Get token using Basic authentication (async)"""
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": self.basic_auth_header,
            "Accept": "application/json"
        }
        
        token_data = {
            "grant_type": "client_credentials"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                self.logger.info(f"Requesting token using Basic auth from {config.sso_token_url}")
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
            self.logger.error(f"Failed to obtain token with Basic auth: {e}")
            raise
    
    async def _get_token_password_async(self) -> TokenInfo:
        """Get token using password grant (async)"""
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json"
        }
        
        token_data = {
            "grant_type": "password",
            "username": self.username,
            "password": self.password,
            "scope": self.scope
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                self.logger.info(f"Requesting token using password grant from {config.sso_token_url}")
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
            self.logger.error(f"Failed to obtain token with password grant: {e}")
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


def initialize_auth_basic(basic_auth_header: str) -> BRMAuthenticator:
    """Initialize authenticator with Basic authentication"""
    global authenticator
    authenticator = BRMAuthenticator(
        auth_method="basic",
        basic_auth_header=basic_auth_header
    )
    return authenticator


def initialize_auth_password(username: str, password: str, scope: str = "intraday_api") -> BRMAuthenticator:
    """Initialize authenticator with password grant"""
    global authenticator
    authenticator = BRMAuthenticator(
        auth_method="password",
        username=username,
        password=password,
        scope=scope
    )
    return authenticator


def get_authenticator() -> BRMAuthenticator:
    """Get the global authenticator instance"""
    if authenticator is None:
        raise ValueError("Authenticator not initialized. Call initialize_auth_basic() or initialize_auth_password() first.")
    return authenticator


# Helper function to create Basic auth header from username:password
def create_basic_auth_header(username: str, password: str) -> str:
    """Create Basic authentication header from username and password"""
    credentials = f"{username}:{password}"
    encoded_credentials = base64.b64encode(credentials.encode()).decode()
    return f"Basic {encoded_credentials}"
