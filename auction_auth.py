"""
BRM Auction API Authentication Module
Uses the correct client credentials for auction API access
"""
import asyncio
import logging
import aiohttp
import base64
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from dataclasses import dataclass
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class TokenInfo:
    """Token information"""
    access_token: str
    token_type: str
    expires_in: int
    expires_at: datetime
    scope: str
    
    @property
    def bearer_token(self) -> str:
        """Get the Bearer token string"""
        return f"Bearer {self.access_token}"
    
    @property
    def is_expired(self) -> bool:
        """Check if token is expired"""
        return datetime.now() >= self.expires_at - timedelta(seconds=30)  # 30 second buffer


class BRMAuctionAuth:
    """BRM Auction API Authentication Manager"""
    
    def __init__(self):
        """Initialize the authentication manager"""
        self.token_url = "https://sso.test.brm-power.ro/connect/token"
        self.current_token: Optional[TokenInfo] = None
        
        # Auction API credentials (different from intraday!)
        self.username = "Test_AuctionAPI_ADREM"
        self.password = "odvM6{=15HW1s%H1Wb"
        self.scope = "auction_api"

        # Basic Auth: client_auction_api:client_auction_api
        self.basic_auth_header = "Basic Y2xpZW50X2F1Y3Rpb25fYXBpOmNsaWVudF9hdWN0aW9uX2FwaQ=="
        
        logger.info("BRM Auction API Authentication initialized")
    
    def get_basic_auth_header(self) -> str:
        """Get Basic authentication header for client credentials"""
        return self.basic_auth_header
    
    async def get_token_async(self) -> TokenInfo:
        """Get or refresh the authentication token"""
        if self.current_token and not self.current_token.is_expired:
            return self.current_token
        
        logger.info(f"Requesting auction API token from {self.token_url}")
        
        # Prepare request data
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": self.get_basic_auth_header()
        }
        
        data = {
            "grant_type": "password",
            "scope": self.scope,
            "username": self.username,
            "password": self.password
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.token_url,
                    headers=headers,
                    data=data,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    
                    if response.status == 200:
                        token_data = await response.json()
                        
                        # Create token info
                        expires_at = datetime.now() + timedelta(seconds=token_data.get('expires_in', 3600))
                        
                        self.current_token = TokenInfo(
                            access_token=token_data['access_token'],
                            token_type=token_data.get('token_type', 'Bearer'),
                            expires_in=token_data.get('expires_in', 3600),
                            expires_at=expires_at,
                            scope=token_data.get('scope', self.scope)
                        )
                        
                        logger.info(f"Auction API token acquired successfully, expires at {expires_at}")
                        return self.current_token
                    
                    else:
                        error_text = await response.text()
                        logger.error(f"Token request failed with status {response.status}: {error_text}")
                        raise Exception(f"Authentication failed: {response.status} - {error_text}")
        
        except Exception as e:
            logger.error(f"Failed to get auction API token: {e}")
            raise
    
    async def get_auth_headers_async(self) -> Dict[str, str]:
        """Get authentication headers for API requests"""
        token_info = await self.get_token_async()
        return {
            "Authorization": token_info.bearer_token,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
    
    def get_token_sync(self) -> TokenInfo:
        """Synchronous wrapper for getting token"""
        return asyncio.run(self.get_token_async())
    
    def get_auth_headers_sync(self) -> Dict[str, str]:
        """Synchronous wrapper for getting auth headers"""
        return asyncio.run(self.get_auth_headers_async())


def initialize_auction_auth() -> BRMAuctionAuth:
    """Initialize and return the auction authentication manager"""
    return BRMAuctionAuth()


# Test the authentication
async def test_auction_auth():
    """Test the auction API authentication"""
    logger.info("🧪 Testing BRM Auction API Authentication")
    logger.info("=" * 50)
    
    auth = initialize_auction_auth()
    
    try:
        # Test token acquisition
        token_info = await auth.get_token_async()
        logger.info(f"✅ Token acquired successfully!")
        logger.info(f"   Token type: {token_info.token_type}")
        logger.info(f"   Expires at: {token_info.expires_at}")
        logger.info(f"   Scope: {token_info.scope}")
        logger.info(f"   Bearer token: {token_info.bearer_token[:50]}...")
        
        # Test headers
        headers = await auth.get_auth_headers_async()
        logger.info(f"✅ Auth headers prepared:")
        for key, value in headers.items():
            if key == "Authorization":
                logger.info(f"   {key}: {value[:50]}...")
            else:
                logger.info(f"   {key}: {value}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Authentication test failed: {e}")
        return False


if __name__ == "__main__":
    # Test the authentication
    asyncio.run(test_auction_auth())
