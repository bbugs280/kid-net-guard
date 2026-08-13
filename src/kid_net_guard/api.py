"""REST API routes for the kid-net-guard PWA console.

Proxy-based filtering (Squid) is the single engine. The AdGuard DNS layer
has been retired — selective blocking is now done at the connection level
via the Squid proxy, controlled through the host-side bridge daemon.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from kid_net_guard.squid import SquidClient
from kid_net_guard.config import settings

router = APIRouter()
client = SquidClient()

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
    """Return all managed devices with their block states."""
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
    """Block or unblock a service through the proxy."""
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
    """Block or resume all services through the proxy."""
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
    status = await client.get_status()
    return {
        "proxy_connected": status.get("connected", False),
        "version": settings.VERSION,
    }
