"""Send proactive ChangeReport events to the Alexa Event Gateway."""
import logging
import uuid
from datetime import datetime, timezone

import httpx

from alexa.models import make_power_state_property
from core.config import settings
from devices.models import Device

logger = logging.getLogger(__name__)

ALEXA_EVENT_GATEWAY_URL = "https://api.amazonalexa.com/v3/events"


async def _get_lwa_access_token() -> str | None:
    """Obtain a Login with Amazon (LWA) access token for the Alexa Event Gateway."""
    if not settings.alexa_client_id or not settings.alexa_client_secret:
        logger.debug("Alexa credentials not configured — skipping proactive report")
        return None

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            "https://api.amazon.com/auth/o2/token",
            data={
                "grant_type": "client_credentials",
                "client_id": settings.alexa_client_id,
                "client_secret": settings.alexa_client_secret,
                "scope": "alexa:event:write",
            },
        )
        if response.status_code != 200:
            logger.error("LWA token request failed: %s", response.text)
            return None
        return response.json().get("access_token")


async def send_change_report(device: Device) -> None:
    """POST a ChangeReport to the Alexa Event Gateway for the given device."""
    access_token = await _get_lwa_access_token()
    if not access_token:
        return

    payload = {
        "event": {
            "header": {
                "namespace": "Alexa",
                "name": "ChangeReport",
                "payloadVersion": "3",
                "messageId": str(uuid.uuid4()),
            },
            "endpoint": {
                "scope": {"type": "BearerToken", "token": access_token},
                "endpointId": device.id,
            },
            "payload": {
                "change": {
                    "cause": {"type": "APP_INTERACTION"},
                    "properties": [make_power_state_property(device.state)],
                }
            },
        },
        "context": {},
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            ALEXA_EVENT_GATEWAY_URL,
            json=payload,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if response.status_code in (200, 202):
            logger.info("Alexa ChangeReport sent for device %s", device.id)
        else:
            logger.error(
                "Alexa ChangeReport failed for device %s: %s %s",
                device.id,
                response.status_code,
                response.text,
            )
