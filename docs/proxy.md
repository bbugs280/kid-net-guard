# Proxy Layer (Squid) — selective connection-level filtering

## Why a proxy?

DNS blocking (AdGuard) is weak against client-side caching, DoH, and hardcoded
IPs — the client can resolve a domain once and then bypass DNS entirely.

A proxy sits **in the path of the actual connection**, so it sees the real
destination of every request and can block specific services (YouTube, Roblox,
Discord) while allowing everything else (school sites) — at the connection level,
not the name-lookup level.

**kid-net-guard now uses Squid as its single, primary filtering engine.** The
AdGuard DNS layer has been retired — proxy blocking is more reliable and the
DNS layer added maintenance burden (protection-not-persisted bugs, flag-replace
traps) without unique value for selective app blocking.

## Architecture decision: opt-in vs. gateway

This project currently runs Squid as an **opt-in** proxy.

```
Device (configured to use proxy)  →  Squid (192.168.86.20:3128)  →  Internet
                                          │
                                          └─ blocks youtube.com/roblox.com/discord.com
                                          └─ allows everything else
```

| | Opt-in (current) | Gateway (future) |
|---|---|---|
| How traffic is captured | Device *configured* to use proxy | Proxy *is* the network gateway |
| Bypassable? | Apps ignoring system proxy leak | ❌ Nothing can bypass |
| Hardware | Any box (Mac Mini) | Box with 2 NICs, Nest → bridge mode |
| Effort | ~30 min | Hours/days (network rebuild) |

**The filter engine is identical** — the only difference is enforcement (whether
traffic can *choose* to avoid it).

## The two processes

```
┌───────────────────────────────────────────────────────────┐
│  Kid Net Guard app (Docker, :8082)                       │
│  FastAPI + PWA console — talks to the bridge over HTTP    │
└──────────────────────────┬────────────────────────────────┘
                           │ host.docker.internal:3129
┌──────────────────────────▼────────────────────────────────┐
│  Squid Bridge daemon (HOST, :3129)                       │
│  scripts/squid_bridge.py — rewrites squid.conf ACL +     │
│  runs `squid -k reconfigure`                              │
└──────────────────────────┬────────────────────────────────┘
                           │ edits /opt/homebrew/etc/squid.conf
┌──────────────────────────▼────────────────────────────────┐
│  Squid proxy (HOST, :3128, Homebrew)                     │
│  Filters device traffic by dstdomain ACL                  │
└───────────────────────────────────────────────────────────┘
```

**Why a bridge?** Squid has no REST/management API. Only the host can edit
`/opt/homebrew/etc/squid.conf` and run `squid -k reconfigure`, so a small host-
side daemon exposes a control API that the Dockerized app reaches via
`host.docker.internal:3129`.

## Host services

| Service | Port | How it runs |
|---|---|---|
| Squid proxy | 3128 | `brew services start squid` |
| Bridge daemon | 3129 | launchd (`com.kidnet.squid-bridge`) → `scripts/squid_bridge.py` |

Logs: `/opt/homebrew/var/logs/squid/access.log`

## The service → domain map

`src/kid_net_guard/services.py` maps each service ID (youtube, roblox, …) to the
full set of domains its **native iOS app** needs. This is the critical insight:
an app like YouTube uses ~10 domains (youtube.com + googlevideo + ytimg + ggpht
+ youtubei.googleapis.com…), not one. The `SERVICES` dict is the single source of
truth the bridge writes into squid.conf.

Shared/ambiguous domains (e.g. `.fbcdn.net` across Meta) are commented in the map —
review before broad blocking.

## Configure a client (iPhone)

```
Settings → Wi-Fi → (i) on your network → Configure Proxy → Manual
  Server: 192.168.86.20
  Port:   3128
```

Lock this with Screen Time so it can't be changed without your passcode.

## Verify

```bash
# Blocked (expect TCP_DENIED/403 → curl shows 000)
curl -s -x http://192.168.86.20:3128 -o /dev/null -w "%{http_code}\n" https://www.youtube.com

# Allowed (expect 200)
curl -s -x http://192.168.86.20:3128 -o /dev/null -w "%{http_code}\n" https://example.com

# Bridge state
curl -s http://127.0.0.1:3129/api/squid/blocks

# Watch live
tail -f /opt/homebrew/var/logs/squid/access.log
```

## Known limitation (opt-in mode)

Apps that ignore the iOS system proxy (some DoH clients, apps with own networking
stacks, hardcoded IPs) will **bypass** Squid and connect directly. The gateway
(transparent/inline) rebuild removes this hole.
