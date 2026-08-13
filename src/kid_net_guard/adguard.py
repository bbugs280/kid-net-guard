"""AdGuard Home API client — per-client blocking via blocked_services.

Uses persistent client matching by name with CIDR ids: ["0.0.0.0/0"]
to match ALL DNS traffic through this server. Docker NAT is irrelevant —
AdGuard matches persistent clients by name and CIDR, not source IP.

CRITICAL RULES (learned from debugging):
1. filtering_enabled + parental_enabled MUST be True for blocked_services to work
2. use_global_blocked_services MUST be False — the global list conflicts with per-client
3. Client update is a FULL REPLACE — must carry forward all flags
4. AdGuard client matching by name + CIDR works through Docker bridge NAT
"""

import httpx
from kid_net_guard.config import settings

# AdGuard service IDs we expose in the console
SERVICE_IDS = [
    "youtube", "netflix", "tiktok", "twitch", "discord",
    "facebook", "snapchat", "roblox", "minecraft",
    "steam", "epic_games", "whatsapp",
    "instagram", "spotify",
]

# Client config constants
CLIENT_NAME = "wayne-iphone"
CLIENT_IDS = ["0.0.0.0/0"]  # Match ALL DNS traffic

REQUIRED_FLAGS = {
    "filtering_enabled": True,
    "parental_enabled": True,
    "use_global_blocked_services": False,
    "use_global_settings": True,
}


class AdGuardClient:
    """Wrapper around AdGuard Home REST API for per-client service blocking."""

    def __init__(self):
        self.base = settings.ADGUARD_URL.rstrip("/")
        self.auth = (settings.ADGUARD_USER, settings.ADGUARD_PASS)

    async def _request(self, method: str, path: str, **kwargs) -> dict | list:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.request(method, f"{self.base}{path}", auth=self.auth, **kwargs)
            r.raise_for_status()
            if not r.text.strip():
                return {}
            return r.json()

    # ── Client management ────────────────────────────────

    async def _get_client_by_name(self, name: str) -> dict | None:
        data = await self._request("GET", "/control/clients")
        for c in (data.get("clients") or []):
            if c.get("name") == name:
                return c
        return None

    async def _create_client(self):
        """Create the persistent client with all required flags."""
        await self._request("POST", "/control/clients/add", json={
            "name": CLIENT_NAME,
            "ids": CLIENT_IDS,
            "blocked_services": [],
            **REQUIRED_FLAGS,
        })

    async def _ensure_client(self):
        """Ensure client exists with correct flags. Fixes/recreates if needed."""
        existing = await self._get_client_by_name(CLIENT_NAME)
        if existing is None:
            await self._create_client()
            return

        # Check if flags are correct
        flags_ok = all(
            existing.get(k) == v for k, v in REQUIRED_FLAGS.items()
        )
        ids_ok = CLIENT_IDS == (existing.get("ids") or [])
        
        if not flags_ok or not ids_ok:
            # Recreate — preserve existing blocked_services
            saved_services = existing.get("blocked_services", [])
            await self._request("POST", "/control/clients/delete",
                               json={"name": CLIENT_NAME})
            await self._request("POST", "/control/clients/add", json={
                "name": CLIENT_NAME,
                "ids": CLIENT_IDS,
                "blocked_services": saved_services,
                **REQUIRED_FLAGS,
            })

    async def _update_client(self, data: dict):
        """Update the client via full replace. Merges required flags."""
        existing = await self._get_client_by_name(CLIENT_NAME)
        if existing is None:
            await self._create_client()
            existing = await self._get_client_by_name(CLIENT_NAME)

        merged = {
            "name": CLIENT_NAME,
            "ids": CLIENT_IDS,
            **REQUIRED_FLAGS,
            "blocked_services": existing.get("blocked_services", []),
            **data,
        }
        await self._request("POST", "/control/clients/update",
                           json={"name": CLIENT_NAME, "data": merged})

    # ── Toggle operations ─────────────────────────────────

    async def block_service(self, service: str):
        """Block a service for the client."""
        await self._ensure_client()
        c = await self._get_client_by_name(CLIENT_NAME)
        current = set(c.get("blocked_services") or [])
        current.add(service)
        await self._update_client({"blocked_services": list(current)})

    async def unblock_service(self, service: str):
        """Unblock a service for the client."""
        await self._ensure_client()
        c = await self._get_client_by_name(CLIENT_NAME)
        current = set(c.get("blocked_services") or [])
        current.discard(service)
        await self._update_client({"blocked_services": list(current)})

    # AdGuard user-rule that blocks EVERYTHING (true internet kill switch).
    # `||*^` matches any hostname — every DNS query resolves to 0.0.0.0.
    KILL_RULE = "||*^"

    async def pause_all(self):
        """Emergency pause: cut ALL internet via a catch-all user rule.

        This is distinct from per-service blocking — it blocks every domain,
        not just the 14 named services. Backed by a global filtering user rule
        (`||*^`), applied through /control/filtering/set_rules.
        """
        # Read current user rules so we don't clobber unrelated rules.
        status = await self._request("GET", "/control/filtering/status")
        current = list(status.get("user_rules") or [])
        if self.KILL_RULE not in current:
            current.append(self.KILL_RULE)
        await self._request("POST", "/control/filtering/set_rules",
                            json={"rules": current})

    async def resume_all(self):
        """Resume: remove the catch-all rule and clear per-service blocks."""
        status = await self._request("GET", "/control/filtering/status")
        current = [r for r in (status.get("user_rules") or [])
                   if r != self.KILL_RULE]
        await self._request("POST", "/control/filtering/set_rules",
                            json={"rules": current})
        await self._ensure_client()
        await self._update_client({"blocked_services": []})

    # ── Status ────────────────────────────────────────────

    async def get_status(self) -> dict:
        return await self._request("GET", "/control/status")

    async def ensure_protection_enabled(self):
        """Enable AdGuard protection if it's off. Must be on for blocking to work."""
        status = await self.get_status()
        if not status.get("protection_enabled"):
            await self._request("POST", "/control/protection", json={"enabled": True})

    # ── Console display ───────────────────────────────────

    async def get_client_services(self) -> dict[str, bool]:
        """Return toggle states for the console."""
        try:
            await self._ensure_client()
            c = await self._get_client_by_name(CLIENT_NAME)
            if c is None:
                return {s: False for s in SERVICE_IDS}
            blocked = set(c.get("blocked_services") or [])
            return {s: s in blocked for s in SERVICE_IDS}
        except Exception:
            return {s: False for s in SERVICE_IDS}
