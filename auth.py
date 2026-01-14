"""
Authentication module for BRM Trading Bot
Handles OAuth2 token acquisition and refresh
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
    """Handles authentication with BRM SSO service"""
    
    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.token_info: Optional[TokenInfo] = None
        self.logger = logging.getLogger(__name__)
    
    def get_token_sync(self) -> TokenInfo:
        """
        Synchronously obtain an access token using client credentials grant
        """
        if self.token_info and not self.token_info.is_expired:
            return self.token_info
        
        token_data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": "api"  # Adjust scope as needed
        }
        
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json"
        }
        
        try:
            self.logger.info(f"Requesting token from {config.sso_token_url}")
            response = requests.post(
                config.sso_token_url,
                data=token_data,
                headers=headers,
                timeout=30
            )
            response.raise_for_status()
            
            token_response = response.json()
            
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
            
        except requests.RequestException as e:
            self.logger.error(f"Failed to obtain token: {e}")
            raise
        except KeyError as e:
            self.logger.error(f"Invalid token response format: {e}")
            raise
    
    async def get_token_async(self) -> TokenInfo:
        """
        Asynchronously obtain an access token using client credentials grant
        """
        if self.token_info and not self.token_info.is_expired:
            return self.token_info
        
        token_data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": "api"
        }
        
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                self.logger.info(f"Requesting token from {config.sso_token_url}")
                async with session.post(
                    config.sso_token_url,
                    data=token_data,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    response.raise_for_status()
                    token_response = await response.json()
            
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
            
        except aiohttp.ClientError as e:
            self.logger.error(f"Failed to obtain token: {e}")
            raise
        except KeyError as e:
            self.logger.error(f"Invalid token response format: {e}")
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


# Global authenticator instance (will be initialized when credentials are provided)
authenticator: Optional[BRMAuthenticator] = None


def initialize_auth(client_id: str, client_secret: str) -> BRMAuthenticator:
    """Initialize the global authenticator with credentials"""
    global authenticator
    authenticator = BRMAuthenticator(client_id, client_secret)
    return authenticator


def get_authenticator() -> BRMAuthenticator:
    """Get the global authenticator instance"""
    if authenticator is None:
        if config.client_id and config.client_secret:
            return initialize_auth(config.client_id, config.client_secret)
        else:
            raise ValueError("Authenticator not initialized. Call initialize_auth() first.")
    return authenticator
