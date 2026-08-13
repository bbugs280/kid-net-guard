"""Unit tests for kid-net-guard AdGuard client and API routes.

Tests mock AdGuardClient — no real HTTP calls.
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import ASGITransport, AsyncClient

from kid_net_guard.adguard import AdGuardClient, SERVICE_IDS, CLIENT_NAME, REQUIRED_FLAGS


# ── AdGuard client unit tests ──────────────────────────

@pytest.mark.asyncio
async def test_create_client_sets_required_flags():
    """_create_client must set all REQUIRED_FLAGS — key lesson from debugging."""
    client = AdGuardClient()
    mock_request = AsyncMock(return_value={})
    
    with patch.object(client, '_request', mock_request):
        await client._create_client()
    
    call = mock_request.call_args
    method, url = call[0][0], call[0][1]
    assert method == "POST"
    assert url == "/control/clients/add"
    
    json_body = call[1].get("json", {})
    assert json_body["name"] == CLIENT_NAME
    assert json_body["ids"] == ["0.0.0.0/0"]
    assert json_body["filtering_enabled"] is True
    assert json_body["parental_enabled"] is True
    assert json_body["use_global_blocked_services"] is False  # critical!
    assert json_body["use_global_settings"] is True
    assert json_body["blocked_services"] == []


@pytest.mark.asyncio
async def test_ensure_client_creates_when_missing():
    """_ensure_client calls _create_client when no client exists."""
    client = AdGuardClient()
    mock_create = AsyncMock()
    
    with patch.object(client, '_get_client_by_name', AsyncMock(return_value=None)):
        with patch.object(client, '_create_client', mock_create):
            await client._ensure_client()
    
    mock_create.assert_called_once()


@pytest.mark.asyncio
async def test_ensure_client_fixes_broken_flags():
    """_ensure_client deletes+recreates client with wrong flags, preserving blocked_services."""
    client = AdGuardClient()
    # Client exists but has wrong flags
    broken = {"name": CLIENT_NAME, "ids": ["0.0.0.0/0"],
              "filtering_enabled": False, "parental_enabled": False,
              "use_global_blocked_services": True, "use_global_settings": False,
              "blocked_services": ["roblox", "youtube"]}
    
    mock_request = AsyncMock()
    
    with patch.object(client, '_get_client_by_name', AsyncMock(return_value=broken)):
        with patch.object(client, '_request', mock_request):
            await client._ensure_client()
    
    assert mock_request.call_count == 2
    # First call: DELETE
    assert mock_request.call_args_list[0][0][0] == "POST"
    assert mock_request.call_args_list[0][0][1] == "/control/clients/delete"
    # Second call: ADD with preserved blocked_services
    assert mock_request.call_args_list[1][0][0] == "POST"
    assert mock_request.call_args_list[1][0][1] == "/control/clients/add"
    add_payload = mock_request.call_args_list[1][1]["json"]
    assert add_payload["blocked_services"] == ["roblox", "youtube"]
    assert add_payload["filtering_enabled"] is True
    assert add_payload["parental_enabled"] is True
    assert add_payload["use_global_blocked_services"] is False


@pytest.mark.asyncio
async def test_ensure_client_skips_when_ok():
    """_ensure_client should NOT recreate when flags are correct."""
    client = AdGuardClient()
    ok = {"name": CLIENT_NAME, "ids": ["0.0.0.0/0"],
          "filtering_enabled": True, "parental_enabled": True,
          "use_global_blocked_services": False, "use_global_settings": True,
          "blocked_services": ["roblox"]}
    
    mock_create = AsyncMock()
    
    with patch.object(client, '_get_client_by_name', AsyncMock(return_value=ok)):
        with patch.object(client, '_create_client', mock_create):
            await client._ensure_client()
    
    mock_create.assert_not_called()


@pytest.mark.asyncio
async def test_update_client_preserves_flags():
    """_update_client must carry forward required flags — AdGuard update is full replace."""
    client = AdGuardClient()
    
    existing = {"name": CLIENT_NAME, "ids": ["0.0.0.0/0"],
                "filtering_enabled": True, "parental_enabled": True,
                "use_global_blocked_services": False, "use_global_settings": True,
                "blocked_services": ["roblox"]}
    
    mock_request = AsyncMock(return_value={})
    
    with patch.object(client, '_get_client_by_name', AsyncMock(return_value=existing)):
        with patch.object(client, '_request', mock_request):
            await client._update_client({"blocked_services": ["roblox", "youtube"]})
    
    json_body = mock_request.call_args[1].get("json", {})
    merged = json_body.get("data", {})
    
    assert merged["filtering_enabled"] is True
    assert merged["parental_enabled"] is True
    assert merged["use_global_blocked_services"] is False
    assert merged["use_global_settings"] is True
    assert "roblox" in merged["blocked_services"]
    assert "youtube" in merged["blocked_services"]


@pytest.mark.asyncio
async def test_block_service_adds_to_list():
    client = AdGuardClient()
    existing = {"name": CLIENT_NAME, "ids": ["0.0.0.0/0"],
                "filtering_enabled": True, "parental_enabled": True,
                "use_global_blocked_services": False, "use_global_settings": True,
                "blocked_services": ["roblox"]}
    
    mock_update = AsyncMock()
    
    with patch.object(client, '_ensure_client', AsyncMock()):
        with patch.object(client, '_get_client_by_name', AsyncMock(return_value=existing)):
            with patch.object(client, '_update_client', mock_update):
                await client.block_service("youtube")
    
    call_data = mock_update.call_args[0][0]
    assert "roblox" in call_data["blocked_services"]
    assert "youtube" in call_data["blocked_services"]


@pytest.mark.asyncio
async def test_unblock_service_removes_from_list():
    client = AdGuardClient()
    existing = {"name": CLIENT_NAME, "ids": ["0.0.0.0/0"],
                "filtering_enabled": True, "parental_enabled": True,
                "use_global_blocked_services": False, "use_global_settings": True,
                "blocked_services": ["roblox", "youtube"]}
    
    mock_update = AsyncMock()
    
    with patch.object(client, '_ensure_client', AsyncMock()):
        with patch.object(client, '_get_client_by_name', AsyncMock(return_value=existing)):
            with patch.object(client, '_update_client', mock_update):
                await client.unblock_service("roblox")
    
    call_data = mock_update.call_args[0][0]
    assert "roblox" not in call_data["blocked_services"]
    assert "youtube" in call_data["blocked_services"]


@pytest.mark.asyncio
async def test_pause_all_blocks_everything():
    client = AdGuardClient()
    # Mock the two requests pause_all makes: GET status, then POST set_rules
    mock_request = AsyncMock()
    mock_request.side_effect = [
        {"user_rules": []},          # GET /control/filtering/status
        {},                          # POST /control/filtering/set_rules
    ]

    with patch.object(client, '_request', mock_request):
        await client.pause_all()

    # First call: GET status
    assert mock_request.call_args_list[0][0][0] == "GET"
    assert mock_request.call_args_list[0][0][1] == "/control/filtering/status"
    # Second call: POST set_rules with the catch-all kill rule
    assert mock_request.call_args_list[1][0][0] == "POST"
    assert mock_request.call_args_list[1][0][1] == "/control/filtering/set_rules"
    rules = mock_request.call_args_list[1][1]["json"]["rules"]
    assert client.KILL_RULE in rules


@pytest.mark.asyncio
async def test_resume_all_clears_kill_rule_and_services():
    client = AdGuardClient()
    # resume_all calls: GET status, POST set_rules, then _update_client (which
    # we stub out entirely so we only assert the kill-rule removal path).
    mock_request = AsyncMock()
    mock_request.side_effect = [
        {"user_rules": [client.KILL_RULE]},  # GET /control/filtering/status
        {},                                   # POST /control/filtering/set_rules
    ]

    with patch.object(client, '_ensure_client', AsyncMock()):
        with patch.object(client, '_update_client', AsyncMock()) as mock_update:
            with patch.object(client, '_request', mock_request):
                await client.resume_all()

    # First call: GET status (kill rule present)
    assert mock_request.call_args_list[0][0][1] == "/control/filtering/status"
    # Second call: POST set_rules with kill rule REMOVED
    rules = mock_request.call_args_list[1][1]["json"]["rules"]
    assert client.KILL_RULE not in rules
    # _update_client still called to clear per-service blocks
    mock_update.assert_called_once_with({"blocked_services": []})


@pytest.mark.asyncio
async def test_get_client_services_returns_dict():
    client = AdGuardClient()
    mock_client = {"blocked_services": ["roblox", "youtube"]}
    
    with patch.object(client, '_ensure_client', AsyncMock()):
        with patch.object(client, '_get_client_by_name', AsyncMock(return_value=mock_client)):
            result = await client.get_client_services()
    
    assert result["roblox"] is True
    assert result["youtube"] is True
    assert result["minecraft"] is False
    assert result["discord"] is False


@pytest.mark.asyncio
async def test_get_client_services_all_unblocked():
    client = AdGuardClient()
    mock_client = {"blocked_services": []}
    
    with patch.object(client, '_ensure_client', AsyncMock()):
        with patch.object(client, '_get_client_by_name', AsyncMock(return_value=mock_client)):
            result = await client.get_client_services()
    
    assert all(v is False for v in result.values())


# ── API route tests (mocked AdGuardClient) ──────────────

@pytest.fixture(autouse=True)
def mock_adguard_client():
    mock = MagicMock()
    mock.get_client_services = AsyncMock(return_value={
        "youtube": True, "roblox": False,
    })
    mock.block_service = AsyncMock()
    mock.unblock_service = AsyncMock()
    mock.pause_all = AsyncMock()
    mock.resume_all = AsyncMock()
    mock.get_status = AsyncMock(return_value={"protection_enabled": True})
    mock.ensure_protection_enabled = AsyncMock()

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
async def test_toggle_block(mock_adguard_client, async_client):
    r = await async_client.post("/api/toggle", json={
        "device_id": "wayne-iphone",
        "service": "youtube",
        "action": "block",
    })
    assert r.status_code == 200
    assert r.json()["status"] == "blocked"
    mock_adguard_client.block_service.assert_called_once_with("youtube")


@pytest.mark.asyncio
async def test_toggle_unblock(mock_adguard_client, async_client):
    r = await async_client.post("/api/toggle", json={
        "device_id": "wayne-iphone",
        "service": "roblox",
        "action": "unblock",
    })
    assert r.status_code == 200
    assert r.json()["status"] == "unblocked"
    mock_adguard_client.unblock_service.assert_called_once_with("roblox")


@pytest.mark.asyncio
async def test_toggle_unknown_device(mock_adguard_client, async_client):
    r = await async_client.post("/api/toggle", json={
        "device_id": "nonexistent",
        "service": "youtube",
        "action": "block",
    })
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_pause_all(mock_adguard_client, async_client):
    r = await async_client.post("/api/pause-all", json={"action": "pause"})
    assert r.status_code == 200
    mock_adguard_client.pause_all.assert_called_once()


@pytest.mark.asyncio
async def test_resume_all(mock_adguard_client, async_client):
    r = await async_client.post("/api/pause-all", json={"action": "resume"})
    assert r.status_code == 200
    mock_adguard_client.resume_all.assert_called_once()


@pytest.mark.asyncio
async def test_index(async_client):
    r = await async_client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


@pytest.mark.asyncio
async def test_status_endpoint(mock_adguard_client, async_client):
    r = await async_client.get("/api/status")
    assert r.status_code == 200
    data = r.json()
    assert data["adguard_connected"] is True
    assert data["protection_enabled"] is True
