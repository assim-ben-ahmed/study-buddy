"""Settings from environment variables (and an optional .env file, never committed)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_dotenv(path: Path = ROOT / ".env") -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("'\""))


@dataclass
class Settings:
    api_key: str = ""
    model: str = "mistral-small-latest"
    fallback_model: str = "ministral-8b-latest"
    requests_per_minute: int = 12  # per visitor, protects the API quota once deployed
    max_message_chars: int = 4000
    max_history: int = 12
    allowed_origins: list[str] = field(default_factory=list)

    @property
    def demo(self) -> bool:
        return not self.api_key


def get_settings() -> Settings:
    _load_dotenv()
    origins = [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "").split(",") if o.strip()]
    return Settings(
        api_key=os.environ.get("MISTRAL_API_KEY", ""),
        model=os.environ.get("MISTRAL_MODEL", "mistral-small-latest"),
        fallback_model=os.environ.get("MISTRAL_FALLBACK_MODEL", "ministral-8b-latest"),
        requests_per_minute=int(os.environ.get("REQUESTS_PER_MINUTE", "12")),
        allowed_origins=origins,
    )
