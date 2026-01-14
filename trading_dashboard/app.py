"""
BRM Trading Dashboard - FastAPI Backend
Professional trading interface for Day-Ahead and Intraday markets
"""
import asyncio
import json
import random
import string
import ssl
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from contextlib import asynccontextmanager

import requests
import websockets
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
import urllib3

# Disable SSL warnings for test environment
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# ============================================================================
# Configuration
# ============================================================================
class Config:
    # Day-Ahead API
    DA_TOKEN_URL = "https://sso.test.brm-power.ro/connect/token"
    DA_API_BASE = "https://auctions-api.test.brm-power.ro"
    DA_CLIENT_AUTH = "Basic Y2xpZW50X2F1Y3Rpb25fYXBpOmNsaWVudF9hdWN0aW9uX2FwaQ=="
    DA_USERNAME = "Test_AuctionAPI_ADREM"
    DA_PASSWORD = "odvM6{=15HW1s%H1Wb"
    DA_SCOPE = "auction_api"

    # Intraday API
    ID_TOKEN_URL = "https://sso.test.brm-power.ro/connect/token"
    ID_WS_URL = "wss://intraday-pmd-api-ws-brm.test.nordpoolgroup.com"
    ID_CLIENT_AUTH = "Basic Y2xpZW50X2ludHJhZGF5X2FwaToxeEI5SWsxeHNFdTJuYndWYTFCUg=="
    ID_USERNAME = "Test_IntradayAPI_ADREM"
    ID_PASSWORD = "nR(B8fDY{485Nq4mu"
    ID_SCOPE = "intraday_api"


# ============================================================================
# Data Models
# ============================================================================
class TestResult(BaseModel):
    test_name: str
    status: str  # "success", "failed", "warning"
    message: str
    details: Optional[Dict] = None
    timestamp: str = ""


class OrderAttempt(BaseModel):
    market: str
    order_type: str
    details: Dict
    response_code: int
    response_message: str
    timestamp: str


# ============================================================================
# API Clients
# ============================================================================
class DayAheadClient:
    def __init__(self):
        self.token = None
        self.token_expires = None

    def get_token(self) -> Optional[str]:
        if self.token and self.token_expires and datetime.now() < self.token_expires:
            return self.token

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": Config.DA_CLIENT_AUTH
        }
        data = {
            "grant_type": "password",
            "scope": Config.DA_SCOPE,
            "username": Config.DA_USERNAME,
            "password": Config.DA_PASSWORD
        }

        try:
            resp = requests.post(Config.DA_TOKEN_URL, headers=headers, data=data, verify=False, timeout=10)
            if resp.status_code == 200:
                token_data = resp.json()
                self.token = token_data["access_token"]
                self.token_expires = datetime.now() + timedelta(seconds=token_data.get("expires_in", 3600) - 60)
                return self.token
        except Exception as e:
            print(f"Day-Ahead auth error: {e}")
        return None

    def api_request(self, endpoint: str, method: str = "GET", data: Dict = None) -> Dict:
        token = self.get_token()
        if not token:
            return {"success": False, "error": "Authentication failed", "status_code": 401}

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

        url = f"{Config.DA_API_BASE}{endpoint}"

        try:
            if method == "GET":
                resp = requests.get(url, headers=headers, verify=False, timeout=15)
            elif method == "POST":
                resp = requests.post(url, headers=headers, json=data, verify=False, timeout=15)
            else:
                return {"success": False, "error": f"Unsupported method: {method}"}

            result = {
                "success": resp.status_code in [200, 201],
                "status_code": resp.status_code,
                "data": None,
                "error": None
            }

            try:
                result["data"] = resp.json()
            except:
                result["data"] = resp.text

            if not result["success"]:
                result["error"] = result["data"]

            return result

        except Exception as e:
            return {"success": False, "error": str(e), "status_code": 0}

    def get_auctions(self) -> Dict:
        today = datetime.now()
        params = f"?closeBiddingFrom={today.strftime('%Y-%m-%d')}&closeBiddingTo={(today + timedelta(days=3)).strftime('%Y-%m-%d')}"
        return self.api_request(f"/api/v1/auctions{params}")

    def get_auction_details(self, auction_id: str) -> Dict:
        return self.api_request(f"/api/v1/auctions/{auction_id}")

    def get_orders(self, auction_id: str) -> Dict:
        return self.api_request(f"/api/v1/auctions/{auction_id}/orders")

    def place_curve_order(self, order_data: Dict) -> Dict:
        return self.api_request("/api/v1/curveorders", method="POST", data=order_data)


class IntradayClient:
    def __init__(self):
        self.token = None
        self.token_expires = None
        self.delivery_areas = []
        self.contracts = []
        self.connected = False

    def get_token(self) -> Optional[str]:
        if self.token and self.token_expires and datetime.now() < self.token_expires:
            return self.token

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": Config.ID_CLIENT_AUTH
        }
        data = {
            "grant_type": "password",
            "scope": Config.ID_SCOPE,
            "username": Config.ID_USERNAME,
            "password": Config.ID_PASSWORD
        }

        try:
            resp = requests.post(Config.ID_TOKEN_URL, headers=headers, data=data, verify=False, timeout=10)
            if resp.status_code == 200:
                token_data = resp.json()
                self.token = token_data["access_token"]
                self.token_expires = datetime.now() + timedelta(seconds=token_data.get("expires_in", 3600) - 60)
                return self.token
        except Exception as e:
            print(f"Intraday auth error: {e}")
        return None

    async def fetch_market_data(self) -> Dict:
        """Fetch market data via WebSocket"""
        token = self.get_token()
        if not token:
            return {"success": False, "error": "Authentication failed"}

        server_id = str(random.randint(0, 999)).zfill(3)
        session_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=16))
        ws_url = f"{Config.ID_WS_URL}/user/{server_id}/{session_id}/websocket"

        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE

        result = {
            "success": False,
            "delivery_areas": [],
            "contracts": [],
            "config_error": None,
            "order_report_error": None
        }

        try:
            async with websockets.connect(ws_url, ssl=ssl_ctx, max_size=10*1024*1024) as ws:
                # Wait for open frame
                open_frame = await asyncio.wait_for(ws.recv(), timeout=10)
                if open_frame != 'o':
                    return {"success": False, "error": f"Expected 'o', got: {open_frame}"}

                # STOMP CONNECT
                connect = f"CONNECT\naccept-version:1.2\nhost:intraday-pmd-api-ws-brm.test.nordpoolgroup.com\nheart-beat:10000,10000\nX-AUTH-TOKEN:{token}\n\n\x00"
                await ws.send(json.dumps([connect]))

                resp = await asyncio.wait_for(ws.recv(), timeout=10)
                if 'CONNECTED' not in resp:
                    return {"success": False, "error": "STOMP handshake failed"}

                result["success"] = True
                self.connected = True

                # Subscribe to topics
                subscriptions = [
                    ("config", f"/user/{Config.ID_USERNAME}/v1/configuration"),
                    ("areas", f"/user/{Config.ID_USERNAME}/v1/streaming/deliveryAreas"),
                    ("contracts", f"/user/{Config.ID_USERNAME}/v1/streaming/contracts"),
                    ("orders", f"/user/{Config.ID_USERNAME}/v1/streaming/orderExecutionReport"),
                ]

                for sub_id, dest in subscriptions:
                    sub_frame = f"SUBSCRIBE\nid:{sub_id}\ndestination:{dest}\nack:auto\n\n\x00"
                    await ws.send(json.dumps([sub_frame]))

                # Collect messages
                for _ in range(20):
                    try:
                        msg = await asyncio.wait_for(ws.recv(), timeout=1)
                        if msg.startswith('a['):
                            messages = json.loads(msg[1:])
                            for stomp in messages:
                                if 'ERROR' in stomp and 'configuration' in stomp:
                                    result["config_error"] = "Unable to match subscription (no permission)"
                                elif 'ERROR' in stomp and 'orderExecutionReport' in stomp:
                                    result["order_report_error"] = "Unable to match subscription (no permission)"
                                elif 'MESSAGE' in stomp:
                                    body_idx = stomp.find('\n\n') + 2
                                    body = stomp[body_idx:].rstrip('\x00')
                                    if body:
                                        data = json.loads(body)
                                        if 'deliveryAreas' in stomp and isinstance(data, list):
                                            result["delivery_areas"] = data
                                            self.delivery_areas = data
                                        elif 'contracts' in stomp and isinstance(data, list):
                                            result["contracts"] = data
                                            self.contracts = data
                    except asyncio.TimeoutError:
                        continue

        except Exception as e:
            result["error"] = str(e)

        return result


# ============================================================================
# Global State
# ============================================================================
da_client = DayAheadClient()
id_client = IntradayClient()
test_results: List[TestResult] = []
order_attempts: List[OrderAttempt] = []


# ============================================================================
# FastAPI App
# ============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("BRM Trading Dashboard starting...")
    yield
    # Shutdown
    print("BRM Trading Dashboard shutting down...")


app = FastAPI(title="BRM Trading Dashboard", lifespan=lifespan)

# Mount static files
import os
static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/", response_class=HTMLResponse)
async def root():
    return FileResponse(os.path.join(os.path.dirname(__file__), "static", "index.html"))


@app.get("/api/test/dayahead/auth")
async def test_da_auth():
    """Test Day-Ahead authentication"""
    start = datetime.now()
    token = da_client.get_token()
    duration = (datetime.now() - start).total_seconds()

    if token:
        return {
            "status": "success",
            "message": "Authentication successful",
            "details": {
                "token_preview": f"{token[:20]}...{token[-10:]}",
                "expires_at": da_client.token_expires.isoformat() if da_client.token_expires else None,
                "duration_ms": int(duration * 1000)
            }
        }
    return {"status": "failed", "message": "Authentication failed"}


@app.get("/api/test/dayahead/auctions")
async def test_da_auctions():
    """Get Day-Ahead auctions"""
    result = da_client.get_auctions()
    if result["success"]:
        auctions = result["data"]
        return {
            "status": "success",
            "message": f"Found {len(auctions)} auctions",
            "data": auctions
        }
    return {"status": "failed", "message": result.get("error", "Failed to get auctions")}


@app.get("/api/test/dayahead/auction/{auction_id}")
async def test_da_auction_details(auction_id: str):
    """Get auction details including portfolios and contracts"""
    result = da_client.get_auction_details(auction_id)
    if result["success"]:
        return {
            "status": "success",
            "data": result["data"]
        }
    return {"status": "failed", "message": result.get("error")}


@app.get("/api/test/dayahead/orders/{auction_id}")
async def test_da_orders(auction_id: str):
    """Get orders for an auction"""
    result = da_client.get_orders(auction_id)
    if result["success"]:
        return {
            "status": "success",
            "message": "Orders retrieved successfully",
            "data": result["data"]
        }
    return {"status": "failed", "message": result.get("error")}


@app.post("/api/test/dayahead/place-order")
async def test_da_place_order():
    """Attempt to place a Day-Ahead order - demonstrates permission issue"""
    # First get auction details to get valid IDs
    auctions_result = da_client.get_auctions()
    if not auctions_result["success"] or not auctions_result["data"]:
        return {"status": "failed", "message": "No auctions available"}

    # Find an open auction
    open_auction = None
    for auction in auctions_result["data"]:
        if auction.get("state") == "Open":
            open_auction = auction
            break

    if not open_auction:
        return {"status": "failed", "message": "No open auctions found"}

    # Get auction details for portfolio and contracts
    details = da_client.get_auction_details(open_auction["id"])
    if not details["success"]:
        return {"status": "failed", "message": "Failed to get auction details"}

    auction_data = details["data"]
    portfolio = auction_data.get("portfolios", [{}])[0].get("id", "UNKNOWN")
    contracts = auction_data.get("contracts", [{}])[0].get("contracts", [])
    contract_id = contracts[0]["id"] if contracts else "UNKNOWN"

    # Create order
    order = {
        "auctionId": open_auction["id"],
        "portfolio": portfolio,
        "areaCode": "TEL",
        "curves": [{
            "contractId": contract_id,
            "curvePoints": [{"price": 50.0, "volume": 1.0}]
        }],
        "comment": "Test order from BRM Dashboard"
    }

    # Attempt to place order
    result = da_client.place_curve_order(order)

    attempt = OrderAttempt(
        market="Day-Ahead",
        order_type="CurveOrder",
        details=order,
        response_code=result.get("status_code", 0),
        response_message=str(result.get("error") or result.get("data")),
        timestamp=datetime.now().isoformat()
    )
    order_attempts.append(attempt)

    return {
        "status": "success" if result["success"] else "failed",
        "order_sent": order,
        "response_code": result.get("status_code"),
        "response_message": result.get("error") or result.get("data"),
        "evidence": {
            "endpoint": "POST /api/v1/curveorders",
            "portfolio_used": portfolio,
            "portfolio_visible": True,
            "order_submission": "DENIED" if not result["success"] else "ALLOWED"
        }
    }


@app.get("/api/test/intraday/auth")
async def test_id_auth():
    """Test Intraday authentication"""
    start = datetime.now()
    token = id_client.get_token()
    duration = (datetime.now() - start).total_seconds()

    if token:
        return {
            "status": "success",
            "message": "Authentication successful",
            "details": {
                "token_preview": f"{token[:20]}...{token[-10:]}",
                "expires_at": id_client.token_expires.isoformat() if id_client.token_expires else None,
                "duration_ms": int(duration * 1000)
            }
        }
    return {"status": "failed", "message": "Authentication failed"}


@app.get("/api/test/intraday/market-data")
async def test_id_market_data():
    """Fetch Intraday market data via WebSocket"""
    result = await id_client.fetch_market_data()

    # Find Romania
    romania = None
    for area in result.get("delivery_areas", []):
        if area.get("countryIsoCode") == "RO":
            romania = area
            break

    # Count active contracts for Romania
    ro_active = 0
    if romania:
        ro_id = romania.get("deliveryAreaId")
        for contract in result.get("contracts", []):
            for state in contract.get("dlvryAreaState", []):
                if state.get("dlvryAreaId") == ro_id and state.get("state") == "ACTI":
                    ro_active += 1
                    break

    return {
        "status": "success" if result.get("success") else "failed",
        "websocket_connected": result.get("success", False),
        "delivery_areas_count": len(result.get("delivery_areas", [])),
        "contracts_count": len(result.get("contracts", [])),
        "romania": romania,
        "romania_active_contracts": ro_active,
        "config_subscription": {
            "status": "DENIED" if result.get("config_error") else "NOT_TESTED",
            "error": result.get("config_error")
        },
        "order_report_subscription": {
            "status": "DENIED" if result.get("order_report_error") else "NOT_TESTED",
            "error": result.get("order_report_error")
        }
    }


@app.get("/api/test/intraday/permissions")
async def test_id_permissions():
    """Test Intraday subscription permissions"""
    token = id_client.get_token()
    if not token:
        return {"status": "failed", "message": "Authentication failed"}

    server_id = str(random.randint(0, 999)).zfill(3)
    session_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=16))
    ws_url = f"{Config.ID_WS_URL}/user/{server_id}/{session_id}/websocket"

    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE

    results = {
        "authentication": {"status": "success", "message": "Token obtained"},
        "websocket_connection": {"status": "pending"},
        "stomp_handshake": {"status": "pending"},
        "subscriptions": {}
    }

    topics_to_test = [
        ("deliveryAreas", f"/user/{Config.ID_USERNAME}/v1/streaming/deliveryAreas", "Market Data"),
        ("contracts", f"/user/{Config.ID_USERNAME}/v1/streaming/contracts", "Market Data"),
        ("localview", f"/user/{Config.ID_USERNAME}/v1/streaming/localview", "Market Data"),
        ("configuration", f"/user/{Config.ID_USERNAME}/v1/configuration", "Trading Config"),
        ("orderExecutionReport", f"/user/{Config.ID_USERNAME}/v1/streaming/orderExecutionReport", "Trading"),
        ("privateTrade", f"/user/{Config.ID_USERNAME}/v1/streaming/privateTrade", "Trading"),
        ("errors", f"/user/{Config.ID_USERNAME}/v1/streaming/errors", "Trading"),
    ]

    try:
        async with websockets.connect(ws_url, ssl=ssl_ctx, max_size=10*1024*1024) as ws:
            # Open frame
            open_frame = await asyncio.wait_for(ws.recv(), timeout=10)
            results["websocket_connection"] = {
                "status": "success" if open_frame == 'o' else "failed",
                "message": "SockJS connection established" if open_frame == 'o' else f"Unexpected: {open_frame}"
            }

            if open_frame != 'o':
                return results

            # STOMP CONNECT
            connect = f"CONNECT\naccept-version:1.2\nhost:intraday-pmd-api-ws-brm.test.nordpoolgroup.com\nheart-beat:10000,10000\nX-AUTH-TOKEN:{token}\n\n\x00"
            await ws.send(json.dumps([connect]))

            resp = await asyncio.wait_for(ws.recv(), timeout=10)
            results["stomp_handshake"] = {
                "status": "success" if 'CONNECTED' in resp else "failed",
                "message": "STOMP handshake successful" if 'CONNECTED' in resp else "STOMP handshake failed"
            }

            if 'CONNECTED' not in resp:
                return results

            # Test each subscription
            for topic_name, destination, category in topics_to_test:
                sub_frame = f"SUBSCRIBE\nid:test-{topic_name}\ndestination:{destination}\nack:auto\n\n\x00"
                await ws.send(json.dumps([sub_frame]))

                # Check for response
                results["subscriptions"][topic_name] = {
                    "destination": destination,
                    "category": category,
                    "status": "pending"
                }

            # Collect responses
            await asyncio.sleep(0.5)
            for _ in range(15):
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=0.5)
                    if msg.startswith('a['):
                        messages = json.loads(msg[1:])
                        for stomp in messages:
                            if 'ERROR' in stomp:
                                # Find which topic failed
                                for topic_name, dest, _ in topics_to_test:
                                    if dest in stomp:
                                        results["subscriptions"][topic_name]["status"] = "DENIED"
                                        results["subscriptions"][topic_name]["error"] = "Unable to match subscription"
                            elif 'MESSAGE' in stomp:
                                for topic_name, dest, _ in topics_to_test:
                                    if topic_name in stomp or dest in stomp:
                                        results["subscriptions"][topic_name]["status"] = "ALLOWED"
                                        results["subscriptions"][topic_name]["data_received"] = True
                except asyncio.TimeoutError:
                    continue

            # Mark remaining as allowed (data received)
            for topic_name in results["subscriptions"]:
                if results["subscriptions"][topic_name]["status"] == "pending":
                    if results["subscriptions"][topic_name].get("data_received"):
                        results["subscriptions"][topic_name]["status"] = "ALLOWED"
                    else:
                        results["subscriptions"][topic_name]["status"] = "UNKNOWN"

    except Exception as e:
        results["error"] = str(e)

    return results


@app.get("/api/evidence/summary")
async def get_evidence_summary():
    """Get summary of all permission evidence"""
    return {
        "timestamp": datetime.now().isoformat(),
        "environment": "TEST",
        "day_ahead": {
            "api_url": Config.DA_API_BASE,
            "username": Config.DA_USERNAME,
            "capabilities": {
                "authentication": "WORKING",
                "view_auctions": "WORKING",
                "view_auction_details": "WORKING",
                "view_portfolios": "WORKING",
                "view_contracts": "WORKING",
                "view_orders": "WORKING",
                "place_orders": "DENIED - 'user has no permissions to submit orders to that portfolio'"
            }
        },
        "intraday": {
            "websocket_url": Config.ID_WS_URL,
            "username": Config.ID_USERNAME,
            "capabilities": {
                "authentication": "WORKING",
                "websocket_connection": "WORKING",
                "stomp_handshake": "WORKING",
                "subscribe_deliveryAreas": "WORKING",
                "subscribe_contracts": "WORKING",
                "subscribe_localview": "WORKING",
                "subscribe_configuration": "DENIED - 'Unable to match subscription'",
                "subscribe_orderExecutionReport": "DENIED - 'Unable to match subscription'",
                "subscribe_privateTrade": "DENIED - 'Unable to match subscription'",
                "place_orders": "DENIED - No access to trading topics"
            }
        },
        "conclusion": "Test users have READ-ONLY permissions. Trading/order submission requires additional permissions from BRM."
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
