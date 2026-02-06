"""
Imbalance Manager - Shared utilities for DA and Intraday automation
Handles position storage, timezone conversion, and unit conversion for the Astro solar asset.
"""
import json
import os
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, List, Tuple
from zoneinfo import ZoneInfo

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants - use local Astro directory
POSITION_FILE_DIR = Path(__file__).parent / "Astro"
POSITION_FILE_NAME = "da_position.json"
POSITION_FILE = POSITION_FILE_DIR / POSITION_FILE_NAME

# Timezone offset: EET (UTC+2) to CET (UTC+1) = -1 hour = -4 intervals
EET_TO_CET_OFFSET = -4

# Default imbalance threshold in MW (minimum tradeable quantity is 0.1 MW)
DEFAULT_IMBALANCE_THRESHOLD_MW = 0.1

# Timezone definitions
TZ_EET = ZoneInfo("Europe/Bucharest")  # EET/EEST
TZ_CET = ZoneInfo("Europe/Berlin")     # CET/CEST


def eet_to_cet_interval(eet_interval: int) -> int:
    """
    Convert EET interval to CET interval.

    Shift by -4 intervals (1 hour earlier) with wraparound for day boundaries.

    Args:
        eet_interval: 15-min interval in EET (1-96)

    Returns:
        Corresponding interval in CET (1-96)
    """
    cet_interval = eet_interval + EET_TO_CET_OFFSET  # -4 intervals
    if cet_interval < 1:
        cet_interval += 96  # wrap to previous day
    return cet_interval


def cet_to_eet_interval(cet_interval: int) -> int:
    """
    Convert CET interval to EET interval.

    Shift by +4 intervals (1 hour later) with wraparound for day boundaries.

    Args:
        cet_interval: 15-min interval in CET (1-96)

    Returns:
        Corresponding interval in EET (1-96)
    """
    eet_interval = cet_interval - EET_TO_CET_OFFSET  # +4 intervals
    if eet_interval > 96:
        eet_interval -= 96  # wrap to next day
    return eet_interval


def mwh_to_mw(mwh_value: float) -> float:
    """
    Convert MWh (15-min energy) to MW (power).

    For 15-min intervals, MWh * 4 = MW

    Args:
        mwh_value: Energy in MWh for 15-min interval

    Returns:
        Power in MW
    """
    return mwh_value * 4


def mw_to_mwh(mw_value: float) -> float:
    """
    Convert MW (power) to MWh (15-min energy).

    For 15-min intervals, MW / 4 = MWh

    Args:
        mw_value: Power in MW

    Returns:
        Energy in MWh for 15-min interval
    """
    return mw_value / 4


def convert_for_intraday(mw_value: float, environment: str = "test") -> float:
    """
    Convert MW to the appropriate unit for intraday API.

    - Test environment: kW (multiply by 1000)
    - Production environment: MW (no conversion)

    Args:
        mw_value: Power in MW
        environment: "test" or "production"

    Returns:
        Power in appropriate unit for API
    """
    if environment == "test":
        return mw_value * 1000  # Convert to kW
    else:
        return mw_value  # Keep as MW


def convert_from_intraday(api_value: float, environment: str = "test") -> float:
    """
    Convert intraday API unit back to MW.

    - Test environment: from kW (divide by 1000)
    - Production environment: already MW (no conversion)

    Args:
        api_value: Value from API
        environment: "test" or "production"

    Returns:
        Power in MW
    """
    if environment == "test":
        return api_value / 1000  # Convert from kW to MW
    else:
        return api_value  # Already MW


def get_current_cet_interval() -> int:
    """
    Get the current 15-minute interval number in CET timezone.

    Returns:
        Current interval (1-96)
    """
    now_cet = datetime.now(TZ_CET)
    return now_cet.hour * 4 + now_cet.minute // 15 + 1


def get_current_eet_interval() -> int:
    """
    Get the current 15-minute interval number in EET timezone.

    Returns:
        Current interval (1-96)
    """
    now_eet = datetime.now(TZ_EET)
    return now_eet.hour * 4 + now_eet.minute // 15 + 1


def get_remaining_intervals(current_interval: int) -> List[int]:
    """
    Get list of remaining intervals in the day after the current one.

    Args:
        current_interval: Current interval (1-96)

    Returns:
        List of interval numbers from current+1 to 96
    """
    return list(range(current_interval + 1, 97))


def interval_to_datetime(delivery_date: str, interval: int, timezone: ZoneInfo = TZ_CET) -> datetime:
    """
    Convert delivery date and interval to datetime.

    Args:
        delivery_date: Date string in YYYY-MM-DD format
        interval: Interval number (1-96)
        timezone: Target timezone (default CET)

    Returns:
        datetime object at the start of the interval
    """
    date = datetime.strptime(delivery_date, "%Y-%m-%d")
    # Interval 1 starts at 00:00, interval 2 at 00:15, etc.
    hour = (interval - 1) // 4
    minute = ((interval - 1) % 4) * 15
    return date.replace(hour=hour, minute=minute, tzinfo=timezone)


def datetime_to_interval(dt: datetime) -> int:
    """
    Convert datetime to interval number.

    Args:
        dt: datetime object

    Returns:
        Interval number (1-96)
    """
    return dt.hour * 4 + dt.minute // 15 + 1


def get_tomorrow_date() -> str:
    """
    Get tomorrow's date in YYYY-MM-DD format.

    Returns:
        Date string for tomorrow
    """
    tomorrow = datetime.now() + timedelta(days=1)
    return tomorrow.strftime("%Y-%m-%d")


def get_today_date() -> str:
    """
    Get today's date in YYYY-MM-DD format.

    Returns:
        Date string for today
    """
    return datetime.now().strftime("%Y-%m-%d")


# ==================== Position File Management ====================

def init_position_file(delivery_date: str, da_sold_dict: Dict[int, float], da_forecast_dict: Dict[int, float] = None) -> Dict:
    """
    Initialize position file with DA sold quantities and DA forecast.

    Creates the position file with DA sold values and zeros for IDM fields.
    Uses database if available, falls back to file storage.

    Args:
        delivery_date: Delivery date in YYYY-MM-DD format
        da_sold_dict: Dict mapping interval (1-96) to DA sold MW
        da_forecast_dict: Dict mapping interval (1-96) to DA forecast MW (optional)

    Returns:
        The created position data
    """
    # If no forecast dict provided, use da_sold_dict (they should be equal at DA time)
    if da_forecast_dict is None:
        da_forecast_dict = da_sold_dict

    # Build position structure
    position = {
        "delivery_date": delivery_date,
        "intervals": {},
        "last_updated": datetime.now().isoformat()
    }

    # Initialize all 96 intervals
    # Round to 1 decimal as required by DA and IDM markets
    for interval in range(1, 97):
        da_sold = da_sold_dict.get(interval, 0.0)
        da_forecast = da_forecast_dict.get(interval, 0.0)
        position["intervals"][str(interval)] = {
            "da_sold": round(da_sold, 1),
            "da_forecast": round(da_forecast, 2),  # Store the forecast used for DA
            "idm_sold": 0.0,
            "idm_bought": 0.0,
            "contracted": round(da_sold, 1)  # Initially equals DA sold
        }

    # Try to save to database first
    try:
        from database import save_position_to_db, is_database_available
        if is_database_available():
            if save_position_to_db(delivery_date, position):
                logger.info(f"Position saved to database for {delivery_date}")
    except ImportError:
        pass

    # Also save to file as backup
    POSITION_FILE_DIR.mkdir(parents=True, exist_ok=True)
    with open(POSITION_FILE, 'w') as f:
        json.dump(position, f, indent=2)

    logger.info(f"Position file initialized for {delivery_date}")
    return position


def load_position(delivery_date: str) -> Optional[Dict]:
    """
    Load position data for a specific delivery date.

    Tries database first, then falls back to file storage.
    If file has data but database doesn't, syncs file to database.

    Args:
        delivery_date: Delivery date in YYYY-MM-DD format

    Returns:
        Position data dict or None if not found or wrong date
    """
    db_available = False
    db_has_position = False

    # Try database first
    try:
        from database import load_position_from_db, save_position_to_db, is_database_available
        db_available = is_database_available()
        if db_available:
            position = load_position_from_db(delivery_date)
            if position:
                logger.info(f"Position loaded from database for {delivery_date}")
                db_has_position = True
                return position
    except ImportError:
        pass

    # Fall back to file storage
    if not POSITION_FILE.exists():
        logger.warning(f"Position file not found: {POSITION_FILE}")
        return None

    try:
        with open(POSITION_FILE, 'r') as f:
            position = json.load(f)

        if position.get("delivery_date") != delivery_date:
            logger.warning(f"Position file is for {position.get('delivery_date')}, not {delivery_date}")
            return None

        # Sync file to database if database is available but doesn't have this position
        if db_available and not db_has_position:
            try:
                from database import save_position_to_db
                if save_position_to_db(delivery_date, position):
                    logger.info(f"Position synced from file to database for {delivery_date}")
            except Exception as e:
                logger.warning(f"Failed to sync position to database: {e}")

        return position
    except Exception as e:
        logger.error(f"Error loading position file: {e}")
        return None


def save_position(position: Dict) -> bool:
    """
    Save position data to database and file.

    Args:
        position: Position data dict

    Returns:
        True if saved successfully
    """
    position["last_updated"] = datetime.now().isoformat()
    delivery_date = position.get("delivery_date")

    success = False

    # Try to save to database first
    try:
        from database import save_position_to_db, is_database_available
        if is_database_available() and delivery_date:
            if save_position_to_db(delivery_date, position):
                success = True
                logger.info(f"Position saved to database for {delivery_date}")
    except ImportError:
        pass

    # Also save to file as backup
    try:
        POSITION_FILE_DIR.mkdir(parents=True, exist_ok=True)
        with open(POSITION_FILE, 'w') as f:
            json.dump(position, f, indent=2)
        success = True
    except Exception as e:
        logger.error(f"Error saving position file: {e}")

    return success


def update_position_after_trade(
    delivery_date: str,
    interval: int,
    side: str,
    quantity_mw: float
) -> Optional[Dict]:
    """
    Update position after an intraday trade.

    Args:
        delivery_date: Delivery date in YYYY-MM-DD format
        interval: Interval number (1-96)
        side: "BUY" or "SELL"
        quantity_mw: Traded quantity in MW

    Returns:
        Updated position data or None on error
    """
    position = load_position(delivery_date)
    if not position:
        logger.error(f"Cannot update position - file not found for {delivery_date}")
        return None

    interval_key = str(interval)
    if interval_key not in position["intervals"]:
        logger.error(f"Invalid interval: {interval}")
        return None

    interval_data = position["intervals"][interval_key]

    if side.upper() == "BUY":
        interval_data["idm_bought"] = round(interval_data["idm_bought"] + quantity_mw, 1)
    elif side.upper() == "SELL":
        interval_data["idm_sold"] = round(interval_data["idm_sold"] + quantity_mw, 1)
    else:
        logger.error(f"Invalid side: {side}")
        return None

    # Recalculate contracted
    # contracted = da_sold + idm_sold - idm_bought
    interval_data["contracted"] = round(
        interval_data["da_sold"] + interval_data["idm_sold"] - interval_data["idm_bought"],
        1
    )

    if save_position(position):
        logger.info(f"Position updated for interval {interval}: {side} {quantity_mw} MW, "
                   f"new contracted = {interval_data['contracted']} MW")
        return position
    return None


def get_contracted(delivery_date: str, interval: int) -> Optional[float]:
    """
    Get the current contracted (TSO notification) value for an interval.

    Args:
        delivery_date: Delivery date in YYYY-MM-DD format
        interval: Interval number (1-96)

    Returns:
        Contracted MW or None if not found
    """
    position = load_position(delivery_date)
    if not position:
        return None

    interval_key = str(interval)
    if interval_key not in position["intervals"]:
        return None

    return position["intervals"][interval_key]["contracted"]


def get_all_contracted(delivery_date: str) -> Optional[Dict[int, float]]:
    """
    Get contracted values for all intervals.

    Args:
        delivery_date: Delivery date in YYYY-MM-DD format

    Returns:
        Dict mapping interval to contracted MW, or None
    """
    position = load_position(delivery_date)
    if not position:
        return None

    return {
        int(k): v["contracted"]
        for k, v in position["intervals"].items()
    }


# ==================== Imbalance Calculation ====================

def calculate_imbalances(
    position: Dict,
    new_forecast: Dict[int, float],
    from_interval: int,
    threshold_mw: float = DEFAULT_IMBALANCE_THRESHOLD_MW
) -> List[Tuple[int, float, str]]:
    """
    Calculate imbalances between contracted and new forecast.

    Args:
        position: Position data with contracted values (MW)
        new_forecast: Dict mapping CET interval to new forecast (MW)
        from_interval: Start interval (inclusive)
        threshold_mw: Minimum imbalance to trade (MW)

    Returns:
        List of (interval, imbalance_mw, side) tuples where trading is needed
    """
    imbalances = []

    for interval in range(from_interval, 97):
        interval_key = str(interval)

        if interval_key not in position["intervals"]:
            continue

        contracted = position["intervals"][interval_key]["contracted"]
        forecast = new_forecast.get(interval, 0.0)

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


# ==================== Contract ID Mapping ====================

def get_contract_id_for_interval(delivery_date: str, interval: int, area_id: int = 111, contract_type: str = "QH") -> str:
    """
    Generate contract ID for a given delivery date and interval.

    BRM/NordPool Intraday contract ID formats:
    - Hourly (H): BRM_ID_H_YYYYMMDD_HH (e.g., BRM_ID_H_20260203_12)
    - Quarter-hourly (QH): BRM_ID_QH_YYYYMMDD_HH_Q (e.g., BRM_ID_QH_20260203_12_1)

    Args:
        delivery_date: Delivery date in YYYY-MM-DD format
        interval: Interval number (1-96)
        area_id: Delivery area ID (default 111 for Romania)
        contract_type: "QH" for quarter-hourly (15min) or "H" for hourly

    Returns:
        Contract ID string for BRM/NordPool IDM
    """
    # Calculate hour and quarter from interval
    hour = (interval - 1) // 4
    quarter = (interval - 1) % 4 + 1  # 1-4

    # Format date
    date_compact = delivery_date.replace("-", "")

    if contract_type == "H":
        # Hourly contract: BRM_ID_H_YYYYMMDD_HH
        return f"BRM_ID_H_{date_compact}_{hour:02d}"
    else:
        # Quarter-hourly contract: BRM_ID_QH_YYYYMMDD_HH_Q
        return f"BRM_ID_QH_{date_compact}_{hour:02d}_{quarter}"


def parse_contract_id(contract_id: str) -> Optional[Tuple[str, int]]:
    """
    Parse a contract ID to extract delivery date and interval.

    Args:
        contract_id: Contract ID string

    Returns:
        Tuple of (delivery_date, interval) or None if parsing fails
    """
    # This needs to be implemented based on actual contract ID format
    # Placeholder implementation
    try:
        parts = contract_id.split("_")
        if len(parts) >= 3:
            date_str = parts[1]
            # Parse date from YYYYMMDD format
            delivery_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"

            # Parse hour and quarter
            time_part = parts[2]
            if "Q" in time_part:
                hour = int(time_part.split("Q")[0])
                quarter = int(time_part.split("Q")[1])
                interval = hour * 4 + quarter
                return delivery_date, interval
    except Exception as e:
        logger.error(f"Error parsing contract ID {contract_id}: {e}")

    return None


# ==================== Utility Functions ====================

def format_position_summary(position: Dict) -> str:
    """
    Format position data as a summary string.

    Args:
        position: Position data dict

    Returns:
        Formatted summary string
    """
    lines = [
        f"Position Summary for {position['delivery_date']}",
        f"Last updated: {position['last_updated']}",
        "-" * 50,
        f"{'Interval':<10} {'DA Sold':>10} {'IDM Sold':>10} {'IDM Bought':>12} {'Contracted':>12}"
    ]

    for interval in range(1, 97):
        data = position["intervals"].get(str(interval), {})
        if data.get("da_sold", 0) > 0 or data.get("contracted", 0) != 0:
            lines.append(
                f"{interval:<10} {data.get('da_sold', 0):>10.1f} "
                f"{data.get('idm_sold', 0):>10.1f} {data.get('idm_bought', 0):>12.1f} "
                f"{data.get('contracted', 0):>12.1f}"
            )

    return "\n".join(lines)


def get_minutes_until_interval(delivery_date: str, interval: int) -> float:
    """
    Calculate minutes until a specific interval starts.

    Args:
        delivery_date: Delivery date in YYYY-MM-DD format
        interval: Target interval (1-96)

    Returns:
        Minutes until interval starts (negative if already passed)
    """
    interval_start = interval_to_datetime(delivery_date, interval, TZ_CET)
    now = datetime.now(TZ_CET)
    delta = interval_start - now
    return delta.total_seconds() / 60


def is_market_open_for_interval(delivery_date: str, interval: int, gate_closure_minutes: int = 5) -> bool:
    """
    Check if the intraday market is still open for a specific interval.

    Args:
        delivery_date: Delivery date in YYYY-MM-DD format
        interval: Target interval (1-96)
        gate_closure_minutes: Minutes before delivery when market closes (default 5)

    Returns:
        True if market is still open for trading this interval
    """
    minutes_until = get_minutes_until_interval(delivery_date, interval)
    return minutes_until > gate_closure_minutes


if __name__ == "__main__":
    # Test the utilities
    print("Testing Imbalance Manager utilities...")

    # Test timezone conversion
    print(f"\nTimezone conversion test:")
    print(f"EET interval 49 (12:00 EET) -> CET interval {eet_to_cet_interval(49)} (should be 45)")
    print(f"EET interval 1 (00:00 EET) -> CET interval {eet_to_cet_interval(1)} (should be 93)")
    print(f"CET interval 45 -> EET interval {cet_to_eet_interval(45)} (should be 49)")

    # Test unit conversion
    print(f"\nUnit conversion test:")
    print(f"1 MWh -> {mwh_to_mw(1)} MW")
    print(f"1 MW -> {mw_to_mwh(1)} MWh")
    print(f"1 MW in test env -> {convert_for_intraday(1, 'test')} kW")
    print(f"1 MW in prod env -> {convert_for_intraday(1, 'production')} MW")

    # Test interval utilities
    print(f"\nInterval utilities:")
    print(f"Current CET interval: {get_current_cet_interval()}")
    print(f"Current EET interval: {get_current_eet_interval()}")
    print(f"Tomorrow's date: {get_tomorrow_date()}")
    print(f"Today's date: {get_today_date()}")

    # Test position file
    print(f"\nPosition file test:")
    test_date = get_tomorrow_date()
    test_da_sold = {i: 0.5 if 25 <= i <= 72 else 0.0 for i in range(1, 97)}

    position = init_position_file(test_date, test_da_sold)
    print(f"Created position file for {test_date}")

    loaded = load_position(test_date)
    if loaded:
        print(f"Loaded position file successfully")
        print(f"Contracted for interval 49: {get_contracted(test_date, 49)} MW")

    print("\nImbalance Manager utilities test complete!")
