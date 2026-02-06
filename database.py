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


# Initialize database on module load
if DATABASE_URL:
    init_database()
