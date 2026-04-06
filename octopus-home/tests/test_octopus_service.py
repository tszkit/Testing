"""Tests for Octopus price service helpers."""
import pytest
from datetime import datetime, timedelta, timezone

from core.database import async_session_factory
from octopus.models import PriceSlot
from octopus.service import get_current_price, is_cheap_now, get_cheapest_slots


async def _insert_slot(session, valid_from, valid_to, price):
    slot = PriceSlot(
        valid_from=valid_from,
        valid_to=valid_to,
        value_inc_vat=price,
        fetched_at=datetime.now(timezone.utc),
    )
    session.add(slot)
    await session.commit()
    return slot


@pytest.mark.asyncio
async def test_get_current_price_returns_none_when_no_data(db_session):
    price = await get_current_price()
    assert price is None


@pytest.mark.asyncio
async def test_get_current_price_returns_active_slot(db_session):
    now = datetime.now(timezone.utc)
    await _insert_slot(db_session, now - timedelta(minutes=15), now + timedelta(minutes=15), 12.5)

    price = await get_current_price()
    assert price == pytest.approx(12.5)


@pytest.mark.asyncio
async def test_is_cheap_now_below_threshold(db_session):
    now = datetime.now(timezone.utc)
    await _insert_slot(db_session, now - timedelta(minutes=5), now + timedelta(minutes=25), 10.0)

    result = await is_cheap_now()
    assert result is True


@pytest.mark.asyncio
async def test_is_cheap_now_above_threshold(db_session):
    now = datetime.now(timezone.utc)
    await _insert_slot(db_session, now - timedelta(minutes=5), now + timedelta(minutes=25), 30.0)

    result = await is_cheap_now()
    assert result is False


@pytest.mark.asyncio
async def test_get_cheapest_slots_returns_sorted_by_price(db_session):
    now = datetime.now(timezone.utc)
    prices = [25.0, 8.0, 15.0, 5.0, 20.0]
    for i, p in enumerate(prices):
        start = now + timedelta(minutes=30 * i)
        await _insert_slot(db_session, start, start + timedelta(minutes=30), p)

    slots = await get_cheapest_slots(n=3)
    values = [s.value_inc_vat for s in slots]
    assert values == sorted(values)
    assert len(slots) == 3
    assert values[0] == pytest.approx(5.0)
