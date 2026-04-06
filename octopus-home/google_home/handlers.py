"""Google Home Cloud-to-Cloud fulfillment intent handlers (SYNC, QUERY, EXECUTE)."""
import logging

from auth.service import get_user_id_from_token
from core.database import async_session_factory
from devices.repository import DeviceRepository
from devices.service import set_device_state
from google_home.models import GoogleRequest

logger = logging.getLogger(__name__)


async def handle_fulfillment(request: GoogleRequest, bearer_token: str) -> dict:
    user_id = get_user_id_from_token(bearer_token) or "homeuser1"
    responses = []

    for inp in request.inputs:
        intent = inp.intent
        if intent == "action.devices.SYNC":
            responses.append(await handle_sync(request.requestId, user_id))
        elif intent == "action.devices.QUERY":
            responses.append(await handle_query(request.requestId, inp.payload, user_id))
        elif intent == "action.devices.EXECUTE":
            responses.append(await handle_execute(request.requestId, inp.payload, user_id))
        elif intent == "action.devices.DISCONNECT":
            responses.append({"requestId": request.requestId, "payload": {}})
        else:
            logger.warning("Unknown Google intent: %s", intent)

    # Google expects a single response object (the last input's response)
    return responses[-1] if responses else {"requestId": request.requestId, "payload": {}}


# ---------------------------------------------------------------------------
# SYNC — return device list
# ---------------------------------------------------------------------------

async def handle_sync(request_id: str, user_id: str) -> dict:
    async with async_session_factory() as session:
        repo = DeviceRepository(session)
        devices = await repo.list_all(user_id)

    google_devices = []
    for device in devices:
        google_devices.append({
            "id": device.id,
            "type": "action.devices.types.OUTLET" if device.device_type == "outlet" else "action.devices.types.SWITCH",
            "traits": ["action.devices.traits.OnOff"],
            "name": {
                "defaultNames": [device.name],
                "name": device.name,
                "nicknames": [device.name],
            },
            "willReportState": True,
            "attributes": {"commandOnlyOnOff": False},
            "deviceInfo": {
                "manufacturer": "Octopus Home",
                "model": device.device_type,
            },
            "otherDeviceIds": [{"deviceId": device.id}],
        })

    return {
        "requestId": request_id,
        "payload": {
            "agentUserId": user_id,
            "devices": google_devices,
        },
    }


# ---------------------------------------------------------------------------
# QUERY — return current state
# ---------------------------------------------------------------------------

async def handle_query(request_id: str, payload: dict, user_id: str) -> dict:
    device_ids = [d["id"] for d in payload.get("devices", [])]

    async with async_session_factory() as session:
        repo = DeviceRepository(session)
        states: dict[str, dict] = {}
        for device_id in device_ids:
            device = await repo.get(device_id, user_id)
            if device:
                states[device_id] = {"on": device.state, "online": True, "status": "SUCCESS"}
            else:
                states[device_id] = {"status": "ERROR", "errorCode": "deviceNotFound"}

    return {
        "requestId": request_id,
        "payload": {"devices": states},
    }


# ---------------------------------------------------------------------------
# EXECUTE — apply commands
# ---------------------------------------------------------------------------

async def handle_execute(request_id: str, payload: dict, user_id: str) -> dict:
    results = []

    for command_block in payload.get("commands", []):
        device_ids = [d["id"] for d in command_block.get("devices", [])]
        for cmd in command_block.get("execution", []):
            cmd_name = cmd.get("command", "")
            params = cmd.get("params", {})

            if cmd_name == "action.devices.commands.OnOff":
                desired_state: bool = params.get("on", False)
                succeeded = []
                failed = []
                for device_id in device_ids:
                    device = await set_device_state(device_id, desired_state)
                    if device:
                        succeeded.append(device_id)
                    else:
                        failed.append(device_id)

                if succeeded:
                    results.append({
                        "ids": succeeded,
                        "status": "SUCCESS",
                        "states": {"on": desired_state, "online": True},
                    })
                if failed:
                    results.append({
                        "ids": failed,
                        "status": "ERROR",
                        "errorCode": "deviceNotFound",
                    })
            else:
                results.append({
                    "ids": device_ids,
                    "status": "ERROR",
                    "errorCode": "notSupported",
                })

    return {
        "requestId": request_id,
        "payload": {"commands": results},
    }
