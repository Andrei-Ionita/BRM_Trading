# BRM API Documentation Findings

## Initial API Structure Overview

### Base URL (Test Environment)
- **Day-ahead API**: https://auctions-api.test.brm-power.ro/swagger/index.html
- **Swagger JSON**: https://auctions-api.test.brm-power.ro/swagger/v1/swagger.json

### Main API Categories

#### 1. Auctions
- `GET /api/v{version}/auctions` - Get all auctions
- `GET /api/v{version}/auctions/{auctionId}/orders` - Get orders for specific auction
- `GET /api/v{version}/auctions/{auctionId}/trades` - Get trades for specific auction
- `GET /api/v{version}/auctions/{auctionId}/prices` - Get prices for specific auction
- `GET /api/v{version}/auctions/{auctionId}/portfoliovolumes` - Get portfolio volumes
- `GET /api/v{version}/auctions/{auctionId}` - Get specific auction details

#### 2. BlockOrders
- `GET /api/v{version}/blockorders/{orderId}` - Get specific block order
- `PATCH /api/v{version}/blockorders/{orderId}` - Modify block order
- `POST /api/v{version}/blockorders` - Create new block order

#### 3. CurveOrders
- `GET /api/v{version}/curveorders/{orderId}` - Get specific curve order
- `PATCH /api/v{version}/curveorders/{orderId}` - Modify curve order
- `POST /api/v{version}/curveorders` - Create new curve order

#### 4. State
- `GET /api/v{version}/state` - Get system state

### Key Data Models
- BlockOrder, CurveOrder structures
- Auction, Trade, Price models
- Portfolio and volume tracking
- Order approval and state management

### Authentication
- All endpoints show authorization buttons (OAuth/Bearer token based)
- Authorization endpoint: https://sso.test.brm-power.ro/connect/token (test)
- Production: https://sso.brm-power.ro/connect/token

## Next Steps
1. Explore detailed endpoint specifications
2. Check Nordpool Group documentation
3. Document authentication flow
4. Create implementation guide


## Nordpool Group API Integration

### Key URLs for BRM Integration
- **Test Authentication**: https://sso.test.brm-power.ro/connect/token
- **Production Authentication**: https://sso.brm-power.ro/connect/token
- **Intraday API (Test)**: intraday2-api.test.nordpoolgroup.com
- **Intraday API (Production)**: intraday2-api.nordpoolgroup.com
- **WebSocket (Test)**: intraday-pmd-api-ws-brm.test.nordpoolgroup.com
- **WebSocket (Production)**: https://intraday-pmd-api-ws-brm.nordpoolgroup.com/

### Intraday Trading API Features

#### Authentication & Authorization
- Uses OpenID Connect and OAuth2 standards
- Token-based authentication required for all API calls
- Configuration endpoint provides user permissions, portfolios, and market areas
- Time-dependent access rights with validity restrictions

#### WebSocket-Based Trading
- Uses STOMP protocol over WebSocket
- Real-time streaming for market data and order updates
- Automatic order deactivation on connection loss (optional, within 10 seconds)
- Subscription topics for different data streams

#### Order Management
- **Order Types**: LIMIT, ICEBERG, USER_DEFINED_BLOCK
- **Time in Force**: FOK (Fill or Kill), IOC (Immediate or Cancel), GFS (Good for Session), GTD (Good Till Date)
- **Execution Restrictions**: AON (All or None), NON (No restrictions)
- **Order States**: ACTI (Active), IACT (Closed/Matched), HIBE (Deactivated), PENDING
- **Sides**: BUY, SELL

#### Key Trading Concepts
- **Portfolio-based trading** with specific area permissions
- **Contract-based orders** for different market segments
- **Linked basket orders** (max 100 orders, XBID/SIDC only)
- **Iceberg orders** with clip size and price change parameters
- **Client Order ID** tracking for order management

#### Market Data Access
- Real-time price feeds
- Order book data
- Trade execution reports
- Market statistics and local view data
- Transmission capacity information

### API Endpoints Structure

#### WebSocket Subscriptions
- `/user/<username>/<version>/configuration` - User permissions and portfolios
- `/user/<username>/<version>/<streaming>/orderExecutionReport` - Order status updates
- `/user/<username>/<version>/<streaming>/privateTrade` - Private trade data
- `/user/<username>/<version>/<streaming>/localview` - Market view data

#### REST API Endpoints
- Historical order data retrieval
- User preferences management
- Throttling limits information

### Integration Requirements
- **Conformance Testing**: Required for production access
- **Test Environment**: Place and modify orders via API
- **Documentation**: Complete API documentation available at developers.nordpoolgroup.com
- **Support Contact**: idapi@nordpoolgroup.com
