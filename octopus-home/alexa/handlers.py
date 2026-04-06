"""Alexa Smart Home Skill directive handlers."""
import logging
import uuid

from alexa.models import AlexaRequest, make_power_state_property, make_response_header
from auth.service import get_user_id_from_token
from core.database import async_session_factory
from devices.repository import DeviceRepository
from devices.service import set_device_state
from octopus.service import get_current_price, get_cheapest_slots

logger = logging.getLogger(__name__)


async def handle_directive(request: AlexaRequest) -> dict:
    namespace = request.directive.header.namespace
    name = request.directive.header.name

    if namespace == "Alexa.Discovery" and name == "Discover":
        return await handle_discovery(request)
    elif namespace == "Alexa.PowerController":
        return await handle_power_controller(request)
    elif namespace == "Alexa" and name == "ReportState":
        return await handle_report_state(request)
    else:
        logger.warning("Unhandled directive: %s/%s", namespace, name)
        return _error_response(request, "INVALID_DIRECTIVE", f"Unsupported: {namespace}/{name}")


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

async def handle_discovery(request: AlexaRequest) -> dict:
    token = request.directive.payload.get("scope", {}).get("token", "")
    user_id = get_user_id_from_token(token) or "homeuser1"

    async with async_session_factory() as session:
        repo = DeviceRepository(session)
        devices = await repo.list_all(user_id)

    endpoints = []
    for device in devices:
        endpoints.append({
            "endpointId": device.id,
            "friendlyName": device.name,
            "description": device.description or f"Smart {device.device_type}",
            "manufacturerName": "Octopus Home",
            "displayCategories": ["SWITCH" if device.device_type == "switch" else "SMARTPLUG"],
            "cookie": {},
            "capabilities": [
                {
                    "type": "AlexaInterface",
                    "interface": "Alexa.PowerController",
                    "version": "3",
                    "properties": {
                        "supported": [{"name": "powerState"}],
                        "proactivelyReported": True,
                        "retrievable": True,
                    },
                },
                {
                    "type": "AlexaInterface",
                    "interface": "Alexa.EndpointHealth",
                    "version": "3",
                    "properties": {
                        "supported": [{"name": "connectivity"}],
                        "proactivelyReported": True,
                        "retrievable": True,
                    },
                },
                {"type": "AlexaInterface", "interface": "Alexa", "version": "3"},
            ],
        })

    return {
        "event": {
            "header": make_response_header("Discover.Response", namespace="Alexa.Discovery"),
            "payload": {"endpoints": endpoints},
        }
    }


# ---------------------------------------------------------------------------
# PowerController (TurnOn / TurnOff)
# ---------------------------------------------------------------------------

async def handle_power_controller(request: AlexaRequest) -> dict:
    name = request.directive.header.name
    correlation_token = request.directive.header.correlationToken
    endpoint_id = request.directive.endpoint.endpointId if request.directive.endpoint else None

    if not endpoint_id:
        return _error_response(request, "NO_SUCH_ENDPOINT", "Missing endpointId")

    desired_state = name == "TurnOn"
    device = await set_device_state(endpoint_id, desired_state)

    if device is None:
        return _error_response(request, "NO_SUCH_ENDPOINT", f"Device {endpoint_id} not found")

    return {
        "context": {"properties": [make_power_state_property(device.state)]},
        "event": {
            "header": make_response_header("Response", correlation_token=correlation_token),
            "endpoint": {"endpointId": endpoint_id},
            "payload": {},
        },
    }


# ---------------------------------------------------------------------------
# ReportState
# ---------------------------------------------------------------------------

async def handle_report_state(request: AlexaRequest) -> dict:
    correlation_token = request.directive.header.correlationToken
    endpoint_id = request.directive.endpoint.endpointId if request.directive.endpoint else None
    user_id = "homeuser1"

    if not endpoint_id:
        return _error_response(request, "NO_SUCH_ENDPOINT", "Missing endpointId")

    async with async_session_factory() as session:
        repo = DeviceRepository(session)
        device = await repo.get(endpoint_id, user_id)

    if device is None:
        return _error_response(request, "NO_SUCH_ENDPOINT", f"Device {endpoint_id} not found")

    return {
        "context": {"properties": [make_power_state_property(device.state)]},
        "event": {
            "header": make_response_header("StateReport", correlation_token=correlation_token),
            "endpoint": {"endpointId": endpoint_id},
            "payload": {},
        },
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _error_response(request: AlexaRequest, error_type: str, message: str) -> dict:
    correlation_token = request.directive.header.correlationToken
    endpoint_id = request.directive.endpoint.endpointId if request.directive.endpoint else "UNKNOWN"
    return {
        "event": {
            "header": make_response_header("ErrorResponse", correlation_token=correlation_token),
            "endpoint": {"endpointId": endpoint_id},
            "payload": {"type": error_type, "message": message},
        }
    }
