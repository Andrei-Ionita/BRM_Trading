# Nord Pool Market Data API Endpoints

## Base URL
https://data-api.nordpoolgroup.com

## Key Intraday Market Data Endpoints

### Real-time Market Data
- `/api/v2/Intraday/OrderBook/ByContractId` - **Live Order Book** (buy/sell orders)
- `/api/v2/Intraday/OrderBook/ContractsIds/ByArea` - Available contracts for order book
- `/api/v2/Intraday/Trades/ByContractId` - **Live Trades** by contract
- `/api/v2/Intraday/Trades/ByDeliveryStart` - Trades by delivery time
- `/api/v2/Intraday/Trades/ByTradeTime` - **Most Recent Trades**
- `/api/v2/Intraday/Orders/ByContractId` - Orders by contract
- `/api/v2/Intraday/Orders/ByDeliveryStart` - Orders by delivery time

### Market Statistics
- `/api/v2/Intraday/ContractStatistics/ByAreas` - Contract statistics by area
- `/api/v2/Intraday/ContractStatistics/Total` - Total contract statistics
- `/api/v2/Intraday/HourlyStatistics/ByAreas` - Hourly statistics by area
- `/api/v2/Intraday/HourlyStatistics/Total` - Total hourly statistics

### Auction Data (Day-Ahead)
- `/api/v2/Auction/Prices/ByAreas` - **Current Auction Prices**
- `/api/v2/Auction/Volumes/ByAreas` - Auction volumes
- `/api/v2/Auction/Flows/ByAreas` - Power flows between areas

### System Data
- `/api/v2/System/Price` - **System Price** (current market price)
- `/api/v2/System/Turnover` - Market turnover

## Authentication
- Requires Bearer token from BRM SSO
- Same authentication as BRM trading APIs

## Romanian Market Areas
- Need to identify Romanian area codes for filtering data
- Likely area codes: RO, Romania, or specific numeric IDs

## Next Steps
1. Test these endpoints with BRM authentication
2. Identify Romanian area/market codes
3. Get real-time order book and trade data
4. Display live market information
