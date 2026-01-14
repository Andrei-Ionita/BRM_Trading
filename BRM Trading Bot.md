# BRM Trading Bot

A comprehensive trading bot for the Romanian Intraday Market (BRM) that supports both Day-Ahead and Intraday trading operations.

## Features

- **Dual Market Support**: Trade on both Day-Ahead and Intraday markets
- **OAuth2 Authentication**: Secure authentication with BRM SSO
- **Real-time WebSocket**: STOMP protocol for real-time market data and order management
- **Multiple Order Types**: Support for limit orders, iceberg orders, and block orders
- **Trading Strategies**: Built-in support for arbitrage, mean reversion, and momentum strategies
- **Risk Management**: Position tracking and risk limits
- **Event-driven Architecture**: Extensible event handlers for custom logic

## Architecture

The trading bot consists of several key components:

- **Authentication Module** (`auth.py`): Handles OAuth2 token management
- **Day-Ahead Client** (`day_ahead_client.py`): REST API client for Day-Ahead market
- **Intraday Client** (`intraday_client.py`): WebSocket client for Intraday market
- **Trading Bot** (`trading_bot.py`): Main orchestrator with trading logic
- **Configuration** (`config.py`): Centralized configuration management

## Installation

1. **Clone or download the trading bot files**

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure credentials**:
   ```bash
   cp .env.example .env
   # Edit .env with your actual credentials
   ```

## Configuration

### Environment Variables

Create a `.env` file with the following variables:

```bash
# Environment
BRM_ENVIRONMENT=test  # or "production"

# Credentials (obtain from BRM operator)
BRM_CLIENT_ID=your_client_id
BRM_CLIENT_SECRET=your_client_secret
BRM_USERNAME=your_username
BRM_PORTFOLIO_ID=your_portfolio_id
```

### API Endpoints

The bot automatically selects the correct endpoints based on the environment:

**Test Environment:**
- Day-Ahead API: `https://auctions-api.test.brm-power.ro`
- Intraday WebSocket: `wss://intraday-pmd-api-ws-brm.test.nordpoolgroup.com`
- SSO Token: `https://sso.test.brm-power.ro/connect/token`

**Production Environment:**
- Day-Ahead API: `https://auctions-api.brm-power.ro`
- Intraday WebSocket: `wss://intraday-pmd-api-ws-brm.nordpoolgroup.com`
- SSO Token: `https://sso.brm-power.ro/connect/token`

## Usage

### Basic Usage

```python
import asyncio
from trading_bot import BRMTradingBot, TradingStrategy

async def main():
    # Initialize the bot
    bot = BRMTradingBot(
        client_id="your_client_id",
        client_secret="your_client_secret",
        username="your_username",
        portfolio_id="your_portfolio_id",
        strategy=TradingStrategy.MANUAL
    )
    
    # Start the bot
    await bot.start()

if __name__ == "__main__":
    asyncio.run(main())
```

### Manual Trading

```python
# Place a Day-Ahead block order
await bot.place_day_ahead_block_order(
    name="Test Block Order",
    price=50.0,  # EUR/MWh
    periods=[
        {
            "contractId": "NPIDA_1-20241101-01",
            "volume": 100  # kW
        }
    ]
)

# Place an Intraday limit order
order_id = await bot.place_intraday_limit_order(
    contract_id="NX_7650",
    side="BUY",
    quantity=100,  # kW
    price=45.0,    # EUR/MWh
    area_id=1
)
```

### Auto Trading

```python
# Enable automatic trading
bot.enable_auto_trading()

# Add custom signal handler
def my_signal_handler(signal):
    print(f"Signal: {signal.action} {signal.quantity} @ {signal.price}")

bot.add_signal_handler(my_signal_handler)

# Add position update handler
def my_position_handler(position):
    print(f"Position: {position.contract_id} - {position.quantity} @ {position.average_price}")

bot.add_position_handler(my_position_handler)
```

## Testing

Run the test suite to verify your setup:

```bash
python test_bot.py
```

The test script will:
1. Test authentication with your credentials
2. Verify Day-Ahead API connectivity
3. Test Intraday WebSocket connection
4. Validate order structures
5. Test signal handling

## Order Types

### Day-Ahead Market

**Block Orders**: Orders that must be executed as a complete block across multiple periods.

```python
await bot.place_day_ahead_block_order(
    name="Morning Peak Block",
    price=60.0,
    periods=[
        {"contractId": "NPIDA_1-20241101-07", "volume": 200},
        {"contractId": "NPIDA_1-20241101-08", "volume": 200},
        {"contractId": "NPIDA_1-20241101-09", "volume": 200}
    ],
    minimum_acceptance_ratio=1.0  # Must be 100% filled
)
```

**Curve Orders**: Price-quantity curves for flexible bidding.

### Intraday Market

**Limit Orders**: Standard orders with specified price and quantity.

**Iceberg Orders**: Large orders with only partial quantity visible.

```python
from intraday_client import IntradayOrder, OrderType

iceberg_order = IntradayOrder(
    portfolio_id="your_portfolio",
    contract_ids=["NX_7650"],
    delivery_area_id=1,
    side="BUY",
    order_type=OrderType.ICEBERG,
    unit_price=4500,  # 45 EUR/MWh in cents
    quantity=1000,    # Total quantity
    clip_size=100,    # Visible quantity
    clip_price_change=50,  # Price change per clip
    time_in_force=TimeInForce.GFS,
    execution_restriction=ExecutionRestriction.NON
)
```

## Trading Strategies

The bot supports multiple trading strategies:

### Simple Arbitrage
Identifies price differences between Day-Ahead and Intraday markets.

### Mean Reversion
Trades based on price deviations from historical averages.

### Momentum
Follows price trends and momentum indicators.

### Custom Strategies
Implement your own strategy by extending the bot's signal generation methods.

## Risk Management

The bot includes several risk management features:

- **Position Limits**: Maximum position size per contract
- **Price Limits**: Minimum and maximum acceptable prices
- **Risk Limits**: Total exposure limits
- **Auto-disconnect**: Automatic order deactivation on connection loss

## Event Handling

The bot uses an event-driven architecture with handlers for:

- **Trading Signals**: Generated by strategies
- **Position Updates**: Changes in trading positions
- **Order Updates**: Order execution reports
- **Market Data**: Real-time market information

## Error Handling

The bot includes comprehensive error handling:

- **Connection Recovery**: Automatic reconnection with exponential backoff
- **Token Refresh**: Automatic token renewal before expiration
- **Order Validation**: Pre-submission order validation
- **Exception Logging**: Detailed error logging for debugging

## Conformance Testing

Before using the bot in production:

1. **Test Environment**: Thoroughly test all functionality in the test environment
2. **Order Placement**: Place and modify orders as required by BRM
3. **Documentation**: Complete conformance test documentation
4. **Approval**: Submit for BRM operator approval

## Security Considerations

- **Credential Storage**: Store credentials securely (environment variables, key management)
- **Network Security**: Use secure connections (HTTPS/WSS)
- **Access Control**: Limit access to trading functions
- **Audit Logging**: Maintain detailed logs of all trading activities

## Troubleshooting

### Common Issues

**Authentication Failures**:
- Verify client ID and secret
- Check token endpoint URL
- Ensure proper scope permissions

**Connection Issues**:
- Verify WebSocket URL
- Check firewall settings
- Confirm network connectivity

**Order Rejections**:
- Validate order parameters
- Check portfolio permissions
- Verify contract availability

### Logging

Enable debug logging for detailed troubleshooting:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Support

For technical support and questions:

- **BRM API Support**: Contact the BRM operator
- **Nord Pool API**: idapi@nordpoolgroup.com
- **Documentation**: https://developers.nordpoolgroup.com

## License

This trading bot is provided as-is for educational and development purposes. Users are responsible for compliance with all applicable regulations and market rules.

## Disclaimer

Trading in energy markets involves significant financial risk. This software is provided without warranty. Users should thoroughly test and validate all functionality before using in production environments.
