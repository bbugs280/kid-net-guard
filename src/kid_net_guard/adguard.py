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
        """Get AdGuard Home general status."""
        return await self._request("GET", "/control/status")

    # ── Filtering (global) ──────────────────────────────

    async def get_filtering_status(self) -> dict:
        return await self._request("GET", "/control/filtering/status")

    async def toggle_filtering(self, enabled: bool, duration: int = 0) -> dict:
        """Toggle global filtering. duration=0 means permanent."""
        return await self._request("POST", "/control/filtering/config",
                                   json={"enabled": enabled, "interval": duration})

    # ── Clients ─────────────────────────────────────────

    async def get_clients(self) -> dict:
        """List all known clients."""
        return await self._request("GET", "/control/clients")

    async def get_client(self, name: str) -> dict:
        """Get a specific client by name."""
        return await self._request("GET", f"/control/clients/{name}")

    async def update_client(self, name: str, data: dict) -> dict:
        """Update client settings (blocked services, tags, etc.)."""
        return await self._request("PUT", f"/control/clients/{name}", json=data)

    # ── Toggle helpers ──────────────────────────────────

    async def is_service_blocked(self, client_name: str, service: str) -> bool:
        """Check if a specific service is blocked for a client."""
        try:
            client = await self.get_client(client_name)
            blocked = client.get("blocked_services", [])
            return service in blocked
        except httpx.HTTPStatusError:
            return False

    async def block_service(self, client_name: str, service: str) -> dict:
        """Block a service for a specific client."""
        client = await self.get_client(client_name)
        current = set(client.get("blocked_services", []))
        current.add(service)
        return await self.update_client(client_name, {"blocked_services": list(current)})

    async def unblock_service(self, client_name: str, service: str) -> dict:
        """Unblock a service for a specific client."""
        client = await self.get_client(client_name)
        current = set(client.get("blocked_services", []))
        current.discard(service)
        return await self.update_client(client_name, {"blocked_services": list(current)})

    async def get_client_services(self, client_name: str) -> dict[str, bool]:
        """Get all service toggle states for a client."""
        ALL_SERVICES = ["youtube", "netflix", "tiktok", "twitch", "discord",
                         "facebook", "snapchat", "roblox", "minecraft",
                         "fortnite", "steam", "epic_games", "whatsapp",
                         "instagram", "spotify"]
        client = await self.get_client(client_name)
        blocked = set(client.get("blocked_services", []))
        return {s: (s in blocked) for s in ALL_SERVICES}
