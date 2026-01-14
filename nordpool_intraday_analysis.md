# Nord Pool Intraday API Analysis for BRM Integration

## Overview

Based on the Nord Pool documentation and BRM operator instructions, here's the complete analysis for implementing intraday trading functionality.

## API Structure

### 1. WebSocket API (Real-time Trading)
- **Protocol:** STOMP over WebSocket/SockJS
- **Purpose:** Real-time order placement and market data streaming
- **Authentication:** OAuth2 with Nord Pool SSO

#### BRM-Specific URLs (from operator):
- **Test WebSocket:** `intraday-pmd-api-ws-brm.test.nordpoolgroup.com`
- **Production WebSocket:** `intraday-pmd-api-ws-brm.nordpoolgroup.com`

#### Standard Nord Pool URLs:
- **Test Trading:** `intraday2-ws.test.nordpoolgroup.com:443`
- **Production Trading:** `intraday2-ws.nordpoolgroup.com:443`

### 2. REST API (Historical Data)
- **Purpose:** Request-response pattern for data-intensive operations
- **BRM Test URL:** `intraday2-api.test.nordpoolgroup.com`
- **BRM Production URL:** `intraday2-api.nordpoolgroup.com`

## Authentication

### OAuth2 Configuration
- **SSO URL (Test):** `https://sso.test.brm-power.ro/connect/token`
- **SSO URL (Production):** `https://sso.brm-power.ro/connect/token`
- **Scope:** Intraday trading scope (to be provided by BRM operator)

## Trading API Topics

### Private Trading Topics:
1. **Heartbeat ping** - Connection health monitoring
2. **Configuration** - Trading configuration and settings
3. **Order Execution Report** - Order status and execution updates
4. **Private Trade** - Trade confirmations and details
5. **Throttling Limits** - API rate limiting information

### Public Market Data Topics:
1. **Delivery Areas** - Available trading areas
2. **Contracts** - Available contracts for trading
3. **Local View** - Market view and order book
4. **Public Statistics** - Market statistics and aggregated data
5. **Ticker** - Real-time price information
6. **Capacities** - Cross-border capacity information

## Data Standards

### Units and Formats:
- **Trading Unit:** kW (kilowatt)
- **Currency:** Minor units (cents for EUR, pence for GBP)
  - Example: 1.50 EUR = 150 cents
- **DateTime:** ISO 8601 format in UTC (e.g., 2016-12-13T11:08:35Z)
- **Countries:** ISO 3166-1 alpha-2 format
- **Currency Codes:** ISO 4217 format

## Implementation Requirements

### 1. WebSocket Connection Management
- Implement STOMP protocol client
- Handle connection lifecycle (connect, subscribe, disconnect)
- Implement heartbeat mechanism
- Handle reconnection and error recovery

### 2. Order Management
- Place intraday orders via WebSocket
- Monitor order execution reports
- Handle order modifications and cancellations
- Track private trades

### 3. Market Data Streaming
- Subscribe to relevant market data topics
- Process real-time price updates
- Monitor contract availability
- Track market statistics

### 4. Authentication Integration
- Extend existing OAuth2 implementation
- Handle token refresh for long-running connections
- Manage multiple scopes (Day-Ahead + Intraday)

## Integration with Existing BRM System

### Dashboard Enhancement:
1. Add "Intraday Market" tab alongside Day-Ahead
2. Real-time intraday market data display
3. Intraday order placement interface
4. Combined portfolio view (Day-Ahead + Intraday)

### Backend Architecture:
1. Extend existing `BRMOrderManager` for intraday operations
2. Create `IntradayWebSocketClient` for real-time connections
3. Implement `IntradayOrderTracker` for order lifecycle management
4. Add intraday endpoints to Flask application

## Next Steps

1. **Credentials Setup** - Obtain intraday API credentials from BRM operator
2. **WebSocket Client** - Implement STOMP WebSocket client
3. **Market Data Integration** - Connect to public market data streams
4. **Order Placement** - Implement intraday order submission
5. **Dashboard Integration** - Add intraday tab to existing dashboard
6. **Testing** - Test with BRM intraday test environment
7. **Conformance Test** - Complete Nord Pool conformance requirements

## Code Structure

```
brm_trading_bot/
├── intraday/
│   ├── __init__.py
│   ├── websocket_client.py      # STOMP WebSocket client
│   ├── market_data_client.py    # Public market data streaming
│   ├── trading_client.py        # Private trading operations
│   ├── order_manager.py         # Intraday order management
│   └── data_models.py           # Intraday data structures
├── templates/
│   └── intraday_dashboard.html  # Intraday trading interface
└── app_intraday.py              # Enhanced app with intraday support
```

## Risk Considerations

1. **Real-time Requirements** - Intraday trading requires low-latency connections
2. **Connection Reliability** - WebSocket connections must be highly reliable
3. **Order Timing** - Intraday markets have tight timing constraints
4. **Market Data Quality** - Real-time data accuracy is critical
5. **Error Handling** - Robust error handling for trading operations

This analysis provides the foundation for implementing comprehensive intraday trading capabilities alongside the existing Day-Ahead market functionality.
