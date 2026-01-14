"""
Test Intraday Order Placement
Retrieves configuration (portfolios) and attempts to place a test order
"""
import asyncio
import websockets
import json
import logging
import random
import string
import ssl
from datetime import datetime

from intraday_auth import IntradayAuthenticator

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def generate_sockjs_server_id() -> str:
    return str(random.randint(0, 999)).zfill(3)


def generate_sockjs_session_id(length: int = 16) -> str:
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))


class IntradayOrderTest:
    """Test intraday order placement"""

    def __init__(self):
        self.auth = IntradayAuthenticator()
        self.access_token = None
        self.username = "Test_IntradayAPI_ADREM"
        self.base_url = "wss://intraday-pmd-api-ws-brm.test.nordpoolgroup.com"

        # Data from subscriptions
        self.configuration = None
        self.portfolios = []
        self.delivery_areas = []
        self.contracts = []

    def _build_sockjs_url(self) -> str:
        server_id = generate_sockjs_server_id()
        session_id = generate_sockjs_session_id()
        return f"{self.base_url}/user/{server_id}/{session_id}/websocket"

    def _wrap_stomp(self, frame: str) -> str:
        return json.dumps([frame])

    async def run_test(self):
        """Run the full order placement test"""
        logger.info("=" * 60)
        logger.info("INTRADAY ORDER PLACEMENT TEST")
        logger.info("=" * 60)

        # Step 1: Authenticate
        logger.info("\n[STEP 1] Authenticating...")
        self.access_token = self.auth.get_access_token()
        if not self.access_token:
            logger.error("Authentication failed!")
            return False
        logger.info("Authentication successful")

        # Step 2: Connect WebSocket
        logger.info("\n[STEP 2] Connecting to WebSocket...")
        ws_url = self._build_sockjs_url()
        logger.info(f"URL: {ws_url}")

        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        try:
            async with websockets.connect(
                ws_url,
                ssl=ssl_context,
                max_size=10 * 1024 * 1024
            ) as ws:
                # Wait for SockJS open frame
                open_frame = await asyncio.wait_for(ws.recv(), timeout=10)
                if open_frame != 'o':
                    logger.error(f"Expected 'o', got: {open_frame}")
                    return False
                logger.info("SockJS connection established")

                # Step 3: STOMP CONNECT
                logger.info("\n[STEP 3] STOMP handshake...")
                connect_frame = (
                    "CONNECT\n"
                    "accept-version:1.2\n"
                    "host:intraday-pmd-api-ws-brm.test.nordpoolgroup.com\n"
                    "heart-beat:10000,10000\n"
                    f"X-AUTH-TOKEN:{self.access_token}\n"
                    "\n"
                    "\x00"
                )
                await ws.send(self._wrap_stomp(connect_frame))

                response = await asyncio.wait_for(ws.recv(), timeout=10)
                if 'CONNECTED' not in response:
                    logger.error(f"STOMP connect failed: {response[:200]}")
                    return False
                logger.info("STOMP handshake successful")

                # Step 4: Subscribe to configuration (get portfolios)
                logger.info("\n[STEP 4] Subscribing to configuration...")
                config_sub = (
                    "SUBSCRIBE\n"
                    "id:config-sub\n"
                    f"destination:/user/{self.username}/v1/configuration\n"
                    "ack:auto\n"
                    "\n"
                    "\x00"
                )
                await ws.send(self._wrap_stomp(config_sub))
                logger.info("Subscribed to configuration")

                # Step 5: Subscribe to delivery areas
                logger.info("\n[STEP 5] Subscribing to delivery areas...")
                areas_sub = (
                    "SUBSCRIBE\n"
                    "id:areas-sub\n"
                    f"destination:/user/{self.username}/v1/streaming/deliveryAreas\n"
                    "ack:auto\n"
                    "\n"
                    "\x00"
                )
                await ws.send(self._wrap_stomp(areas_sub))

                # Step 6: Subscribe to contracts
                logger.info("\n[STEP 6] Subscribing to contracts...")
                contracts_sub = (
                    "SUBSCRIBE\n"
                    "id:contracts-sub\n"
                    f"destination:/user/{self.username}/v1/streaming/contracts\n"
                    "ack:auto\n"
                    "\n"
                    "\x00"
                )
                await ws.send(self._wrap_stomp(contracts_sub))

                # Step 7: Subscribe to order execution reports
                logger.info("\n[STEP 7] Subscribing to order execution reports...")
                order_report_sub = (
                    "SUBSCRIBE\n"
                    "id:order-report-sub\n"
                    f"destination:/user/{self.username}/v1/streaming/orderExecutionReport\n"
                    "ack:auto\n"
                    "\n"
                    "\x00"
                )
                await ws.send(self._wrap_stomp(order_report_sub))

                # Step 8: Wait for data
                logger.info("\n[STEP 8] Waiting for market data...")
                await self._receive_messages(ws, timeout=10)

                # Step 9: Display received data
                logger.info("\n" + "=" * 60)
                logger.info("RECEIVED DATA SUMMARY")
                logger.info("=" * 60)

                if self.portfolios:
                    logger.info(f"\nPortfolios ({len(self.portfolios)}):")
                    for p in self.portfolios:
                        logger.info(f"  - ID: {p.get('id')}, Name: {p.get('name')}")
                else:
                    logger.warning("No portfolios received!")

                if self.delivery_areas:
                    logger.info(f"\nDelivery Areas ({len(self.delivery_areas)}):")
                    for area in self.delivery_areas[:5]:
                        logger.info(f"  - ID: {area.get('id')}, Code: {area.get('code')}, Name: {area.get('name')}")
                else:
                    logger.warning("No delivery areas received!")

                if self.contracts:
                    logger.info(f"\nContracts ({len(self.contracts)}):")
                    for c in self.contracts[:5]:
                        logger.info(f"  - ID: {c.get('id')}, Name: {c.get('name')}")
                else:
                    logger.warning("No contracts received!")

                # Step 10: Attempt to place a test order (if we have required data)
                if self.portfolios and self.delivery_areas and self.contracts:
                    logger.info("\n" + "=" * 60)
                    logger.info("ATTEMPTING TEST ORDER")
                    logger.info("=" * 60)

                    portfolio_id = self.portfolios[0].get('id')

                    # Find Romania delivery area
                    romania_area = None
                    for area in self.delivery_areas:
                        if area.get('code') == 'RO' or 'Romania' in str(area.get('name', '')):
                            romania_area = area
                            break

                    if not romania_area and self.delivery_areas:
                        romania_area = self.delivery_areas[0]  # Use first area if RO not found

                    delivery_area_id = romania_area.get('id') if romania_area else 1

                    # Get first tradeable contract
                    contract_id = None
                    for c in self.contracts:
                        if c.get('state') in ['OPEN', 'ACTIVE', 'TRADING']:
                            contract_id = c.get('id')
                            break

                    if not contract_id and self.contracts:
                        contract_id = self.contracts[0].get('id')

                    logger.info(f"Using:")
                    logger.info(f"  - Portfolio ID: {portfolio_id}")
                    logger.info(f"  - Delivery Area ID: {delivery_area_id}")
                    logger.info(f"  - Contract ID: {contract_id}")

                    # Create a small BUY limit order
                    import uuid
                    client_order_id = str(uuid.uuid4())

                    order_request = {
                        "requestId": str(uuid.uuid4()),
                        "rejectPartially": False,
                        "linkedBasket": False,
                        "orders": [{
                            "portfolioId": str(portfolio_id),
                            "contractIds": [str(contract_id)],
                            "deliveryAreaId": int(delivery_area_id),
                            "side": "BUY",
                            "orderType": "LIMIT",
                            "unitPrice": 1000,  # 10.00 EUR/MWh (price in cents)
                            "quantity": 100,     # 0.1 MW (quantity in kW)
                            "timeInForce": "GFS",  # Good for Session
                            "executionRestriction": "NON",  # No restriction
                            "state": "ACTI",
                            "clientOrderId": client_order_id
                        }]
                    }

                    logger.info(f"\nSending order: {json.dumps(order_request, indent=2)}")

                    order_frame = (
                        "SEND\n"
                        "destination:/v1/orderEntryRequest\n"
                        "content-type:application/json\n"
                        "\n"
                        f"{json.dumps(order_request)}\x00"
                    )
                    await ws.send(self._wrap_stomp(order_frame))
                    logger.info("Order sent! Waiting for response...")

                    # Wait for order response
                    await self._receive_messages(ws, timeout=10)

                else:
                    logger.warning("\nCannot place order - missing required data:")
                    if not self.portfolios:
                        logger.warning("  - No portfolios")
                    if not self.delivery_areas:
                        logger.warning("  - No delivery areas")
                    if not self.contracts:
                        logger.warning("  - No contracts")

                logger.info("\n" + "=" * 60)
                logger.info("TEST COMPLETED")
                logger.info("=" * 60)

        except asyncio.TimeoutError:
            logger.error("Connection timeout!")
            return False
        except Exception as e:
            logger.error(f"Error: {e}")
            import traceback
            traceback.print_exc()
            return False

        return True

    async def _receive_messages(self, ws, timeout: int = 10):
        """Receive and process messages for a duration"""
        end_time = asyncio.get_event_loop().time() + timeout

        while asyncio.get_event_loop().time() < end_time:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=2)
                self._process_message(msg)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.debug(f"Receive error: {e}")
                break

    def _process_message(self, msg: str):
        """Process a received SockJS message"""
        if msg == 'h':
            logger.debug("Heartbeat received")
            return

        if not msg.startswith('a['):
            return

        try:
            messages = json.loads(msg[1:])
            for stomp_msg in messages:
                self._process_stomp_frame(stomp_msg)
        except Exception as e:
            logger.debug(f"Parse error: {e}")

    def _process_stomp_frame(self, frame: str):
        """Process a STOMP frame"""
        lines = frame.split('\n')
        if not lines:
            return

        command = lines[0]

        # Parse headers and body
        headers = {}
        body_start = 1
        for i, line in enumerate(lines[1:], 1):
            if line == '':
                body_start = i + 1
                break
            if ':' in line:
                key, value = line.split(':', 1)
                headers[key] = value

        body = '\n'.join(lines[body_start:]).rstrip('\x00')

        if command == 'MESSAGE':
            destination = headers.get('destination', '')
            try:
                data = json.loads(body) if body else {}
                self._handle_message(destination, data)
            except json.JSONDecodeError:
                pass

        elif command == 'ERROR':
            logger.error(f"STOMP ERROR: {body}")

        elif command == 'RECEIPT':
            logger.info(f"RECEIPT: {headers.get('receipt-id')}")

    def _handle_message(self, destination: str, data):
        """Handle different message types"""
        if 'configuration' in destination:
            logger.info(f"Configuration received!")
            self.configuration = data
            if isinstance(data, dict):
                self.portfolios = data.get('portfolios', [])
                logger.info(f"  Portfolios: {len(self.portfolios)}")

        elif 'deliveryAreas' in destination:
            if isinstance(data, list):
                self.delivery_areas = data
            elif isinstance(data, dict) and 'deliveryAreas' in data:
                self.delivery_areas = data['deliveryAreas']
            logger.info(f"Delivery areas received: {len(self.delivery_areas)}")

        elif 'contracts' in destination:
            if isinstance(data, list):
                self.contracts = data
            elif isinstance(data, dict) and 'contracts' in data:
                self.contracts = data['contracts']
            logger.info(f"Contracts received: {len(self.contracts)}")

        elif 'orderExecutionReport' in destination:
            logger.info(f"ORDER EXECUTION REPORT: {json.dumps(data, indent=2)}")

        elif 'Error' in str(data) or 'error' in str(data):
            logger.warning(f"Error in message: {data}")

        else:
            logger.debug(f"Message from {destination}: {str(data)[:100]}")


async def main():
    test = IntradayOrderTest()
    await test.run_test()


if __name__ == "__main__":
    asyncio.run(main())
