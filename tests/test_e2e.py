"""E2E tests for kid-net-guard — real AdGuard API calls + Playwright UI tests.

Per-client blocking approach. Tests clean up after themselves.
"""

import httpx
from playwright.sync_api import sync_playwright, expect


BASE_URL = "http://localhost:8082"
ADGUARD_URL = "http://localhost:8081"
AUTH = "Basic YWRtaW46a2lkbmV0MjAyNg=="  # admin:kidnet2026

CLIENT_NAME = "wayne-iphone"
SERVICE_IDS = [
    "youtube", "netflix", "tiktok", "twitch", "discord",
    "facebook", "snapchat", "roblox", "minecraft",
    "steam", "epic_games", "whatsapp",
    "instagram", "spotify",
]


def _headers():
    return {"Authorization": AUTH, "Content-Type": "application/json"}


def _get_client():
    r = httpx.get(f"{ADGUARD_URL}/control/clients", headers={"Authorization": AUTH}, timeout=5)
    for c in r.json().get("clients", []):
        if c.get("name") == CLIENT_NAME:
            return c
    return None


def _ensure_client():
    """Ensure a clean client exists."""
    existing = _get_client()
    if existing:
        # Delete and recreate
        httpx.post(f"{ADGUARD_URL}/control/clients/delete",
                    json={"name": CLIENT_NAME}, headers=_headers(), timeout=5)
    httpx.post(f"{ADGUARD_URL}/control/clients/add",
                json={
                    "name": CLIENT_NAME, "ids": ["0.0.0.0/0"],
                    "filtering_enabled": True, "parental_enabled": True,
                    "use_global_blocked_services": False, "use_global_settings": True,
                    "blocked_services": [],
                }, headers=_headers(), timeout=5)


def _block_via_api(*services):
    """Block services directly in AdGuard for test setup."""
    _ensure_client()
    for svc in services:
        httpx.post(f"{BASE_URL}/api/toggle", json={
            "device_id": "wayne-iphone", "service": svc, "action": "block",
        }, timeout=5)


def _unblock_via_api(*services):
    """Unblock services."""
    for svc in services:
        httpx.post(f"{BASE_URL}/api/toggle", json={
            "device_id": "wayne-iphone", "service": svc, "action": "unblock",
        }, timeout=5)


def _cleanup():
    """Reset client to empty blocked_services."""
    try:
        _ensure_client()
        httpx.post(f"{BASE_URL}/api/pause-all", json={"action": "resume"}, timeout=5)
    except Exception:
        pass


# ── module-level setup/teardown ────────────────────────

def setup_module():
    _cleanup()


def teardown_module():
    _cleanup()


# ── API-level E2E tests ────────────────────────────────

def test_get_devices_returns_data():
    """GET /api/devices returns service states that match actual AdGuard state."""
    _cleanup()
    _block_via_api("youtube", "roblox")

    r = httpx.get(f"{BASE_URL}/api/devices", timeout=5)
    assert r.status_code == 200
    data = r.json()
    assert len(data["devices"]) >= 1
    wayne = data["devices"][0]
    assert wayne["id"] == "wayne-iphone"

    services = wayne.get("services", {})
    assert services.get("youtube") is True, f"youtube should be blocked, got {services}"
    assert services.get("roblox") is True, f"roblox should be blocked, got {services}"
    assert services.get("netflix") is False, f"netflix should NOT be blocked, got {services}"

    _cleanup()


def test_toggle_block_works():
    """POST /api/toggle block should add service to blocked_services."""
    _cleanup()

    r = httpx.post(f"{BASE_URL}/api/toggle", json={
        "device_id": "wayne-iphone", "service": "netflix", "action": "block",
    }, timeout=5)
    assert r.status_code == 200

    # Verify in AdGuard
    client = _get_client()
    assert client is not None
    assert "netflix" in (client.get("blocked_services") or []), \
        f"netflix should be blocked, got {client.get('blocked_services')}"

    _cleanup()


def test_toggle_unblock_works():
    """POST /api/toggle unblock should remove service from blocked_services."""
    _cleanup()
    _block_via_api("netflix")

    r = httpx.post(f"{BASE_URL}/api/toggle", json={
        "device_id": "wayne-iphone", "service": "netflix", "action": "unblock",
    }, timeout=5)
    assert r.status_code == 200

    client = _get_client()
    assert "netflix" not in (client.get("blocked_services") or [])

    _cleanup()


def test_pause_all_blocks_everything():
    """POST /api/pause-all pause should cut ALL internet via catch-all rule."""
    _cleanup()

    r = httpx.post(f"{BASE_URL}/api/pause-all", json={"action": "pause"}, timeout=5)
    assert r.status_code == 200

    # The catch-all rule should be present in AdGuard's user_rules
    fr = httpx.get(f"{ADGUARD_URL}/control/filtering/status",
                   headers={"Authorization": AUTH}, timeout=5).json()
    rules = fr.get("user_rules") or []
    assert "||*^" in rules, f"Expected catch-all kill rule, got {rules}"

    _cleanup()


def test_resume_all_unblocks_everything():
    """POST /api/pause-all resume should remove the catch-all rule AND service blocks."""
    _cleanup()
    _block_via_api("youtube", "roblox", "tiktok", "discord", "minecraft")

    r = httpx.post(f"{BASE_URL}/api/pause-all", json={"action": "resume"}, timeout=5)
    assert r.status_code == 200

    # Catch-all rule removed
    fr = httpx.get(f"{ADGUARD_URL}/control/filtering/status",
                   headers={"Authorization": AUTH}, timeout=5).json()
    assert "||*^" not in (fr.get("user_rules") or [])

    # Service blocks cleared
    client = _get_client()
    blocked = client.get("blocked_services") or []
    assert len(blocked) == 0, f"Expected 0 blocked, got {blocked}"

    _cleanup()


def test_toggle_roundtrip():
    """Block → verify → unblock → verify."""
    _cleanup()

    # Block
    httpx.post(f"{BASE_URL}/api/toggle", json={
        "device_id": "wayne-iphone", "service": "tiktok", "action": "block",
    }, timeout=5)
    client = _get_client()
    assert "tiktok" in (client.get("blocked_services") or [])

    # Unblock
    httpx.post(f"{BASE_URL}/api/toggle", json={
        "device_id": "wayne-iphone", "service": "tiktok", "action": "unblock",
    }, timeout=5)
    client = _get_client()
    assert "tiktok" not in (client.get("blocked_services") or [])

    _cleanup()


def test_adguard_client_has_correct_flags():
    """After an API toggle, the AdGuard client must have all required flags."""
    _cleanup()

    httpx.post(f"{BASE_URL}/api/toggle", json={
        "device_id": "wayne-iphone", "service": "roblox", "action": "block",
    }, timeout=5)

    client = _get_client()
    assert client["filtering_enabled"] is True, f"filtering_enabled={client.get('filtering_enabled')}"
    assert client["parental_enabled"] is True, f"parental_enabled={client.get('parental_enabled')}"
    assert client["use_global_blocked_services"] is False, \
        f"use_global_blocked_services={client.get('use_global_blocked_services')} — must be False"
    assert "roblox" in (client.get("blocked_services") or [])

    _cleanup()


# ── UI tests ───────────────────────────────────────────

def test_console_loads():
    """PWA console should load with topbar showing Wayne."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 390, "height": 844})
        pg = ctx.new_page()
        pg.goto(BASE_URL)
        expect(pg.locator(".topbar-name")).to_contain_text("Wayne")
        browser.close()


def test_toggle_slider_via_ui():
    """Clicking a slider should toggle the service state."""
    _cleanup()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 390, "height": 844})
        pg = ctx.new_page()
        pg.goto(BASE_URL)
        pg.wait_for_selector(".slider", timeout=5000)

        slider = pg.locator("#slider-youtube")
        expect(slider).to_be_visible()
        was_on = "on" in (slider.get_attribute("class") or "")

        slider.click()
        pg.wait_for_timeout(2000)

        slider2 = pg.locator("#slider-youtube")
        is_on = "on" in (slider2.get_attribute("class") or "")
        assert is_on != was_on, f"Slider should have flipped. was_on={was_on}, is_on={is_on}"

        browser.close()

    _cleanup()


# ── DNS resolution tests ───────────────────────────────

def test_dns_resolution_works_when_nothing_blocked():
    """DNS queries should resolve normally when nothing is blocked."""
    _cleanup()
    import subprocess
    result = subprocess.run(
        ["dig", "@192.168.86.20", "google.com", "+short", "+time=5"],
        capture_output=True, text=True, timeout=10
    )
    ips = [l.strip() for l in result.stdout.strip().split("\n") if l.strip()]
    assert len(ips) > 0
    assert "." in ips[0]


def test_dns_resolution_blocks_when_service_blocked():
    """When a service is blocked, its domain should resolve to 0.0.0.0."""
    _cleanup()
    _block_via_api("roblox")
    import subprocess
    result = subprocess.run(
        ["dig", "@192.168.86.20", "roblox.com", "+short", "+time=5"],
        capture_output=True, text=True, timeout=10
    )
    ips = [l.strip() for l in result.stdout.strip().split("\n") if l.strip()]
    assert "0.0.0.0" in ips, f"Expected roblox.com → 0.0.0.0, got {ips}"
    _cleanup()


def test_dns_resolution_unblocks_after_toggle():
    """After unblocking, the domain should resolve to real IPs."""
    _cleanup()
    _block_via_api("roblox")

    # Unblock via API
    httpx.post(f"{BASE_URL}/api/toggle", json={
        "device_id": "wayne-iphone", "service": "roblox", "action": "unblock",
    }, timeout=5)

    import subprocess
    result = subprocess.run(
        ["dig", "@192.168.86.20", "roblox.com", "+short", "+time=5"],
        capture_output=True, text=True, timeout=10
    )
    ips = [l.strip() for l in result.stdout.strip().split("\n") if l.strip()]
    assert len(ips) > 0
    assert "0.0.0.0" not in ips, f"roblox.com should NOT be blocked after unblock, got {ips}"
    _cleanup()


def test_youtube_not_blocked_by_filter():
    """Regression: AdGuard DNS filter should NOT block youtube.com."""
    _cleanup()
    import subprocess
    result = subprocess.run(
        ["dig", "@192.168.86.20", "youtube.com", "+short", "+time=5"],
        capture_output=True, text=True, timeout=10
    )
    ips = [l.strip() for l in result.stdout.strip().split("\n") if l.strip()]
    assert len(ips) > 0
    assert "0.0.0.0" not in ips, "youtube.com should NOT be blocked by DNS filter"
