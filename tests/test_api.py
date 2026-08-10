"""Tests for kid-net-guard API routes."""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import ASGITransport, AsyncClient


@pytest.fixture(autouse=True)
def mock_adguard_client():
    """Mock the AdGuardClient at the module level so the router's `client` instance is mocked."""
    mock = MagicMock()
    mock.get_client_services = AsyncMock(return_value={
        "youtube": True, "roblox": False, "minecraft": False,
    })
    mock.block_service = AsyncMock()
    mock.unblock_service = AsyncMock()
    mock.toggle_filtering = AsyncMock()
    mock.get_status = AsyncMock(return_value={
        "protection_enabled": True
    })

    # Patch the client instance in the api module — it's already instantiated
    with patch("kid_net_guard.api.client", mock):
        yield mock


@pytest_asyncio.fixture
async def client():
    from kid_net_guard import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_get_devices(client):
    r = await client.get("/api/devices")
    assert r.status_code == 200
    data = r.json()
    assert "devices" in data
    assert len(data["devices"]) >= 1
    assert data["devices"][0]["id"] == "wayne-iphone"


@pytest.mark.asyncio
async def test_toggle_block(mock_adguard_client, client):
    r = await client.post("/api/toggle", json={
        "device_id": "wayne-iphone",
        "service": "youtube",
        "action": "block",
    })
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "blocked"
    mock_adguard_client.block_service.assert_called_once()


@pytest.mark.asyncio
async def test_toggle_unblock(mock_adguard_client, client):
    r = await client.post("/api/toggle", json={
        "device_id": "wayne-iphone",
        "service": "roblox",
        "action": "unblock",
    })
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "unblocked"
    mock_adguard_client.unblock_service.assert_called_once()


@pytest.mark.asyncio
async def test_toggle_unknown_device(mock_adguard_client, client):
    r = await client.post("/api/toggle", json={
        "device_id": "nonexistent",
        "service": "youtube",
        "action": "block",
    })
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_pause_all(mock_adguard_client, client):
    r = await client.post("/api/pause-all", json={"action": "pause"})
    assert r.status_code == 200
    mock_adguard_client.toggle_filtering.assert_called_once_with(enabled=False)


@pytest.mark.asyncio
async def test_index(client):
    r = await client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
