"""AdGuard Home API client — per-client filtering toggle operations."""

import httpx
from kid_net_guard.config import settings


class AdGuardClient:
    """Thin wrapper around AdGuard Home REST API for per-client filtering."""

    def __init__(self):
        self.base = settings.ADGUARD_URL.rstrip("/")
        self.auth = (settings.ADGUARD_USER, settings.ADGUARD_PASS)

    async def _request(self, method: str, path: str, **kwargs) -> dict:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.request(method, f"{self.base}{path}", auth=self.auth, **kwargs)
            r.raise_for_status()
            return r.json() if r.text else {}

    # ── Status ──────────────────────────────────────────

    async def get_status(self) -> dict:
        return await self._request("GET", "/control/status")

    # ── Filtering (global) ──────────────────────────────

    async def toggle_filtering(self, enabled: bool, duration: int = 0) -> dict:
        return await self._request("POST", "/control/filtering/config",
                                   json={"enabled": enabled, "interval": duration})

    # ── Clients ─────────────────────────────────────────
    # AdGuard has no GET /clients/{name} — we list all and filter.

    async def _get_client_by_name(self, name: str) -> dict | None:
        """Find a persistent client by name from the full clients list."""
        data = await self._request("GET", "/control/clients")
        for c in (data.get("clients") or []):
            if c.get("name") == name:
                return c
        return None

    async def _create_client(self, name: str):
        """Create a persistent client with per-client blocked services disabled."""
        await self._request("POST", "/control/clients/add", json={
            "name": name,
            "use_global_blocked_services": False,
        })

    async def _ensure_client(self, name: str):
        """Create the client if it doesn't exist."""
        existing = await self._get_client_by_name(name)
        if existing is None:
            await self._create_client(name)

    async def _update_client(self, name: str, data: dict) -> dict:
        """Update client via POST /control/clients/update.
        
        AdGuard's update API requires data.name and data.ids in the payload.
        We merge the existing client data so we don't lose required fields.
        """
        existing = await self._get_client_by_name(name)
        if existing is None:
            await self._create_client(name)
            existing = await self._get_client_by_name(name)

        merged = {
            "name": name,
            "ids": existing.get("ids", []),
            **data,
        }
        return await self._request("POST", "/control/clients/update",
                                   json={"name": name, "data": merged})

    # ── Toggle helpers ──────────────────────────────────

    async def block_service(self, client_name: str, service: str) -> dict:
        """Block a service for a specific client."""
        await self._ensure_client(client_name)
        c = await self._get_client_by_name(client_name)
        current = set(c.get("blocked_services") or [])
        current.add(service)
        return await self._update_client(client_name, {"blocked_services": list(current)})

    async def unblock_service(self, client_name: str, service: str) -> dict:
        """Unblock a service for a specific client."""
        await self._ensure_client(client_name)
        c = await self._get_client_by_name(client_name)
        current = set(c.get("blocked_services") or [])
        current.discard(service)
        return await self._update_client(client_name, {"blocked_services": list(current)})

    async def get_client_services(self, client_name: str) -> dict[str, bool]:
        """Get all service toggle states for a client."""
        ALL_SERVICES = ["youtube", "netflix", "tiktok", "twitch", "discord",
                         "facebook", "snapchat", "roblox", "minecraft",
                         "fortnite", "steam", "epic_games", "whatsapp",
                         "instagram", "spotify"]
        try:
            await self._ensure_client(client_name)
            c = await self._get_client_by_name(client_name)
            if c is None:
                return {s: False for s in ALL_SERVICES}
            blocked = set(c.get("blocked_services") or [])
            return {s: (s in blocked) for s in ALL_SERVICES}
        except Exception:
            return {s: False for s in ALL_SERVICES}
