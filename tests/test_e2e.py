"""E2E tests for kid-net-guard — real Squid bridge + proxy + Playwright UI.

Proxy-based filtering approach. Tests clean up after themselves.
"""

import httpx
import subprocess
from playwright.sync_api import sync_playwright, expect


BASE_URL = "http://localhost:8082"
BRIDGE_URL = "http://127.0.0.1:3129"
PROXY = "http://192.168.86.20:3128"

CLIENT_NAME = "wayne-iphone"


def _cleanup():
    """Reset proxy to all-unblocked."""
    try:
        httpx.post(f"{BRIDGE_URL}/api/squid/pause-all",
                   json={"action": "resume"}, timeout=5)
    except Exception:
        pass


def _block_via_api(*services):
    for svc in services:
        httpx.post(f"{BASE_URL}/api/toggle", json={
            "device_id": "wayne-iphone", "service": svc, "action": "block",
        }, timeout=10)


def _unblock_via_api(*services):
    for svc in services:
        httpx.post(f"{BASE_URL}/api/toggle", json={
            "device_id": "wayne-iphone", "service": svc, "action": "unblock",
        }, timeout=10)


def _proxy_check(domain):
    """Return True if domain is blocked (proxy denies), False if allowed."""
    r = subprocess.run(
        ["curl", "-s", "-x", PROXY, f"https://{domain}", "-o", "/dev/null",
         "-w", "%{http_code}", "--max-time", "8"],
        capture_output=True, text=True, timeout=15,
    )
    code = r.stdout.strip()
    # 000 / empty / 403 = blocked; 200/301/302 = allowed
    return code in ("", "000", "403")


def setup_module():
    _cleanup()


def teardown_module():
    _cleanup()


# ── API-level E2E tests ────────────────────────────────

def test_get_devices_returns_data():
    _cleanup()
    _block_via_api("youtube", "roblox")

    r = httpx.get(f"{BASE_URL}/api/devices", timeout=5)
    assert r.status_code == 200
    data = r.json()
    assert len(data["devices"]) >= 1
    wayne = data["devices"][0]
    assert wayne["id"] == "wayne-iphone"
    services = wayne.get("services", {})
    assert services.get("youtube") is True
    assert services.get("roblox") is True
    assert services.get("netflix") is False

    _cleanup()


def test_toggle_block_works():
    _cleanup()
    r = httpx.post(f"{BASE_URL}/api/toggle", json={
        "device_id": "wayne-iphone", "service": "youtube", "action": "block",
    }, timeout=10)
    assert r.status_code == 200

    # Verify YouTube is actually blocked through the proxy
    assert _proxy_check("www.youtube.com"), "youtube.com should be blocked"
    _cleanup()


def test_toggle_unblock_works():
    _cleanup()
    _block_via_api("youtube")
    assert _proxy_check("www.youtube.com"), "youtube should be blocked first"

    r = httpx.post(f"{BASE_URL}/api/toggle", json={
        "device_id": "wayne-iphone", "service": "youtube", "action": "unblock",
    }, timeout=10)
    assert r.status_code == 200
    assert not _proxy_check("www.youtube.com"), "youtube should be unblocked"
    _cleanup()


def test_pause_all_and_resume():
    _cleanup()
    r = httpx.post(f"{BASE_URL}/api/pause-all", json={"action": "pause"}, timeout=10)
    assert r.status_code == 200
    # All major services blocked
    for d in ["www.youtube.com", "www.roblox.com", "discord.com"]:
        assert _proxy_check(d), f"{d} should be blocked during pause-all"

    # School/neutral sites unaffected? Actually pause-all blocks only known
    # services — example.com should still work
    assert not _proxy_check("example.com"), "example.com should NOT be blocked"

    r = httpx.post(f"{BASE_URL}/api/pause-all", json={"action": "resume"}, timeout=10)
    assert r.status_code == 200
    assert not _proxy_check("www.youtube.com"), "youtube should be unblocked after resume"
    _cleanup()


def test_selective_blocking_allows_neutral_sites():
    """Blocking youtube must NOT break example.com (selective)."""
    _cleanup()
    _block_via_api("youtube")
    assert _proxy_check("www.youtube.com"), "youtube blocked"
    assert not _proxy_check("example.com"), "neutral site still allowed"
    _cleanup()


# ── UI tests ──────────────────────────────────────────

def test_console_loads():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 390, "height": 844})
        pg = ctx.new_page()
        pg.goto(BASE_URL)
        expect(pg.locator(".topbar-name")).to_contain_text("Wayne")
        browser.close()


def test_toggle_slider_via_ui():
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
        pg.wait_for_timeout(3000)

        slider2 = pg.locator("#slider-youtube")
        is_on = "on" in (slider2.get_attribute("class") or "")
        assert is_on != was_on, f"Slider should have flipped. was_on={was_on}, is_on={is_on}"

        browser.close()
    _cleanup()
