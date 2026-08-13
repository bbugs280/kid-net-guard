# Kid Net Guard 🛡️

**Open source mobile web console for toggling kids' internet access.**

Two complementary layers, both self-hosted, zero data leaves your house:

1. **AdGuard Home (DNS)** — network-wide ad/malware/tracker blocking + per-service soft toggles (YouTube, Roblox, TikTok, Discord…).
2. **Squid (proxy)** — selective *connection-level* filtering that blocks specific domains reliably (where DNS is weak against cache/DoH).

## How It Works

```
Your phone → PWA console → AdGuard Home API → DNS blocking → Kid's device
                     └─→ Squid proxy → connection-level domain filtering (docs/proxy.md)
```

1. **AdGuard Home** runs as a DNS server on your home server (Mac Mini, Raspberry Pi, anything)
2. **Kid Net Guard** provides a mobile web console that talks to AdGuard's API
3. **Squid** (optional) provides a proxy that filters domains at the connection level
4. **Kid's device** points its DNS and/or proxy at the server → services get blocked/unblocked

## Quick Start

```bash
git clone https://github.com/bbugs280/kid-net-guard.git
cd kid-net-guard
cp .env.example .env
# Edit .env — set ADGUARD_PASS to something secure
docker compose up -d
```

Open `http://your-server-ip:8080` on your phone. Add to home screen for a native app feel.

Then on your kid's device:
- WiFi → tap (i) → Configure DNS → Manual
- Set DNS to your server's IP
- Lock DNS settings with Screen Time passcode

## Features

- 🎮 **One-tap toggles** — Block YouTube, Roblox, TikTok, Discord, Fortnite, and more
- 📱 **Mobile PWA** — Add to home screen, works like a native app
- 🛡️ **Zero data leaves your house** — Everything runs locally
- ⏸️ **Emergency pause** — Cut all internet with one button (catch-all rule)
- 🌐 **Selective proxy filtering** — Reliable domain-level blocking via Squid (see `docs/proxy.md`)
- ⏰ **Schedules** (coming soon) — Homework mode, bedtime rules
- 🆓 **Free and open source** — MIT license

## Architecture

```
┌──────────────────────┐
│   kid-net-guard PWA   │  ← Mobile console (this repo)
│   FastAPI + vanilla JS │
└──────────┬───────────┘
           │ REST API
┌──────────▼───────────┐     ┌──────────────────────┐
│     AdGuard Home      │     │   Squid (proxy)      │
│     (separate)        │     │   (optional layer)   │
│      DNS filtering    │     │   connection-level   │
└───────────────────────┘     │   domain filtering   │
                              └──────────────────────┘
```

## Tech Stack

- **Backend:** Python 3.11, FastAPI, httpx
- **Frontend:** Vanilla HTML/CSS/JS, PWA manifest, service worker
- **DNS Engine:** AdGuard Home (Docker)
- **Proxy Engine:** Squid 7 (optional, `docs/proxy.md`)
- **No build step, no framework, no npm**

## Development

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python -m kid_net_guard.main
```

## License

MIT — see LICENSE
