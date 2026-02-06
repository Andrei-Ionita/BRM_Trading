"""
Intraday Automation Script for Astro Solar Asset
Runs continuously on delivery day, monitors imbalances and trades to zero.

Usage:
    python intraday_automation.py [--dry-run] [--date YYYY-MM-DD] [--interval-minutes 15]

    --dry-run: Calculate imbalances but don't place orders
    --date: Specify delivery date (default: today)
    --interval-minutes: How often to run (default: 15)
"""
import asyncio
import argparse
import logging
import os
import sys
import signal
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path

import pandas as pd

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from config import config
from intraday_auth import IntradayAuthenticator
from intraday_client import (
    IntradayWebSocketClient,
    IntradayOrder,
    OrderType,
    TimeInForce,
    ExecutionRestriction
)
from imbalance_manager import (
    mwh_to_mw,
    convert_for_intraday,
    get_current_cet_interval,
    get_remaining_intervals,
    get_today_date,
    load_position,
    update_position_after_trade,
    calculate_imbalances,
    get_contract_id_for_interval,
    is_market_open_for_interval,
    interval_to_datetime,
    TZ_CET,
    DEFAULT_IMBALANCE_THRESHOLD_MW
)

# IDM trading window: only trade the next N intervals (2 hours = 8 intervals)
# This prevents excessive trading on distant intervals with less accurate forecasts
IDM_TRADING_WINDOW_INTERVALS = 8


def calculate_imbalances_windowed(
    position: Dict,
    new_forecast: Dict[int, float],
    from_interval: int,
    to_interval: int,
    threshold_mw: float = DEFAULT_IMBALANCE_THRESHOLD_MW
) -> List[Tuple[int, float, str]]:
    """
    Calculate imbalances between contracted and new forecast for a specific window.

    Args:
        position: Position data with contracted values (MW)
        new_forecast: Dict mapping CET interval to new forecast (MW)
        from_interval: Start interval (inclusive)
        to_interval: End interval (inclusive)
        threshold_mw: Minimum imbalance to trade (MW)

    Returns:
        List of (interval, imbalance_mw, side) tuples where trading is needed
    """
    imbalances = []

    for interval in range(from_interval, to_interval + 1):
        interval_key = str(interval)

        if interval_key not in position["intervals"]:
            continue

        interval_data = position["intervals"][interval_key]
        contracted = interval_data["contracted"]
        forecast = new_forecast.get(interval, 0.0)

        # IMPORTANT: If forecast is 0 or missing, look for last non-zero in history
        # This prevents the Solcast bug where near-term intervals show 0
        # because Solcast only returns FUTURE intervals
        if forecast == 0.0:
            # First try: get last non-zero forecast from database history
            try:
                from database import get_last_nonzero_forecast
                last_valid = get_last_nonzero_forecast(
                    position.get("delivery_date", ""),
                    interval
                )
                if last_valid and last_valid > 0:
                    logger.warning(f"Interval {interval}: Solcast returned 0, using last valid forecast {last_valid:.2f} from history")
                    forecast = last_valid
            except Exception as e:
                logger.debug(f"Could not get last non-zero forecast from DB: {e}")

            # Second fallback: use DA forecast if no history available
            if forecast == 0.0:
                da_forecast = interval_data.get("da_forecast", interval_data.get("da_sold", 0.0))
                if da_forecast > 0:
                    logger.warning(f"Interval {interval}: No history found, using DA forecast {da_forecast:.2f} as final fallback")
                    forecast = da_forecast

        # imbalance = contracted - forecast
        # positive: we committed more than we'll produce -> BUY
        # negative: we'll produce more than committed -> SELL
        imbalance = contracted - forecast

        if abs(imbalance) >= threshold_mw:
            side = "BUY" if imbalance > 0 else "SELL"
            imbalances.append((interval, abs(imbalance), side))
            logger.debug(f"Interval {interval}: contracted={contracted:.1f}, "
                        f"forecast={forecast:.1f}, imbalance={imbalance:.1f} -> {side}")

    return imbalances

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global flag for graceful shutdown
shutdown_requested = False


def handle_shutdown(signum, frame):
    """Handle shutdown signals gracefully."""
    global shutdown_requested
    logger.info(f"Shutdown requested (signal {signum})")
    shutdown_requested = True


# Register signal handlers
signal.signal(signal.SIGINT, handle_shutdown)
signal.signal(signal.SIGTERM, handle_shutdown)


# ==================== Forecast Functions ====================

def fetch_fresh_forecast() -> pd.DataFrame:
    """
    Fetch fresh Solcast forecast data.

    Returns:
        DataFrame with forecast data
    """
    from Forecast_functions import fetching_Astro_data_15min
    logger.info("Fetching fresh Solcast forecast data...")
    return fetching_Astro_data_15min()


def run_prediction() -> pd.DataFrame:
    """
    Run XGBoost prediction model on current forecast data.

    Returns:
        DataFrame with predictions
    """
    from Forecast_functions import predicting_exporting_Astro_15min
    logger.info("Running XGBoost prediction model...")
    return predicting_exporting_Astro_15min(0, 24, 0)


def get_forecast_for_date(delivery_date: str) -> Optional[Dict[int, float]]:
    """
    Get forecast predictions for a specific delivery date.

    Args:
        delivery_date: Date in YYYY-MM-DD format

    Returns:
        Dict mapping interval (1-96) to predicted MWh (all in CET)
    """
    results_path = Path(__file__).parent / "Astro" / "Results_Production_Astro_xgb_15min.xlsx"

    if not results_path.exists():
        logger.error(f"Prediction results file not found: {results_path}")
        return None

    try:
        df = pd.read_excel(results_path)
        df["Data"] = pd.to_datetime(df["Data"])

        target_date = datetime.strptime(delivery_date, "%Y-%m-%d")
        df_date = df[df["Data"].dt.date == target_date.date()]

        if df_date.empty:
            logger.warning(f"No predictions found for {delivery_date}")
            return None

        forecast = {}
        for _, row in df_date.iterrows():
            interval = int(row["Interval"])
            prediction = float(row["Prediction"])
            forecast[interval] = prediction

        logger.info(f"Loaded {len(forecast)} intervals for {delivery_date}")
        return forecast

    except Exception as e:
        logger.error(f"Error reading forecast file: {e}")
        return None


def get_updated_forecast_mw(delivery_date: str) -> Optional[Dict[int, float]]:
    """
    Fetch fresh forecast and convert to MW.
    Also saves the forecast to history database for tracking.

    Returns:
        Dict mapping interval (1-96) to forecast MW
    """
    # Fetch and predict
    try:
        logger.info("Fetching fresh Solcast data...")
        fetch_fresh_forecast()
        logger.info("Running XGBoost prediction...")
        run_prediction()
        logger.info("Forecast updated successfully")
    except Exception as e:
        logger.warning(f"Error refreshing forecast: {e}")
        logger.info("Continuing with existing forecast data")

    # Get forecast (already in CET)
    logger.info(f"Loading forecast for {delivery_date}...")
    forecast = get_forecast_for_date(delivery_date)
    if not forecast:
        logger.error(f"No forecast data found for {delivery_date}")
        return None

    # Convert MWh to MW
    forecast_mw = {}
    for interval, mwh in forecast.items():
        forecast_mw[interval] = mwh_to_mw(mwh)

    logger.info(f"Loaded forecast: {len(forecast_mw)} intervals, total {sum(forecast_mw.values()):.2f} MW")

    # Save forecast to history database
    try:
        from database import save_forecast_to_history
        save_forecast_to_history(delivery_date, forecast_mw)
        logger.info(f"Forecast saved to history for {delivery_date}")
    except Exception as e:
        logger.warning(f"Could not save forecast to history: {e}")

    return forecast_mw


# ==================== Market Data ====================

class MarketDataHandler:
    """Handler for real-time market data from WebSocket."""

    def __init__(self):
        self.order_book: Dict[str, Dict] = {}  # contract_id -> {bids: [], asks: []}
        self.contracts: Dict[str, Dict] = {}   # contract_id -> contract info
        self.last_update: Optional[datetime] = None

    def handle_local_view(self, data: Dict[str, Any]):
        """Handle order book updates."""
        try:
            contract_id = data.get("contractId")
            if contract_id:
                self.order_book[contract_id] = {
                    "bids": data.get("buyOrders", []),
                    "asks": data.get("sellOrders", [])
                }
                self.last_update = datetime.now()
                logger.debug(f"Updated order book for {contract_id}")
        except Exception as e:
            logger.error(f"Error handling local view: {e}")

    def handle_contracts(self, data: Dict[str, Any]):
        """Handle contract updates."""
        try:
            contracts = data.get("contracts", [data]) if isinstance(data, dict) else data
            for contract in contracts:
                contract_id = contract.get("contractId") or contract.get("id")
                if contract_id:
                    self.contracts[contract_id] = contract
                    logger.debug(f"Updated contract info for {contract_id}")
        except Exception as e:
            logger.error(f"Error handling contracts: {e}")

    def get_best_bid(self, contract_id: str) -> Optional[Tuple[float, float]]:
        """Get best bid (price, quantity) for a contract."""
        book = self.order_book.get(contract_id, {})
        bids = book.get("bids", [])
        if bids:
            # Bids sorted by price descending (best first)
            best = max(bids, key=lambda x: x.get("price", 0))
            return (best.get("price", 0) / 100, best.get("quantity", 0))  # Convert from cents
        return None

    def get_best_ask(self, contract_id: str) -> Optional[Tuple[float, float]]:
        """Get best ask (price, quantity) for a contract."""
        book = self.order_book.get(contract_id, {})
        asks = book.get("asks", [])
        if asks:
            # Asks sorted by price ascending (best first)
            best = min(asks, key=lambda x: x.get("price", float("inf")))
            return (best.get("price", float("inf")) / 100, best.get("quantity", 0))
        return None

    def get_mid_price(self, contract_id: str) -> Optional[float]:
        """Get mid price for a contract."""
        bid = self.get_best_bid(contract_id)
        ask = self.get_best_ask(contract_id)
        if bid and ask:
            return (bid[0] + ask[0]) / 2
        return None


# ==================== Trade Execution ====================

class TradeExecutor:
    """Handles intraday trade execution and tracking."""

    def __init__(self, delivery_date: str, environment: str = "test"):
        self.delivery_date = delivery_date
        self.environment = environment
        self.pending_orders: Dict[str, Dict] = {}  # request_id -> order info
        self.executed_trades: List[Dict] = []
        self.ws_client: Optional[IntradayWebSocketClient] = None

    async def handle_execution_report(self, data: Dict[str, Any]):
        """Handle order execution reports."""
        try:
            order_id = data.get("orderId")
            status = data.get("state") or data.get("orderState")
            executed_qty = data.get("executedQuantity", 0)

            logger.info(f"Execution report: order={order_id}, status={status}, executed={executed_qty}")

            # Find the pending order by client_order_id or request_id
            client_order_id = data.get("clientOrderId")
            for req_id, order_info in list(self.pending_orders.items()):
                if order_info.get("client_order_id") == client_order_id:
                    order_info["status"] = status
                    order_info["executed_qty"] = executed_qty

                    if status in ["FILL", "FILLED", "EXECUTED"]:
                        # Trade executed - update position
                        await self._process_executed_trade(order_info, executed_qty)
                        del self.pending_orders[req_id]

                    elif status in ["REJE", "REJECTED", "CANC", "CANCELLED"]:
                        logger.warning(f"Order rejected/cancelled: {client_order_id}")
                        del self.pending_orders[req_id]

                    break

        except Exception as e:
            logger.error(f"Error handling execution report: {e}")

    async def handle_private_trade(self, data: Dict[str, Any]):
        """Handle private trade confirmations."""
        try:
            trade_qty = data.get("quantity", 0)
            trade_price = data.get("price", 0)
            side = data.get("side")
            contract_id = data.get("contractId")

            logger.info(f"Private trade: {side} {trade_qty} @ {trade_price} for {contract_id}")
            self.executed_trades.append(data)

        except Exception as e:
            logger.error(f"Error handling private trade: {e}")

    async def _process_executed_trade(self, order_info: Dict, executed_qty: float):
        """Process an executed trade and update position."""
        interval = order_info.get("interval")
        side = order_info.get("side")

        # Convert quantity back to MW
        qty_mw = executed_qty / 1000 if self.environment == "test" else executed_qty

        logger.info(f"Processing executed trade: interval={interval}, {side} {qty_mw:.1f} MW")

        # Update position file
        update_position_after_trade(
            self.delivery_date,
            interval,
            side,
            qty_mw
        )

    async def place_order(
        self,
        contract_id: str,
        interval: int,
        side: str,
        quantity_mw: float,
        price_cents: int,
        portfolio_id: str,
        area_id: int = 111
    ) -> Optional[str]:
        """
        Place an intraday order.

        Args:
            contract_id: Contract ID
            interval: Delivery interval
            side: "BUY" or "SELL"
            quantity_mw: Quantity in MW
            price_cents: Price in cents
            portfolio_id: Portfolio ID
            area_id: Delivery area ID

        Returns:
            Request ID if order sent, None on error
        """
        if not self.ws_client or not self.ws_client.stomp_connected:
            logger.error("WebSocket not connected")
            return None

        # Convert MW to appropriate unit
        quantity_api = int(convert_for_intraday(quantity_mw, self.environment))

        order = IntradayOrder(
            portfolio_id=portfolio_id,
            contract_ids=[contract_id],
            delivery_area_id=area_id,
            side=side,
            order_type=OrderType.LIMIT,
            unit_price=price_cents,
            quantity=quantity_api,
            time_in_force=TimeInForce.IOC,  # Immediate or Cancel
            execution_restriction=ExecutionRestriction.NON
        )

        try:
            request_id = await self.ws_client.send_order(order)

            # Track pending order
            self.pending_orders[request_id] = {
                "interval": interval,
                "contract_id": contract_id,
                "side": side,
                "quantity_mw": quantity_mw,
                "price_cents": price_cents,
                "client_order_id": order.client_order_id,
                "timestamp": datetime.now(),
                "status": "PENDING"
            }

            logger.info(f"Order sent: {side} {quantity_mw:.1f} MW for interval {interval} "
                       f"@ {price_cents/100:.2f} EUR/MWh (request_id={request_id})")

            return request_id

        except Exception as e:
            logger.error(f"Error placing order: {e}")
            return None


# ==================== Main Intraday Loop ====================

async def run_intraday_iteration(
    delivery_date: str,
    executor: TradeExecutor,
    market_data: MarketDataHandler,
    portfolio_id: str,
    area_id: int,
    threshold_mw: float,
    dry_run: bool = False
) -> int:
    """
    Run one iteration of intraday monitoring.

    Args:
        delivery_date: Delivery date
        executor: Trade executor
        market_data: Market data handler
        portfolio_id: Portfolio ID
        area_id: Delivery area ID
        threshold_mw: Minimum imbalance to trade
        dry_run: If True, don't place orders

    Returns:
        Number of orders placed
    """
    orders_placed = 0

    # Get current position
    logger.info(f"Loading position for {delivery_date}...")
    position = load_position(delivery_date)

    if not position:
        # DA didn't run - create empty position so we sell everything on IDM
        logger.warning(f"No position for {delivery_date} - DA may have failed. Creating empty position to sell all on IDM.")
        from imbalance_manager import init_position_file
        # Create position with all zeros - this will make contracted = 0
        # So imbalance = contracted - forecast = 0 - forecast = -forecast (SELL everything)
        empty_da_sold = {i: 0.0 for i in range(1, 97)}
        position = init_position_file(delivery_date, empty_da_sold)
        if not position:
            logger.error(f"Failed to create empty position for {delivery_date}")
            return 0
        logger.info(f"Empty position created - will sell all forecast production on IDM")

    total_contracted = sum(v.get("contracted", 0) for v in position.get("intervals", {}).values())
    logger.info(f"Position loaded: {len(position.get('intervals', {}))} intervals, total contracted: {total_contracted:.2f} MW")

    # Get current interval and calculate trading window
    current_interval = get_current_cet_interval()

    # Only trade the next N intervals (default: 8 = 2 hours)
    # This prevents excessive trading on distant intervals with less accurate forecasts
    first_tradeable = current_interval + 1
    last_tradeable = min(current_interval + IDM_TRADING_WINDOW_INTERVALS, 96)

    if first_tradeable > 96:
        logger.info("No remaining intervals to trade")
        return 0

    logger.info(f"Current interval: {current_interval}, trading window: {first_tradeable}-{last_tradeable} ({last_tradeable - first_tradeable + 1} intervals)")

    # Get updated forecast
    forecast_mw = get_updated_forecast_mw(delivery_date)
    if not forecast_mw:
        logger.warning("Could not get updated forecast - using previous contracted values")
        return 0

    total_forecast = sum(forecast_mw.values())
    logger.info(f"Forecast total: {total_forecast:.2f} MW, Contracted total: {total_contracted:.2f} MW")

    # Calculate imbalances only for the trading window
    logger.info(f"Calculating imbalances for intervals {first_tradeable}-{last_tradeable} (threshold: {threshold_mw} MW)...")
    imbalances = calculate_imbalances_windowed(position, forecast_mw, first_tradeable, last_tradeable, threshold_mw)

    if not imbalances:
        logger.info("No significant imbalances detected (forecast matches contracted)")
        return 0

    logger.info(f"Found {len(imbalances)} intervals with imbalances")

    # Process each imbalance
    for interval, imbalance_mw, side in imbalances:
        # Check if market is still open
        if not is_market_open_for_interval(delivery_date, interval):
            logger.warning(f"Market closed for interval {interval} - skipping")
            continue

        # Get contract ID
        contract_id = get_contract_id_for_interval(delivery_date, interval, area_id)

        # Get price from order book
        if side == "BUY":
            price_info = market_data.get_best_ask(contract_id)
            # Add small premium to ensure execution
            price_adjustment = 1.01
        else:
            price_info = market_data.get_best_bid(contract_id)
            # Add small discount to ensure execution
            price_adjustment = 0.99

        if price_info:
            price_eur = price_info[0] * price_adjustment
        else:
            # Use default price if no order book data
            # SELL at low but reasonable price, BUY at high price to ensure execution
            price_eur = 200.0 if side == "BUY" else 50.0
            logger.warning(f"No order book data for {contract_id} - using default price {price_eur}")

        price_cents = int(price_eur * 100)

        # Round imbalance to 1 decimal as required by IDM market
        rounded_imbalance = round(imbalance_mw, 1)

        # Skip if rounded quantity is 0 (too small to trade)
        if rounded_imbalance < 0.1:
            logger.debug(f"Interval {interval}: imbalance {imbalance_mw:.3f} MW too small to trade (rounds to {rounded_imbalance:.1f})")
            continue

        logger.info(f"Interval {interval}: {side} {rounded_imbalance:.1f} MW @ {price_eur:.2f} EUR/MWh")

        if dry_run:
            logger.info(f"[DRY RUN] Would place order: {side} {rounded_imbalance:.1f} MW")
            orders_placed += 1
        else:
            request_id = await executor.place_order(
                contract_id=contract_id,
                interval=interval,
                side=side,
                quantity_mw=rounded_imbalance,
                price_cents=price_cents,
                portfolio_id=portfolio_id,
                area_id=area_id
            )
            if request_id:
                orders_placed += 1
                # Update position immediately when order is sent (optimistic update)
                # This ensures dashboard shows activity even if execution reports are delayed
                update_position_after_trade(
                    delivery_date,
                    interval,
                    side,
                    rounded_imbalance
                )
                logger.info(f"Position updated for interval {interval}: {side} {rounded_imbalance:.1f} MW")

                # Save trade to database for historical tracking
                try:
                    from database import save_trade
                    save_trade(
                        delivery_date=delivery_date,
                        interval=interval,
                        market="IDM",
                        side=side,
                        quantity_mw=rounded_imbalance,
                        price_eur=price_eur,
                        contract_id=contract_id,
                        order_id=request_id
                    )
                except Exception as e:
                    logger.warning(f"Could not save trade to database: {e}")

    return orders_placed


async def run_intraday_automation(
    delivery_date: Optional[str] = None,
    interval_minutes: int = 15,
    dry_run: bool = False,
    single_run: bool = False
) -> bool:
    """
    Run the continuous intraday automation loop.

    Args:
        delivery_date: Delivery date (default: today)
        interval_minutes: How often to check for imbalances
        dry_run: If True, don't place orders
        single_run: If True, run once and exit

    Returns:
        True if completed successfully
    """
    global shutdown_requested

    logger.info("=" * 60)
    logger.info("Starting Intraday Automation")
    logger.info("=" * 60)

    # Determine delivery date
    if delivery_date is None:
        delivery_date = get_today_date()
    logger.info(f"Delivery date: {delivery_date}")

    # Get configuration
    environment = os.getenv("BRM_ENVIRONMENT", config.environment)
    portfolio_id = os.getenv("INTRADAY_PORTFOLIO_ID", config.intraday_portfolio_id)
    area_id = int(os.getenv("INTRADAY_DELIVERY_AREA_ID", str(config.intraday_delivery_area_id)))
    threshold_mw = float(os.getenv("IMBALANCE_THRESHOLD_MW", str(DEFAULT_IMBALANCE_THRESHOLD_MW)))
    username = os.getenv("INTRADAY_USERNAME", "Test_IntradayAPI_ADREM")

    if not portfolio_id:
        logger.error("No portfolio ID configured - set BRM_PORTFOLIO_ID")
        return False

    logger.info(f"Environment: {environment}")
    logger.info(f"Portfolio ID: {portfolio_id}")
    logger.info(f"Area ID: {area_id}")
    logger.info(f"Imbalance threshold: {threshold_mw} MW")
    logger.info(f"Dry run: {dry_run}")

    # Initialize components
    market_data = MarketDataHandler()
    executor = TradeExecutor(delivery_date, environment)

    # Connect to WebSocket if not dry run
    ws_client = None
    if not dry_run:
        logger.info("Connecting to intraday WebSocket...")
        ws_client = IntradayWebSocketClient(username)

        if await ws_client.connect():
            executor.ws_client = ws_client

            # Subscribe to data feeds
            await ws_client.subscribe_to_contracts(market_data.handle_contracts)
            await ws_client.subscribe_to_local_view(area_id, market_data.handle_local_view)
            await ws_client.subscribe_to_order_execution_reports(executor.handle_execution_report)
            await ws_client.subscribe_to_private_trades(executor.handle_private_trade)

            logger.info("WebSocket connected and subscribed to feeds")

            # Wait briefly for initial data
            await asyncio.sleep(2)
        else:
            logger.error("Failed to connect to WebSocket")
            if not single_run:
                return False

    # Helper function to connect/reconnect WebSocket
    async def ensure_websocket_connected():
        nonlocal ws_client
        if ws_client and ws_client.stomp_connected:
            return True

        logger.info("WebSocket disconnected - reconnecting...")
        if ws_client:
            try:
                await ws_client.disconnect()
            except:
                pass

        ws_client = IntradayWebSocketClient(username)
        executor.ws_client = ws_client

        if await ws_client.connect():
            await ws_client.subscribe_to_contracts(market_data.handle_contracts)
            await ws_client.subscribe_to_local_view(area_id, market_data.handle_local_view)
            await ws_client.subscribe_to_order_execution_reports(executor.handle_execution_report)
            await ws_client.subscribe_to_private_trades(executor.handle_private_trade)
            logger.info("WebSocket reconnected and subscribed to feeds")
            await asyncio.sleep(2)
            return True
        else:
            logger.error("Failed to reconnect WebSocket")
            return False

    # Main loop
    iteration = 0
    try:
        while not shutdown_requested:
            iteration += 1
            logger.info(f"\n--- Iteration {iteration} at {datetime.now(TZ_CET).strftime('%H:%M:%S')} ---")

            current_interval = get_current_cet_interval()

            # Check if delivery day is over
            if current_interval >= 96:
                logger.info("All intervals complete - exiting")
                break

            # Ensure WebSocket is connected before trading (skip for dry run)
            if not dry_run:
                if not await ensure_websocket_connected():
                    logger.error("Cannot trade without WebSocket connection - skipping iteration")
                    continue

            # Run iteration
            try:
                orders = await run_intraday_iteration(
                    delivery_date=delivery_date,
                    executor=executor,
                    market_data=market_data,
                    portfolio_id=portfolio_id,
                    area_id=area_id,
                    threshold_mw=threshold_mw,
                    dry_run=dry_run
                )
                logger.info(f"Iteration complete: {orders} orders placed")

            except Exception as e:
                logger.error(f"Error in iteration: {e}")

            if single_run:
                break

            # Sleep until next interval
            now = datetime.now(TZ_CET)
            next_run = now + timedelta(minutes=interval_minutes)
            # Round to next interval boundary
            next_run = next_run.replace(second=0, microsecond=0)
            next_run = next_run.replace(minute=(next_run.minute // interval_minutes) * interval_minutes)
            if next_run <= now:
                next_run += timedelta(minutes=interval_minutes)

            sleep_seconds = (next_run - now).total_seconds()
            logger.info(f"Next run at {next_run.strftime('%H:%M:%S')} (sleeping {sleep_seconds:.0f}s)")

            # Sleep in small increments to allow graceful shutdown
            while sleep_seconds > 0 and not shutdown_requested:
                await asyncio.sleep(min(sleep_seconds, 5))
                sleep_seconds -= 5

    finally:
        # Cleanup
        if ws_client:
            await ws_client.disconnect()
            logger.info("WebSocket disconnected")

    logger.info("=" * 60)
    logger.info("Intraday Automation Complete")
    logger.info("=" * 60)

    return True


# ==================== CLI Entry Point ====================

def main():
    parser = argparse.ArgumentParser(
        description="Intraday Automation for Astro Solar Asset"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Calculate imbalances but don't place orders"
    )
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="Delivery date (YYYY-MM-DD, default: today)"
    )
    parser.add_argument(
        "--interval-minutes",
        type=int,
        default=15,
        help="How often to run (default: 15 minutes)"
    )
    parser.add_argument(
        "--single-run",
        action="store_true",
        help="Run once and exit (instead of continuous loop)"
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Run the automation
    success = asyncio.run(run_intraday_automation(
        delivery_date=args.date,
        interval_minutes=args.interval_minutes,
        dry_run=args.dry_run,
        single_run=args.single_run
    ))

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
