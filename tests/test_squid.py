"""Unit tests for the SquidClient and the services domain map."""

import pytest
from unittest.mock import AsyncMock, patch

from kid_net_guard.squid import SquidClient
from kid_net_guard.services import SERVICES, domains_for, all_domains


# ── services domain map ────────────────────────────────

def test_all_services_have_domains():
    assert len(SERVICES) == 14
    for svc, domains in SERVICES.items():
        assert domains, f"{svc} has no domains"


def test_youtube_has_critical_api_domain():
    # The API endpoint that initially leaked is present
    assert ".youtubei.googleapis.com" in SERVICES["youtube"]
    assert ".googlevideo.com" in SERVICES["youtube"]


def test_domains_for_unknown_returns_empty():
    assert domains_for("nonexistent") == []


def test_all_domains_is_union():
    result = all_domains()
    assert ".youtube.com" in result
    assert ".roblox.com" in result
    assert ".discord.com" in result


# ── SquidClient ────────────────────────────────────────

@pytest.mark.asyncio
async def test_block_service_calls_toggle():
    client = SquidClient(base_url="http://bridge:3129")
    mock_request = AsyncMock(return_value={"status": "blocked"})
    with patch.object(client, "_request", mock_request):
        await client.block_service("youtube")
    mock_request.assert_called_once_with(
        "POST", "/api/squid/toggle",
        json={"service": "youtube", "action": "block"},
    )


@pytest.mark.asyncio
async def test_unblock_service_calls_toggle():
    client = SquidClient(base_url="http://bridge:3129")
    mock_request = AsyncMock(return_value={"status": "unblocked"})
    with patch.object(client, "_request", mock_request):
        await client.unblock_service("roblox")
    mock_request.assert_called_once_with(
        "POST", "/api/squid/toggle",
        json={"service": "roblox", "action": "unblock"},
    )


@pytest.mark.asyncio
async def test_pause_all():
    client = SquidClient(base_url="http://bridge:3129")
    mock_request = AsyncMock(return_value={"status": "paused"})
    with patch.object(client, "_request", mock_request):
        await client.pause_all()
    mock_request.assert_called_once_with(
        "POST", "/api/squid/pause-all", json={"action": "pause"},
    )


@pytest.mark.asyncio
async def test_get_client_services_maps_blocked():
    client = SquidClient(base_url="http://bridge:3129")
    # Bridge reports youtube + roblox blocked
    mock_request = AsyncMock(return_value={"blocked_services": ["youtube", "roblox"]})
    with patch.object(client, "_request", mock_request):
        result = await client.get_client_services()
    assert result["youtube"] is True
    assert result["roblox"] is True
    assert result["discord"] is False
    assert result["netflix"] is False


@pytest.mark.asyncio
async def test_get_client_services_fail_open():
    """If the bridge is unreachable, report all-unblocked (don't crash)."""
    client = SquidClient(base_url="http://bridge:3129")
    mock_request = AsyncMock(side_effect=Exception("connection refused"))
    with patch.object(client, "_request", mock_request):
        result = await client.get_client_services()
    assert all(v is False for v in result.values())


@pytest.mark.asyncio
async def test_get_status_fail_returns_disconnected():
    client = SquidClient(base_url="http://bridge:3129")
    mock_request = AsyncMock(side_effect=Exception("refused"))
    with patch.object(client, "_request", mock_request):
        result = await client.get_status()
    assert result == {"connected": False}
