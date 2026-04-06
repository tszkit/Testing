"""Automation rule engine: evaluates price-based rules and triggers device state changes."""
import logging

from core.database import async_session_factory
from devices.repository import AutomationRuleRepository, DeviceRepository
from devices.service import set_device_state
from octopus.service import get_current_price

logger = logging.getLogger(__name__)


async def evaluate_all_rules() -> None:
    """Fetch current price and evaluate every enabled automation rule.

    Called every 30 minutes by the scheduler.
    """
    price = await get_current_price()
    if price is None:
        logger.warning("No current price available — skipping automation evaluation")
        return

    logger.info("Evaluating automation rules at %.2fp/kWh", price)

    async with async_session_factory() as session:
        rule_repo = AutomationRuleRepository(session)
        device_repo = DeviceRepository(session)
        rules = await rule_repo.list_enabled()

    for rule in rules:
        async with async_session_factory() as session:
            device_repo = DeviceRepository(session)
            # Fetch device without user scope — rules are system-level
            from sqlalchemy import select
            from devices.models import Device
            result = await session.execute(select(Device).where(Device.id == rule.device_id))
            device = result.scalar_one_or_none()

        if device is None:
            logger.warning("Rule %d references missing device %s", rule.id, rule.device_id)
            continue

        is_cheap = price <= rule.price_threshold_pence

        if rule.action_below_threshold == "on":
            # Turn on when cheap, off when expensive
            desired_state = is_cheap
        else:
            # Turn off when cheap (e.g. stop export / pause charging)
            desired_state = not is_cheap

        if device.state != desired_state:
            logger.info(
                "Rule %d: %s → %s (price=%.2fp, threshold=%.2fp)",
                rule.id,
                device.name,
                "ON" if desired_state else "OFF",
                price,
                rule.price_threshold_pence,
            )
            await set_device_state(rule.device_id, desired_state)
        else:
            logger.debug(
                "Rule %d: %s already %s — no change",
                rule.id,
                device.name,
                "ON" if device.state else "OFF",
            )
