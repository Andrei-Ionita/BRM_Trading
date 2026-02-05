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


# Initialize database on module load
if DATABASE_URL:
    init_database()
