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
    
    # WebSocket URLs - Trading (for order placement)
    trading_ws_url_test: str = "wss://intraday2-ws.test.nordpoolgroup.com"
    trading_ws_url_prod: str = "wss://intraday2-ws.nordpoolgroup.com"

    # WebSocket URLs - Market Data (for contracts, ticker, order book)
    market_data_ws_url_test: str = "wss://intraday-pmd-api-ws-brm.test.nordpoolgroup.com"
    market_data_ws_url_prod: str = "wss://intraday-pmd-api-ws-brm.nordpoolgroup.com"

    # Legacy alias (kept for backwards compatibility)
    websocket_url_test: str = "wss://intraday2-ws.test.nordpoolgroup.com"
    websocket_url_prod: str = "wss://intraday2-ws.nordpoolgroup.com"
    
    # SSO Token URLs
    sso_token_url_test: str = "https://sso.test.brm-power.ro/connect/token"
    sso_token_url_prod: str = "https://sso.brm-power.ro/connect/token"
    
    # API Version (just the number, "v" is added in URL construction)
    api_version: str = "1"
    
    # Trading settings
    default_portfolio_id: Optional[str] = "ADREM - DA"  # For Day-Ahead
    intraday_portfolio_id: Optional[str] = "E00160-1"   # For Intraday (NordPool)
    default_delivery_area_id: int = 1      # DA delivery area
    intraday_delivery_area_id: int = 111   # IDM delivery area (Romania)
    
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
    def trading_ws_url(self) -> str:
        """Get the appropriate Trading WebSocket URL based on environment"""
        return self.trading_ws_url_test if self.environment == "test" else self.trading_ws_url_prod

    @property
    def market_data_ws_url(self) -> str:
        """Get the appropriate Market Data WebSocket URL based on environment"""
        return self.market_data_ws_url_test if self.environment == "test" else self.market_data_ws_url_prod

    @property
    def websocket_url(self) -> str:
        """Get the appropriate WebSocket URL based on environment (alias for trading_ws_url)"""
        return self.trading_ws_url
    
    @property
    def sso_token_url(self) -> str:
        """Get the appropriate SSO token URL based on environment"""
        return self.sso_token_url_test if self.environment == "test" else self.sso_token_url_prod


# Global configuration instance
config = BRMConfig()
