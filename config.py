"""Load API keys from a local .env file (not committed to git)."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).parent
ENV_FILE = ROOT / ".env"

# Model A (default): each person pastes their own free Gemini key in the sidebar.
# For solo local dev with .env auto-load, add FITLINE_BYO_KEY=0 to your .env file.
BYO_KEY_ONLY = os.environ.get("FITLINE_BYO_KEY", "1").strip().lower() not in (
    "0",
    "false",
    "no",
)


def load_env_file() -> None:
    """Load KEY=value lines from .env into os.environ (does not overwrite existing)."""
    if not ENV_FILE.exists():
        return
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def env_gemini_key() -> str:
    return os.environ.get("GEMINI_API_KEY", "") or os.environ.get("GOOGLE_API_KEY", "")


def gemini_key_looks_valid(key: str) -> bool:
    """AI Studio keys start with AIza (legacy) or AQ. (auth keys)."""
    k = key.strip()
    if k.startswith("AIza"):
        return len(k) >= 35
    if k.startswith("AQ."):
        return len(k) >= 45
    return len(k) >= 20


def server_has_gemini_key() -> bool:
    """True when a server-side Gemini key is active (disabled under Model A / BYO)."""
    if BYO_KEY_ONLY:
        return False
    k = env_gemini_key()
    return bool(k and gemini_key_looks_valid(k))


def env_openai_key() -> str:
    return os.environ.get("OPENAI_API_KEY", "")


def has_env_file() -> bool:
    return ENV_FILE.exists()


# Load once on import
load_env_file()
