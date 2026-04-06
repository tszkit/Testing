"""Tests for the Alexa Smart Home Skill endpoint."""
import uuid

import pytest


def _discovery_directive() -> dict:
    return {
        "directive": {
            "header": {
                "namespace": "Alexa.Discovery",
                "name": "Discover",
                "payloadVersion": "3",
                "messageId": str(uuid.uuid4()),
            },
            "payload": {
                "scope": {"type": "BearerToken", "token": "fake-token"}
            },
        }
    }


def _turn_on_directive(endpoint_id: str) -> dict:
    return {
        "directive": {
            "header": {
                "namespace": "Alexa.PowerController",
                "name": "TurnOn",
                "payloadVersion": "3",
                "messageId": str(uuid.uuid4()),
                "correlationToken": "correlation-token-123",
            },
            "endpoint": {"endpointId": endpoint_id, "cookie": {}},
            "payload": {},
        }
    }


def _report_state_directive(endpoint_id: str) -> dict:
    return {
        "directive": {
            "header": {
                "namespace": "Alexa",
                "name": "ReportState",
                "payloadVersion": "3",
                "messageId": str(uuid.uuid4()),
                "correlationToken": "correlation-token-456",
            },
            "endpoint": {
                "endpointId": endpoint_id,
                "scope": {"type": "BearerToken", "token": "fake-token"},
                "cookie": {},
            },
            "payload": {},
        }
    }


@pytest.mark.asyncio
async def test_alexa_discovery_no_devices(client):
    response = await client.post("/alexa/skill", json=_discovery_directive())
    assert response.status_code == 200
    data = response.json()
    assert data["event"]["header"]["name"] == "Discover.Response"
    assert data["event"]["payload"]["endpoints"] == []


@pytest.mark.asyncio
async def test_alexa_discovery_with_device(client):
    await client.post("/devices", json={"name": "Smart Plug", "device_type": "outlet"})

    response = await client.post("/alexa/skill", json=_discovery_directive())
    data = response.json()
    endpoints = data["event"]["payload"]["endpoints"]
    assert len(endpoints) == 1
    assert endpoints[0]["friendlyName"] == "Smart Plug"


@pytest.mark.asyncio
async def test_alexa_turn_on_device(client):
    create_resp = await client.post("/devices", json={"name": "Washing Machine"})
    device_id = create_resp.json()["id"]

    response = await client.post("/alexa/skill", json=_turn_on_directive(device_id))
    assert response.status_code == 200
    data = response.json()
    assert data["event"]["header"]["name"] == "Response"
    power_prop = data["context"]["properties"][0]
    assert power_prop["value"] == "ON"


@pytest.mark.asyncio
async def test_alexa_turn_on_nonexistent_device(client):
    response = await client.post("/alexa/skill", json=_turn_on_directive("no-such-device"))
    assert response.status_code == 200
    data = response.json()
    assert data["event"]["header"]["name"] == "ErrorResponse"
    assert data["event"]["payload"]["type"] == "NO_SUCH_ENDPOINT"


@pytest.mark.asyncio
async def test_alexa_report_state(client):
    create_resp = await client.post("/devices", json={"name": "Heater"})
    device_id = create_resp.json()["id"]

    response = await client.post("/alexa/skill", json=_report_state_directive(device_id))
    data = response.json()
    assert data["event"]["header"]["name"] == "StateReport"
    assert data["context"]["properties"][0]["name"] == "powerState"
