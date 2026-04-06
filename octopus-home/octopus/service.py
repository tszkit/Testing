"""Price fetching, caching, and analysis."""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select

from core.config import settings
from core.database import async_session_factory
from octopus.client import OctopusClient, parse_dt
from octopus.models import PriceSlot

logger = logging.getLogger(__name__)


async def fetch_and_store_prices() -> None:
    """Fetch next 48 hours of Agile prices and upsert into the DB.

    Called on startup and every 30 minutes by the scheduler.
    """
    now = datetime.now(timezone.utc)
    period_from = now
    period_to = now + timedelta(hours=48)

    async with OctopusClient() as client:
        try:
            slots = await client.get_agile_unit_rates(period_from=period_from, period_to=period_to)
        except Exception as exc:
            logger.error("Failed to fetch Octopus prices: %s", exc)
            return

    async with async_session_factory() as session:
        # Delete existing future slots to avoid duplicates
        await session.execute(
            delete(PriceSlot).where(PriceSlot.valid_from >= now)
        )
        fetched_at = datetime.now(timezone.utc)
        for slot in slots:
            session.add(
                PriceSlot(
                    valid_from=parse_dt(slot["valid_from"]),
                    valid_to=parse_dt(slot["valid_to"]),
                    value_inc_vat=slot["value_inc_vat"],
                    fetched_at=fetched_at,
                )
            )
        await session.commit()
        logger.info("Stored %d price slots", len(slots))


async def get_current_price() -> float | None:
    """Return the current price in pence/kWh, or None if unavailable."""
    now = datetime.now(timezone.utc)
    async with async_session_factory() as session:
        result = await session.execute(
            select(PriceSlot)
            .where(PriceSlot.valid_from <= now, PriceSlot.valid_to > now)
            .limit(1)
        )
        slot = result.scalar_one_or_none()
        return slot.value_inc_vat if slot else None


async def is_cheap_now() -> bool:
    """Return True if the current price is below the configured threshold."""
    price = await get_current_price()
    if price is None:
        return False
    return price <= settings.price_cheap_threshold_pence


async def get_cheapest_slots(n: int = 3, hours_ahead: int = 24) -> list[PriceSlot]:
    """Return the n cheapest half-hour slots in the next `hours_ahead` hours."""
    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(hours=hours_ahead)
    async with async_session_factory() as session:
        result = await session.execute(
            select(PriceSlot)
            .where(PriceSlot.valid_from >= now, PriceSlot.valid_from < cutoff)
            .order_by(PriceSlot.value_inc_vat)
            .limit(n)
        )
        return list(result.scalars().all())


async def get_upcoming_prices(hours_ahead: int = 24) -> list[PriceSlot]:
    """Return all slots for the next `hours_ahead` hours, sorted by time."""
    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(hours=hours_ahead)
    async with async_session_factory() as session:
        result = await session.execute(
            select(PriceSlot)
            .where(PriceSlot.valid_from >= now, PriceSlot.valid_from < cutoff)
            .order_by(PriceSlot.valid_from)
        )
        return list(result.scalars().all())
