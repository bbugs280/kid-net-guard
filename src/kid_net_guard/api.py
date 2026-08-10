"""REST API routes for the kid-net-guard PWA console."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from kid_net_guard.adguard import AdGuardClient
from kid_net_guard.config import settings

router = APIRouter()

client = AdGuardClient()

# ── Models ─────────────────────────────────────────────

class ToggleRequest(BaseModel):
    device_id: str
    service: str
    action: str  # "block" | "unblock"

class PauseRequest(BaseModel):
    action: str  # "pause" | "resume"

# ── Devices ────────────────────────────────────────────

@router.get("/devices")
async def get_devices():
    """Return all managed devices with their toggle states."""
    devices = []
    for dev in settings.DEVICES:
        try:
            services = await client.get_client_services(dev["adguard_client_id"])
        except Exception:
            services = {}

        devices.append({
            "id": dev["id"],
            "name": dev["name"],
            "subtitle": dev.get("subtitle", ""),
            "services": services,
        })
    return {"devices": devices}

# ── Toggle ─────────────────────────────────────────────

@router.post("/toggle")
async def toggle_service(req: ToggleRequest):
    """Block or unblock a service for a device."""
    device = next((d for d in settings.DEVICES if d["id"] == req.device_id), None)
    if not device:
        raise HTTPException(404, f"Device not found: {req.device_id}")

    adguard_name = device["adguard_client_id"]

    if req.action == "block":
        await client.block_service(adguard_name, req.service)
        return {"device": req.device_id, "service": req.service, "status": "blocked"}
    elif req.action == "unblock":
        await client.unblock_service(adguard_name, req.service)
        return {"device": req.device_id, "service": req.service, "status": "unblocked"}
    else:
        raise HTTPException(400, f"Unknown action: {req.action}")

# ── Pause All ──────────────────────────────────────────

@router.post("/pause-all")
async def pause_all(req: PauseRequest):
    """Emergency pause: block/resume ALL services for ALL devices."""
    target_enabled = req.action == "resume"
    await client.toggle_filtering(enabled=target_enabled)
    return {"filtering": "enabled" if target_enabled else "disabled"}

# ── Status ─────────────────────────────────────────────

@router.get("/status")
async def get_status():
    """Health check + AdGuard connectivity."""
    try:
        status = await client.get_status()
        adguard_ok = True
        protection = status.get("protection_enabled", False)
    except Exception:
        adguard_ok = False
        protection = False

    return {
        "adguard_connected": adguard_ok,
        "protection_enabled": protection,
        "version": settings.VERSION,
    }
