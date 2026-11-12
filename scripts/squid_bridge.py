"""Squid bridge daemon — runs ON THE HOST (Mac Mini), not in Docker.

Exposes an HTTP API that rewrites the ``blocked_sites`` ACL in squid.conf and
reloads Squid. Only the host can edit /opt/homebrew/etc/squid.conf and run
`squid -k reconfigure`, which is why this is a separate process from the
Dockerized kid-net-guard app.

Run:
    python3 scripts/squid_bridge.py       # listens on 127.0.0.1:3129 (bind configurable)

The Docker app reaches it via host.docker.internal:3129.
"""

import os
import re
import subprocess
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

# ── Config ──────────────────────────────────────────────
# squid.conf lives here on the host (Homebrew layout)
SQUID_CONF = Path(os.getenv("SQUID_CONF", "/opt/homebrew/etc/squid.conf"))
SQUID_BIN = os.getenv("SQUID_BIN", "/opt/homebrew/opt/squid/sbin/squid")
BRIDGE_HOST = os.getenv("SQUID_BRIDGE_HOST", "127.0.0.1")
BRIDGE_PORT = int(os.getenv("SQUID_BRIDGE_PORT", "3129"))

# Blocked services are tracked as a dedicated comment-marked block in squid.conf.
# We only touch the lines between these markers, leaving the rest untouched.
BLOCK_START = "# >>> kid-net-guard blocked services (auto-managed) >>>"
BLOCK_END = "# <<< kid-net-guard blocked services (auto-managed) <<<"

# Kill-switch: a separate http_access rule that denies ALL localnet traffic when
# active. This makes "Pause All Internet" actually cut everything (not just the
# 14 named services). Localhost is still allowed so the console stays reachable.
# Marker format — a comment toggled on/off by the bridge:
#   KILL_ACTIVE = "# >>> kid-net-guard kill-switch (auto-managed) >>>\nhttp_access deny localnet kill_switch\n# <<< kid-net-guard kill-switch (auto-managed) <<<"
KILL_START = "# >>> kid-net-guard kill-switch (auto-managed) >>>"
KILL_END = "# <<< kid-net-guard kill-switch (auto-managed) <<<"
# Deny ALL localnet traffic — no separate ACL needed, reuses `localnet`.
KILL_RULE = "http_access deny localnet"

# Import the service->domain map from the package (same source of truth).
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from kid_net_guard.services import SERVICES, SERVICE_ORDER  # noqa: E402

app = FastAPI(title="kid-net-guard Squid Bridge")


# ── State helpers ───────────────────────────────────────

def _read_conf() -> str:
    return SQUID_CONF.read_text()


def _write_conf(text: str) -> None:
    SQUID_CONF.write_text(text)


def _reconfigure() -> None:
    """Reload Squid config (soft — keeps established connections)."""
    r = subprocess.run([SQUID_BIN, "-k", "reconfigure"],
                       capture_output=True, text=True, timeout=15)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or f"squid reconfigure rc={r.returncode}")


def _restart() -> None:
    """Full Squid restart — DROPS all established tunnels.

    We restart (not reconfigure) on every toggle so that already-open app
    connections (e.g. a running YouTube or WhatsApp stream) are torn down and
    the app must reconnect — hitting the new blocklist. This is the only way to
    make toggles take effect immediately rather than "on next app launch".

    IMPORTANT: Homebrew runs squid as `squid -N -d` (foreground, non-daemonized),
    so `squid -k restart` shuts it down but does NOT respawn a daemon (squid stays
    dead). We must use `brew services restart squid` so launchd/brew respawns it.
    Squid re-reads the on-disk conf on start, so toggled state (including the
    kill-switch rule) is preserved automatically.

    Tradeoff: a ~2s blip for any other device routed through the proxy.
    """
    # Homebrew prefix may differ; resolve brew bin.
    brew = os.getenv("BREW_BIN", "/opt/homebrew/bin/brew")
    r = subprocess.run([brew, "services", "restart", "squid"],
                       capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or f"brew services restart squid rc={r.returncode}")


def _get_blocked_services(conf: str) -> set[str]:
    """Parse the auto-managed block to discover which services are blocked."""
    # A blocked service is represented by a line: acl blocked_sites dstdomain <domain>
    # inside the managed block. We map domains back to their service.
    block = _extract_managed_block(conf)
    if block is None:
        return set()

    blocked_domains: set[str] = set()
    for line in block.splitlines():
        m = re.match(r"\s*acl\s+blocked_sites\s+dstdomain\s+(\S+)", line)
        if m:
            blocked_domains.add(m.group(1))

    # A service is "blocked" if ALL its domains are present in the ACL.
    blocked_services: set[str] = set()
    for svc in SERVICE_ORDER:
        domains = set(SERVICES.get(svc, []))
        if domains and domains.issubset(blocked_domains):
            blocked_services.add(svc)
    return blocked_services


def _extract_managed_block(conf: str) -> str | None:
    """Return the text between BLOCK_START and BLOCK_END, or None."""
    if BLOCK_START not in conf:
        return None
    start = conf.index(BLOCK_START)
    end = conf.index(BLOCK_END) + len(BLOCK_END)
    return conf[start:end]


def _serialize_acl(blocked_services: set[str]) -> str:
    """Render the managed ACL block from a set of service IDs.

    Always emits at least one (dummy) dstdomain entry because Squid requires
    the `blocked_sites` ACL to be non-empty when referenced by
    `http_access deny blocked_sites` — an empty ACL triggers
    "ACL not found: blocked_sites".
    """
    lines = [BLOCK_START]
    for svc in SERVICE_ORDER:
        if svc in blocked_services:
            for domain in SERVICES.get(svc, []):
                lines.append(f"acl blocked_sites dstdomain {domain}")
    if len(lines) == 1:
        # No services blocked — emit a dummy entry that matches nothing real.
        lines.append("acl blocked_sites dstdomain .kidnet.invalid")
    lines.append(BLOCK_END)
    return "\n".join(lines)


def _rewrite_conf(blocked_services: set[str]) -> str:
    """Return squid.conf text with the managed block set to blocked_services."""
    conf = _read_conf()
    new_block = _serialize_acl(blocked_services)

    if BLOCK_START in conf:
        start = conf.index(BLOCK_START)
        end = conf.index(BLOCK_END) + len(BLOCK_END)
        conf = conf[:start] + new_block + conf[end:]
    else:
        # No managed block yet — append before the final http_access rules area.
        # Simplest safe approach: append at end of file (ACL definitions are order-
        # independent for dstdomain lists; http_access rules already reference
        # blocked_sites by name).
        conf = conf.rstrip() + "\n\n" + new_block + "\n"

    return conf


def _set_kill_switch(conf: str, active: bool) -> str:
    """Insert/remove the kill-switch http_access rule.

    When active, denies ALL localnet traffic (true "pause internet") while
    leaving localhost reachable (so the console/bridge keep working).
    """
    block = "\n".join([
        KILL_START,
        KILL_RULE,
        KILL_END,
    ])

    if active:
        if KILL_START not in conf:
            # Insert the kill-switch rule immediately after the
            # `http_access deny blocked_sites` line, so it runs BEFORE the
            # `http_access allow localnet` rule (first-match-wins ordering).
            anchor = "http_access deny blocked_sites"
            if anchor in conf:
                idx = conf.index(anchor) + len(anchor)
                conf = conf[:idx] + "\n" + block + conf[idx:]
            else:
                conf = conf.rstrip() + "\n\n" + block + "\n"
    else:
        if KILL_START in conf:
            start = conf.index(KILL_START)
            end = conf.index(KILL_END) + len(KILL_END)
            conf = conf[:start] + conf[end:].lstrip("\n")

    return conf


# ── API routes ──────────────────────────────────────────

@app.get("/api/squid/blocks")
async def get_blocks():
    try:
        conf = _read_conf()
    except FileNotFoundError:
        raise HTTPException(500, f"squid.conf not found at {SQUID_CONF}")
    blocked = _get_blocked_services(conf)
    return {"blocked_services": sorted(blocked)}


@app.post("/api/squid/toggle")
async def toggle(payload: dict):
    service = payload.get("service")
    action = payload.get("action")
    if service not in SERVICES:
        raise HTTPException(400, f"Unknown service: {service}")
    if action not in ("block", "unblock"):
        raise HTTPException(400, f"Unknown action: {action}")

    try:
        conf = _read_conf()
    except FileNotFoundError:
        raise HTTPException(500, "squid.conf not found")

    currently = _get_blocked_services(conf)
    if action == "block":
        currently.add(service)
    else:
        currently.discard(service)

    new_conf = _rewrite_conf(currently)
    _write_conf(new_conf)
    try:
        _restart()
    except RuntimeError as e:
        raise HTTPException(500, f"restart failed: {e}")

    return {"service": service, "status": "blocked" if action == "block" else "unblocked"}


@app.post("/api/squid/pause-all")
async def pause_all(payload: dict):
    action = payload.get("action")
    if action not in ("pause", "resume"):
        raise HTTPException(400, f"Unknown action: {action}")

    try:
        conf = _read_conf()
    except FileNotFoundError:
        raise HTTPException(500, "squid.conf not found")

    new_conf = _set_kill_switch(conf, active=(action == "pause"))
    _write_conf(new_conf)
    try:
        _restart()
    except RuntimeError as e:
        raise HTTPException(500, f"restart failed: {e}")

    return {"status": "paused" if action == "pause" else "resumed"}


@app.get("/api/squid/status")
async def status():
    conf_exists = SQUID_CONF.exists()
    return {"connected": True, "conf_exists": conf_exists, "conf": str(SQUID_CONF)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=BRIDGE_HOST, port=BRIDGE_PORT, log_level="info")
