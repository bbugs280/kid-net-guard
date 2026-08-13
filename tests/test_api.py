"""Unit tests for kid-net-guard API routes (proxy engine).

Tests mock SquidClient — no real HTTP calls to the bridge.
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import ASGITransport, AsyncClient


@pytest.fixture(autouse=True)
def mock_squid_client():
    mock = MagicMock()
    mock.get_client_services = AsyncMock(return_value={
        "youtube": True, "roblox": False,
    })
    mock.block_service = AsyncMock()
    mock.unblock_service = AsyncMock()
    mock.pause_all = AsyncMock()
    mock.resume_all = AsyncMock()
    mock.get_status = AsyncMock(return_value={"connected": True})

    with patch("kid_net_guard.api.client", mock):
        yield mock


@pytest_asyncio.fixture
async def async_client():
    from kid_net_guard import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_health(async_client):
    r = await async_client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_get_devices(async_client):
    r = await async_client.get("/api/devices")
    assert r.status_code == 200
    data = r.json()
    assert "devices" in data
    assert len(data["devices"]) >= 1
    assert data["devices"][0]["id"] == "wayne-iphone"


@pytest.mark.asyncio
async def test_toggle_block(mock_squid_client, async_client):
    r = await async_client.post("/api/toggle", json={
        "device_id": "wayne-iphone",
        "service": "youtube",
        "action": "block",
    })
    assert r.status_code == 200
    assert r.json()["status"] == "blocked"
    mock_squid_client.block_service.assert_called_once_with("youtube")


@pytest.mark.asyncio
async def test_toggle_unblock(mock_squid_client, async_client):
    r = await async_client.post("/api/toggle", json={
        "device_id": "wayne-iphone",
        "service": "roblox",
        "action": "unblock",
    })
    assert r.status_code == 200
    assert r.json()["status"] == "unblocked"
    mock_squid_client.unblock_service.assert_called_once_with("roblox")


@pytest.mark.asyncio
async def test_toggle_unknown_device(mock_squid_client, async_client):
    r = await async_client.post("/api/toggle", json={
        "device_id": "nonexistent",
        "service": "youtube",
        "action": "block",
    })
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_pause_all(mock_squid_client, async_client):
    r = await async_client.post("/api/pause-all", json={"action": "pause"})
    assert r.status_code == 200
    mock_squid_client.pause_all.assert_called_once()


@pytest.mark.asyncio
async def test_resume_all(mock_squid_client, async_client):
    r = await async_client.post("/api/pause-all", json={"action": "resume"})
    assert r.status_code == 200
    mock_squid_client.resume_all.assert_called_once()


@pytest.mark.asyncio
async def test_index(async_client):
    r = await async_client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


@pytest.mark.asyncio
async def test_status_endpoint(mock_squid_client, async_client):
    r = await async_client.get("/api/status")
    assert r.status_code == 200
    data = r.json()
    assert data["proxy_connected"] is True
