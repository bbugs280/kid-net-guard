"""Playwright E2E tests for kid-net-guard PWA."""

import pytest
import httpx
from playwright.sync_api import sync_playwright, expect


BASE_URL = "http://localhost:8082"
ADGUARD_URL = "http://localhost:8081"
AUTH = "Basic YWRtaW46a2lkbmV0MjAyNg=="  # admin:kidnet2026


def _ensure_client():
    """Ensure wayne-iphone client exists in AdGuard."""
    headers = {"Authorization": AUTH, "Content-Type": "application/json"}
    try:
        r = httpx.get(f"{ADGUARD_URL}/control/clients/wayne-iphone", headers=headers, timeout=5)
        if r.status_code == 404:
            payload = {"name": "wayne-iphone", "ids": ["192.168.86.0/24"]}
            r = httpx.post(f"{ADGUARD_URL}/control/clients/add", headers=headers, json=payload, timeout=5)
            print(f"Created client: {r.status_code} {r.text}")
    except Exception as e:
        print(f"Setup: {e}")


@pytest.fixture(scope="session", autouse=True)
def setup_adguard():
    _ensure_client()


@pytest.fixture(scope="function")
def page():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 390, "height": 844})
        page = context.new_page()
        # Capture console errors
        errors = []
        page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
        page.on("pageerror", lambda err: errors.append(str(err)))
        yield page
        if errors:
            print(f"JS errors: {errors}")
        browser.close()


# ── API-level tests (fail = real bug) ──────────────────

def test_api_get_devices_returns_data():
    """RED: GET /api/devices must return Wayne's device with service states."""
    # Block youtube and roblox via AdGuard directly 
    headers = {"Authorization": AUTH, "Content-Type": "application/json"}
    # AdGuard update needs name+ids inside data
    payload = {
        "name": "wayne-iphone",
        "data": {
            "name": "wayne-iphone",
            "ids": ["192.168.86.0/24"],
            "blocked_services": ["youtube", "roblox"],
        }
    }
    r = httpx.post(f"{ADGUARD_URL}/control/clients/update", headers=headers, json=payload, timeout=5)
    assert r.status_code == 200, f"Update failed: {r.status_code} {r.text}"

    # Now test the API
    r = httpx.get(f"{BASE_URL}/api/devices", timeout=5)
    assert r.status_code == 200
    data = r.json()
    assert "devices" in data
    assert len(data["devices"]) >= 1
    wayne = data["devices"][0]
    assert wayne["id"] == "wayne-iphone"

    # Service states should be populated — this is the bug fix
    services = wayne.get("services", {})
    assert len(services) > 0, f"Expected services to be populated, got: {services}"
    # youtube should be blocked since we just set it
    assert services.get("youtube") is True, f"Expected youtube=True, got {services.get('youtube')}"


def test_api_toggle_block_works():
    """RED: POST /api/toggle should successfully block a service."""
    r = httpx.post(f"{BASE_URL}/api/toggle", json={
        "device_id": "wayne-iphone",
        "service": "netflix",
        "action": "block",
    }, timeout=5)
    assert r.status_code == 200, f"Got {r.status_code}: {r.text}"
    data = r.json()
    assert data["status"] == "blocked"

    # Verify it was actually blocked in AdGuard via the list endpoint
    headers = {"Authorization": AUTH}
    r2 = httpx.get(f"{ADGUARD_URL}/control/clients", headers=headers, timeout=5)
    assert r2.status_code == 200
    clients = r2.json().get("clients", [])
    wayne = next((c for c in clients if c.get("name") == "wayne-iphone"), None)
    assert wayne is not None
    assert "netflix" in (wayne.get("blocked_services") or [])


def test_api_toggle_unblock_works():
    """RED: POST /api/toggle should successfully unblock a service."""
    # First block it
    headers = {"Authorization": AUTH, "Content-Type": "application/json"}
    httpx.post(f"{ADGUARD_URL}/control/clients/update", headers=headers, json={
        "name": "wayne-iphone", "data": {"blocked_services": ["netflix"]}
    }, timeout=5)

    # Now unblock via our API
    r = httpx.post(f"{BASE_URL}/api/toggle", json={
        "device_id": "wayne-iphone",
        "service": "netflix",
        "action": "unblock",
    }, timeout=5)
    assert r.status_code == 200, f"Got {r.status_code}: {r.text}"
    data = r.json()
    assert data["status"] == "unblocked"


# ── UI tests ───────────────────────────────────────────

def test_console_loads(page):
    """PWA console should load."""
    page.goto(BASE_URL)
    expect(page.locator("h1")).to_contain_text("Kid Net Guard")


def test_toggle_youtube_block_via_ui(page):
    """RED: Clicking YouTube toggle should actually change state via API."""
    page.goto(BASE_URL)
    page.wait_for_selector(".toggle", timeout=5000)

    # Find YouTube button
    yt = page.locator(".toggle").filter(has_text="YouTube").first
    expect(yt).to_be_visible()

    # Get initial state
    initial = yt.text_content()
    was_blocked = "BLOCKED" in initial

    # Click to toggle
    yt.click()
    page.wait_for_timeout(2500)

    # After reload, state should flip
    yt_after = page.locator(".toggle").filter(has_text="YouTube").first
    after = yt_after.text_content()
    now_blocked = "BLOCKED" in after

    if was_blocked:
        assert not now_blocked, f"YouTube should now be ALLOWED but got: {after}"
    else:
        assert now_blocked, f"YouTube should now be BLOCKED but got: {after}"
