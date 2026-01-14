# Building a Trading Bot for the Romanian Intraday Market (BRM)

This guide provides a comprehensive overview of the necessary steps to build a trading bot for the Romanian Intraday Market (BRM), leveraging the APIs provided by BRM and Nord Pool.

## 1. Authentication and Access

Access to the BRM trading APIs is secured using OAuth 2.0 and OpenID Connect. To interact with the API, you must first obtain an authentication token from the designated Single Sign-On (SSO) server.

### 1.1. Obtaining an Authentication Token

A token is obtained by sending a POST request to the appropriate token endpoint. You will need a `clientId` and `clientSecret`, which should be provided to you by the market operator.

The following table summarizes the token endpoints for the test and production environments:

| Environment | Token Endpoint                                    |
| :---------- | :------------------------------------------------ |
| Test        | `https://sso.test.brm-power.ro/connect/token`     |
| Production  | `https://sso.brm-power.ro/connect/token`          |

The request must be a standard OAuth 2.0 client credentials grant request.

### 1.2. Using the Authentication Token

Once you have obtained an authentication token, you must include it in the header of all subsequent API requests. The token is passed in the `Authorization` header as a Bearer token:

```
Authorization: Bearer <YOUR_TOKEN>
```

For WebSocket connections using the STOMP protocol, the token is passed in a custom header `X-AUTH-TOKEN` during the `CONNECT` frame.

### 1.3. Token Refresh

Authentication tokens have a limited lifetime (typically 60 minutes). To maintain an active session, you must refresh your token before it expires. A new token can be obtained by making another request to the token endpoint. For active WebSocket sessions, a `TOKEN_REFRESH` command can be sent over the STOMP connection to update the token without disconnecting.



## 2. API Endpoints and Operations

The BRM trading landscape is divided into two main areas: the Day-Ahead Market and the Intraday Market. Each market has its own set of API endpoints and interaction methods.

### 2.1. Day-Ahead Market API

The Day-Ahead market operations are managed through a RESTful API. The base URL for the test environment is `https://auctions-api.test.brm-power.ro`.

#### 2.1.1. Auctions

- **Get all auctions:** `GET /api/v{version}/auctions`
- **Get a specific auction:** `GET /api/v{version}/auctions/{auctionId}`
- **Get orders for an auction:** `GET /api/v{version}/auctions/{auctionId}/orders`
- **Get trades for an auction:** `GET /api/v{version}/auctions/{auctionId}/trades`
- **Get prices for an auction:** `GET /api/v{version}/auctions/{auctionId}/prices`

#### 2.1.2. Order Management

The Day-Ahead API supports two main types of orders: **Block Orders** and **Curve Orders**.

- **Block Orders:**
    - `POST /api/v{version}/blockorders`: Create a new block order.
    - `GET /api/v{version}/blockorders/{orderId}`: Retrieve a specific block order.
    - `PATCH /api/v{version}/blockorders/{orderId}`: Modify an existing block order.

- **Curve Orders:**
    - `POST /api/v{version}/curveorders`: Create a new curve order.
    - `GET /api/v{version}/curveorders/{orderId}`: Retrieve a specific curve order.
    - `PATCH /api/v{version}/curveorders/{orderId}`: Modify an existing curve order.

### 2.2. Intraday Market API

The Intraday market is accessed through a combination of a REST API and a WebSocket-based streaming API. The Intraday API is provided by Nord Pool, and the specific URLs for BRM are provided in the introductory email.

**API URL (Test):** `intraday2-api.test.nordpoolgroup.com`
**WebSocket URL (Test):** `intraday-pmd-api-ws-brm.test.nordpoolgroup.com`

#### 2.2.1. WebSocket API (STOMP Protocol)

The Intraday API uses the STOMP protocol over WebSocket for real-time communication. This is the primary method for placing orders and receiving market data.

**Key Subscription Topics:**

- `/user/<username>/<version>/configuration`: Receive user permissions, portfolios, and market areas.
- `/user/<username>/<version>/<streaming>/orderExecutionReport`: Get real-time updates on order status.
- `/user/<username>/<version>/<streaming>/privateTrade`: Receive information about your private trades.
- `/user/<username>/<version>/<streaming>/localview`: Subscribe to public market data for a specific area.

#### 2.2.2. Order Management (Intraday)

Orders on the Intraday market are created and managed by sending STOMP messages to the `/v1/orderEntryRequest` topic. The message payload contains the order details.

**Order Types:**

- **LIMIT:** A standard limit order.
- **ICEBERG:** An order where only a portion of the total volume is visible to the market at any time.
- **USER_DEFINED_BLOCK:** A block order with specific execution conditions.

**Key Order Parameters:**

- `portfolioId`: The portfolio to use for the order.
- `contractIds`: The specific contract(s) to trade.
- `deliveryAreaId`: The delivery area for the order.
- `side`: `BUY` or `SELL`.
- `unitPrice`: The price of the order.
- `quantity`: The volume of the order in kW.
- `timeInForce`: The order's lifetime (e.g., `GFS`, `GTD`, `FOK`, `IOC`).
- `clientOrderId`: A unique identifier for the order provided by your application.

## 3. Getting Started: A Step-by-Step Guide

1.  **Obtain Credentials:** Contact the market operator to get your `clientId` and `clientSecret` for both the test and production environments.
2.  **Conformance Testing:** Before gaining access to the production environment, you must pass a conformance test. This involves placing and modifying orders in the test environment.
3.  **Authentication:** Implement the OAuth 2.0 client credentials flow to obtain an authentication token.
4.  **Connect to the API:**
    - For Day-Ahead, use the REST API with the obtained token.
    - For Intraday, establish a WebSocket connection and use the token to authenticate your STOMP session.
5.  **Place Orders:**
    - For Day-Ahead, use the `POST /api/v{version}/blockorders` or `POST /api/v{version}/curveorders` endpoints.
    - For Intraday, send a STOMP message to the `/v1/orderEntryRequest` topic.
6.  **Monitor and Manage Orders:** Use the respective API endpoints and WebSocket subscriptions to monitor the status of your orders and manage them as needed.

## 4. Important Considerations

- **Error Handling:** Implement robust error handling to manage API errors, connection issues, and order rejections.
- **Throttling:** Be mindful of API rate limits and implement mechanisms to avoid being throttled.
- **Connection Loss:** For the Intraday API, you can configure your orders to be automatically deactivated upon connection loss to mitigate risk.
- **Documentation:** Refer to the official Nord Pool and BRM API documentation for detailed information on all endpoints, data models, and protocols.

