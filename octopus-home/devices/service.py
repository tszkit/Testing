"""Central device state management with fan-out to Alexa and Google Home."""
import logging

from core.database import async_session_factory
from devices.repository import DeviceRepository
from devices.models import Device

logger = logging.getLogger(__name__)


async def set_device_state(device_id: str, state: bool) -> Device | None:
    """Update device state in DB and fan out to Alexa + Google Home."""
    async with async_session_factory() as session:
        repo = DeviceRepository(session)
        device = await repo.update_state(device_id, state)

    if device is None:
        logger.warning("set_device_state: device %s not found", device_id)
        return None

    logger.info("Device %s (%s) set to %s", device.name, device_id, "ON" if state else "OFF")

    # Fan out state change to both platforms (best-effort, errors are logged not raised)
    await _notify_alexa(device)
    await _notify_google(device)

    return device


async def _notify_alexa(device: Device) -> None:
    try:
        from alexa.proactive import send_change_report
        await send_change_report(device)
    except Exception as exc:
        logger.error("Alexa proactive report failed for device %s: %s", device.id, exc)


async def _notify_google(device: Device) -> None:
    try:
        from google_home.report_state import report_device_state
        await report_device_state(device)
    except Exception as exc:
        logger.error("Google report state failed for device %s: %s", device.id, exc)
