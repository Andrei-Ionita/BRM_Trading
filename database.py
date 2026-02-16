"""
Database module for persistent storage of position data.
Uses PostgreSQL on Railway for persistence across deployments.
"""
import os
import json
import logging
from datetime import datetime
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)

# Database URL from Railway environment
DATABASE_URL = os.getenv("DATABASE_URL")

# Flag to track if DB is available
_db_available = None


def is_database_available() -> bool:
    """Check if database is configured and accessible."""
    global _db_available

    if _db_available is not None:
        return _db_available

    if not DATABASE_URL:
        logger.warning("DATABASE_URL not set - using file-based storage")
        _db_available = False
        return False

    try:
        import psycopg2
        conn = psycopg2.connect(DATABASE_URL)
        conn.close()
        _db_available = True
        logger.info("Database connection successful")
        return True
    except Exception as e:
        logger.warning(f"Database connection failed: {e} - using file-based storage")
        _db_available = False
        return False


def init_database():
    """Initialize database tables if they don't exist."""
    if not is_database_available():
        return False

    import psycopg2

    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()

        # Create positions table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS positions (
                id SERIAL PRIMARY KEY,
                delivery_date DATE NOT NULL UNIQUE,
                data JSONB NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create index on delivery_date
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_positions_delivery_date
            ON positions(delivery_date)
        """)

        # Create forecast_history table to track all forecast refreshes
        cur.execute("""
            CREATE TABLE IF NOT EXISTS forecast_history (
                id SERIAL PRIMARY KEY,
                delivery_date DATE NOT NULL,
                refreshed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                forecast_data JSONB NOT NULL
            )
        """)

        # Create index on delivery_date and refreshed_at
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_forecast_history_date
            ON forecast_history(delivery_date, refreshed_at DESC)
        """)

        # Create trades table to track all DA and IDM trades
        cur.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id SERIAL PRIMARY KEY,
                delivery_date DATE NOT NULL,
                interval_num INTEGER NOT NULL,
                market VARCHAR(10) NOT NULL,
                side VARCHAR(10) NOT NULL,
                quantity_mw DECIMAL(10, 4) NOT NULL,
                price_eur DECIMAL(10, 2),
                contract_id VARCHAR(100),
                order_id VARCHAR(100),
                status VARCHAR(20) DEFAULT 'executed',
                executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create index on trades for querying
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_trades_date_market
            ON trades(delivery_date, market, interval_num)
        """)

        conn.commit()
        cur.close()
        conn.close()

        logger.info("Database tables initialized")
        return True

    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        return False


def save_position_to_db(delivery_date: str, position_data: Dict[str, Any]) -> bool:
    """
    Save position data to database.

    Args:
        delivery_date: Date in YYYY-MM-DD format
        position_data: Position dictionary with intervals

    Returns:
        True if successful
    """
    if not is_database_available():
        return False

    import psycopg2
    from psycopg2.extras import Json

    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()

        # Upsert position data
        cur.execute("""
            INSERT INTO positions (delivery_date, data, updated_at)
            VALUES (%s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (delivery_date)
            DO UPDATE SET data = %s, updated_at = CURRENT_TIMESTAMP
        """, (delivery_date, Json(position_data), Json(position_data)))

        conn.commit()
        cur.close()
        conn.close()

        logger.info(f"Position saved to database for {delivery_date}")
        return True

    except Exception as e:
        logger.error(f"Failed to save position to database: {e}")
        return False


def load_position_from_db(delivery_date: str) -> Optional[Dict[str, Any]]:
    """
    Load position data from database.

    Args:
        delivery_date: Date in YYYY-MM-DD format

    Returns:
        Position dictionary or None if not found
    """
    if not is_database_available():
        return None

    import psycopg2

    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()

        cur.execute("""
            SELECT data FROM positions WHERE delivery_date = %s
        """, (delivery_date,))

        result = cur.fetchone()

        cur.close()
        conn.close()

        if result:
            logger.info(f"Position loaded from database for {delivery_date}")
            return result[0]
        else:
            logger.info(f"No position found in database for {delivery_date}")
            return None

    except Exception as e:
        logger.error(f"Failed to load position from database: {e}")
        return None


def update_position_in_db(delivery_date: str, interval: int, field: str, value: float) -> bool:
    """
    Update a specific field in position data.

    Args:
        delivery_date: Date in YYYY-MM-DD format
        interval: Interval number (1-96)
        field: Field to update (e.g., 'idm_sold', 'idm_bought')
        value: New value to add

    Returns:
        True if successful
    """
    if not is_database_available():
        return False

    import psycopg2

    try:
        # Load current position
        position = load_position_from_db(delivery_date)
        if not position:
            logger.error(f"Cannot update - no position for {delivery_date}")
            return False

        # Update the specific interval
        interval_key = str(interval)
        if interval_key not in position.get("intervals", {}):
            logger.error(f"Interval {interval} not found in position")
            return False

        # Update the field
        current_value = position["intervals"][interval_key].get(field, 0)
        position["intervals"][interval_key][field] = current_value + value

        # Recalculate contracted
        interval_data = position["intervals"][interval_key]
        interval_data["contracted"] = (
            interval_data.get("da_sold", 0) +
            interval_data.get("idm_sold", 0) -
            interval_data.get("idm_bought", 0)
        )

        # Update timestamp
        position["last_updated"] = datetime.now().isoformat()

        # Save back to database
        return save_position_to_db(delivery_date, position)

    except Exception as e:
        logger.error(f"Failed to update position in database: {e}")
        return False


def save_forecast_to_history(delivery_date: str, forecast_data: Dict[int, float]) -> bool:
    """
    Save a forecast refresh to history.

    Args:
        delivery_date: Date in YYYY-MM-DD format
        forecast_data: Dict mapping interval to forecast MW

    Returns:
        True if successful
    """
    if not is_database_available():
        return False

    import psycopg2
    from psycopg2.extras import Json

    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO forecast_history (delivery_date, forecast_data)
            VALUES (%s, %s)
        """, (delivery_date, Json(forecast_data)))

        conn.commit()
        cur.close()
        conn.close()

        logger.info(f"Forecast saved to history for {delivery_date}")
        return True

    except Exception as e:
        logger.error(f"Failed to save forecast to history: {e}")
        return False


def get_latest_forecast_from_history(delivery_date: str) -> Optional[Dict[str, Any]]:
    """
    Get the latest forecast from history.

    Args:
        delivery_date: Date in YYYY-MM-DD format

    Returns:
        Dict with forecast_data and refreshed_at, or None
    """
    if not is_database_available():
        return None

    import psycopg2

    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()

        cur.execute("""
            SELECT forecast_data, refreshed_at
            FROM forecast_history
            WHERE delivery_date = %s
            ORDER BY refreshed_at DESC
            LIMIT 1
        """, (delivery_date,))

        result = cur.fetchone()

        cur.close()
        conn.close()

        if result:
            return {
                "forecast_data": result[0],
                "refreshed_at": result[1].isoformat() if result[1] else None
            }
        return None

    except Exception as e:
        logger.error(f"Failed to get latest forecast from history: {e}")
        return None


def get_forecast_before_interval(delivery_date: str, interval: int, minutes_before: int = 30) -> Optional[float]:
    """
    Get the forecast value for an interval from a refresh that happened at least N minutes before.

    This is useful when the latest forecast shows 0 (missing data) but we need
    a valid forecast from an earlier refresh.

    Args:
        delivery_date: Date in YYYY-MM-DD format
        interval: Interval number (1-96)
        minutes_before: Minimum minutes before delivery to consider

    Returns:
        Forecast value in MW, or None if not found
    """
    if not is_database_available():
        return None

    import psycopg2
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo

    try:
        # Calculate the interval start time
        TZ_CET = ZoneInfo("Europe/Berlin")
        interval_hour = (interval - 1) // 4
        interval_minute = ((interval - 1) % 4) * 15

        delivery_dt = datetime.strptime(delivery_date, "%Y-%m-%d")
        interval_start = delivery_dt.replace(
            hour=interval_hour, minute=interval_minute, tzinfo=TZ_CET
        )

        # We want forecasts from at least N minutes before this interval
        cutoff_time = interval_start - timedelta(minutes=minutes_before)

        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()

        # Get the latest forecast that was refreshed before the cutoff
        cur.execute("""
            SELECT forecast_data
            FROM forecast_history
            WHERE delivery_date = %s AND refreshed_at <= %s
            ORDER BY refreshed_at DESC
            LIMIT 1
        """, (delivery_date, cutoff_time))

        result = cur.fetchone()

        cur.close()
        conn.close()

        if result and result[0]:
            forecast_data = result[0]
            return forecast_data.get(str(interval), 0.0)

        return None

    except Exception as e:
        logger.error(f"Failed to get forecast before interval: {e}")
        return None


def get_last_nonzero_forecast(delivery_date: str, interval: int) -> Optional[float]:
    """
    Get the last non-zero forecast value for an interval from history.

    Searches through all forecast history entries for the delivery date
    and returns the most recent non-zero value for the specified interval.

    This is useful when Solcast returns 0 for near-term intervals -
    we can fall back to the last valid forecast instead of DA forecast.

    Args:
        delivery_date: Date in YYYY-MM-DD format
        interval: Interval number (1-96)

    Returns:
        Last non-zero forecast value in MW, or None if not found
    """
    if not is_database_available():
        return None

    import psycopg2

    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()

        # Get all forecasts for this date, ordered by most recent first
        cur.execute("""
            SELECT forecast_data, refreshed_at
            FROM forecast_history
            WHERE delivery_date = %s
            ORDER BY refreshed_at DESC
        """, (delivery_date,))

        results = cur.fetchall()

        cur.close()
        conn.close()

        interval_key = str(interval)

        # Search through history for last non-zero value
        for forecast_data, refreshed_at in results:
            if forecast_data and interval_key in forecast_data:
                value = float(forecast_data[interval_key])
                if value > 0:
                    logger.info(f"Found last non-zero forecast for interval {interval}: {value:.2f} MW (from {refreshed_at})")
                    return value

        return None

    except Exception as e:
        logger.error(f"Failed to get last non-zero forecast: {e}")
        return None


def get_last_forecast_per_interval(delivery_date: str) -> Dict[int, float]:
    """
    Get the last stored forecast for every interval from history.

    Goes through all forecast history entries (newest first) and for each
    interval returns the value from the most recent entry that contains it.
    This ensures past intervals show the forecast that was active when
    IDM adjustments were made.

    Args:
        delivery_date: Date in YYYY-MM-DD format

    Returns:
        Dict mapping interval number to forecast MW value
    """
    if not is_database_available():
        return {}

    import psycopg2

    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()

        # Get all forecasts for this date, ordered by most recent first
        cur.execute("""
            SELECT forecast_data
            FROM forecast_history
            WHERE delivery_date = %s
            ORDER BY refreshed_at DESC
        """, (delivery_date,))

        results = cur.fetchall()

        cur.close()
        conn.close()

        merged = {}

        # For each history entry (newest first), fill in intervals we haven't seen yet
        for (forecast_data,) in results:
            if not forecast_data:
                continue
            for interval_str, value in forecast_data.items():
                interval_num = int(interval_str)
                if interval_num not in merged:
                    merged[interval_num] = round(float(value), 2)

        return merged

    except Exception as e:
        logger.error(f"Failed to get last forecast per interval: {e}")
        return {}


def save_trade(
    delivery_date: str,
    interval: int,
    market: str,
    side: str,
    quantity_mw: float,
    price_eur: float = None,
    contract_id: str = None,
    order_id: str = None,
    status: str = "executed"
) -> bool:
    """
    Save a trade to the database.

    Args:
        delivery_date: Date in YYYY-MM-DD format
        interval: Interval number (1-96)
        market: 'DA' or 'IDM'
        side: 'BUY' or 'SELL'
        quantity_mw: Quantity in MW
        price_eur: Price in EUR/MWh (optional)
        contract_id: Contract/instrument ID (optional)
        order_id: Order ID from exchange (optional)
        status: Trade status (default: 'executed')

    Returns:
        True if successful
    """
    if not is_database_available():
        return False

    import psycopg2

    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO trades (delivery_date, interval_num, market, side, quantity_mw, price_eur, contract_id, order_id, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (delivery_date, interval, market, side, quantity_mw, price_eur, contract_id, order_id, status))

        conn.commit()
        cur.close()
        conn.close()

        logger.info(f"Trade saved: {market} {side} {quantity_mw:.2f} MW @ {price_eur} EUR for interval {interval}")
        return True

    except Exception as e:
        logger.error(f"Failed to save trade: {e}")
        return False


def get_trades(delivery_date: str, market: str = None) -> list:
    """
    Get all trades for a delivery date.

    Args:
        delivery_date: Date in YYYY-MM-DD format
        market: Optional filter by market ('DA' or 'IDM')

    Returns:
        List of trade dictionaries
    """
    if not is_database_available():
        return []

    import psycopg2

    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()

        if market:
            cur.execute("""
                SELECT id, delivery_date, interval_num, market, side, quantity_mw, price_eur, contract_id, order_id, status, executed_at
                FROM trades
                WHERE delivery_date = %s AND market = %s
                ORDER BY interval_num, executed_at
            """, (delivery_date, market))
        else:
            cur.execute("""
                SELECT id, delivery_date, interval_num, market, side, quantity_mw, price_eur, contract_id, order_id, status, executed_at
                FROM trades
                WHERE delivery_date = %s
                ORDER BY market, interval_num, executed_at
            """, (delivery_date,))

        results = cur.fetchall()
        cur.close()
        conn.close()

        trades = []
        for row in results:
            trades.append({
                "id": row[0],
                "delivery_date": str(row[1]),
                "interval": row[2],
                "market": row[3],
                "side": row[4],
                "quantity_mw": float(row[5]),
                "price_eur": float(row[6]) if row[6] else None,
                "contract_id": row[7],
                "order_id": row[8],
                "status": row[9],
                "executed_at": row[10].isoformat() if row[10] else None
            })

        return trades

    except Exception as e:
        logger.error(f"Failed to get trades: {e}")
        return []


def get_trade_summary(delivery_date: str) -> dict:
    """
    Get trade summary statistics for a delivery date.

    Args:
        delivery_date: Date in YYYY-MM-DD format

    Returns:
        Summary dictionary with totals by market and side
    """
    if not is_database_available():
        return {}

    import psycopg2

    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()

        cur.execute("""
            SELECT market, side, SUM(quantity_mw) as total_mw, COUNT(*) as trade_count, AVG(price_eur) as avg_price
            FROM trades
            WHERE delivery_date = %s
            GROUP BY market, side
            ORDER BY market, side
        """, (delivery_date,))

        results = cur.fetchall()
        cur.close()
        conn.close()

        summary = {
            "DA": {"SELL": 0, "BUY": 0, "sell_count": 0, "buy_count": 0},
            "IDM": {"SELL": 0, "BUY": 0, "sell_count": 0, "buy_count": 0}
        }

        for row in results:
            market, side, total_mw, count, avg_price = row
            if market in summary:
                summary[market][side] = float(total_mw) if total_mw else 0
                summary[market][f"{side.lower()}_count"] = count
                summary[market][f"{side.lower()}_avg_price"] = float(avg_price) if avg_price else None

        return summary

    except Exception as e:
        logger.error(f"Failed to get trade summary: {e}")
        return {}


# Initialize database on module load
if DATABASE_URL:
    init_database()
