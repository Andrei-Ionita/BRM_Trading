"""
Day-Ahead Automation Script for Astro Solar Asset
Runs daily before DA gate closure, submits 15-min forecast as curve orders.

Usage:
    python day_ahead_automation.py [--dry-run] [--date YYYY-MM-DD]

    --dry-run: Print orders without submitting
    --date: Specify delivery date (default: tomorrow)
"""
import asyncio
import argparse
import logging
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path

import pandas as pd

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from config import config
from auth import get_authenticator, initialize_auth
from day_ahead_client import DayAheadClient, CurveOrderRequest, OrderSide
from imbalance_manager import (
    mwh_to_mw,
    get_tomorrow_date,
    init_position_file,
    POSITION_FILE
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ==================== Forecast Functions ====================

def fetch_forecast_data() -> pd.DataFrame:
    """
    Fetch fresh Solcast forecast data.

    Returns:
        DataFrame with forecast data
    """
    # Change to Portfolio directory (Forecast_functions uses relative paths like ./Astro/)
    original_dir = os.getcwd()
    portfolio_dir = Path(__file__).parent.parent / "Portfolio"

    try:
        os.chdir(portfolio_dir)
        from Forecast_functions import fetching_Astro_data_15min
        logger.info("Fetching Solcast forecast data...")
        return fetching_Astro_data_15min()
    finally:
        os.chdir(original_dir)


def run_prediction_model(interval_from: int = 0, interval_to: int = 24, limitation: float = 0) -> pd.DataFrame:
    """
    Run XGBoost prediction model on forecast data.

    Args:
        interval_from: Start interval for limitation
        interval_to: End interval for limitation
        limitation: Limitation percentage

    Returns:
        DataFrame with predictions
    """
    # Change to Portfolio directory (Forecast_functions uses relative paths like ./Astro/)
    original_dir = os.getcwd()
    portfolio_dir = Path(__file__).parent.parent / "Portfolio"

    try:
        os.chdir(portfolio_dir)
        from Forecast_functions import predicting_exporting_Astro_15min
        logger.info("Running XGBoost prediction model...")
        return predicting_exporting_Astro_15min(interval_from, interval_to, limitation)
    finally:
        os.chdir(original_dir)


def get_forecast_for_date(delivery_date: str) -> Optional[Dict[int, float]]:
    """
    Get forecast predictions for a specific delivery date.

    Args:
        delivery_date: Date in YYYY-MM-DD format

    Returns:
        Dict mapping interval (1-96) to predicted MWh (all in CET), or None if no data
    """
    # Read the prediction results file
    results_path = Path(__file__).parent.parent / "Portfolio" / "Astro" / "Results_Production_Astro_xgb_15min.xlsx"

    if not results_path.exists():
        logger.error(f"Prediction results file not found: {results_path}")
        return None

    try:
        df = pd.read_excel(results_path)
        df["Data"] = pd.to_datetime(df["Data"])

        # Filter for delivery date
        target_date = datetime.strptime(delivery_date, "%Y-%m-%d")
        df_date = df[df["Data"].dt.date == target_date.date()]

        if df_date.empty:
            logger.warning(f"No predictions found for {delivery_date}")
            return None

        # Build dict: interval -> MWh prediction
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


def get_tomorrow_forecast() -> Optional[Dict[int, float]]:
    """
    Fetch fresh forecast and get predictions for tomorrow (D+1).

    Returns:
        Dict mapping interval (1-96) to predicted MWh
    """
    # Fetch fresh data
    fetch_forecast_data()

    # Run prediction model
    run_prediction_model()

    # Get predictions for tomorrow
    tomorrow = get_tomorrow_date()
    return get_forecast_for_date(tomorrow)


# ==================== Order Building ====================

def build_curve_orders(
    forecast: Dict[int, float],
    delivery_date: str,
    portfolio_id: str,
    area_id: int = 111,
    price: float = 0.0
) -> List[CurveOrderRequest]:
    """
    Build curve orders for all 96 intervals.

    Args:
        forecast: Dict mapping CET interval (1-96) to MWh prediction
        delivery_date: Delivery date in YYYY-MM-DD format
        portfolio_id: Portfolio ID for orders
        area_id: Delivery area ID (default 111 for Romania)
        price: Price for orders (default 0 = price-taker)

    Returns:
        List of 96 CurveOrderRequest objects
    """
    orders = []
    da_sold_mw = {}  # Track DA sold quantities for position file

    # Loop over CET intervals 1-96
    for interval in range(1, 97):
        # Get prediction for this interval (default 0 if not available)
        mwh_prediction = forecast.get(interval, 0.0)

        # Convert MWh to MW (multiply by 4 for 15-min intervals)
        mw_quantity = mwh_to_mw(mwh_prediction)

        # Generate contract ID for this interval
        contract_id = generate_contract_id(delivery_date, interval, area_id)

        # Build order name
        order_name = f"ASTRO_DA_{delivery_date}_{interval:02d}"

        # Create curve order (single point at price with quantity)
        # Round to 1 decimal as required by DA market
        curve_points = [{
            "price": price,
            "quantity": round(mw_quantity, 1)
        }]

        order = CurveOrderRequest(
            name=order_name,
            contract_id=contract_id,
            side=OrderSide.SELL,
            curve_points=curve_points
        )

        orders.append(order)

        # Track for position file
        da_sold_mw[interval] = round(mw_quantity, 1)

        if mw_quantity > 0:
            logger.debug(f"Order {order_name}: {mw_quantity:.1f} MW @ {price}")

    logger.info(f"Built {len(orders)} curve orders for {delivery_date}")
    return orders, da_sold_mw


def generate_contract_id(delivery_date: str, cet_interval: int, area_id: int = 111) -> str:
    """
    Generate contract ID for a DA 15-min product.

    Note: This format may need adjustment based on actual BRM API contract naming.

    Args:
        delivery_date: Date in YYYY-MM-DD format
        cet_interval: Interval number in CET (1-96)
        area_id: Delivery area ID

    Returns:
        Contract ID string
    """
    # Calculate hour and quarter from interval
    hour = (cet_interval - 1) // 4
    quarter = (cet_interval - 1) % 4 + 1  # 1-4

    # Format date as compact string
    date_compact = delivery_date.replace("-", "")

    # Typical format: RO_{date}_{hour:02d}Q{quarter}
    # This may need adjustment based on actual API
    return f"RO_{date_compact}_{hour:02d}Q{quarter}"


# ==================== Order Submission ====================

async def submit_da_orders(
    orders: List[CurveOrderRequest],
    da_sold_mw: Dict[int, float],
    delivery_date: str,
    dry_run: bool = False
) -> Dict[str, any]:
    """
    Submit curve orders to the Day-Ahead market.

    Args:
        orders: List of CurveOrderRequest objects (for logging)
        da_sold_mw: Dict mapping interval to MW quantity
        delivery_date: Delivery date in YYYY-MM-DD format
        dry_run: If True, don't actually submit (just print)

    Returns:
        Dict with submission results
    """
    results = {
        "submitted": 0,
        "failed": 0,
        "skipped": 0,
        "errors": []
    }

    if dry_run:
        logger.info("DRY RUN - Orders will not be submitted")
        logger.info(f"Complete curve with {len(orders)} intervals:")
        for order in orders:
            qty = order.curve_points[0]["quantity"] if order.curve_points else 0
            logger.info(f"[DRY RUN] Would submit: {order.name} - SELL {qty:.1f} MW")
            results["skipped"] += 1
        return results

    client = DayAheadClient()

    # Step 1: Find the open auction for the delivery date
    logger.info(f"Finding open auction for delivery date {delivery_date}...")
    auction = await client.get_open_auction_for_date(delivery_date)

    if not auction:
        error_msg = f"No open auction found for {delivery_date}"
        logger.error(error_msg)
        results["errors"].append(error_msg)
        results["failed"] = len(orders)
        return results

    auction_id = auction.get('id')
    logger.info(f"Found auction: {auction_id}")

    # Step 2: Get the contracts (delivery periods) for the auction
    contracts = await client.get_auction_contracts(auction_id)

    if not contracts:
        error_msg = f"No contracts found for auction {auction_id}"
        logger.error(error_msg)
        results["errors"].append(error_msg)
        results["failed"] = len(orders)
        return results

    logger.info(f"Found {len(contracts)} contracts")

    # Step 3: Build curves in the correct BRM API format
    # Map interval number to contract ID
    # Contracts should be sorted by delivery time
    contracts_sorted = sorted(contracts, key=lambda c: c.get('deliveryStart', ''))

    # Log contract info for debugging
    logger.debug(f"First 3 contracts: {contracts_sorted[:3]}")
    logger.debug(f"da_sold_mw intervals with production: {[k for k, v in da_sold_mw.items() if v > 0][:10]}...")

    curves = []
    total_volume = 0
    for i, contract in enumerate(contracts_sorted):
        # Use interval from contract if available, otherwise use index
        interval = contract.get('interval', i + 1)
        contract_id = contract.get('id')
        delivery_start = contract.get('deliveryStart')
        delivery_end = contract.get('deliveryEnd')

        if not contract_id:
            logger.warning(f"Contract at index {i} has no ID, skipping")
            continue

        # Get the MW quantity for this interval (negative for SELL)
        quantity_mw = da_sold_mw.get(interval, 0.0)

        # BRM expects negative volume for SELL
        volume = -quantity_mw if quantity_mw > 0 else 0

        # Only include non-zero curves
        if volume != 0:
            # BRM API requires curve points at min (-2700) and max (21000) price steps
            curve = {
                "ContractId": contract_id,
                "CurvePoints": [
                    {"Price": -2700.0, "Volume": round(volume, 1)},  # Min price step
                    {"Price": 21000.0, "Volume": round(volume, 1)}   # Max price step
                ]
            }
            curves.append(curve)
            total_volume += abs(volume)
            logger.debug(f"Interval {interval}: contract {contract_id}, volume {volume:.1f} MW")

    logger.info(f"Built {len(curves)} curves with total volume {total_volume:.1f} MW")
    if curves:
        logger.info(f"Sample curve being submitted: {curves[0]}")

    if not curves:
        logger.warning("No curves with non-zero volume to submit")
        results["skipped"] = len(orders)
        return results

    logger.info(f"Submitting {len(curves)} curves with non-zero volume...")

    # Step 4: Check for existing orders and handle them
    existing_orders = await client.get_existing_curve_orders(
        auction_id=auction_id,
        portfolio="ADREM - DA",
        area_code="TEL"
    )

    if existing_orders:
        logger.info(f"Found {len(existing_orders)} existing curve orders - will update via PATCH")
        # Get the existing order ID
        existing_order_id = None
        for order in existing_orders:
            existing_order_id = order.get('id') or order.get('orderId')
            if existing_order_id:
                break

        if existing_order_id:
            # Try to update existing order via PATCH
            result = await client.update_da_curves(
                order_id=existing_order_id,
                auction_id=auction_id,
                curves=curves,
                area_code="TEL",
                portfolio="ADREM - DA"
            )
            if result.get("success"):
                logger.info("DA curves updated successfully!")
                results["submitted"] = len(curves)
                results["skipped"] = len(orders) - len(curves)
                return results

    # Step 5: Submit new curves if no existing orders or update failed
    result = await client.submit_da_curves(
        auction_id=auction_id,
        curves=curves,
        area_code="TEL",  # Romania
        portfolio="ADREM - DA"
    )

    if result.get("success"):
        logger.info("DA curves submitted successfully!")
        results["submitted"] = len(curves)
        results["skipped"] = len(orders) - len(curves)
    else:
        error_msg = f"DA submission failed: {result.get('error')}"
        logger.error(error_msg)
        results["errors"].append(error_msg)
        results["failed"] = len(curves)

    return results


# ==================== Main Workflow ====================

async def run_da_automation(
    delivery_date: Optional[str] = None,
    dry_run: bool = False,
    skip_fetch: bool = False
) -> bool:
    """
    Run the complete Day-Ahead automation workflow.

    Steps:
    1. Fetch fresh Solcast forecast (unless skip_fetch=True)
    2. Run XGBoost prediction model
    3. Filter predictions for delivery date
    4. Convert MWh to MW and EET to CET
    5. Build 96 curve orders
    6. Submit orders to DA market (unless dry_run=True)
    7. Initialize position file

    Args:
        delivery_date: Target delivery date (default: tomorrow)
        dry_run: If True, don't submit orders
        skip_fetch: If True, skip fetching new forecast data

    Returns:
        True if successful
    """
    logger.info("=" * 60)
    logger.info("Starting Day-Ahead Automation")
    logger.info("=" * 60)

    # Determine delivery date
    if delivery_date is None:
        delivery_date = get_tomorrow_date()
    logger.info(f"Delivery date: {delivery_date}")

    # Initialize authentication
    if config.client_id and config.client_secret:
        initialize_auth(config.client_id, config.client_secret)
        logger.info("Authentication initialized")
    else:
        logger.warning("No credentials configured - some features may not work")

    # Step 1 & 2: Fetch forecast and run model
    if not skip_fetch:
        try:
            forecast = get_tomorrow_forecast()
        except Exception as e:
            logger.error(f"Failed to get forecast: {e}")
            forecast = None

        if not forecast:
            # Try to load from existing file
            forecast = get_forecast_for_date(delivery_date)
            if not forecast:
                logger.error("No forecast data available - aborting")
                return False
    else:
        logger.info("Skipping forecast fetch - using existing data")
        forecast = get_forecast_for_date(delivery_date)
        if not forecast:
            logger.error("No existing forecast data available - aborting")
            return False

    # Log forecast summary
    total_mwh = sum(forecast.values())
    non_zero = sum(1 for v in forecast.values() if v > 0)
    logger.info(f"Forecast summary: {non_zero} intervals with production, total {total_mwh:.2f} MWh")

    # Get portfolio ID from config or environment
    portfolio_id = os.getenv("BRM_PORTFOLIO_ID", config.default_portfolio_id)
    area_id = int(os.getenv("ASTRO_DELIVERY_AREA_ID", "111"))

    if not portfolio_id:
        logger.error("No portfolio ID configured - set BRM_PORTFOLIO_ID")
        return False

    # Step 3-5: Build curve orders
    orders, da_sold_mw = build_curve_orders(
        forecast=forecast,
        delivery_date=delivery_date,
        portfolio_id=portfolio_id,
        area_id=area_id,
        price=0.0  # Price-taker strategy
    )

    # Step 6: Submit orders
    results = await submit_da_orders(orders, da_sold_mw, delivery_date, dry_run=dry_run)
    logger.info(f"Submission results: {results['submitted']} submitted, "
               f"{results['failed']} failed, {results['skipped']} skipped")

    if results["errors"]:
        for error in results["errors"]:
            logger.error(f"  - {error}")

    # Step 7: Initialize position file
    if not dry_run:
        position = init_position_file(delivery_date, da_sold_mw)
        logger.info(f"Position file initialized: {POSITION_FILE}")

        # Log position summary
        total_contracted = sum(data["contracted"] for data in position["intervals"].values())
        logger.info(f"Total contracted for delivery: {total_contracted:.2f} MW across all intervals")
    else:
        logger.info("[DRY RUN] Position file not created")

    logger.info("=" * 60)
    logger.info("Day-Ahead Automation Complete")
    logger.info("=" * 60)

    return results["failed"] == 0


# ==================== CLI Entry Point ====================

def main():
    # Suppress asyncio cleanup warnings on Windows
    import warnings
    warnings.filterwarnings("ignore", message=".*Event loop is closed.*")

    parser = argparse.ArgumentParser(
        description="Day-Ahead Automation for Astro Solar Asset"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print orders without submitting"
    )
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="Delivery date (YYYY-MM-DD, default: tomorrow)"
    )
    parser.add_argument(
        "--skip-fetch",
        action="store_true",
        help="Skip fetching new forecast, use existing data"
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
    success = asyncio.run(run_da_automation(
        delivery_date=args.date,
        dry_run=args.dry_run,
        skip_fetch=args.skip_fetch
    ))

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
