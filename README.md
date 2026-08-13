# Kid Net Guard 🛡️

**Open source mobile web console for toggling kids' internet access.**

Selective filtering via a self-hosted **Squid proxy** — blocks specific services
(YouTube, Roblox, Discord…) at the connection level while allowing everything
else. Zero data leaves your house.

## How It Works

```
Your phone → PWA console → Squid bridge → squid.conf + reconfigure → proxy blocks
```

1. **Squid** runs as a proxy on your server (Mac Mini), filtering by domain
2. **Squid bridge** (host daemon) exposes a control API over the console
3. **Kid Net Guard** provides the mobile web console + API in front of it
4. **Kid's device** points its proxy at the server → services get blocked/unblocked

## Quick Start

```bash
git clone https://github.com/bbugs280/kid-net-guard.git
cd kid-net-guard
cp .env.example .env
docker compose up -d
```

Open `http://your-server-ip:8080` on your phone. Add to home screen for a native app feel.

Then on your kid's device:
- WiFi → tap (i) → Configure Proxy → Manual
- Set proxy to your server's IP, port 3128
- Lock proxy settings with Screen Time passcode

## Features

- 🎮 **One-tap toggles** — Block YouTube, Roblox, TikTok, Discord, Fortnite, and more
- 📱 **Mobile PWA** — Add to home screen, works like a native app
- 🛡️ **Zero data leaves your house** — Everything runs locally
- ⏸️ **Emergency pause** — Block all services with one button
- 🌐 **Connection-level filtering** — Blocks the *app* (not just DNS), survives cache/DoH
- 🆓 **Free and open source** — MIT license

## Architecture

```
┌──────────────────────┐
│   kid-net-guard PWA   │  ← Mobile console (this repo)
│   FastAPI + vanilla JS │
└──────────┬───────────┘
           │ REST API
┌──────────▼───────────┐     ┌──────────────────────┐
│   Squid Bridge        │     │   Squid proxy        │
│   (host daemon :3129) │────▶│   (host :3128)       │
│   rewrites squid.conf │     │   connection-level   │
└───────────────────────┘     │   domain filtering   │
                              └──────────────────────┘
```

## Tech Stack

- **Backend:** Python 3.11, FastAPI, httpx
- **Frontend:** Vanilla HTML/CSS/JS, PWA manifest, service worker
- **Proxy Engine:** Squid 7 (see `docs/proxy.md`) + host bridge daemon
- **No build step, no framework, no npm**

## Development

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python -m kid_net_guard.main
```

## License

MIT — see LICENSE
