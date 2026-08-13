"""SquidClient — talks to the host-side Squid bridge daemon.

Squid itself exposes no REST/management API. The bridge daemon
(``scripts/squid_bridge.py`` on the host) rewrites the ``blocked_sites``
ACL in squid.conf and runs ``squid -k reconfigure``. This client is a thin
HTTP wrapper around that bridge, mirroring the AdGuardClient shape so the
API routes can fan out cleanly.
"""

import httpx

from kid_net_guard.config import settings


class SquidClient:
    """HTTP client for the host-side Squid bridge."""

    def __init__(self, base_url: str | None = None):
        self.base = (base_url or settings.SQUID_BRIDGE_URL).rstrip("/")

    async def _request(self, method: str, path: str, **kwargs):
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.request(method, f"{self.base}{path}", **kwargs)
            r.raise_for_status()
            if not r.text.strip():
                return {}
            return r.json()

    # ── Toggle operations ─────────────────────────────────

    async def block_service(self, service: str):
        return await self._request("POST", "/api/squid/toggle",
                                   json={"service": service, "action": "block"})

    async def unblock_service(self, service: str):
        return await self._request("POST", "/api/squid/toggle",
                                   json={"service": service, "action": "unblock"})

    async def pause_all(self):
        """Block ALL services through the proxy."""
        return await self._request("POST", "/api/squid/pause-all",
                                   json={"action": "pause"})

    async def resume_all(self):
        """Unblock ALL services through the proxy."""
        return await self._request("POST", "/api/squid/pause-all",
                                   json={"action": "resume"})

    # ── State ─────────────────────────────────────────────

    async def get_client_services(self) -> dict[str, bool]:
        """Return {service_id: blocked} for all known services."""
        try:
            data = await self._request("GET", "/api/squid/blocks")
            blocked = set(data.get("blocked_services", []))
            # Build the full map for every service we know about
            from kid_net_guard.services import SERVICE_ORDER
            return {s: s in blocked for s in SERVICE_ORDER}
        except Exception:
            # Bridge unreachable — report all unblocked (fail-open UI)
            from kid_net_guard.services import SERVICE_ORDER
            return {s: False for s in SERVICE_ORDER}

    async def get_status(self) -> dict:
        """Bridge health / proxy status."""
        try:
            return await self._request("GET", "/api/squid/status")
        except Exception:
            return {"connected": False}
