"""Tests for the automation rule engine."""
from datetime import datetime, timedelta, timezone

import pytest

from core.database import async_session_factory
from devices.repository import AutomationRuleRepository, DeviceRepository
from octopus.models import PriceSlot
from automation.engine import evaluate_all_rules


@pytest.mark.asyncio
async def test_automation_turns_device_on_when_cheap(db_session):
    # Insert a cheap price slot covering now
    now = datetime.now(timezone.utc)
    db_session.add(
        PriceSlot(
            valid_from=now - timedelta(minutes=5),
            valid_to=now + timedelta(minutes=25),
            value_inc_vat=8.0,  # below default threshold of 15p
            fetched_at=now,
        )
    )
    await db_session.commit()

    # Create a device and automation rule
    device_repo = DeviceRepository(db_session)
    device = await device_repo.create("Dishwasher", "", "outlet", "homeuser1")
    assert device.state is False

    rule_repo = AutomationRuleRepository(db_session)
    await rule_repo.create(device.id, 15.0, "on", "homeuser1")

    # Run the engine
    await evaluate_all_rules()

    # Device should now be on
    async with async_session_factory() as s:
        updated = await DeviceRepository(s).get(device.id, "homeuser1")
    assert updated.state is True


@pytest.mark.asyncio
async def test_automation_turns_device_off_when_expensive(db_session):
    now = datetime.now(timezone.utc)
    db_session.add(
        PriceSlot(
            valid_from=now - timedelta(minutes=5),
            valid_to=now + timedelta(minutes=25),
            value_inc_vat=35.0,  # above threshold
            fetched_at=now,
        )
    )
    await db_session.commit()

    device_repo = DeviceRepository(db_session)
    device = await device_repo.create("Boiler", "", "switch", "homeuser1")
    # Manually set device to ON
    await device_repo.update_state(device.id, True)

    rule_repo = AutomationRuleRepository(db_session)
    await rule_repo.create(device.id, 15.0, "on", "homeuser1")

    await evaluate_all_rules()

    async with async_session_factory() as s:
        updated = await DeviceRepository(s).get(device.id, "homeuser1")
    assert updated.state is False


@pytest.mark.asyncio
async def test_automation_no_change_when_already_correct(db_session):
    now = datetime.now(timezone.utc)
    db_session.add(
        PriceSlot(
            valid_from=now - timedelta(minutes=5),
            valid_to=now + timedelta(minutes=25),
            value_inc_vat=10.0,
            fetched_at=now,
        )
    )
    await db_session.commit()

    device_repo = DeviceRepository(db_session)
    device = await device_repo.create("Heat Pump", "", "switch", "homeuser1")
    # Already ON (matches what the rule would set)
    await device_repo.update_state(device.id, True)

    rule_repo = AutomationRuleRepository(db_session)
    await rule_repo.create(device.id, 15.0, "on", "homeuser1")

    # Should run without errors and leave device ON
    await evaluate_all_rules()

    async with async_session_factory() as s:
        updated = await DeviceRepository(s).get(device.id, "homeuser1")
    assert updated.state is True
