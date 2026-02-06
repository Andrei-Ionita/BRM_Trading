"""
Trading Scheduler for Railway Cloud Deployment
Handles both DA and IDM automation with proper timing.

Usage:
    python scheduler.py [--da-only] [--idm-only]
"""
import asyncio
import logging
import os
import sys
import signal
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from imbalance_manager import TZ_CET, get_today_date, get_tomorrow_date

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Scheduling configuration
# DA gate closes at 13:00 EET (12:00 CET) for next day delivery
# Run DA at 12:00 EET (11:00 CET) - 1 hour buffer before gate closure
DA_RUN_HOUR = 11  # 11:00 CET = 12:00 EET (Romania time)
DA_RUN_MINUTE = 0
IDM_INTERVAL_MINUTES = 30  # Run IDM every 30 minutes - gives buffer for Solcast data availability

# Global shutdown flag
shutdown_requested = False


def handle_shutdown(signum, frame):
    """Handle shutdown signals gracefully."""
    global shutdown_requested
    logger.info(f"Shutdown requested (signal {signum})")
    shutdown_requested = True


signal.signal(signal.SIGINT, handle_shutdown)
signal.signal(signal.SIGTERM, handle_shutdown)


async def run_da_automation():
    """Run Day-Ahead automation."""
    logger.info("=" * 60)
    logger.info("Running Day-Ahead Automation")
    logger.info("=" * 60)

    try:
        from day_ahead_automation import run_da_automation as da_run
        success = await da_run(dry_run=False)
        logger.info(f"DA automation completed: {'SUCCESS' if success else 'FAILED'}")
        return success
    except Exception as e:
        logger.error(f"DA automation error: {e}")
        return False


async def run_idm_iteration():
    """Run one iteration of Intraday automation."""
    logger.info("-" * 40)
    logger.info("Running Intraday Iteration")
    logger.info("-" * 40)

    try:
        from intraday_automation import run_intraday_automation as idm_run
        success = await idm_run(
            delivery_date=get_today_date(),
            dry_run=False,
            single_run=True
        )
        logger.info(f"IDM iteration completed: {'SUCCESS' if success else 'FAILED'}")
        return success
    except Exception as e:
        logger.error(f"IDM iteration error: {e}")
        return False


def should_run_da(now: datetime, last_da_run: datetime = None) -> bool:
    """Check if DA automation should run now."""
    # Run DA at scheduled time if not already run today
    if now.hour == DA_RUN_HOUR and now.minute < DA_RUN_MINUTE + 5:
        if last_da_run is None or last_da_run.date() < now.date():
            return True
    return False


def get_next_idm_run(now: datetime) -> datetime:
    """Calculate next IDM run time (aligned to 15-minute intervals)."""
    minutes = (now.minute // IDM_INTERVAL_MINUTES + 1) * IDM_INTERVAL_MINUTES
    if minutes >= 60:
        next_run = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    else:
        next_run = now.replace(minute=minutes, second=0, microsecond=0)
    return next_run


async def main_scheduler(run_da: bool = True, run_idm: bool = True):
    """
    Main scheduler loop.

    Args:
        run_da: Enable DA automation
        run_idm: Enable IDM automation
    """
    global shutdown_requested

    logger.info("=" * 60)
    logger.info("BRM Trading Scheduler Started")
    logger.info(f"  DA automation: {'ENABLED' if run_da else 'DISABLED'}")
    logger.info(f"  IDM automation: {'ENABLED' if run_idm else 'DISABLED'}")
    logger.info(f"  DA scheduled time: {DA_RUN_HOUR:02d}:{DA_RUN_MINUTE:02d} CET")
    logger.info(f"  IDM interval: {IDM_INTERVAL_MINUTES} minutes")
    logger.info("=" * 60)

    last_da_run = None

    while not shutdown_requested:
        now = datetime.now(TZ_CET)
        logger.info(f"Scheduler tick at {now.strftime('%Y-%m-%d %H:%M:%S')} CET")

        # Check DA
        if run_da and should_run_da(now, last_da_run):
            logger.info("DA run triggered")
            await run_da_automation()
            last_da_run = now

        # Check IDM (only run during delivery day, intervals 1-96)
        if run_idm:
            # IDM runs for today's delivery
            current_hour = now.hour
            current_minute = now.minute

            # Check if we're in a valid delivery window (00:00 - 23:59)
            # and if it's time for an IDM check (every 15 min)
            if current_minute % IDM_INTERVAL_MINUTES == 0:
                await run_idm_iteration()

        # Sleep until next check (every minute)
        await asyncio.sleep(60)

    logger.info("Scheduler shutdown complete")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="BRM Trading Scheduler")
    parser.add_argument("--da-only", action="store_true", help="Run DA automation only")
    parser.add_argument("--idm-only", action="store_true", help="Run IDM automation only")
    args = parser.parse_args()

    run_da = not args.idm_only
    run_idm = not args.da_only

    asyncio.run(main_scheduler(run_da=run_da, run_idm=run_idm))


if __name__ == "__main__":
    main()
