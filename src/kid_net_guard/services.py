"""Service → domain mapping for Squid proxy filtering.

Each service maps to the complete set of domains its NATIVE iOS APP needs
(not just the website). These are drawn from the research in
docs/proxy.md and are designed to fully stop the app at the connection level.

Blocking uses Squid `dstdomain` ACLs with leading-dot wildcards, so `.youtube.com`
matches youtube.com and all subdomains.

Shared/ambiguous domains (e.g. .fbcdn.net shared across all Meta) are marked
with a comment — review before adding to a broad block.
"""

# Service ID (console-facing) → list of domain suffix patterns for Squid.
# Leading dot = wildcard subdomains. Order: core/API first, then CDN.
SERVICES = {
    "youtube": [
        ".youtube.com",
        ".youtubei.googleapis.com",   # critical API endpoint
        ".youtube.googleapis.com",
        ".youtube-nocookie.com",
        ".googlevideo.com",
        ".youtubekids.com",
        ".ytimg.com",
        ".ggpht.com",
        ".yt.be",
        "youtu.be",
    ],
    "roblox": [
        ".roblox.com",
        ".rbxcdn.com",
        ".rbxtrk.com",
        ".robloxlabs.com",
        ".rbxinfra.net",
        ".roblox.net",
    ],
    "discord": [
        ".discord.com",
        ".discord.gg",
        ".discordapp.com",
        ".discordapp.net",
        ".discord.media",
        ".discordcdn.com",
        ".dis.gd",
    ],
    "netflix": [
        ".netflix.com",
        ".netflix.net",
        ".nflxvideo.net",
        ".nflxso.net",
        ".nflxext.com",
        ".nflximg.com",
        ".nflximg.net",
    ],
    "tiktok": [
        ".tiktok.com",
        ".tiktokv.com",
        ".tiktokv.eu",
        ".tiktokv.us",
        ".tiktokcdn.com",
        ".tiktokcdn-us.com",
        ".tiktokcdn-eu.com",
        ".muscdn.com",
        ".musical.ly",
        ".musically.ly",
    ],
    "twitch": [
        ".twitch.tv",
        ".jtvnw.net",
        ".ttvnw.net",
        ".live-video.net",
        ".twitchcdn.net",
        ".twitchsvc.net",
        ".ext-twitch.tv",
    ],
    "snapchat": [
        ".snapchat.com",
        ".sc-cdn.net",
        ".sc-gw.com",
        ".sc-static.net",
        ".sc-prod.net",
        ".feelinsonice.com",
        ".snapkit.com",
        ".snapmap.com",
    ],
    "whatsapp": [
        ".whatsapp.com",
        ".whatsapp.net",
        "wa.me",
        ".fbcdn.net",       # WhatsApp media/CDN rides Facebook's CDN (shared Meta)
        ".cdninstagram.com",  # some WhatsApp status media
    ],
    "instagram": [
        ".instagram.com",
        ".cdninstagram.com",
        ".fbcdn.net",       # IG media also on Facebook CDN (shared Meta)
    ],
    "facebook": [
        ".facebook.com",
        ".fbcdn.net",   # ALSO shared with Instagram/WhatsApp — review
        ".fbcdn.com",
        ".fbsbx.com",
        ".messenger.com",
        ".facebook.net",
    ],
    "minecraft": [
        ".minecraft.net",
        ".minecraftservices.com",
        ".mojang.com",
    ],
    "steam": [
        ".steampowered.com",
        ".steamcommunity.com",
        ".steamstatic.com",
        ".steamusercontent.com",
        ".steamcontent.com",
        ".steamserver.net",
        ".steam-chat.com",
    ],
    "epic_games": [
        ".epicgames.com",
        ".epicgames.dev",
        ".epicgames.net",
        ".fortnite.com",
        ".unrealengine.com",
    ],
    "spotify": [
        ".spotify.com",
        ".scdn.co",
        ".spotifycdn.com",
        ".spotifycdn.net",
        ".pscdn.co",
        ".tospotify.com",
    ],
}

# Friendly display order for the console (matches the existing AdGuard ordering).
SERVICE_ORDER = [
    "youtube", "netflix", "tiktok", "twitch", "discord",
    "facebook", "snapchat", "roblox", "minecraft",
    "steam", "epic_games", "whatsapp",
    "instagram", "spotify",
]


def domains_for(service: str) -> list[str]:
    """Return the domain list for a service (empty if unknown)."""
    return SERVICES.get(service, [])


def all_domains() -> set[str]:
    """Return the union of all service domains."""
    out: set[str] = set()
    for domains in SERVICES.values():
        out.update(domains)
    return out
