import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


def setup_scheduler() -> None:
    """Register all recurring jobs."""
    from octopus.service import fetch_and_store_prices
    from automation.engine import evaluate_all_rules

    # Fetch Octopus Agile prices every 30 minutes
    scheduler.add_job(
        fetch_and_store_prices,
        trigger="interval",
        minutes=30,
        id="fetch_prices",
        replace_existing=True,
        max_instances=1,
    )

    # Evaluate automation rules every 30 minutes (after price fetch)
    scheduler.add_job(
        evaluate_all_rules,
        trigger="interval",
        minutes=30,
        id="evaluate_rules",
        replace_existing=True,
        max_instances=1,
        seconds=60,  # 60s after the price fetch job starts
    )

    logger.info("Scheduler jobs registered")
