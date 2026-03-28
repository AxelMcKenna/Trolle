from __future__ import annotations

import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

HEARTBEAT_FILE = Path("/tmp/worker-heartbeat")

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.scrapers.registry import CHAINS, get_chain_scraper
from app.services.alerting import send_alert

configure_logging()
logger = logging.getLogger(__name__)


# Configuration
SCRAPER_TIMEOUT_MINUTES = 240  # Max time per scraper (grocery catalogs are large)
SEQUENTIAL_DELAY_SECONDS = 60  # Delay between scrapers to avoid overwhelming system
SCRAPER_RETRY_DELAY_SECONDS = 300  # Wait 5 min before retrying a failed scraper
SCHEDULE_HOUR = 2  # Run scrapers at 2:00 AM
SCHEDULE_TZ = ZoneInfo("Pacific/Auckland")  # NZST/NZDT
CHECK_INTERVAL_SECONDS = 60  # How often to check if it's time to run


def _seconds_until_next_run() -> float:
    """Return seconds until the next 2:00 AM NZST."""
    now = datetime.now(SCHEDULE_TZ)
    target = now.replace(hour=SCHEDULE_HOUR, minute=0, second=0, microsecond=0)
    if now >= target:
        target += timedelta(days=1)
    return (target - now).total_seconds()


class WorkerScheduler:
    """Manages scraper scheduling and execution with proper error handling."""

    def __init__(self, chains_to_run: Optional[List[str]] = None):
        self.chains_to_run = chains_to_run or list(CHAINS.keys())
        self.last_run: Dict[str, Optional[datetime]] = {chain: None for chain in self.chains_to_run}
        self.running_chains: Dict[str, asyncio.Task] = {}

    async def run_scraper(self, chain: str) -> None:
        """Run a single scraper with timeout, retry, and alerting."""
        logger.info(f"Starting scraper: {chain}")
        start_time = datetime.utcnow()
        last_error: Optional[str] = None

        for attempt in range(1, 3):  # max 2 attempts (1 retry)
            try:
                scraper = get_chain_scraper(chain)

                # Run with timeout
                await asyncio.wait_for(
                    scraper.run(),
                    timeout=SCRAPER_TIMEOUT_MINUTES * 60
                )

                duration = (datetime.utcnow() - start_time).total_seconds()
                logger.info(f"Scraper completed: {chain} ({duration:.1f}s)")
                self.last_run[chain] = datetime.utcnow()

                # Check price alerts after successful scrape
                try:
                    from app.services.price_alerts import check_triggered_alerts
                    from app.db.session import async_transaction
                    async with async_transaction() as alert_session:
                        triggered = await check_triggered_alerts(alert_session)
                    if triggered:
                        logger.info(f"Triggered {triggered} price alert(s) after {chain} scrape")
                except Exception as alert_err:
                    logger.warning(f"Price alert check failed: {alert_err}")

                return  # success

            except asyncio.TimeoutError:
                duration = (datetime.utcnow() - start_time).total_seconds()
                last_error = f"Timeout after {duration:.0f}s (limit={SCRAPER_TIMEOUT_MINUTES}m)"
                logger.error(f"Scraper timeout: {chain} — {last_error}")

            except Exception as e:
                duration = (datetime.utcnow() - start_time).total_seconds()
                last_error = f"{type(e).__name__}: {e}"
                logger.error(f"Scraper failed: {chain} ({duration:.1f}s) - {last_error}")
                logger.exception(e)

            if attempt < 2:
                logger.info(f"Retrying {chain} in {SCRAPER_RETRY_DELAY_SECONDS}s...")
                await asyncio.sleep(SCRAPER_RETRY_DELAY_SECONDS)
                start_time = datetime.utcnow()  # reset for retry timing

        # Both attempts failed — fire alert
        duration = (datetime.utcnow() - start_time).total_seconds()
        await send_alert(
            title=f"Scraper failed: {chain}",
            message=last_error or "Unknown error after retries",
            severity="error",
            chain=chain,
            duration_seconds=duration,
        )

        # Remove from running tasks
        if chain in self.running_chains:
            del self.running_chains[chain]

    async def should_run_scraper(self, chain: str) -> bool:
        """Check if a scraper should run based on schedule."""
        if chain in self.running_chains:
            return False  # Already running

        last_run = self.last_run.get(chain)
        if last_run is None:
            return True  # Never run before

        # Check if enough time has passed (at least 20 hours to prevent double-runs)
        time_since_last_run = datetime.utcnow() - last_run
        return time_since_last_run >= timedelta(hours=20)

    async def run_all_scrapers(self, force: bool = False, parallel: bool = False) -> None:
        """Run all scrapers, either sequentially or in parallel."""
        logger.info(f"Checking {len(self.chains_to_run)} scrapers for scheduled runs")

        chains_to_run = []
        for chain in self.chains_to_run:
            if force or await self.should_run_scraper(chain):
                chains_to_run.append(chain)
            else:
                last_run = self.last_run.get(chain)
                if last_run:
                    time_since = datetime.utcnow() - last_run
                    logger.info(f"Skipping {chain} (last run {time_since.total_seconds() / 3600:.1f}h ago)")

        if not chains_to_run:
            return

        if parallel:
            logger.info(f"Running {len(chains_to_run)} scrapers in PARALLEL: {', '.join(chains_to_run)}")
            tasks = []
            for chain in chains_to_run:
                task = asyncio.create_task(self.run_scraper(chain))
                self.running_chains[chain] = task
                tasks.append(task)
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for chain, result in zip(chains_to_run, results):
                if isinstance(result, Exception):
                    logger.error(f"Scraper failed for chain={chain}: {result}")
        else:
            for chain in chains_to_run:
                task = asyncio.create_task(self.run_scraper(chain))
                self.running_chains[chain] = task

                try:
                    await task
                except Exception as e:
                    logger.error(f"Scraper failed for chain={chain}: {e}")

                logger.info(f"Waiting {SEQUENTIAL_DELAY_SECONDS}s before next scraper...")
                await asyncio.sleep(SEQUENTIAL_DELAY_SECONDS)


async def _check_stale_chains(scheduler: WorkerScheduler) -> None:
    """Alert if any chain hasn't had a successful run within the stale threshold."""
    settings = get_settings()
    threshold = timedelta(hours=settings.stale_threshold_hours)
    now = datetime.utcnow()

    stale_chains = []
    for chain in scheduler.chains_to_run:
        last_run = scheduler.last_run.get(chain)
        if last_run is None or (now - last_run) > threshold:
            stale_chains.append(chain)

    if stale_chains:
        hours = settings.stale_threshold_hours
        logger.warning(f"Stale chains (no success in >{hours}h): {', '.join(stale_chains)}")
        await send_alert(
            title="Stale data detected",
            message=f"Chains with no successful scrape in >{hours}h: {', '.join(stale_chains)}",
            severity="warning",
        )


async def main(chains_to_run: Optional[List[str]] = None) -> None:
    """Main worker loop — runs scrapers daily at 2:00 AM NZST."""
    # Parse flags from command line args
    parallel = "--parallel" in sys.argv or os.environ.get("TROLLE_PARALLEL", "true").lower() in ("1", "true")
    force_now = "--now" in sys.argv  # Allow one-off immediate run via --now flag
    args = [a for a in sys.argv[1:] if a not in ("--parallel", "--now")]

    # Parse chains from command line args or env var if not provided
    if chains_to_run is None:
        # Check environment variable
        env_chains = os.environ.get("TROLLE_CHAINS")
        if env_chains:
            chains_to_run = [c.strip() for c in env_chains.split(",")]
        # Check command line args
        elif args:
            chains_to_run = args[0].split(",")

    logger.info("=" * 60)
    logger.info("Starting Troll-E Worker")
    logger.info("=" * 60)

    if chains_to_run:
        # Validate chains
        invalid_chains = [c for c in chains_to_run if c not in CHAINS]
        if invalid_chains:
            logger.error(f"Invalid chains: {', '.join(invalid_chains)}")
            logger.error(f"Available chains: {', '.join(CHAINS.keys())}")
            sys.exit(1)
        logger.info(f"Running specific chains: {', '.join(chains_to_run)}")
    else:
        chains_to_run = list(CHAINS.keys())
        logger.info(f"Running all chains: {', '.join(chains_to_run)}")

    logger.info(f"Schedule: daily at {SCHEDULE_HOUR}:00 {SCHEDULE_TZ}")
    logger.info(f"Timeout: {SCRAPER_TIMEOUT_MINUTES}m per scraper")
    logger.info(f"Parallel: {parallel}")
    logger.info("=" * 60)

    scheduler = WorkerScheduler(chains_to_run=chains_to_run)

    # If --now flag passed, run immediately (for manual triggers / first deploy)
    if force_now:
        logger.info("--now flag set, running immediate scraper pass...")
        await scheduler.run_all_scrapers(force=True, parallel=parallel)

    HEARTBEAT_FILE.write_text(datetime.utcnow().isoformat())

    # Main loop — sleep until 2am NZST, then run scrapers
    while True:
        wait_seconds = _seconds_until_next_run()
        next_run = datetime.now(SCHEDULE_TZ) + timedelta(seconds=wait_seconds)
        logger.info(f"Next scrape at {next_run.strftime('%Y-%m-%d %H:%M %Z')} ({wait_seconds / 3600:.1f}h from now)")

        # Sleep in chunks so heartbeat stays fresh and we can run cleanup
        while wait_seconds > 0:
            sleep_chunk = min(wait_seconds, 3600)  # Wake every hour for housekeeping
            await asyncio.sleep(sleep_chunk)
            wait_seconds -= sleep_chunk
            HEARTBEAT_FILE.write_text(datetime.utcnow().isoformat())

            # Hourly housekeeping while waiting
            try:
                from app.workers.cleanup import run_promo_expiry_cleanup
                await run_promo_expiry_cleanup()
            except Exception as e:
                logger.warning(f"Promo expiry cleanup failed: {e}")

            await _check_stale_chains(scheduler)

        # It's 2am — run all scrapers
        logger.info(f"Schedule triggered at {datetime.now(SCHEDULE_TZ).strftime('%H:%M %Z')} — running scrapers")
        await scheduler.run_all_scrapers(force=True, parallel=parallel)
        HEARTBEAT_FILE.write_text(datetime.utcnow().isoformat())


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Worker stopped by user")
    except Exception as e:
        logger.error(f"Worker crashed: {e}")
        logger.exception(e)
        raise
