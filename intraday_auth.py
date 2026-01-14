"""
Intraday API Authentication for BRM Integration
Handles OAuth2 authentication for Nord Pool Intraday API
"""

import requests
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional
import base64

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class IntradayAuthenticator:
    """
    Handles authentication for Nord Pool Intraday API
    Uses OAuth2 password grant flow with BRM SSO
    """
    
    def __init__(self):
        # BRM Intraday API Credentials
        self.username = "Test_IntradayAPI_ADREM"
        self.password = "nR(B8fDY{485Nq4mu"
        self.scope = "intraday_api"
        self.grant_type = "password"
        
        # BRM SSO URLs (from operator instructions)
        self.sso_url_test = "https://sso.test.brm-power.ro/connect/token"
        self.sso_url_prod = "https://sso.brm-power.ro/connect/token"
        
        # Use test environment for now
        self.sso_url = self.sso_url_test
        
        # Token storage
        self.access_token = None
        self.refresh_token = None
        self.token_expires_at = None
        self.token_type = "Bearer"
        
        # Client credentials for Basic Auth
        self.basic_auth = "Basic Y2xpZW50X2ludHJhZGF5X2FwaToxeEI5SWsxeHNFdTJuYndWYTFCUg=="
    
    def authenticate(self) -> bool:
        """
        Authenticate with BRM SSO and obtain access token
        
        Returns:
            bool: True if authentication successful
        """
        try:
            logger.info("Authenticating with BRM Intraday API...")
            
            # Prepare authentication request
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
                'Accept': 'application/json'
            }
            
            # OAuth2 password grant data
            data = {
                'grant_type': self.grant_type,
                'username': self.username,
                'password': self.password,
                'scope': self.scope
            }
            
            # Add Basic Auth header (required for BRM intraday API)
            headers['Authorization'] = self.basic_auth
            
            # Make authentication request
            response = requests.post(
                self.sso_url,
                headers=headers,
                data=data,
                timeout=30
            )
            
            logger.info(f"Authentication response: {response.status_code}")
            
            if response.status_code == 200:
                token_data = response.json()
                
                # Extract token information
                self.access_token = token_data.get('access_token')
                self.refresh_token = token_data.get('refresh_token')
                self.token_type = token_data.get('token_type', 'Bearer')
                expires_in = token_data.get('expires_in', 3600)
                
                # Calculate expiration time
                self.token_expires_at = datetime.now() + timedelta(seconds=expires_in)
                
                logger.info("Intraday API authentication successful!")
                logger.info(f"Token expires at: {self.token_expires_at}")
                
                return True
            else:
                error_text = response.text
                logger.error(f"Authentication failed: HTTP {response.status_code}")
                logger.error(f"Response: {error_text}")
                
                # Try to parse error details
                try:
                    error_data = response.json()
                    error_description = error_data.get('error_description', 'Unknown error')
                    logger.error(f"Error description: {error_description}")
                except:
                    pass
                
                return False
                
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return False
    
    def get_access_token(self) -> Optional[str]:
        """
        Get current access token, refreshing if necessary
        
        Returns:
            str: Access token or None if authentication failed
        """
        # Check if we need to authenticate or refresh
        if not self.access_token or self.is_token_expired():
            if not self.authenticate():
                return None
        
        return self.access_token
    
    def is_token_expired(self) -> bool:
        """Check if current token is expired"""
        if not self.token_expires_at:
            return True
        
        # Add 5 minute buffer
        return datetime.now() >= (self.token_expires_at - timedelta(minutes=5))
    
    def get_auth_headers(self) -> Dict[str, str]:
        """
        Get authentication headers for API requests
        
        Returns:
            dict: Headers with Authorization token
        """
        token = self.get_access_token()
        if not token:
            return {}
        
        return {
            'Authorization': f'{self.token_type} {token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
    
    def test_authentication(self) -> Dict[str, any]:
        """
        Test authentication and return status
        
        Returns:
            dict: Authentication test results
        """
        result = {
            'success': False,
            'token_available': False,
            'token_valid': False,
            'expires_at': None,
            'error': None
        }
        
        try:
            # Try to authenticate
            if self.authenticate():
                result['success'] = True
                result['token_available'] = True
                result['token_valid'] = not self.is_token_expired()
                result['expires_at'] = self.token_expires_at.isoformat() if self.token_expires_at else None
            else:
                result['error'] = 'Authentication failed'
                
        except Exception as e:
            result['error'] = str(e)
        
        return result


def test_intraday_authentication():
    """Test function for intraday authentication"""
    logger.info("Testing Intraday API authentication...")
    
    auth = IntradayAuthenticator()
    
    # Test authentication
    test_result = auth.test_authentication()
    
    logger.info("Authentication test results:")
    for key, value in test_result.items():
        logger.info(f"  {key}: {value}")
    
    if test_result['success']:
        logger.info("✅ Intraday authentication successful!")
        
        # Test getting auth headers
        headers = auth.get_auth_headers()
        logger.info(f"Auth headers: {list(headers.keys())}")
        
        return auth
    else:
        logger.error("❌ Intraday authentication failed!")
        return None


if __name__ == "__main__":
    # Run authentication test
    authenticator = test_intraday_authentication()
    
    if authenticator:
        print("\n🎉 Intraday API authentication is working!")
        print(f"Access token available: {bool(authenticator.access_token)}")
        print(f"Token expires at: {authenticator.token_expires_at}")
    else:
        print("\n❌ Intraday API authentication failed!")
        print("Check credentials and network connectivity.")
