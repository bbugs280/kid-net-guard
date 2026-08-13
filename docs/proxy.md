# Proxy Layer (Squid) — selective connection-level filtering

## Why a proxy?

DNS blocking (AdGuard) is weak against client-side caching, DoH, and hardcoded
IPs — the client can resolve a domain once and then bypass DNS entirely.

A proxy sits **in the path of the actual connection**, so it sees the real
destination of every request and can block specific domains (YouTube, Roblox,
Discord) while allowing everything else (school sites) — at the connection level,
not the name-lookup level.

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
traffic can *choose* to avoid it). Opt-in is a good discovery step: run it, watch
the access log to see which apps leak, then decide if the gateway upgrade is warranted.

## Host

- **Mac Mini** (`192.168.86.20`), installed via Homebrew
- Service: `brew services start squid` (launchd, survives reboot)
- Config: `/opt/homebrew/etc/squid.conf` (copy of `squid.conf` in this dir)
- Logs: `/opt/homebrew/var/logs/squid/access.log`

## Blocked domains

Edit `/opt/homebrew/etc/squid.conf` → the `blocked_sites` ACL:

```
acl blocked_sites dstdomain .youtube.com
acl blocked_sites dstdomain .googlevideo.com
acl blocked_sites dstdomain .roblox.com
acl blocked_sites dstdomain .discord.com
...
```

Then reload: `brew services restart squid` (or `squid -k reconfigure`).

## Configure a client (iPhone)

```
Settings → Wi-Fi → (i) on your network → Configure Proxy → Manual
  Server: 192.168.86.20
  Port:   3128
```

Lock this with Screen Time so it can't be changed without your passcode.

## Verify

```bash
# Blocked (expect TCP_DENIED/403)
curl -s -x http://192.168.86.20:3128 -o /dev/null -w "%{http_code}\n" https://www.youtube.com

# Allowed (expect 200)
curl -s -x http://192.168.86.20:3128 -o /dev/null -w "%{http_code}\n" https://example.com

# Watch live
tail -f /opt/homebrew/var/logs/squid/access.log
```

## Known limitation (opt-in mode)

Apps that ignore the iOS system proxy (some DoH clients, apps with own networking
stacks, hardcoded IPs) will **bypass** Squid and connect directly. The gateway
(transparent/inline) rebuild removes this hole. See `kid-net-guard-development`
skill for the full layered-controls picture.
