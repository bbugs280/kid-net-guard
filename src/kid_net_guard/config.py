"""Configuration — loaded from environment or .env file."""

import os
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class Settings:
    VERSION: str = (Path(__file__).parent.parent.parent / "VERSION").read_text().strip()
    STATIC_DIR: Path = Path(__file__).parent / "static"

    # AdGuard Home connection
    ADGUARD_URL: str = os.getenv("ADGUARD_URL", "http://adguard:80")
    ADGUARD_USER: str = os.getenv("ADGUARD_USER", "admin")
    ADGUARD_PASS: str = os.getenv("ADGUARD_PASS", "")

    # Console auth
    CONSOLE_PASSWORD: str = os.getenv("CONSOLE_PASSWORD", "changeme")

    # Database
    DB_PATH: Path = Path(os.getenv("DB_PATH", str(Path(__file__).parent.parent.parent / "data" / "kidnet.db")))

    # Devices to manage
    DEVICES: list[dict] = field(default_factory=list)

    def __post_init__(self):
        # Default device config — hardcoded for now, will move to DB
        if not self.DEVICES:
            self.DEVICES = [
                {
                    "id": "wayne-iphone",
                    "name": "Wayne",
                    "subtitle": "iPhone",
                    "adguard_client_id": "wayne-iphone",  # matches AdGuard client name
                }
            ]


settings = Settings()
