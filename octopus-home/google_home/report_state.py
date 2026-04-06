"""Send Report State notifications to the Google Home Graph API."""
import json
import logging
import time
import uuid
from pathlib import Path

import httpx

from core.config import settings
from devices.models import Device

logger = logging.getLogger(__name__)

HOME_GRAPH_API = "https://homegraph.googleapis.com/v1/devices:reportStateAndNotification"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPE = "https://www.googleapis.com/auth/homegraph"


async def _get_google_access_token() -> str | None:
    """Obtain a Google OAuth2 access token using a service account JWT."""
    sa_path = Path(settings.google_service_account_json)
    if not sa_path.exists():
        logger.debug("Google service account file not found — skipping report state")
        return None

    try:
        sa = json.loads(sa_path.read_text())
    except Exception as exc:
        logger.error("Failed to read Google service account JSON: %s", exc)
        return None

    # Build the JWT assertion
    now = int(time.time())
    claim = {
        "iss": sa["client_email"],
        "scope": SCOPE,
        "aud": TOKEN_URL,
        "iat": now,
        "exp": now + 3600,
    }

    try:
        from jose import jwt as jose_jwt
        from cryptography.hazmat.primitives.serialization import load_pem_private_key

        private_key = load_pem_private_key(sa["private_key"].encode(), password=None)
        signed = jose_jwt.encode(claim, private_key, algorithm="RS256")
    except Exception as exc:
        logger.error("Failed to sign Google service account JWT: %s", exc)
        return None

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            TOKEN_URL,
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": signed,
            },
        )
        if response.status_code != 200:
            logger.error("Google token request failed: %s", response.text)
            return None
        return response.json().get("access_token")


async def report_device_state(device: Device) -> None:
    """POST a Report State notification to Google Home Graph for the given device."""
    access_token = await _get_google_access_token()
    if not access_token:
        return

    payload = {
        "requestId": str(uuid.uuid4()),
        "agentUserId": settings.google_agent_user_id,
        "payload": {
            "devices": {
                "states": {
                    device.id: {
                        "on": device.state,
                        "online": True,
                    }
                }
            }
        },
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            HOME_GRAPH_API,
            json=payload,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if response.status_code == 200:
            logger.info("Google Report State sent for device %s", device.id)
        else:
            logger.error(
                "Google Report State failed for device %s: %s %s",
                device.id,
                response.status_code,
                response.text,
            )
