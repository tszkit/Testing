"""Tests for device management REST API."""
import pytest


@pytest.mark.asyncio
async def test_list_devices_empty(client):
    response = await client.get("/devices")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_create_and_get_device(client):
    create_resp = await client.post("/devices", json={"name": "Dishwasher", "device_type": "outlet"})
    assert create_resp.status_code == 201
    device = create_resp.json()
    assert device["name"] == "Dishwasher"
    device_id = device["id"]

    get_resp = await client.get(f"/devices/{device_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["device_type"] == "outlet"


@pytest.mark.asyncio
async def test_update_device_state(client):
    create_resp = await client.post("/devices", json={"name": "Boiler"})
    device_id = create_resp.json()["id"]

    patch_resp = await client.patch(f"/devices/{device_id}/state", json={"state": True})
    assert patch_resp.status_code == 200
    assert patch_resp.json()["state"] is True

    patch_resp2 = await client.patch(f"/devices/{device_id}/state", json={"state": False})
    assert patch_resp2.json()["state"] is False


@pytest.mark.asyncio
async def test_delete_device(client):
    create_resp = await client.post("/devices", json={"name": "EV Charger"})
    device_id = create_resp.json()["id"]

    del_resp = await client.delete(f"/devices/{device_id}")
    assert del_resp.status_code == 204

    get_resp = await client.get(f"/devices/{device_id}")
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_get_nonexistent_device(client):
    response = await client.get("/devices/does-not-exist")
    assert response.status_code == 404
