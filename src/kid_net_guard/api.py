"""REST API routes for the kid-net-guard PWA console.

Per-client blocking approach — all devices share the same AdGuard client.
"""

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
    try:
        services = await client.get_client_services()
    except Exception:
        services = {}

    devices = []
    for dev in settings.DEVICES:
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
    """Block or unblock a service."""
    device = next((d for d in settings.DEVICES if d["id"] == req.device_id), None)
    if not device:
        raise HTTPException(404, f"Device not found: {req.device_id}")

    if req.action == "block":
        await client.block_service(req.service)
        return {"device": req.device_id, "service": req.service, "status": "blocked"}
    elif req.action == "unblock":
        await client.unblock_service(req.service)
        return {"device": req.device_id, "service": req.service, "status": "unblocked"}
    else:
        raise HTTPException(400, f"Unknown action: {req.action}")


# ── Pause All ──────────────────────────────────────────

@router.post("/pause-all")
async def pause_all(req: PauseRequest):
    """Emergency pause: cut ALL internet (catch-all rule), or resume."""
    if req.action == "pause":
        await client.pause_all()
        return {"status": "paused"}
    elif req.action == "resume":
        await client.resume_all()
        return {"status": "resumed"}
    else:
        raise HTTPException(400, f"Unknown action: {req.action}")


# ── Status ─────────────────────────────────────────────

@router.get("/status")
async def get_status():
    try:
        status = await client.get_status()
        return {
            "adguard_connected": True,
            "protection_enabled": status.get("protection_enabled", False),
            "version": settings.VERSION,
        }
    except Exception:
        return {
            "adguard_connected": False,
            "protection_enabled": False,
            "version": settings.VERSION,
        }
