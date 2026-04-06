"""Tests for the Google Home Cloud-to-Cloud fulfillment endpoint."""
import uuid

import pytest


def _sync_request() -> dict:
    return {
        "requestId": str(uuid.uuid4()),
        "inputs": [{"intent": "action.devices.SYNC"}],
    }


def _query_request(device_ids: list[str]) -> dict:
    return {
        "requestId": str(uuid.uuid4()),
        "inputs": [
            {
                "intent": "action.devices.QUERY",
                "payload": {"devices": [{"id": did} for did in device_ids]},
            }
        ],
    }


def _execute_request(device_ids: list[str], turn_on: bool) -> dict:
    return {
        "requestId": str(uuid.uuid4()),
        "inputs": [
            {
                "intent": "action.devices.EXECUTE",
                "payload": {
                    "commands": [
                        {
                            "devices": [{"id": did} for did in device_ids],
                            "execution": [
                                {
                                    "command": "action.devices.commands.OnOff",
                                    "params": {"on": turn_on},
                                }
                            ],
                        }
                    ]
                },
            }
        ],
    }


@pytest.mark.asyncio
async def test_google_sync_no_devices(client):
    response = await client.post("/google/fulfillment", json=_sync_request())
    assert response.status_code == 200
    data = response.json()
    assert data["payload"]["devices"] == []


@pytest.mark.asyncio
async def test_google_sync_with_device(client):
    await client.post("/devices", json={"name": "Heat Pump", "device_type": "switch"})

    response = await client.post("/google/fulfillment", json=_sync_request())
    data = response.json()
    devices = data["payload"]["devices"]
    assert len(devices) == 1
    assert devices[0]["name"]["name"] == "Heat Pump"
    assert "action.devices.traits.OnOff" in devices[0]["traits"]


@pytest.mark.asyncio
async def test_google_query_device_state(client):
    create_resp = await client.post("/devices", json={"name": "Pool Pump"})
    device_id = create_resp.json()["id"]

    response = await client.post("/google/fulfillment", json=_query_request([device_id]))
    data = response.json()
    states = data["payload"]["devices"]
    assert device_id in states
    assert states[device_id]["online"] is True
    assert "on" in states[device_id]


@pytest.mark.asyncio
async def test_google_execute_turn_on(client):
    create_resp = await client.post("/devices", json={"name": "Tumble Dryer"})
    device_id = create_resp.json()["id"]

    response = await client.post("/google/fulfillment", json=_execute_request([device_id], turn_on=True))
    data = response.json()
    commands = data["payload"]["commands"]
    assert any(c["status"] == "SUCCESS" and device_id in c["ids"] for c in commands)
    assert any(c["states"]["on"] is True for c in commands if c["status"] == "SUCCESS")


@pytest.mark.asyncio
async def test_google_execute_turn_off(client):
    create_resp = await client.post("/devices", json={"name": "Dishwasher"})
    device_id = create_resp.json()["id"]
    # Turn on first
    await client.post("/google/fulfillment", json=_execute_request([device_id], turn_on=True))
    # Now turn off
    response = await client.post("/google/fulfillment", json=_execute_request([device_id], turn_on=False))
    data = response.json()
    commands = data["payload"]["commands"]
    assert any(c["states"]["on"] is False for c in commands if c["status"] == "SUCCESS")


@pytest.mark.asyncio
async def test_google_execute_unknown_device(client):
    response = await client.post("/google/fulfillment", json=_execute_request(["ghost-device"], turn_on=True))
    data = response.json()
    commands = data["payload"]["commands"]
    assert any(c["status"] == "ERROR" for c in commands)
