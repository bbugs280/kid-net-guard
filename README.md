# Kid Net Guard 🛡️

**Open source mobile web console for toggling kids' internet access.**

Built on AdGuard Home. One `docker compose up`. Toggle YouTube, Roblox, TikTok, and more from your phone — no apps, no subscriptions, no data leaves your house.

## How It Works

```
Your phone → PWA console → AdGuard Home API → DNS blocking → Kid's device
```

1. **AdGuard Home** runs as a DNS server on your home server (Mac Mini, Raspberry Pi, anything)
2. **Kid Net Guard** provides a mobile web console that talks to AdGuard's API
3. **Kid's device** points its DNS to AdGuard → services get blocked/unblocked instantly

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
- ⏸️ **Emergency pause** — Kill all internet with one button
- ⏰ **Schedules** (coming soon) — Homework mode, bedtime rules
- 🆓 **Free and open source** — MIT license

## Architecture

```
┌──────────────────────┐
│   kid-net-guard PWA   │  ← Mobile console (this repo)
│   FastAPI + vanilla JS │
└──────────┬───────────┘
           │ REST API
┌──────────▼───────────┐
│     AdGuard Home      │  ← DNS filtering engine
│     (separate)        │     25K+ GitHub stars
└───────────────────────┘
```

## Tech Stack

- **Backend:** Python 3.11, FastAPI, httpx
- **Frontend:** Vanilla HTML/CSS/JS, PWA manifest, service worker
- **DNS Engine:** AdGuard Home (Docker)
- **No build step, no framework, no npm**

## Development

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python -m kid_net_guard.main
```

## License

MIT — see LICENSE
