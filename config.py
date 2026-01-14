"""
Configuration settings for the BRM Trading Bot
"""
import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class BRMConfig:
    """Configuration class for BRM Trading Bot"""
    
    # Environment settings
    environment: str = "test"  # "test" or "production"
    
    # Authentication
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    
    # Day-Ahead API URLs
    day_ahead_base_url_test: str = "https://auctions-api.test.brm-power.ro"
    day_ahead_base_url_prod: str = "https://auctions-api.brm-power.ro"
    
    # Intraday API URLs
    intraday_api_url_test: str = "intraday2-api.test.nordpoolgroup.com"
    intraday_api_url_prod: str = "intraday2-api.nordpoolgroup.com"
    
    # WebSocket URLs
    websocket_url_test: str = "wss://intraday-pmd-api-ws-brm.test.nordpoolgroup.com"
    websocket_url_prod: str = "wss://intraday-pmd-api-ws-brm.nordpoolgroup.com"
    
    # SSO Token URLs
    sso_token_url_test: str = "https://sso.test.brm-power.ro/connect/token"
    sso_token_url_prod: str = "https://sso.brm-power.ro/connect/token"
    
    # API Version
    api_version: str = "v1"
    
    # Trading settings
    default_portfolio_id: Optional[str] = None
    default_delivery_area_id: int = 1
    
    # Connection settings
    token_refresh_buffer_minutes: int = 5  # Refresh token 5 minutes before expiry
    websocket_heartbeat_interval: int = 15  # seconds
    max_reconnection_attempts: int = 5
    
    def __post_init__(self):
        """Load configuration from environment variables if available"""
        self.client_id = os.getenv("BRM_CLIENT_ID", self.client_id)
        self.client_secret = os.getenv("BRM_CLIENT_SECRET", self.client_secret)
        self.environment = os.getenv("BRM_ENVIRONMENT", self.environment)
        self.default_portfolio_id = os.getenv("BRM_PORTFOLIO_ID", self.default_portfolio_id)
    
    @property
    def day_ahead_base_url(self) -> str:
        """Get the appropriate Day-Ahead API URL based on environment"""
        return self.day_ahead_base_url_test if self.environment == "test" else self.day_ahead_base_url_prod
    
    @property
    def intraday_api_url(self) -> str:
        """Get the appropriate Intraday API URL based on environment"""
        return self.intraday_api_url_test if self.environment == "test" else self.intraday_api_url_prod
    
    @property
    def websocket_url(self) -> str:
        """Get the appropriate WebSocket URL based on environment"""
        return self.websocket_url_test if self.environment == "test" else self.websocket_url_prod
    
    @property
    def sso_token_url(self) -> str:
        """Get the appropriate SSO token URL based on environment"""
        return self.sso_token_url_test if self.environment == "test" else self.sso_token_url_prod


# Global configuration instance
config = BRMConfig()
